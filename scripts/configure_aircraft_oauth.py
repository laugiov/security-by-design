#!/usr/bin/env python3
"""Script to configure Google OAuth for an aircraft.

This script helps configure Google OAuth for an aircraft without needing
a mobile application. It can be used:
- In development (localhost)
- In production (with Google Cloud credentials)
- For manual testing

Usage:
    # Interactive mode
    python scripts/configure_aircraft_oauth.py

    # CLI mode
    python scripts/configure_aircraft_oauth.py \
        --aircraft-id=550e8400-e29b-41d4-a716-446655440000 \
        --client-id=YOUR_CLIENT_ID \
        --client-secret=YOUR_SECRET \
        --redirect-uri=http://localhost:8003/oauth/callback

Prerequisites:
    1. Google Cloud OAuth credentials configured
    2. Contacts service running
    3. ENCRYPTION_KEY variable defined
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
    print("❌ Error: Missing dependencies")
    print("\nInstall the required dependencies:")
    print("  poetry add httpx rich")
    sys.exit(1)

console = Console()


def build_authorization_url(client_id: str, redirect_uri: str, state: str = None) -> str:
    """Build Google OAuth authorization URL.

    Args:
        client_id: Google OAuth client ID
        redirect_uri: Redirect URI
        state: Optional state (anti-CSRF)

    Returns:
        Complete URL for Google consent screen
    """
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/contacts.readonly",
        "access_type": "offline",
        "prompt": "consent",  # Force re-consent to obtain refresh_token
    }

    if state:
        params["state"] = state

    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


def extract_code_from_url(url: str) -> str:
    """Extract authorization code from callback URL.

    Args:
        url: Complete callback URL with ?code=...

    Returns:
        Authorization code

    Raises:
        ValueError: If the code is not found
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
    aircraft_id: str, authorization_code: str, service_url: str = "http://localhost:8003"
) -> dict:
    """Call the /oauth/callback endpoint of the contacts service.

    Args:
        aircraft_id: Aircraft UUID
        authorization_code: Google authorization code
        service_url: Contacts service URL

    Returns:
        JSON response from the service

    Raises:
        httpx.HTTPError: If the call fails
    """
    url = f"{service_url}/oauth/callback"
    params = {
        "code": authorization_code,
        "aircraft_id": aircraft_id,
    }

    with httpx.Client(timeout=10.0) as client:
        response = client.post(url, params=params)
        response.raise_for_status()
        return response.json()


