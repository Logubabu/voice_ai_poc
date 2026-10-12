import os
import json
import sqlite3
import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from app.callbacks.models import (
    CallbackModel,
    CallbackStatus,
    can_transition_status,
    mask_phone_number,
)
from app.utils.logging import logger


class CallbackRepositoryError(Exception):
    """Database exception for callback repository operations."""
    pass


class CallbackRepository:
    """Persistent SQLite-backed repository for Scheduled Callbacks with atomic multi-worker claiming."""

    def __init__(self, db_path: str = "data/callbacks.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._lock = asyncio.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS callbacks (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    customer_id TEXT,
                    conversation_id TEXT NOT NULL,
                    source_call_id TEXT,
                    phone_number TEXT NOT NULL,
                    masked_phone_number TEXT NOT NULL,
                    customer_name TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    callback_context TEXT,
                    requested_time_text TEXT NOT NULL,
                    scheduled_at_utc TEXT NOT NULL,
                    timezone TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt_count INTEGER DEFAULT 0,
                    max_attempts INTEGER DEFAULT 3,
                    last_attempt_at TEXT,
                    next_attempt_at TEXT,
                    call_sid TEXT,
                    telephony_provider TEXT DEFAULT 'twilio',
                    idempotency_key TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    failure_reason TEXT,
                    last_call_status TEXT,
                    metadata TEXT
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_callbacks_tenant_status ON callbacks(tenant_id, status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_callbacks_status_scheduled ON callbacks(status, scheduled_at_utc)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_callbacks_phone ON callbacks(phone_number)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_callbacks_idempotency ON callbacks(idempotency_key)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_callbacks_next_attempt ON callbacks(next_attempt_at)")
            conn.commit()

    def _row_to_model(self, row: sqlite3.Row) -> CallbackModel:
        d = dict(row)
        metadata_str = d.get("metadata")
        if metadata_str:
            try:
                d["metadata"] = json.loads(metadata_str)
            except Exception:
                d["metadata"] = {}
        else:
            d["metadata"] = {}
        return CallbackModel(**d)

    async def create_callback(self, callback: CallbackModel) -> Tuple[CallbackModel, bool]:
        """Idempotently creates a callback record. Returns (callback_model, created_new_bool)."""
        async with self._lock:
            def _op():
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    # Check for existing idempotency key
                    cursor.execute("SELECT * FROM callbacks WHERE idempotency_key = ?", (callback.idempotency_key,))
                    existing = cursor.fetchone()
                    if existing:
                        logger.info(f"[CALLBACK-REPO] Idempotency match found for key '{callback.idempotency_key}'. Returning existing callback '{existing['id']}'.")
                        return self._row_to_model(existing), False

                    metadata_json = json.dumps(callback.metadata)
                    cursor.execute("""
                        INSERT INTO callbacks (
                            id, tenant_id, customer_id, conversation_id, source_call_id,
                            phone_number, masked_phone_number, customer_name, reason,
                            callback_context, requested_time_text, scheduled_at_utc, timezone,
                            status, attempt_count, max_attempts, last_attempt_at, next_attempt_at,
                            call_sid, telephony_provider, idempotency_key, created_at, updated_at,
                            completed_at, failure_reason, last_call_status, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        callback.id, callback.tenant_id, callback.customer_id, callback.conversation_id,
                        callback.source_call_id, callback.phone_number, callback.masked_phone_number or mask_phone_number(callback.phone_number),
                        callback.customer_name, callback.reason, callback.callback_context, callback.requested_time_text,
                        callback.scheduled_at_utc, callback.timezone, callback.status, callback.attempt_count,
                        callback.max_attempts, callback.last_attempt_at, callback.next_attempt_at, callback.call_sid,
                        callback.telephony_provider, callback.idempotency_key, callback.created_at, callback.updated_at,
                        callback.completed_at, callback.failure_reason, callback.last_call_status, metadata_json
                    ))
                    conn.commit()
                    return callback, True

            return await asyncio.to_thread(_op)

    async def get_callback(self, callback_id: str, tenant_id: Optional[str] = None) -> Optional[CallbackModel]:
        """Retrieves callback by ID with tenant isolation check."""
        def _op():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if tenant_id:
                    cursor.execute("SELECT * FROM callbacks WHERE id = ? AND tenant_id = ?", (callback_id, tenant_id))
                else:
                    cursor.execute("SELECT * FROM callbacks WHERE id = ?", (callback_id,))
                row = cursor.fetchone()
                return self._row_to_model(row) if row else None
        return await asyncio.to_thread(_op)

    async def list_callbacks(
        self,
        tenant_id: Optional[str] = None,
        status: Optional[str] = None,
        phone_number: Optional[str] = None,
        limit: int = 50,
    ) -> List[CallbackModel]:
        """Lists callbacks matching criteria."""
        def _op():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM callbacks WHERE 1=1"
                params = []

                if tenant_id:
                    query += " AND tenant_id = ?"
                    params.append(tenant_id)
                if status:
                    query += " AND status = ?"
                    params.append(status)
                if phone_number:
                    query += " AND phone_number = ?"
                    params.append(phone_number)

                query += " ORDER BY created_at DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [self._row_to_model(r) for r in rows]
        return await asyncio.to_thread(_op)

    async def update_status(
        self,
        callback_id: str,
        target_status: str,
        call_sid: Optional[str] = None,
        failure_reason: Optional[str] = None,
        last_call_status: Optional[str] = None,
        next_attempt_at: Optional[str] = None,
    ) -> Optional[CallbackModel]:
        """Updates callback status with explicit state machine transition check."""
        async with self._lock:
            def _op():
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM callbacks WHERE id = ?", (callback_id,))
                    row = cursor.fetchone()
                    if not row:
                        return None

                    current = self._row_to_model(row)
                    if not can_transition_status(current.status, target_status):
                        logger.warning(f"[CALLBACK-REPO] Invalid state transition from '{current.status}' to '{target_status}' for callback '{callback_id}'. Ignoring.")
                        return current

                    now_utc = datetime.now(timezone.utc).isoformat()
                    completed_at = current.completed_at
                    if target_status in (CallbackStatus.COMPLETED.value, CallbackStatus.CANCELLED.value):
                        completed_at = now_utc

                    new_call_sid = call_sid or current.call_sid
                    new_failure_reason = failure_reason or current.failure_reason
                    new_last_call_status = last_call_status or current.last_call_status
                    new_next_attempt_at = next_attempt_at if next_attempt_at is not None else current.next_attempt_at

                    cursor.execute("""
                        UPDATE callbacks SET
                            status = ?,
                            updated_at = ?,
                            completed_at = ?,
                            call_sid = ?,
                            failure_reason = ?,
                            last_call_status = ?,
                            next_attempt_at = ?
                        WHERE id = ?
                    """, (
                        target_status, now_utc, completed_at, new_call_sid,
                        new_failure_reason, new_last_call_status, new_next_attempt_at, callback_id
                    ))
                    conn.commit()

                    cursor.execute("SELECT * FROM callbacks WHERE id = ?", (callback_id,))
                    return self._row_to_model(cursor.fetchone())

            return await asyncio.to_thread(_op)

    async def claim_due_callbacks(self, now_utc_iso: str, limit: int = 10, worker_id: str = "worker-1") -> List[CallbackModel]:
        """Atomically claims due callbacks using SQLite BEGIN IMMEDIATE transaction.
        
        Guarantees that multiple concurrent workers claiming jobs will NEVER pick up or dial the same callback!
        """
        async with self._lock:
            def _op():
                claimed: List[CallbackModel] = []
                with self._get_connection() as conn:
                    conn.execute("BEGIN IMMEDIATE;")
                    cursor = conn.cursor()

                    # Find candidates due for dialing
                    cursor.execute("""
                        SELECT id FROM callbacks
                        WHERE status IN ('SCHEDULED', 'RETRY_PENDING')
                          AND (scheduled_at_utc <= ? OR (next_attempt_at IS NOT NULL AND next_attempt_at <= ?))
                        ORDER BY scheduled_at_utc ASC
                        LIMIT ?
                    """, (now_utc_iso, now_utc_iso, limit))

                    rows = cursor.fetchall()
                    now_iso = datetime.now(timezone.utc).isoformat()

                    for r in rows:
                        cb_id = r["id"]
                        # Atomically transition candidate to DIALING
                        cursor.execute("""
                            UPDATE callbacks
                            SET status = 'DIALING',
                                attempt_count = attempt_count + 1,
                                last_attempt_at = ?,
                                updated_at = ?
                            WHERE id = ?
                              AND status IN ('SCHEDULED', 'RETRY_PENDING')
                        """, (now_iso, now_iso, cb_id))

                        if cursor.rowcount > 0:
                            cursor.execute("SELECT * FROM callbacks WHERE id = ?", (cb_id,))
                            claimed_row = cursor.fetchone()
                            if claimed_row:
                                claimed.append(self._row_to_model(claimed_row))

                    conn.commit()
                return claimed

            return await asyncio.to_thread(_op)

    async def recover_stale_dialing_callbacks(self, timeout_seconds: float = 60.0) -> int:
        """Watchdog: Recovers callbacks stuck in DIALING/RINGING for too long back to RETRY_PENDING or FAILED."""
        async with self._lock:
            def _op():
                recovered_count = 0
                now_dt = datetime.now(timezone.utc)
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT * FROM callbacks WHERE status IN ('DIALING', 'RINGING', 'QUEUED')
                    """)
                    rows = cursor.fetchall()
                    for r in rows:
                        cb = self._row_to_model(r)
                        updated_dt = datetime.fromisoformat(cb.updated_at.replace("Z", "+00:00"))
                        if (now_dt - updated_dt).total_seconds() > timeout_seconds:
                            now_iso = now_dt.isoformat()
                            if cb.attempt_count < cb.max_attempts:
                                cursor.execute("""
                                    UPDATE callbacks SET status = 'RETRY_PENDING', updated_at = ?, failure_reason = 'Stale dialing timeout' WHERE id = ?
                                """, (now_iso, cb.id))
                            else:
                                cursor.execute("""
                                    UPDATE callbacks SET status = 'FAILED', updated_at = ?, failure_reason = 'Max attempts exceeded after timeout' WHERE id = ?
                                """, (now_iso, cb.id))
                            recovered_count += 1
                    conn.commit()
                return recovered_count
            return await asyncio.to_thread(_op)


callback_repository = CallbackRepository()
