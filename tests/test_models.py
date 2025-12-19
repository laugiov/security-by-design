"""Tests for generated model classes."""

from uuid import UUID

# Contacts models
from skylink.models.contacts.contacts_health_check200_response import (
    ContactsHealthCheck200Response,
)
from skylink.models.contacts.contacts_obtain_token200_response import (
    ContactsObtainToken200Response,
)
from skylink.models.contacts.contacts_obtain_token_request import ContactsObtainTokenRequest
from skylink.models.contacts.contacts_start_google_o_auth200_response import (
    ContactsStartGoogleOAuth200Response,
)
from skylink.models.contacts.contacts_start_google_o_auth_request import (
    ContactsStartGoogleOAuthRequest,
)
from skylink.models.contacts.google_person_addresses_inner import GooglePersonAddressesInner
from skylink.models.contacts.google_person_birthdays_inner import GooglePersonBirthdaysInner
from skylink.models.contacts.google_person_email_addresses_inner import (
    GooglePersonEmailAddressesInner,
)
from skylink.models.contacts.google_person_email_addresses_inner_metadata import (
    GooglePersonEmailAddressesInnerMetadata,
)
from skylink.models.contacts.google_person_metadata import GooglePersonMetadata
from skylink.models.contacts.google_person_names_inner import GooglePersonNamesInner
from skylink.models.contacts.google_person_organizations_inner import (
    GooglePersonOrganizationsInner,
)
from skylink.models.contacts.google_person_phone_numbers_inner import (
    GooglePersonPhoneNumbersInner,
)
from skylink.models.contacts.google_person_photos_inner import GooglePersonPhotosInner

# Gateway models
from skylink.models.gateway.obtain_token200_response import ObtainToken200Response
from skylink.models.gateway.obtain_token_request import ObtainTokenRequest

# Telemetry models
from skylink.models.telemetry.telemetry_event_metrics import TelemetryEventMetrics
from skylink.models.telemetry.telemetry_event_metrics_cabin_pressure import (
    TelemetryEventMetricsCabinPressure,
)
from skylink.models.telemetry.telemetry_event_metrics_engine_status import (
    TelemetryEventMetricsEngineStatus,
)
from skylink.models.telemetry.telemetry_event_metrics_flight_controls import (
    TelemetryEventMetricsFlightControls,
)
from skylink.models.telemetry.telemetry_health_check200_response import (
    TelemetryHealthCheck200Response,
)
from skylink.models.telemetry.telemetry_ingest_telemetry201_response import (
    TelemetryIngestTelemetry201Response,
)
from skylink.models.telemetry.telemetry_obtain_token200_response import (
    TelemetryObtainToken200Response,
)
from skylink.models.telemetry.telemetry_obtain_token_request import TelemetryObtainTokenRequest

# Weather models
from skylink.models.weather.weather_health_check200_response import WeatherHealthCheck200Response
from skylink.models.weather.weather_obtain_token200_response import WeatherObtainToken200Response
from skylink.models.weather.weather_obtain_token_request import WeatherObtainTokenRequest

# ------------- GATEWAY MODELS -------------


def test_obtain_token_request_creation():
    """Test ObtainTokenRequest model creation and basic operations."""
    aircraft_id = UUID("550e8400-e29b-41d4-a716-446655440000")
    model = ObtainTokenRequest(aircraft_id=aircraft_id)
    assert model.aircraft_id == aircraft_id
    assert str(aircraft_id) in model.to_str()
    model_dict = model.to_dict()
    assert model_dict["aircraft_id"] == aircraft_id
    recreated = ObtainTokenRequest.from_dict(model_dict)
    assert recreated.aircraft_id == aircraft_id


def test_obtain_token200_response_creation():
    """Test ObtainToken200Response model creation."""
    model = ObtainToken200Response(
        access_token="test_token", token_type="Bearer", expires_in=900  # noqa: S106
    )
    assert model.access_token == "test_token"  # noqa: S105
    assert model.token_type == "Bearer"  # noqa: S105
    assert model.expires_in == 900
    json_str = model.to_json()
    assert "test_token" in json_str
    model_dict = model.to_dict()
    assert model_dict["access_token"] == "test_token"  # noqa: S105
    recreated = ObtainToken200Response.from_dict(model_dict)
    assert recreated.access_token == "test_token"  # noqa: S105


