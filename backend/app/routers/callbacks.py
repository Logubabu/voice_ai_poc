from typing import List, Optional
from fastapi import APIRouter, HTTPException, Header, Query, Path

from app.callbacks.models import (
    CallbackCreateRequest,
    CallbackRescheduleRequest,
    CallbackCancelRequest,
    CallbackResponse,
    CallbackModel,
)
from app.callbacks.service import callback_service
from app.callbacks.metrics import callback_metrics

router = APIRouter(prefix="/api/callbacks", tags=["Scheduled Callbacks"])


def _get_tenant_id(x_tenant_id: Optional[str] = Header(None), tenant_id: Optional[str] = Query(None)) -> str:
    tid = x_tenant_id or tenant_id or "default_tenant"
    return tid.strip()


@router.post("", response_model=CallbackResponse, summary="Schedule a new voice callback")
async def create_callback(
    req: CallbackCreateRequest,
    x_tenant_id: Optional[str] = Header(None),
):
    """Schedules a new voice callback with E.164 phone normalization, natural language time resolution, and idempotency."""
    if x_tenant_id:
        req.tenant_id = x_tenant_id
    return await callback_service.schedule_callback(req)


@router.get("", response_model=List[CallbackModel], summary="List scheduled callbacks for tenant")
async def list_callbacks(
    status: Optional[str] = Query(None, description="Filter by status (e.g. SCHEDULED, COMPLETED, FAILED)"),
    phone_number: Optional[str] = Query(None, description="Filter by recipient phone number"),
    limit: int = Query(50, ge=1, le=100),
    x_tenant_id: Optional[str] = Header(None),
    tenant_id: Optional[str] = Query(None),
):
    """Returns list of callbacks with tenant isolation."""
    tid = _get_tenant_id(x_tenant_id, tenant_id)
    return await callback_service.repo.list_callbacks(
        tenant_id=tid,
        status=status,
        phone_number=phone_number,
        limit=limit,
    )


@router.get("/metrics", summary="Get callback system metrics")
async def get_callback_metrics():
    """Returns real-time callback system metrics."""
    return callback_metrics.get_summary()


@router.get("/{callback_id}", response_model=CallbackResponse, summary="Get callback status details")
async def get_callback_status(
    callback_id: str = Path(..., description="Callback ID, phone number, or conversation ID"),
    x_tenant_id: Optional[str] = Header(None),
    tenant_id: Optional[str] = Query(None),
):
    """Queries details and status for a callback."""
    tid = _get_tenant_id(x_tenant_id, tenant_id)
    res = await callback_service.get_callback_status(callback_id, tenant_id=tid)
    if not res.success:
        raise HTTPException(status_code=404, detail=res.message)
    return res


@router.patch("/{callback_id}", response_model=CallbackResponse, summary="Reschedule callback")
@router.post("/{callback_id}/reschedule", response_model=CallbackResponse, summary="Reschedule callback")
async def reschedule_callback(
    req: CallbackRescheduleRequest,
    callback_id: str = Path(...),
    x_tenant_id: Optional[str] = Header(None),
    tenant_id: Optional[str] = Query(None),
):
    """Reschedules an existing callback to a new requested time."""
    tid = _get_tenant_id(x_tenant_id, tenant_id)
    res = await callback_service.reschedule_callback(callback_id, req, tenant_id=tid)
    if not res.success:
        raise HTTPException(status_code=400, detail=res.message)
    return res


@router.post("/{callback_id}/cancel", response_model=CallbackResponse, summary="Cancel callback")
async def cancel_callback(
    callback_id: str = Path(...),
    req: Optional[CallbackCancelRequest] = None,
    x_tenant_id: Optional[str] = Header(None),
    tenant_id: Optional[str] = Query(None),
):
    """Cancels a scheduled callback idempotently."""
    tid = _get_tenant_id(x_tenant_id, tenant_id)
    res = await callback_service.cancel_callback(callback_id, req, tenant_id=tid)
    if not res.success:
        raise HTTPException(status_code=400, detail=res.message)
    return res


@router.post("/{callback_id}/retry", response_model=CallbackResponse, summary="Force retry failed callback")
async def retry_callback(
    callback_id: str = Path(...),
    x_tenant_id: Optional[str] = Header(None),
    tenant_id: Optional[str] = Query(None),
):
    """Forces manual retry of a failed or no-answer callback."""
    tid = _get_tenant_id(x_tenant_id, tenant_id)
    cb = await callback_service.repo.get_callback(callback_id, tenant_id=tid)
    if not cb:
        raise HTTPException(status_code=404, detail=f"Callback '{callback_id}' not found.")

    updated = await callback_service.repo.update_status(
        callback_id=cb.id,
        target_status="RETRY_PENDING",
        failure_reason="Manual retry requested via API",
    )
    if not updated:
        raise HTTPException(status_code=400, detail="Could not update callback for retry.")

    return CallbackResponse(
        success=True,
        callback_id=cb.id,
        status="RETRY_PENDING",
        message="Callback has been queued for immediate retry.",
    )
