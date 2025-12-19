#!/usr/bin/env python3
"""Script pour configurer OAuth Google pour un véhicule.

Ce script aide à configurer l'OAuth Google pour un véhicule sans avoir besoin
d'une application mobile. Il peut être utilisé :
- En développement (localhost)
- En production (avec credentials Google Cloud)
- Pour tests manuels

Usage:
    # Mode interactif
    python scripts/configure_vehicle_oauth.py

    # Mode CLI
    python scripts/configure_vehicle_oauth.py \
        --vehicle-id=550e8400-e29b-41d4-a716-446655440000 \
        --client-id=YOUR_CLIENT_ID \
        --client-secret=YOUR_SECRET \
        --redirect-uri=http://localhost:8003/oauth/callback

Prérequis:
    1. Credentials Google Cloud OAuth configurés
    2. Service contacts en cours d'exécution
    3. Variable ENCRYPTION_KEY définie
"""

import argparse
import os
import sys
import webbrowser
from urllib.parse import parse_qs, urlencode, urlparse

try:
    import httpx
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Confirm, Prompt
except ImportError:
    print("❌ Erreur: Dépendances manquantes")
    print("\nInstallez les dépendances requises:")
    print("  poetry add httpx rich")
    sys.exit(1)

console = Console()


def build_authorization_url(client_id: str, redirect_uri: str, state: str = None) -> str:
    """Construit l'URL d'autorisation Google OAuth.

    Args:
        client_id: Google OAuth client ID
        redirect_uri: URI de redirection
        state: État optionnel (anti-CSRF)

    Returns:
        URL complète pour le consent screen Google
    """
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/contacts.readonly",
        "access_type": "offline",
        "prompt": "consent",  # Force re-consent pour obtenir refresh_token
    }

    if state:
        params["state"] = state

    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