# ------------- WEATHER MODELS -------------


def test_weather_health_check200_response_creation():
    """Test WeatherHealthCheck200Response model creation."""
    model = WeatherHealthCheck200Response(status="healthy", service="weather", version="1.0.0")
    assert model.status == "healthy"
    assert model.service == "weather"
    json_str = model.to_json()
    assert "healthy" in json_str
    recreated = WeatherHealthCheck200Response.from_json(json_str)
    assert recreated.status == "healthy"


def test_weather_obtain_token_request_creation():
    """Test WeatherObtainTokenRequest model creation."""
    aircraft_id = UUID("550e8400-e29b-41d4-a716-446655440000")
    model = WeatherObtainTokenRequest(aircraft_id=aircraft_id)
    assert model.aircraft_id == aircraft_id
    model_dict = model.to_dict()
    recreated = WeatherObtainTokenRequest.from_dict(model_dict)
    assert recreated.aircraft_id == aircraft_id


def test_weather_obtain_token200_response_creation():
    """Test WeatherObtainToken200Response model creation."""
    model = WeatherObtainToken200Response(
        access_token="weather_token", token_type="Bearer", expires_in=3600  # noqa: S106
    )
    assert model.access_token == "weather_token"  # noqa: S105
    json_str = model.to_json()
    recreated = WeatherObtainToken200Response.from_json(json_str)
    assert recreated.access_token == "weather_token"  # noqa: S105


# ------------- CONTACTS MODELS -------------


def test_contacts_health_check200_response_creation():
    """Test ContactsHealthCheck200Response model creation."""
    model = ContactsHealthCheck200Response(status="healthy", service="contacts", version="1.0.0")
    assert model.status == "healthy"
    json_str = model.to_json()
    recreated = ContactsHealthCheck200Response.from_json(json_str)
    assert recreated.service == "contacts"


def test_contacts_obtain_token_request_creation():
    """Test ContactsObtainTokenRequest model creation."""
    aircraft_id = UUID("550e8400-e29b-41d4-a716-446655440000")
    model = ContactsObtainTokenRequest(aircraft_id=aircraft_id)
    assert model.aircraft_id == aircraft_id
    recreated = ContactsObtainTokenRequest.from_dict(model.to_dict())
    assert recreated.aircraft_id == aircraft_id


def test_contacts_obtain_token200_response_creation():
    """Test ContactsObtainToken200Response model creation."""
    model = ContactsObtainToken200Response(
        access_token="contacts_token", token_type="Bearer", expires_in=3600  # noqa: S106
    )
    assert model.access_token == "contacts_token"  # noqa: S105
    recreated = ContactsObtainToken200Response.from_json(model.to_json())
    assert recreated.expires_in == 3600


# ------------- TELEMETRY MODELS -------------


def test_telemetry_health_check200_response_creation():
    """Test TelemetryHealthCheck200Response model creation."""
    model = TelemetryHealthCheck200Response(status="healthy", service="telemetry", version="1.0.0")
    assert model.service == "telemetry"
    recreated = TelemetryHealthCheck200Response.from_json(model.to_json())
    assert recreated.status == "healthy"


def test_telemetry_obtain_token_request_creation():
    """Test TelemetryObtainTokenRequest model creation."""
    aircraft_id = UUID("550e8400-e29b-41d4-a716-446655440000")
    model = TelemetryObtainTokenRequest(aircraft_id=aircraft_id)
    assert model.aircraft_id == aircraft_id
    recreated = TelemetryObtainTokenRequest.from_dict(model.to_dict())
    assert recreated.aircraft_id == aircraft_id


def test_telemetry_obtain_token200_response_creation():
    """Test TelemetryObtainToken200Response model creation."""
    model = TelemetryObtainToken200Response(
        access_token="telemetry_token", token_type="Bearer", expires_in=3600  # noqa: S106
    )
    assert model.access_token == "telemetry_token"  # noqa: S105
    recreated = TelemetryObtainToken200Response.from_json(model.to_json())
    assert recreated.token_type == "Bearer"  # noqa: S105