def main():
    """Main script entry point."""
    parser = argparse.ArgumentParser(description="Configure Google OAuth for a SkyLink aircraft")
    parser.add_argument(
        "--aircraft-id", help="Aircraft UUID (e.g.: 550e8400-e29b-41d4-a716-446655440000)"
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
        help="Contacts service URL (default: http://localhost:8003)",
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="Do not open browser automatically"
    )

    args = parser.parse_args()

    # Display header
    console.print("\n")
    console.print(
        Panel.fit(
            "[bold cyan]🚗 Google OAuth Configuration - SkyLink[/bold cyan]\n"
            "[dim]Aircraft configuration script[/dim]",
            border_style="cyan",
        )
    )
    console.print("\n")

    # Retrieve parameters (CLI or interactive)
    aircraft_id = args.aircraft_id or Prompt.ask(
        "🔑 [bold]Aircraft ID (UUID)[/bold]", default="550e8400-e29b-41d4-a716-446655440000"
    )

    client_id = (
        args.client_id
        or os.getenv("GOOGLE_CLIENT_ID")
        or Prompt.ask("🔐 [bold]Google Client ID[/bold]")
    )

    client_secret = args.client_secret or os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_secret:
        console.print("[yellow]Note: Client secret required but not used by this script[/yellow]")

    redirect_uri = args.redirect_uri
    service_url = args.service_url

    # Validate parameters
    if not aircraft_id or not client_id:
        console.print("[red]❌ Error: aircraft_id and client_id are required[/red]")
        sys.exit(1)

    # Build authorization URL
    auth_url = build_authorization_url(client_id, redirect_uri)

    console.print("\n[bold green]Step 1: Google Authorization[/bold green]")
    console.print(f"Aircraft ID: [cyan]{aircraft_id}[/cyan]")
    console.print(f"Redirect URI: [cyan]{redirect_uri}[/cyan]\n")

    console.print("[dim]Authorization URL:[/dim]")
    console.print(f"[blue]{auth_url}[/blue]\n")

    # Open browser if requested
    if not args.no_browser:
        if Confirm.ask("Open browser automatically?", default=True):
            webbrowser.open(auth_url)
            console.print("[green]✓[/green] Browser opened\n")
    else:
        console.print("[yellow]Copy this URL into your browser[/yellow]\n")

    # Instructions
    console.print(
        Panel(
            "1. Sign in with your Google account\n"
            "2. Authorize contacts access (read-only)\n"
            "3. You will be redirected to the callback URL\n"
            "4. Copy the complete redirect page URL",
            title="[bold]Instructions[/bold]",
            border_style="yellow",
        )
    )

    console.print("\n[bold green]Step 2: Authorization Code[/bold green]")

    # Retrieve authorization code
    while True:
        callback_url = Prompt.ask(
            "\n📋 [bold]Paste the complete callback URL[/bold]\n"
            "[dim](format: http://localhost:8003/oauth/callback?code=...)[/dim]"
        )

        try:
            authorization_code = extract_code_from_url(callback_url)
            console.print(
                f"[green]✓[/green] Code extracted: [cyan]{authorization_code[:20]}...[/cyan]"
            )
            break
        except ValueError as e:
            console.print(f"[red]❌ Error: {e}[/red]")
            if not Confirm.ask("Try again?", default=True):
                sys.exit(1)

    # Call the service
    console.print("\n[bold green]Step 3: Aircraft Configuration[/bold green]")
    console.print(f"Service URL: [cyan]{service_url}[/cyan]\n")

    try:
        with console.status("[bold cyan]Sending configuration...") as status:
            result = call_oauth_callback(aircraft_id, authorization_code, service_url)

        console.print("\n[bold green]✅ Configuration successful![/bold green]\n")
        console.print(
            Panel(
                f"Aircraft ID: [cyan]{result.get('aircraft_id')}[/cyan]\n"
                f"Message: [green]{result.get('message')}[/green]\n"
                f"Success: [green]{result.get('success')}[/green]",
                title="[bold]Result[/bold]",
                border_style="green",
            )
        )

        console.print("\n[dim]The aircraft can now access Google contacts![/dim]")

    except httpx.HTTPStatusError as e:
        console.print(f"\n[red]❌ HTTP Error {e.response.status_code}[/red]")
        console.print(f"[dim]Details: {e.response.text}[/dim]\n")

        if e.response.status_code == 400:
            console.print("[yellow]Authorization code is invalid or expired.[/yellow]")
            console.print("[yellow]Codes expire after ~10 minutes.[/yellow]")
            console.print("[yellow]Restart the process to get a new code.[/yellow]")
        elif e.response.status_code == 403:
            console.print("[yellow]Insufficient scopes.[/yellow]")
            console.print("[yellow]Verify that 'contacts.readonly' is authorized.[/yellow]")
        elif e.response.status_code == 500:
            console.print("[yellow]Server error (database?).[/yellow]")
            console.print("[yellow]Verify that ENCRYPTION_KEY is defined.[/yellow]")

        sys.exit(1)

    except httpx.ConnectError:
        console.print(f"\n[red]❌ Cannot connect to {service_url}[/red]")
        console.print("[yellow]Verify that the contacts service is started.[/yellow]\n")
        sys.exit(1)

    except Exception as e:
        console.print(f"\n[red]❌ Unexpected error: {e}[/red]\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