def extract_code_from_url(url: str) -> str:
    """Extrait le code d'autorisation de l'URL de callback.

    Args:
        url: URL de callback complète avec ?code=...

    Returns:
        Code d'autorisation

    Raises:
        ValueError: Si le code n'est pas trouvé
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    if "code" not in params:
        if "error" in params:
            error = params["error"][0]
            raise ValueError(f"OAuth error: {error}")
        raise ValueError("No authorization code found in URL")

    return params["code"][0]


def call_oauth_callback(
    vehicle_id: str, authorization_code: str, service_url: str = "http://localhost:8003"
) -> dict:
    """Appelle l'endpoint /oauth/callback du service contacts.

    Args:
        vehicle_id: UUID du véhicule
        authorization_code: Code d'autorisation Google
        service_url: URL du service contacts

    Returns:
        Réponse JSON du service

    Raises:
        httpx.HTTPError: Si l'appel échoue
    """
    url = f"{service_url}/oauth/callback"
    params = {
        "code": authorization_code,
        "vehicle_id": vehicle_id,
    }

    with httpx.Client(timeout=10.0) as client:
        response = client.post(url, params=params)
        response.raise_for_status()
        return response.json()


def main():
    """Point d'entrée principal du script."""
    parser = argparse.ArgumentParser(
        description="Configure OAuth Google pour un véhicule SkyLink"
    )
    parser.add_argument(
        "--vehicle-id", help="UUID du véhicule (ex: 550e8400-e29b-41d4-a716-446655440000)"
    )
    parser.add_argument("--client-id", help="Google OAuth Client ID")
    parser.add_argument("--client-secret", help="Google OAuth Client Secret")
    parser.add_argument(
        "--redirect-uri",
        default="http://localhost:8003/oauth/callback",
        help="OAuth redirect URI (default: http://localhost:8003/oauth/callback)",
    )
    parser.add_argument(
        "--service-url",
        default="http://localhost:8003",
        help="URL du service contacts (default: http://localhost:8003)",
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="Ne pas ouvrir automatiquement le navigateur"
    )

    args = parser.parse_args()

    # Affichage du header
    console.print("\n")
    console.print(
        Panel.fit(
            "[bold cyan]🚗 Configuration OAuth Google - SkyLink[/bold cyan]\n"
            "[dim]Script de configuration véhicule[/dim]",
            border_style="cyan",
        )
    )
    console.print("\n")

    # Récupération des paramètres (CLI ou interactif)
    vehicle_id = args.vehicle_id or Prompt.ask(
        "🔑 [bold]Vehicle ID (UUID)[/bold]", default="550e8400-e29b-41d4-a716-446655440000"
    )

    client_id = (
        args.client_id
        or os.getenv("GOOGLE_CLIENT_ID")
        or Prompt.ask("🔐 [bold]Google Client ID[/bold]")
    )

    client_secret = args.client_secret or os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_secret:
        console.print("[yellow]Note: Client secret requis mais pas utilisé par ce script[/yellow]")

    redirect_uri = args.redirect_uri
    service_url = args.service_url

    # Validation des paramètres
    if not vehicle_id or not client_id:
        console.print("[red]❌ Erreur: vehicle_id et client_id sont requis[/red]")
        sys.exit(1)

    # Construction de l'URL d'autorisation
    auth_url = build_authorization_url(client_id, redirect_uri)

    console.print("\n[bold green]Étape 1: Autorisation Google[/bold green]")
    console.print(f"Vehicle ID: [cyan]{vehicle_id}[/cyan]")
    console.print(f"Redirect URI: [cyan]{redirect_uri}[/cyan]\n")

    console.print("[dim]URL d'autorisation:[/dim]")
    console.print(f"[blue]{auth_url}[/blue]\n")

    # Ouvrir le navigateur si demandé
    if not args.no_browser:
        if Confirm.ask("Ouvrir le navigateur automatiquement?", default=True):
            webbrowser.open(auth_url)
            console.print("[green]✓[/green] Navigateur ouvert\n")
    else:
        console.print("[yellow]Copiez cette URL dans votre navigateur[/yellow]\n")

    # Instructions
    console.print(
        Panel(
            "1. Connectez-vous avec votre compte Google\n"
            "2. Autorisez l'accès aux contacts (lecture seule)\n"
            "3. Vous serez redirigé vers le callback URL\n"
            "4. Copiez l'URL complète de la page de redirection",
            title="[bold]Instructions[/bold]",
            border_style="yellow",
        )
    )

    console.print("\n[bold green]Étape 2: Code d'autorisation[/bold green]")

    # Récupération du code d'autorisation
    while True:
        callback_url = Prompt.ask(
            "\n📋 [bold]Collez l'URL de callback complète[/bold]\n"
            "[dim](format: http://localhost:8003/oauth/callback?code=...)[/dim]"
        )

        try:
            authorization_code = extract_code_from_url(callback_url)
            console.print(
                f"[green]✓[/green] Code extrait: [cyan]{authorization_code[:20]}...[/cyan]"
            )
            break
        except ValueError as e:
            console.print(f"[red]❌ Erreur: {e}[/red]")
            if not Confirm.ask("Réessayer?", default=True):
                sys.exit(1)

    # Appel du service
    console.print("\n[bold green]Étape 3: Configuration du véhicule[/bold green]")
    console.print(f"Service URL: [cyan]{service_url}[/cyan]\n")

    try:
        with console.status("[bold cyan]Envoi de la configuration...") as status:
            result = call_oauth_callback(vehicle_id, authorization_code, service_url)

        console.print("\n[bold green]✅ Configuration réussie ![/bold green]\n")
        console.print(
            Panel(
                f"Vehicle ID: [cyan]{result.get('vehicle_id')}[/cyan]\n"
                f"Message: [green]{result.get('message')}[/green]\n"
                f"Success: [green]{result.get('success')}[/green]",
                title="[bold]Résultat[/bold]",
                border_style="green",
            )
        )

        console.print("\n[dim]Le véhicule peut maintenant accéder aux contacts Google ![/dim]")

    except httpx.HTTPStatusError as e:
        console.print(f"\n[red]❌ Erreur HTTP {e.response.status_code}[/red]")
        console.print(f"[dim]Détails: {e.response.text}[/dim]\n")

        if e.response.status_code == 400:
            console.print("[yellow]Le code d'autorisation est invalide ou expiré.[/yellow]")
            console.print("[yellow]Les codes expirent après ~10 minutes.[/yellow]")
            console.print("[yellow]Recommencez le processus pour obtenir un nouveau code.[/yellow]")
        elif e.response.status_code == 403:
            console.print("[yellow]Scopes insuffisants.[/yellow]")
            console.print("[yellow]Vérifiez que 'contacts.readonly' est autorisé.[/yellow]")
        elif e.response.status_code == 500:
            console.print("[yellow]Erreur serveur (base de données?).[/yellow]")
            console.print("[yellow]Vérifiez que ENCRYPTION_KEY est définie.[/yellow]")

        sys.exit(1)

    except httpx.ConnectError:
        console.print(f"\n[red]❌ Impossible de se connecter à {service_url}[/red]")
        console.print("[yellow]Vérifiez que le service contacts est démarré.[/yellow]\n")
        sys.exit(1)

    except Exception as e:
        console.print(f"\n[red]❌ Erreur inattendue: {e}[/red]\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
