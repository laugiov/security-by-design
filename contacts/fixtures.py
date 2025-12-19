"""Static fixtures for demo mode contacts."""

from typing import Any


def get_contacts_fixtures() -> list[dict[str, Any]]:
    """Return static demo contacts matching Google People API format.

    Returns a simplified subset of GooglePerson schema with:
    - resourceName
    - names (displayName, givenName, familyName)
    - emailAddresses
    - phoneNumbers
    - photos (optional)
    - organizations (optional)

    Used for MVP demonstration without requiring Google OAuth integration.
    """
    return [
        {
            "resourceName": "people/c1001",
            "etag": "%EgUBBgcuNj0=",
            "names": [
                {
                    "displayName": "Alice Dupont",
                    "givenName": "Alice",
                    "familyName": "Dupont",
                    "unstructuredName": "Alice Dupont",
                }
            ],
            "emailAddresses": [
                {"value": "alice.dupont@example.com", "type": "work", "metadata": {"primary": True}}
            ],
            "phoneNumbers": [{"value": "+33612345678", "type": "mobile"}],
            "photos": [{"url": "https://lh3.googleusercontent.com/alice", "default": True}],
            "organizations": [{"name": "SkyLink", "title": "Product Manager"}],
        },
        {
            "resourceName": "people/c1002",
            "etag": "%EgUBBgcuOD0=",
            "names": [
                {
                    "displayName": "Bob Martin",
                    "givenName": "Bob",
                    "familyName": "Martin",
                    "unstructuredName": "Bob Martin",
                }
            ],
            "emailAddresses": [
                {"value": "bob.martin@example.com", "type": "work"},
                {"value": "bob@personal.com", "type": "home", "metadata": {"primary": False}},
            ],
            "phoneNumbers": [
                {"value": "+33623456789", "type": "work"},
                {"value": "+33656781234", "type": "home"},
            ],
            "organizations": [{"name": "TechCorp", "title": "Senior Developer"}],
        },
        {
            "resourceName": "people/c1003",
            "etag": "%EgUBBgcuMD0=",
            "names": [
                {
                    "displayName": "Claire Bernard",
                    "givenName": "Claire",
                    "familyName": "Bernard",
                    "unstructuredName": "Claire Bernard",
                }
            ],
            "emailAddresses": [{"value": "claire.bernard@example.com", "type": "work"}],
            "phoneNumbers": [{"value": "+33634567890", "type": "mobile"}],
            "photos": [{"url": "https://lh3.googleusercontent.com/claire", "default": True}],
        },
        {
            "resourceName": "people/c1004",
            "etag": "%EgUBBgcuND0=",
            "names": [
                {
                    "displayName": "David Leroy",
                    "givenName": "David",
                    "familyName": "Leroy",
                    "unstructuredName": "David Leroy",
                }
            ],
            "emailAddresses": [{"value": "david.leroy@example.com", "type": "work"}],
            "phoneNumbers": [{"value": "+33645678901", "type": "work"}],
            "organizations": [{"name": "Startup Inc", "title": "CTO"}],
        },
        {
            "resourceName": "people/c1005",
            "etag": "%EgUBBgcuNT0=",
            "names": [
                {
                    "displayName": "Emma Petit",
                    "givenName": "Emma",
                    "familyName": "Petit",
                    "unstructuredName": "Emma Petit",
                }
            ],
            "emailAddresses": [
                {"value": "emma.petit@example.com", "type": "work", "metadata": {"primary": True}}
            ],
            "phoneNumbers": [{"value": "+33656789012", "type": "mobile"}],
            "photos": [{"url": "https://lh3.googleusercontent.com/emma", "default": True}],
            "organizations": [{"name": "Design Studio", "title": "UX Designer"}],
        },
    ]
