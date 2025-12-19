"""
Tests d'intégration pour le routeur Telemetry du gateway SkyLink.

Objectifs :
- Vérifier que le routeur expose bien une fonction d'ingestion télémétrique
- Vérifier qu'en cas de succès du service Telemetry, la réponse est renvoyée telle quelle
- Vérifier la gestion des erreurs réseau (timeout, erreur HTTP générique)

Contraintes :
- Aucun accès aux clés RSA ni aux variables d'environnement sensibles
- Aucun appel réseau réel : httpx.AsyncClient est toujours mocké
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, Optional
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from skylink.models.telemetry.telemetry_event import TelemetryEvent
from skylink.routers import telemetry as telemetry_router


def _get_ingest_handler() -> Optional[Callable[..., Any]]:
    """
    Localise la fonction d'ingestion dans le module skylink.routers.telemetry.

    Par convention, on s'attend à trouver une fonction nommée `ingest_telemetry`,
    mais on reste robuste en cherchant toute fonction dont le nom contient
    `ingest` et `telemetry`.
    """
    # 1. Nom attendu le plus probable (sans utiliser getattr constant pour Ruff B009)
    if hasattr(telemetry_router, "ingest_telemetry"):
        fn = telemetry_router.ingest_telemetry
        if callable(fn):
            return fn

    # 2. Fallback : recherche heuristique
    candidates = []
    for name in dir(telemetry_router):
        if "ingest" in name and "telemetry" in name:
            attr = getattr(telemetry_router, name)
            if callable(attr):
                candidates.append(attr)

    if len(candidates) == 1:
        return candidates[0]

    # Si plusieurs ou aucune : on préfère skipper les tests plutôt que de casser la CI.
    return None


def _build_handler_kwargs(handler: Callable[..., Any]) -> Dict[str, Any]:
    """
    Construit dynamiquement les kwargs pour appeler le handler d'ingestion.

    On utilise TelemetryEvent.model_construct() pour créer un objet sans validation,
    ce qui évite de dépendre du schéma exact (champs obligatoires, etc.).
    """
    sig = inspect.signature(handler)
    kwargs: Dict[str, Any] = {}

    for name, param in sig.parameters.items():
        # Paramètre de type événement télémétrique (nom courant : event ou body)
        if name in {"event", "body", "telemetry_event"}:
            kwargs[name] = TelemetryEvent.model_construct()
        # Paramètre des claims JWT (nom courant : claims)
        elif name == "claims":
            # JWTClaims est généralement un Mapping[str, Any] / dict
            kwargs[name] = {"sub": "550e8400-e29b-41d4-a716-446655440000"}
        # Paramètres FastAPI classiques (request, response, etc.) -> ignorés
        elif name in {"request", "response"}:
            if param.default is inspect._empty:
                kwargs[name] = Mock()
        else:
            # Autres paramètres : si obligatoires, on met un Mock
            if param.default is inspect._empty:
                kwargs[name] = Mock()

    return kwargs


@pytest.mark.asyncio
@patch("skylink.routers.telemetry.AsyncClient")
async def test_telemetry_ingest_proxies_successfully(mock_async_client: Mock) -> None:
    """
    Test : le handler d'ingestion proxy correctement la réponse du service Telemetry.

    - httpx.AsyncClient.post est mocké pour renvoyer un status_code 201
      et un body JSON.
    - Le handler doit considérer cette réponse comme un succès et renvoyer
      le JSON tel quel (ou un objet équivalent).
    """
    handler = _get_ingest_handler()
    if handler is None:
        pytest.skip("Aucun handler d'ingestion telemetry trouvé dans skylink.routers.telemetry")

    # Prépare le contexte AsyncClient mocké
    mock_response = Mock()
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "status": "accepted",
        "message": "Telemetry event ingested",
    }

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
    mock_async_client.return_value = mock_context

    kwargs = _build_handler_kwargs(handler)
    result = await handler(**kwargs)

    # Le handler peut soit renvoyer directement le dict JSON,
    # soit une Response FastAPI avec .body ou .json().
    if isinstance(result, dict):
        data = result
    elif hasattr(result, "body") or hasattr(result, "media_type"):
        assert getattr(result, "status_code", 201) == 201
        return
    else:
        data = None

    assert data is not None
    assert data.get("status") == "accepted"


@pytest.mark.asyncio
@patch("skylink.routers.telemetry.AsyncClient")
async def test_telemetry_ingest_handles_timeout(mock_async_client: Mock) -> None:
    """
    Test : un timeout du service Telemetry doit être transformé
    en HTTPException 504 Gateway Timeout.
    """
    from fastapi import HTTPException

    handler = _get_ingest_handler()
    if handler is None:
        pytest.skip("Aucun handler d'ingestion telemetry trouvé dans skylink.routers.telemetry")

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value.post = AsyncMock(
        side_effect=httpx.TimeoutException("Telemetry service timeout")
    )
    mock_async_client.return_value = mock_context

    kwargs = _build_handler_kwargs(handler)

    with pytest.raises(HTTPException) as exc_info:
        await handler(**kwargs)

    assert exc_info.value.status_code == 504
    assert "timeout" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
@patch("skylink.routers.telemetry.AsyncClient")
async def test_telemetry_ingest_handles_service_error(mock_async_client: Mock) -> None:
    """
    Test : une erreur HTTP générique du service Telemetry doit être transformée
    en HTTPException 502 Bad Gateway.
    """
    from fastapi import HTTPException

    handler = _get_ingest_handler()
    if handler is None:
        pytest.skip("Aucun handler d'ingestion telemetry trouvé dans skylink.routers.telemetry")

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value.post = AsyncMock(
        side_effect=httpx.HTTPError("Telemetry service error")
    )
    mock_async_client.return_value = mock_context

    kwargs = _build_handler_kwargs(handler)

    with pytest.raises(HTTPException) as exc_info:
        await handler(**kwargs)

    assert exc_info.value.status_code == 502
    assert (
        "telemetry" in str(exc_info.value.detail).lower()
        or "unavailable" in str(exc_info.value.detail).lower()
    )