def test_telemetry_ingest_telemetry201_response_creation():
    """Test TelemetryIngestTelemetry201Response model creation."""
    event_id = UUID("550e8400-e29b-41d4-a716-446655440001")
    model = TelemetryIngestTelemetry201Response(event_id=event_id, status="received")
    assert model.event_id == event_id
    assert model.status == "received"
    recreated = TelemetryIngestTelemetry201Response.from_dict(model.to_dict())
    assert recreated.status == "received"


# ------------- ADDITIONAL CONTACTS MODELS -------------


def test_contacts_start_google_o_auth_request_creation():
    """Test ContactsStartGoogleOAuthRequest model."""
    model = ContactsStartGoogleOAuthRequest(
        redirect_uri="https://example.com/callback", include_other_contacts=True
    )
    assert model.redirect_uri == "https://example.com/callback"
    assert model.include_other_contacts is True
    assert "example.com" in model.to_str()
    recreated = ContactsStartGoogleOAuthRequest.from_dict(model.to_dict())
    assert recreated.redirect_uri == "https://example.com/callback"


def test_contacts_start_google_o_auth200_response_creation():
    """Test ContactsStartGoogleOAuth200Response model."""
    model = ContactsStartGoogleOAuth200Response(
        authorization_url="https://accounts.google.com/oauth",
        state="random_state",
        code_challenge_method="S256",
    )
    assert "google.com" in model.authorization_url
    assert model.state == "random_state"
    json_str = model.to_json()
    assert "random_state" in json_str
    recreated = ContactsStartGoogleOAuth200Response.from_dict(model.to_dict())
    assert recreated.state == "random_state"


def test_google_person_addresses_inner_creation():
    """Test GooglePersonAddressesInner model."""
    model = GooglePersonAddressesInner(formatted_value="123 Main St, Paris, France")
    assert "Paris" in model.formatted_value
    assert "Main St" in model.to_str()
    recreated = GooglePersonAddressesInner.from_dict(model.to_dict())
    assert "France" in recreated.formatted_value


def test_google_person_birthdays_inner_creation():
    """Test GooglePersonBirthdaysInner model."""
    model = GooglePersonBirthdaysInner(text="January 1, 1990")
    assert "1990" in model.text
    assert "January" in model.to_str()
    json_str = model.to_json()
    assert "1990" in json_str
    recreated = GooglePersonBirthdaysInner.from_dict(model.to_dict())
    assert "January" in recreated.text


def test_google_person_email_addresses_inner_metadata_creation():
    """Test GooglePersonEmailAddressesInnerMetadata model."""
    model = GooglePersonEmailAddressesInnerMetadata(primary=True)
    assert model.primary is True
    recreated = GooglePersonEmailAddressesInnerMetadata.from_dict(model.to_dict())
    assert recreated.primary is True


def test_google_person_email_addresses_inner_creation():
    """Test GooglePersonEmailAddressesInner model."""
    metadata = GooglePersonEmailAddressesInnerMetadata(primary=True)
    model = GooglePersonEmailAddressesInner(value="john@example.com", metadata=metadata)
    assert model.value == "john@example.com"
    assert model.metadata.primary is True
    recreated = GooglePersonEmailAddressesInner.from_dict(model.to_dict())
    assert "john@example.com" in recreated.value


def test_google_person_metadata_creation():
    """Test GooglePersonMetadata model."""
    model = GooglePersonMetadata(deleted=False)
    model.to_json()  # Test JSON serialization
    recreated = GooglePersonMetadata.from_dict(model.to_dict())
    assert recreated is not None


def test_google_person_names_inner_creation():
    """Test GooglePersonNamesInner model."""
    model = GooglePersonNamesInner(display_name="John Doe", given_name="John", family_name="Doe")
    assert model.display_name == "John Doe"
    assert model.given_name == "John"
    recreated = GooglePersonNamesInner.from_dict(model.to_dict())
    assert recreated.family_name == "Doe"


def test_google_person_organizations_inner_creation():
    """Test GooglePersonOrganizationsInner model."""
    model = GooglePersonOrganizationsInner(name="Acme Corp")
    assert model.name == "Acme Corp"
    json_str = model.to_json()
    assert "Acme" in json_str
    recreated = GooglePersonOrganizationsInner.from_dict(model.to_dict())
    assert recreated.name == "Acme Corp"


