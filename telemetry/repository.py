"""Data repository for the telemetry service."""

from typing import Protocol
from uuid import UUID

from telemetry.schemas import TelemetryEvent


class TelemetryRepository(Protocol):
    """Repository contract for event persistence."""

    async def exists(self, aircraft_id: UUID, event_id: UUID) -> bool:
        """Returns True if an event (aircraft_id, event_id) already exists."""

    async def get(self, aircraft_id: UUID, event_id: UUID) -> TelemetryEvent | None:
        """Returns the existing event or None."""

    async def insert(self, event: TelemetryEvent) -> None:
        """Inserts a new event."""


class InMemoryTelemetryRepository:
    """
    In-memory implementation for startup / tests.
    To be replaced later with a PostgreSQL implementation.
    """

    def __init__(self) -> None:
        # Dictionary with key = (aircraft_id, event_id)
        self._events: dict[tuple[UUID, UUID], TelemetryEvent] = {}

    async def exists(self, aircraft_id: UUID, event_id: UUID) -> bool:
        return (aircraft_id, event_id) in self._events

    async def get(self, aircraft_id: UUID, event_id: UUID) -> TelemetryEvent | None:
        return self._events.get((aircraft_id, event_id))

    async def insert(self, event: TelemetryEvent) -> None:
        self._events[(event.aircraft_id, event.event_id)] = event
