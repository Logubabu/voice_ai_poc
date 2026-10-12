import pytest
import asyncio
import os
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import AsyncMock, MagicMock, patch

from app.callbacks.models import (
    CallbackModel,
    CallbackCreateRequest,
    CallbackRescheduleRequest,
    can_transition_status,
    mask_phone_number,
)
from app.callbacks.time_resolver import (
    normalize_e164_phone,
    resolve_timezone,
    parse_natural_language_time,
    TimeResolverError,
)
from app.callbacks.repository import CallbackRepository
from app.callbacks.service import CallbackService
from app.callbacks.scheduler import CallbackSchedulerWorker
from app.tools.callback_tools import (
    ScheduleCallbackTool,
    GetCallbackStatusTool,
)


@pytest.fixture
def temp_db():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_callbacks.db")
    repo = CallbackRepository(db_path=db_path)
    yield repo
    shutil.rmtree(temp_dir, ignore_errors=True)


# --- 1. Natural Language Time Parsing & Timezone Tests ---

def test_e164_phone_normalization():
    assert normalize_e164_phone("9876543210") == "+919876543210"
    assert normalize_e164_phone("+91 98765-43210") == "+919876543210"
    assert normalize_e164_phone("+1 (555) 019-9000") == "+15550199000"

    with pytest.raises(TimeResolverError):
        normalize_e164_phone("invalid")

    with pytest.raises(TimeResolverError):
        normalize_e164_phone("")


def test_timezone_resolution():
    tz, name = resolve_timezone("Asia/Kolkata")
    assert name == "Asia/Kolkata"
    assert isinstance(tz, ZoneInfo)

    tz_ny, name_ny = resolve_timezone("America/New_York")
    assert name_ny == "America/New_York"

    # Invalid timezone falls back to default
    _, name_fallback = resolve_timezone("Invalid/Timezone")
    assert name_fallback in ("Asia/Kolkata", "UTC")


def test_natural_language_time_parsing():
    # Relative offset: in 30 minutes
    res_rel = parse_natural_language_time("in 30 minutes", user_tz_str="Asia/Kolkata")
    assert res_rel["is_ambiguous"] is False
    assert "scheduled_at_utc" in res_rel

    dt_utc = datetime.fromisoformat(res_rel["scheduled_at_utc"].replace("Z", "+00:00"))
    now_utc = datetime.now(timezone.utc)
    diff = (dt_utc - now_utc).total_seconds()
    assert 1700 <= diff <= 1900  # Approx 30 mins (1800s)

    # Specific time: tomorrow at 3 PM
    res_tom = parse_natural_language_time("tomorrow at 3 PM", user_tz_str="Asia/Kolkata")
    assert res_tom["is_ambiguous"] is False
    local_dt = datetime.fromisoformat(res_tom["scheduled_at_local"])
    assert local_dt.hour == 15
    assert local_dt.minute == 0

    # Ambiguous "tomorrow" without specific time
    res_amb = parse_natural_language_time("tomorrow", user_tz_str="Asia/Kolkata")
    assert res_amb["is_ambiguous"] is True


# --- 2. State Machine Tests ---

def test_state_machine_transitions():
    assert can_transition_status("SCHEDULED", "DIALING") is True
    assert can_transition_status("DIALING", "ANSWERED") is True
    assert can_transition_status("ANSWERED", "COMPLETED") is True

    # Invalid transitions
    assert can_transition_status("COMPLETED", "DIALING") is False
    assert can_transition_status("CANCELLED", "SCHEDULED") is False


def test_phone_masking():
    assert mask_phone_number("+919876543210") == "+919******210"
    assert mask_phone_number("+15550199000") == "+155*****000"


# --- 3. Repository & Idempotency Tests ---

@pytest.mark.asyncio
async def test_repository_crud_and_idempotency(temp_db):
    repo = temp_db
    cb = CallbackModel(
        id="cb_test_001",
        tenant_id="tenant_a",
        conversation_id="conv_100",
        phone_number="+919876543210",
        masked_phone_number="+919******210",
        requested_time_text="tomorrow at 3 PM",
        scheduled_at_utc=datetime.now(timezone.utc).isoformat(),
        timezone="Asia/Kolkata",
        idempotency_key="unique_key_001",
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )

    created, is_new = await repo.create_callback(cb)
    assert is_new is True
    assert created.id == "cb_test_001"

    # Duplicate creation with same idempotency key
    created_dup, is_new_dup = await repo.create_callback(cb)
    assert is_new_dup is False
    assert created_dup.id == "cb_test_001"

    # Get callback with tenant isolation
    retrieved = await repo.get_callback("cb_test_001", tenant_id="tenant_a")
    assert retrieved is not None
    assert retrieved.phone_number == "+919876543210"

    # Cross-tenant access denied
    retrieved_cross = await repo.get_callback("cb_test_001", tenant_id="tenant_b")
    assert retrieved_cross is None


