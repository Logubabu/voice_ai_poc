/**
 * Scheduled Callbacks API Service
 * Handles API interactions with backend callback endpoints and normalizes response schemas.
 */

export interface CallbackItem {
  id: string;
  tenant_id: string;
  user_id?: string;
  contact_id?: string;
  phone_number: string;
  contact_name: string;
  callback_reason: string;
  conversation_id?: string;
  source: string;
  scheduled_at: string;
  timezone: string;
  status: 'SCHEDULED' | 'READY' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED' | 'FAILED' | 'EXPIRED' | 'WAITING_FOR_CREDITS';
  attempt_count: number;
  max_attempts: number;
  priority: 'low' | 'normal' | 'high' | 'urgent';
  execution_mode: 'SCHEDULE_ONLY' | 'LIVE_CALL';
  provider?: string;
  provider_call_id?: string;
  last_attempt_at?: string;
  next_attempt_at?: string;
  completed_at?: string;
  cancelled_at?: string;
  failure_reason?: string;
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface CallbackListResponse {
  items: CallbackItem[];
  total: number;
  page: number;
  limit: number;
}

export interface CreateCallbackPayload {
  phone_number: string;
  contact_name?: string;
  scheduled_at: string;
  timezone?: string;
  callback_reason?: string;
  priority?: string;
  conversation_id?: string;
}

export interface RescheduleCallbackPayload {
  scheduled_at?: string;
  timezone?: string;
  callback_reason?: string;
  priority?: string;
}

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

function normalizeCallbackItem(item: any): CallbackItem {
  return {
    id: item.id || `cb_${Math.random().toString(36).substring(2, 8)}`,
    tenant_id: item.tenant_id || 'default_tenant',
    user_id: item.user_id || item.customer_id,
    contact_id: item.contact_id || item.customer_id,
    phone_number: item.phone_number || '',
    contact_name: item.contact_name || item.customer_name || 'Valued Contact',
    callback_reason: item.callback_reason || item.reason || 'Voice AI Follow-up',
    conversation_id: item.conversation_id,
    source: item.source || 'web_call',
    scheduled_at: item.scheduled_at || item.scheduled_at_utc || new Date().toISOString(),
    timezone: item.timezone || 'Asia/Kolkata',
    status: (item.status || 'SCHEDULED') as any,
    attempt_count: item.attempt_count ?? 0,
    max_attempts: item.max_attempts ?? 3,
    priority: (item.priority || 'normal') as any,
    execution_mode: (item.execution_mode || 'SCHEDULE_ONLY') as any,
    provider: item.provider || item.telephony_provider,
    provider_call_id: item.provider_call_id || item.call_sid,
    last_attempt_at: item.last_attempt_at,
    next_attempt_at: item.next_attempt_at,
    completed_at: item.completed_at,
    cancelled_at: item.cancelled_at,
    failure_reason: item.failure_reason,
    metadata: item.metadata || {},
    created_at: item.created_at || new Date().toISOString(),
    updated_at: item.updated_at || new Date().toISOString(),
  };
}

export class CallbackService {
  /**
   * Fetches paginated list of callbacks with optional filtering and sorting.
   */
  async getCallbacks(params?: {
    page?: number;
    limit?: number;
    status?: string;
    search?: string;
    sort?: string;
  }): Promise<CallbackListResponse> {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.append('page', params.page.toString());
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    if (params?.status) searchParams.append('status', params.status);
    if (params?.search) searchParams.append('search', params.search);
    if (params?.sort) searchParams.append('sort', params.sort);

    const query = searchParams.toString();
    const url = `${BACKEND_URL}/api/callbacks${query ? `?${query}` : ''}`;
    
    let res: Response;
    try {
      res = await fetch(url);
    } catch (err: any) {
      console.warn('[CALLBACK-SERVICE] Fetch error, returning empty list:', err);
      return { items: [], total: 0, page: 1, limit: params?.limit || 10 };
    }

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Failed to fetch callbacks (${res.status}): ${errText}`);
    }

    const data = await res.json();
    let rawItems: any[] = [];
    let totalCount = 0;

    if (Array.isArray(data)) {
      rawItems = data;
      totalCount = data.length;
    } else if (data && Array.isArray(data.items)) {
      rawItems = data.items;
      totalCount = data.total ?? data.items.length;
    }

    return {
      items: rawItems.map(normalizeCallbackItem),
      total: totalCount,
      page: params?.page || 1,
      limit: params?.limit || 10,
    };
  }

  /**
   * Fetches a single callback by ID.
   */
  async getCallbackById(id: string): Promise<CallbackItem> {
    const res = await fetch(`${BACKEND_URL}/api/callbacks/${id}`);
    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Failed to fetch callback details (${res.status}): ${errText}`);
    }
    const data = await res.json();
    return normalizeCallbackItem(data.callback || data);
  }

  /**
   * Creates a new scheduled callback record.
   */
  async createCallback(
    payload: CreateCallbackPayload,
    idempotencyKey?: string
  ): Promise<{ success: boolean; callback: CallbackItem }> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (idempotencyKey) {
      headers['Idempotency-Key'] = idempotencyKey;
    }
    const res = await fetch(`${BACKEND_URL}/api/callbacks`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(errData.detail || `Failed to create callback (${res.status})`);
    }
    const data = await res.json();
    return {
      success: data.success ?? true,
      callback: normalizeCallbackItem(data.callback || data),
    };
  }

  /**
   * Reschedules an existing callback.
   */
  async rescheduleCallback(
    id: string,
    payload: RescheduleCallbackPayload
  ): Promise<{ success: boolean; callback: CallbackItem }> {
    const res = await fetch(`${BACKEND_URL}/api/callbacks/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        new_requested_time: payload.scheduled_at,
        timezone: payload.timezone,
        reason: payload.callback_reason,
      }),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(errData.detail || `Failed to reschedule callback (${res.status})`);
    }
    const data = await res.json();
    return {
      success: data.success ?? true,
      callback: normalizeCallbackItem(data.callback || data),
    };
  }

  /**
   * Cancels a scheduled callback.
   */
  async cancelCallback(id: string, reason?: string): Promise<{ success: boolean; callback: CallbackItem }> {
    const res = await fetch(`${BACKEND_URL}/api/callbacks/${id}/cancel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: reason || 'Cancelled by user' }),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(errData.detail || `Failed to cancel callback (${res.status})`);
    }
    const data = await res.json();
    return {
      success: data.success ?? true,
      callback: normalizeCallbackItem(data.callback || data),
    };
  }
}

export const callbackService = new CallbackService();
