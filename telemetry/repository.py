"""Dépôt de données pour le service de télémétrie."""

from typing import Protocol
from uuid import UUID

from telemetry.schemas import TelemetryEvent


class TelemetryRepository(Protocol):
    """Contrat de repository pour la persistance des événements."""

    async def exists(self, vehicle_id: UUID, event_id: UUID) -> bool:
        """Retourne True si un événement (vehicle_id, event_id) existe déjà."""

    async def get(self, vehicle_id: UUID, event_id: UUID) -> TelemetryEvent | None:
        """Retourne l'événement existant ou None."""

    async def insert(self, event: TelemetryEvent) -> None:
        """Insère un nouvel événement."""


class InMemoryTelemetryRepository:
    """
    Implémentation en mémoire pour démarrer / tests.
    À remplacer plus tard par une implémentation PostgreSQL.
    """

    def __init__(self) -> None:
        # Dictionnaire avec clé = (vehicle_id, event_id)
        self._events: dict[tuple[UUID, UUID], TelemetryEvent] = {}

    async def exists(self, vehicle_id: UUID, event_id: UUID) -> bool:
        return (vehicle_id, event_id) in self._events

    async def get(self, vehicle_id: UUID, event_id: UUID) -> TelemetryEvent | None:
        return self._events.get((vehicle_id, event_id))

    async def insert(self, event: TelemetryEvent) -> None:
        self._events[(event.vehicle_id, event.event_id)] = event
