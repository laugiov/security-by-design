"""Tests for Telemetry Service (following Weather/Contacts pattern).

Ce fichier teste le service Telemetry directement, comme test_weather_service.py
et test_contacts_service.py.

Note: Le service Telemetry requiert une authentification JWT (option B - defense in depth).
Les tests mockent la verification JWT via dependency override.
"""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from telemetry.api import verify_bearer_token
from telemetry.main import app

# Aircraft ID de test (simule le "sub" du JWT)
TEST_AIRCRAFT_ID = "550e8400-e29b-41d4-a716-446655440000"


# Override de la dependance JWT pour les tests
async def mock_verify_bearer_token() -> dict:
    """Mock JWT verification - retourne des claims valides."""
    return {"sub": TEST_AIRCRAFT_ID, "aud": "skylink"}


# Applique l'override pour tous les tests
app.dependency_overrides[verify_bearer_token] = mock_verify_bearer_token

client = TestClient(app)


class TestTelemetryHealth:
    """Test health check endpoint."""

    def test_health_check_returns_200(self):
        """Health check should return 200 with status healthy."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "telemetry"

    def test_root_returns_service_info(self):
        """Root endpoint should return service information."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "telemetry"
        assert "version" in data
        assert data["status"] == "running"


class TestTelemetryIngest:
    """Test telemetry ingestion endpoint."""

    def _make_event(self, event_id=None, aircraft_id=None):
        """Helper pour creer un evenement de test."""
        return {
            "event_id": str(event_id or uuid4()),
            "aircraft_id": str(aircraft_id or TEST_AIRCRAFT_ID),
            "ts": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "speed": 50.5,
                "altitude": 75.0,
                "engine_temp": 90.0,
            },
        }

    def test_ingest_telemetry_creates_event(self):
        """POST /telemetry should create new event and return 201."""
        event = self._make_event()
        response = client.post(
            "/telemetry",
            json=event,
            headers={"Authorization": "Bearer fake_token"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "created"
        assert data["event_id"] == event["event_id"]

    def test_ingest_telemetry_duplicate_returns_200(self):
        """POST /telemetry with same event_id should return 200 (duplicate)."""
        event_id = uuid4()
        event = self._make_event(event_id=event_id)

        # Premier envoi -> 201 created
        response1 = client.post(
            "/telemetry",
            json=event,
            headers={"Authorization": "Bearer fake_token"},
        )
        assert response1.status_code == 201

        # Deuxieme envoi (meme payload) -> 200 duplicate
        response2 = client.post(
            "/telemetry",
            json=event,
            headers={"Authorization": "Bearer fake_token"},
        )
        assert response2.status_code == 200
        data = response2.json()
        assert data["status"] == "duplicate"
        assert data["event_id"] == str(event_id)

    def test_ingest_telemetry_conflict_returns_409(self):
        """POST /telemetry with same event_id but different payload -> 409."""
        event_id = uuid4()

        # Premier envoi
        event1 = self._make_event(event_id=event_id)
        response1 = client.post(
            "/telemetry",
            json=event1,
            headers={"Authorization": "Bearer fake_token"},
        )
        assert response1.status_code == 201

        # Deuxieme envoi avec payload different (meme event_id)
        event2 = self._make_event(event_id=event_id)
        event2["metrics"]["speed"] = 100.0  # Valeur differente

        response2 = client.post(
            "/telemetry",
            json=event2,
            headers={"Authorization": "Bearer fake_token"},
        )
        assert response2.status_code == 409
        data = response2.json()
        assert "detail" in data
        assert data["detail"]["code"] == "TELEMETRY_CONFLICT"

    def test_ingest_telemetry_requires_event_id(self):
        """POST /telemetry should require event_id."""
        event = {
            "aircraft_id": TEST_AIRCRAFT_ID,
            "ts": datetime.now(timezone.utc).isoformat(),
            "metrics": {"speed": 50.0},
        }
        response = client.post(
            "/telemetry",
            json=event,
            headers={"Authorization": "Bearer fake_token"},
        )
        assert response.status_code == 422  # Validation error

    def test_ingest_telemetry_requires_aircraft_id(self):
        """POST /telemetry should require aircraft_id."""
        event = {
            "event_id": str(uuid4()),
            "ts": datetime.now(timezone.utc).isoformat(),
            "metrics": {"speed": 50.0},
        }
        response = client.post(
            "/telemetry",
            json=event,
            headers={"Authorization": "Bearer fake_token"},
        )
        assert response.status_code == 422

    def test_ingest_telemetry_requires_timestamp(self):
        """POST /telemetry should require ts (timestamp)."""
        event = {
            "event_id": str(uuid4()),
            "aircraft_id": TEST_AIRCRAFT_ID,
            "metrics": {"speed": 50.0},
        }
        response = client.post(
            "/telemetry",
            json=event,
            headers={"Authorization": "Bearer fake_token"},
        )
        assert response.status_code == 422

    def test_ingest_telemetry_requires_metrics(self):
        """POST /telemetry should require metrics object."""
        event = {
            "event_id": str(uuid4()),
            "aircraft_id": TEST_AIRCRAFT_ID,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        response = client.post(
            "/telemetry",
            json=event,
            headers={"Authorization": "Bearer fake_token"},
        )
        assert response.status_code == 422

    def test_ingest_telemetry_validates_altitude_range(self):
        """altitude must be between 0 and 100."""
        event = self._make_event()
        event["metrics"]["altitude"] = 150  # Invalid

        response = client.post(
            "/telemetry",
            json=event,
            headers={"Authorization": "Bearer fake_token"},
        )
        assert response.status_code == 422

    def test_ingest_telemetry_validates_battery_level_range(self):
        """battery_level must be between 0 and 100."""
        event = self._make_event()
        event["metrics"]["battery_level"] = -10  # Invalid

        response = client.post(
            "/telemetry",
            json=event,
            headers={"Authorization": "Bearer fake_token"},
        )
        assert response.status_code == 422

    def test_ingest_telemetry_rejects_extra_fields(self):
        """Schema strict: extra fields should be rejected."""
        event = self._make_event()
        event["extra_field"] = "not allowed"

        response = client.post(
            "/telemetry",
            json=event,
            headers={"Authorization": "Bearer fake_token"},
        )
        assert response.status_code == 422

    def test_ingest_telemetry_rejects_extra_metrics_fields(self):
        """Schema strict: extra fields in metrics should be rejected."""
        event = self._make_event()
        event["metrics"]["unknown_metric"] = 42

        response = client.post(
            "/telemetry",
            json=event,
            headers={"Authorization": "Bearer fake_token"},
        )
        assert response.status_code == 422


class TestTelemetryMetrics:
    """Test various metrics structures."""

    def _post_event(self, metrics):
        """Helper pour poster un evenement avec des metrics specifiques."""
        event = {
            "event_id": str(uuid4()),
            "aircraft_id": TEST_AIRCRAFT_ID,
            "ts": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics,
        }
        return client.post(
            "/telemetry",
            json=event,
            headers={"Authorization": "Bearer fake_token"},
        )

    def test_metrics_with_gps(self):
        """Test GPS metrics."""
        response = self._post_event(
            {
                "speed": 60.0,
                "gps": {
                    "lat": 48.8566,
                    "lon": 2.3522,
                    "heading": 90.0,
                    "altitude": 35.0,
                    "speed_over_ground": 58.5,
                },
            }
        )
        assert response.status_code == 201

    def test_metrics_with_engine_status(self):
        """Test engine status metrics."""
        response = self._post_event(
            {
                "engine_status": {
                    "front_left": 220.0,
                    "front_right": 220.0,
                    "rear_left": 210.0,
                    "rear_right": 210.0,
                },
            }
        )
        assert response.status_code == 201

    def test_metrics_with_flight_controls(self):
        """Test flight_controls metrics."""
        response = self._post_event(
            {
                "speed": 80.0,
                "flight_controls": {
                    "gear": 5,
                    "mode": "sport",
                },
            }
        )
        assert response.status_code == 201

    def test_metrics_with_lights_status(self):
        """Test lights status metrics."""
        response = self._post_event(
            {
                "lights_status": {
                    "headlights": True,
                    "brake_lights": False,
                    "turn_signal_left": False,
                    "turn_signal_right": True,
                },
            }
        )
        assert response.status_code == 201

    def test_metrics_with_climate_control(self):
        """Test climate control metrics."""
        response = self._post_event(
            {
                "climate_control": {
                    "temperature_setting": 22.5,
                    "fan_speed": 3,
                    "ac_on": True,
                    "recirculation_mode": False,
                },
            }
        )
        assert response.status_code == 201

    def test_metrics_with_cabin_pressure(self):
        """Test cabin pressure metrics."""
        response = self._post_event(
            {
                "cabin_pressure": {
                    "driver": True,
                    "passenger_front": True,
                    "rear_left": False,
                    "rear_center": False,
                    "rear_right": False,
                },
            }
        )
        assert response.status_code == 201

    def test_metrics_empty_object(self):
        """Metrics can be empty object (all fields are optional)."""
        response = self._post_event({})
        assert response.status_code == 201

    def test_metrics_full_payload(self):
        """Test with all metrics populated."""
        response = self._post_event(
            {
                "speed": 90.5,
                "altitude": 65.0,
                "engine_temp": 88.0,
                "oil_level": 80.0,
                "outside_temp": 18.5,
                "brake_status": "ok",
                "battery_level": 95.0,
                "airbag_status": "armed",
                "engine_status": {
                    "front_left": 220.0,
                    "front_right": 220.0,
                    "rear_left": 210.0,
                    "rear_right": 210.0,
                },
                "gps": {
                    "lat": 48.8566,
                    "lon": 2.3522,
                    "heading": 45.0,
                    "altitude": 35.0,
                    "speed_over_ground": 89.0,
                },
                "flight_controls": {
                    "gear": 6,
                    "mode": "eco",
                },
                "lights_status": {
                    "headlights": True,
                    "brake_lights": False,
                    "turn_signal_left": False,
                    "turn_signal_right": False,
                },
                "climate_control": {
                    "temperature_setting": 21.0,
                    "fan_speed": 2,
                    "ac_on": True,
                    "recirculation_mode": False,
                },
                "cabin_pressure": {
                    "driver": True,
                    "passenger_front": True,
                    "rear_left": False,
                    "rear_center": False,
                    "rear_right": False,
                },
            }
        )
        assert response.status_code == 201


class TestAircraftIdValidation:
    """Test aircraft_id validation between token and payload."""

    def test_aircraft_id_mismatch_returns_400(self):
        """aircraft_id in payload must match JWT sub claim."""
        # Le mock retourne sub=TEST_AIRCRAFT_ID
        # On envoie un aircraft_id different
        different_aircraft_id = "11111111-1111-1111-1111-111111111111"

        event = {
            "event_id": str(uuid4()),
            "aircraft_id": different_aircraft_id,  # Different du mock JWT
            "ts": datetime.now(timezone.utc).isoformat(),
            "metrics": {"speed": 50.0},
        }
        response = client.post(
            "/telemetry",
            json=event,
            headers={"Authorization": "Bearer fake_token"},
        )
        assert response.status_code == 400
        data = response.json()
        assert "mismatch" in data["detail"].lower()