# --- 4. Multi-Worker Concurrency Locking Test ---

@pytest.mark.asyncio
async def test_multi_worker_atomic_claiming(temp_db):
    repo = temp_db
    past_utc = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()

    # Insert 5 due callbacks
    for i in range(5):
        cb = CallbackModel(
            id=f"cb_due_{i}",
            tenant_id="default_tenant",
            conversation_id=f"conv_{i}",
            phone_number=f"+91987654320{i}",
            requested_time_text="in 5 mins ago",
            scheduled_at_utc=past_utc,
            idempotency_key=f"key_due_{i}",
            created_at=past_utc,
            updated_at=past_utc,
        )
        await repo.create_callback(cb)

    # Simulate 10 concurrent workers calling claim_due_callbacks
    async def worker_claim_task(worker_id: str):
        now_iso = datetime.now(timezone.utc).isoformat()
        return await repo.claim_due_callbacks(now_utc_iso=now_iso, limit=10, worker_id=worker_id)

    results = await asyncio.gather(*[worker_claim_task(f"worker_{w}") for w in range(10)])

    # Flatten all claimed callbacks across all workers
    all_claimed = [cb for worker_results in results for cb in worker_results]
    claimed_ids = [cb.id for cb in all_claimed]

    # Verify EXACTLY 5 callbacks claimed total across all 10 workers (NO duplicates!)
    assert len(claimed_ids) == 5
    assert len(set(claimed_ids)) == 5


# --- 5. Callback Service & Tools Integration Tests ---

@pytest.mark.asyncio
async def test_callback_service_schedule_and_reschedule(temp_db):
    service = CallbackService(repo=temp_db)

    # Schedule callback
    req = CallbackCreateRequest(
        phone_number="+919876543210",
        requested_time="tomorrow at 3 PM",
        timezone="Asia/Kolkata",
        customer_name="Loganathan",
        reason="Consultation",
    )
    res = await service.schedule_callback(req)
    assert res.success is True
    assert res.callback_id is not None

    # Reschedule callback
    resched_req = CallbackRescheduleRequest(new_requested_time="tomorrow at 5 PM")
    res_resched = await service.reschedule_callback(res.callback_id, resched_req)
    assert res_resched.success is True
    assert "05:00 PM" in res_resched.message or "5 PM" in res_resched.message

    # Cancel callback
    res_cancel = await service.cancel_callback(res.callback_id)
    assert res_cancel.success is True
    assert res_cancel.status == "CANCELLED"


@pytest.mark.asyncio
async def test_callback_tools_execution(temp_db):
    service = CallbackService(repo=temp_db)
    with patch("app.callbacks.service.callback_service", service):
        tool = ScheduleCallbackTool()
        tool_res = await tool.execute({
            "phone_number": "+919876543210",
            "requested_time": "in 15 minutes",
            "reason": "Test Tool",
        })
        assert tool_res["success"] is True
        cb_id = tool_res["callback_id"]

        status_tool = GetCallbackStatusTool()
        status_res = await status_tool.execute({"callback_id": cb_id})
        assert status_res["success"] is True
        assert status_res["status"] == "SCHEDULED"


# --- 6. Worker Outbound Call & Retry Policy Tests ---

@pytest.mark.asyncio
async def test_scheduler_worker_retry_policy(temp_db):
    repo = temp_db
    worker = CallbackSchedulerWorker(repo=repo, poll_interval=0.1)

    past_utc = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    cb = CallbackModel(
        id="cb_retry_test",
        tenant_id="default_tenant",
        conversation_id="conv_retry",
        phone_number="+919876543210",
        requested_time_text="5 mins ago",
        scheduled_at_utc=past_utc,
        idempotency_key="retry_key_001",
        created_at=past_utc,
        updated_at=past_utc,
    )
    await repo.create_callback(cb)

    # Mock telephony provider to simulate call failure
    mock_provider = MagicMock()
    mock_provider.initiate_outbound_call = AsyncMock(return_value={"success": False, "error": "Busy line"})

    with patch("app.callbacks.scheduler.get_telephony_provider", return_value=mock_provider):
        count = await worker.process_due_callbacks()
        assert count == 1
        await asyncio.sleep(0.2)

    # Verify callback transitioned to RETRY_PENDING with attempt_count = 1
    updated = await repo.get_callback("cb_retry_test")
    assert updated.status == "RETRY_PENDING"
    assert updated.attempt_count == 1
    assert updated.next_attempt_at is not None
