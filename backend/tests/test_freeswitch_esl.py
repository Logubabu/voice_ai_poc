import pytest
from app.telephony.freeswitch.esl_client import FreeSWITCHESLClient
from app.telephony.freeswitch.event_listener import FreeSWITCHEventListener


@pytest.mark.asyncio
async def test_freeswitch_esl_client_command():
    client = FreeSWITCHESLClient(host="127.0.0.1", port=8021)
    res = await client.execute_command("status")
    assert res["success"] is True
    assert "+OK" in res["body"]


def test_freeswitch_event_listener_lifecycle():
    listener = FreeSWITCHEventListener()
    test_uuid = "uuid_test_12345"

    listener.handle_event("CHANNEL_CREATE", {"Unique-ID": test_uuid, "Caller-Caller-ID-Number": "12345"})
    assert test_uuid in listener.active_sessions
    assert listener.active_sessions[test_uuid].state == "INCOMING"

    listener.handle_event("CHANNEL_ANSWER", {"Unique-ID": test_uuid})
    assert listener.active_sessions[test_uuid].state == "AI_ACTIVE"

    listener.handle_event("CHANNEL_HANGUP", {"Unique-ID": test_uuid})
    assert test_uuid not in listener.active_sessions