def test_google_person_phone_numbers_inner_creation():
    """Test GooglePersonPhoneNumbersInner model."""
    metadata = GooglePersonEmailAddressesInnerMetadata(primary=False)
    model = GooglePersonPhoneNumbersInner(value="+33123456789", metadata=metadata)
    assert model.value == "+33123456789"
    assert "+33" in model.to_str()
    recreated = GooglePersonPhoneNumbersInner.from_dict(model.to_dict())
    assert recreated.value == "+33123456789"


def test_google_person_photos_inner_creation():
    """Test GooglePersonPhotosInner model."""
    model = GooglePersonPhotosInner(url="https://example.com/photo.jpg")
    assert "photo.jpg" in model.url
    assert "example.com" in model.to_str()
    recreated = GooglePersonPhotosInner.from_dict(model.to_dict())
    assert "example.com" in recreated.url


# ------------- ADDITIONAL TELEMETRY MODELS -------------


def test_telemetry_event_metrics_engine_status_creation():
    """Test TelemetryEventMetricsEngineStatus model."""
    model = TelemetryEventMetricsEngineStatus(
        front_left=2.2, front_right=2.3, rear_left=2.1, rear_right=2.2
    )
    assert model.front_left == 2.2
    assert model.front_right == 2.3
    json_str = model.to_json()
    assert "2.2" in json_str
    recreated = TelemetryEventMetricsEngineStatus.from_dict(model.to_dict())
    assert recreated.rear_right == 2.2


def test_telemetry_event_metrics_cabin_pressure_creation():
    """Test TelemetryEventMetricsCabinPressure model."""
    model = TelemetryEventMetricsCabinPressure(driver=True, passenger_front=False, rear_left=False)
    model.to_json()  # Test JSON serialization
    recreated = TelemetryEventMetricsCabinPressure.from_dict(model.to_dict())
    assert recreated is not None


def test_telemetry_event_metrics_flight_controls_creation():
    """Test TelemetryEventMetricsFlightControls model."""
    model = TelemetryEventMetricsFlightControls(gear=5, mode="sport")
    assert model.gear == 5
    json_str = model.to_json()
    assert "sport" in json_str
    recreated = TelemetryEventMetricsFlightControls.from_dict(model.to_dict())
    assert recreated.gear == 5


def test_telemetry_event_metrics_flight_controls_mode_validation():
    """Test TelemetryEventMetricsFlightControls mode enum validation."""
    # Valid modes
    for mode in ["eco", "normal", "sport", "manual"]:
        model = TelemetryEventMetricsFlightControls(gear=1, mode=mode)
        assert model.mode == mode
        # Test to_str includes the mode
        assert mode in model.to_str() or mode in model.to_dict().get("mode", "")

    # Invalid mode should raise validation error
    import pytest

    with pytest.raises((ValueError, Exception)):
        TelemetryEventMetricsFlightControls(gear=1, mode="invalid")


def test_telemetry_event_metrics_creation():
    """Test TelemetryEventMetrics model."""
    model = TelemetryEventMetrics(
        speed=65.5,
        altitude=75.0,
        engine_temp=90.0,
    )
    assert model.speed == 65.5
    assert model.altitude == 75.0
    assert "65.5" in model.to_str()
    recreated = TelemetryEventMetrics.from_dict(model.to_dict())
    assert recreated.engine_temp == 90.0


# ------------- ADDITIONAL ROUTER EDGE CASES -------------


def test_all_routers_have_correct_prefixes():
    """Test that all routers have the correct URL prefixes."""
    from skylink.routers import auth, contacts, telemetry, weather

    assert auth.router.prefix == "/auth"
    assert weather.router.prefix == "/weather"
    assert contacts.router.prefix == "/contacts"
    assert telemetry.router.prefix == "/telemetry"


def test_all_routers_have_tags():
    """Test that all routers have tags defined."""
    from skylink.routers import auth, contacts, telemetry, weather

    assert "auth" in auth.router.tags
    assert "weather" in weather.router.tags
    assert "contacts" in contacts.router.tags
    assert "telemetry" in telemetry.router.tags


def test_router_module_imports():
    """Test that router modules can be imported successfully."""
    from skylink import routers

    assert hasattr(routers, "auth")
    assert hasattr(routers, "weather")
    assert hasattr(routers, "contacts")
    assert hasattr(routers, "telemetry")
