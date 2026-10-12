import pytest
import httpx
from app.config import config
from app.telephony.twilio_service import twilio_service
from app.telephony.twilio.signature import validate_twilio_request
from app.telephony.provider import get_telephony_provider, TwilioTelephonyProvider, FreeSwitchTelephonyProvider


def test_twilio_twiml_generation():
    twiml = twilio_service.generate_twiml()
    assert "<?xml" in twiml
    assert "<Response>" in twiml
    assert "<Connect>" in twiml
    assert "<Stream" in twiml


def test_twilio_signature_validation():
    # When TWILIO_VALIDATE_SIGNATURE is disabled for local dev/testing
    config.TWILIO_VALIDATE_SIGNATURE = False
    assert validate_twilio_request(
        url="http://localhost:8000/api/twilio/voice",
        params={"From": "+919876543210"},
        signature="",
    ) is True


def test_telephony_provider_abstraction():
    twilio_prov = get_telephony_provider("twilio")
    assert isinstance(twilio_prov, TwilioTelephonyProvider)
    assert twilio_prov.get_provider_name() == "twilio"
    
    freeswitch_prov = get_telephony_provider("freeswitch")
    assert isinstance(freeswitch_prov, FreeSwitchTelephonyProvider)
    assert freeswitch_prov.get_provider_name() == "freeswitch"

    status = twilio_prov.get_status()
    assert status["provider"] == "twilio"
    assert status["account_sid_configured"] is True


@pytest.mark.asyncio
async def test_twilio_outbound_call_mock(monkeypatch):
    async def mock_post(*args, **kwargs):
        class MockResponse:
            status_code = 201
            def json(self):
                return {
                    "sid": "CA_mock_call_sid_12345",
                    "status": "queued",
                    "to": "+919876543210",
                    "from": "+17372508034",
                }
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    provider = get_telephony_provider("twilio")
    res = await provider.initiate_outbound_call("+919876543210")
    assert res["success"] is True
    assert res["call_sid"] == "CA_mock_call_sid_12345"
    assert res["status"] == "queued"
