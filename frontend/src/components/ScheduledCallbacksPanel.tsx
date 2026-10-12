import React, { useEffect, useState, useCallback } from 'react';
import {
  Calendar,
  Clock,
  Plus,
  Search,
  RefreshCw,
  AlertTriangle,
  XCircle,
  Edit2,
  PhoneCall,
  CheckCircle2,
  ShieldAlert,
  Loader2,
  User,
  Phone,
  FileText,
  Globe,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { callbackService, type CallbackItem } from '../services/callbacks';

export const ScheduledCallbacksPanel: React.FC = () => {
  const [callbacks, setCallbacks] = useState<CallbackItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Pagination & Filtering state
  const [page, setPage] = useState<number>(1);
  const [limit] = useState<number>(10);
  const [total, setTotal] = useState<number>(0);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Modal states
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [editingCallback, setEditingCallback] = useState<CallbackItem | null>(null);

  // Form fields
  const [contactName, setContactName] = useState<string>('John Doe');
  const [phoneNumber, setPhoneNumber] = useState<string>('+919876543210');
  const [scheduledDate, setScheduledDate] = useState<string>('');
  const [scheduledTime, setScheduledTime] = useState<string>('');
  const [timezone, setTimezone] = useState<string>('Asia/Kolkata');
  const [reason, setReason] = useState<string>('Follow up call regarding product demo');
  const [priority, setPriority] = useState<string>('normal');

  // Submit / Idempotency state
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Detect browser timezone on mount
  useEffect(() => {
    try {
      const detected = Intl.DateTimeFormat().resolvedOptions().timeZone;
      if (detected) setTimezone(detected);
    } catch {
      // Default fallback
    }

    // Set default date & time to 1 hour from now
    const now = new Date();
    now.setHours(now.getHours() + 1);
    const dateStr = now.toISOString().split('T')[0];
    const timeStr = now.toTimeString().slice(0, 5);
    setScheduledDate(dateStr);
    setScheduledTime(timeStr);
  }, []);

  const fetchCallbacks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const filterStatus = statusFilter === 'ALL' ? undefined : statusFilter;
      const res = await callbackService.getCallbacks({
        page,
        limit,
        status: filterStatus,
        search: searchQuery.trim() || undefined,
        sort: 'scheduled_at ASC',
      });
      setCallbacks(res.items);
      setTotal(res.total);
    } catch (err: any) {
      console.error('[CALLBACKS-UI] Error fetching callbacks:', err);
      setError(err.message || 'Failed to load scheduled callbacks.');
    } finally {
      setLoading(false);
    }
  }, [page, limit, statusFilter, searchQuery]);

  useEffect(() => {
    fetchCallbacks();
    // 30-second interval polling for real-time background status updates
    const interval = setInterval(fetchCallbacks, 30000);
    return () => clearInterval(interval);
  }, [fetchCallbacks]);

  const openCreateModal = () => {
    setEditingCallback(null);
    setContactName('');
    setPhoneNumber('');
    setReason('');
    setPriority('normal');
    setModalError(null);

    const now = new Date();
    now.setHours(now.getHours() + 1);
    setScheduledDate(now.toISOString().split('T')[0]);
    setScheduledTime(now.toTimeString().slice(0, 5));

    setIsModalOpen(true);
  };

  const openRescheduleModal = (cb: CallbackItem) => {
    setEditingCallback(cb);
    setContactName(cb.contact_name);
    setPhoneNumber(cb.phone_number);
    setReason(cb.callback_reason || '');
    setPriority(cb.priority || 'normal');
    setTimezone(cb.timezone || 'Asia/Kolkata');
    setModalError(null);

    try {
      const dt = new Date(cb.scheduled_at);
      setScheduledDate(dt.toISOString().split('T')[0]);
      setScheduledTime(dt.toTimeString().slice(0, 5));
    } catch {
      // fallback
    }

    setIsModalOpen(true);
  };

  const handleSubmitModal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return; // Prevent duplicate submissions

    setModalError(null);

    if (!phoneNumber.trim()) {
      setModalError('Phone number is required');
      return;
    }

    if (!scheduledDate || !scheduledTime) {
      setModalError('Please select both scheduled date and time');
      return;
    }

    setIsSubmitting(true);

    try {
      // Combine date and time into ISO string
      const isoDateTime = new Date(`${scheduledDate}T${scheduledTime}:00`).toISOString();

      if (editingCallback) {
        // Reschedule
        const res = await callbackService.rescheduleCallback(editingCallback.id, {
          scheduled_at: isoDateTime,
          timezone,
          callback_reason: reason.trim() || 'Rescheduled callback',
          priority,
        });

        setActionSuccess(`Callback #${res.callback.id.slice(0, 8)} rescheduled successfully!`);
      } else {
        // Create new
        const idempotencyKey = `cb-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
        const res = await callbackService.createCallback(
          {
            phone_number: phoneNumber.trim(),
            contact_name: contactName.trim() || 'Unknown Contact',
            scheduled_at: isoDateTime,
            timezone,
            callback_reason: reason.trim() || 'Voice AI follow-up callback',
            priority,
          },
          idempotencyKey
        );

        setActionSuccess(`Callback scheduled successfully! (ID: ${res.callback.id.slice(0, 8)})`);
      }

      setIsModalOpen(false);
      fetchCallbacks();

      setTimeout(() => setActionSuccess(null), 5000);
    } catch (err: any) {
      console.error('[CALLBACKS-UI] Modal submit error:', err);
      setModalError(err.message || 'Failed to save callback.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancelCallback = async (cb: CallbackItem) => {
    if (!window.confirm(`Are you sure you want to cancel callback for ${cb.contact_name} (${cb.phone_number})?`)) {
      return;
    }

    try {
      await callbackService.cancelCallback(cb.id, 'User cancelled via frontend panel');
      setActionSuccess(`Callback for ${cb.contact_name} cancelled.`);
      fetchCallbacks();
      setTimeout(() => setActionSuccess(null), 4000);
    } catch (err: any) {
      alert(`Failed to cancel callback: ${err.message}`);
    }
  };

  const renderStatusBadge = (status: CallbackItem['status']) => {
    switch (status) {
      case 'SCHEDULED':
        return (
          <span className="inline-flex items-center space-x-1 text-xs font-bold text-sky-400 bg-sky-500/10 border border-sky-500/30 px-2.5 py-1 rounded-full">
            <Clock className="w-3 h-3 animate-spin" style={{ animationDuration: '4s' }} />
            <span>Scheduled</span>
          </span>
        );
      case 'WAITING_FOR_CREDITS':
        return (
          <span className="inline-flex items-center space-x-1 text-xs font-bold text-amber-400 bg-amber-500/10 border border-amber-500/30 px-2.5 py-1 rounded-full" title="No outbound call credits available. Waiting for calling credits.">
            <AlertTriangle className="w-3 h-3" />
            <span>Waiting for Call Credits</span>
          </span>
        );
      case 'READY':
        return (
          <span className="inline-flex items-center space-x-1 text-xs font-bold text-indigo-400 bg-indigo-500/10 border border-indigo-500/30 px-2.5 py-1 rounded-full">
            <PhoneCall className="w-3 h-3" />
            <span>Ready for Call</span>
          </span>
        );
      case 'IN_PROGRESS':
        return (
          <span className="inline-flex items-center space-x-1 text-xs font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2.5 py-1 rounded-full">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping mr-1" />
            <span>In Call Progress</span>
          </span>
        );
      case 'COMPLETED':
        return (
          <span className="inline-flex items-center space-x-1 text-xs font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2.5 py-1 rounded-full">
            <CheckCircle2 className="w-3 h-3" />
            <span>Completed</span>
          </span>
        );
      case 'CANCELLED':
        return (
          <span className="inline-flex items-center space-x-1 text-xs font-bold text-slate-400 bg-slate-800 border border-slate-700 px-2.5 py-1 rounded-full">
            <XCircle className="w-3 h-3" />
            <span>Cancelled</span>
          </span>
        );
      case 'FAILED':
        return (
          <span className="inline-flex items-center space-x-1 text-xs font-bold text-rose-400 bg-rose-500/10 border border-rose-500/30 px-2.5 py-1 rounded-full">
            <ShieldAlert className="w-3 h-3" />
            <span>Failed</span>
          </span>
        );
      case 'EXPIRED':
        return (
          <span className="inline-flex items-center space-x-1 text-xs font-bold text-purple-400 bg-purple-500/10 border border-purple-500/30 px-2.5 py-1 rounded-full">
            <Clock className="w-3 h-3" />
            <span>Expired (Overdue)</span>
          </span>
        );
      default:
        return <span className="text-xs text-slate-400">{status}</span>;
    }
  };

  const formatScheduledTime = (utcIso: string, tz: string) => {
    try {
      const dt = new Date(utcIso);
      return new Intl.DateTimeFormat('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZoneName: 'short',
        timeZone: tz || undefined,
      }).format(dt);
    } catch {
      return utcIso;
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner Notice */}
      <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-start space-x-3 shadow-lg">
        <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
        <div className="text-xs space-y-1">
          <div className="font-bold text-amber-300 uppercase tracking-wider text-[11px]">
            No Call Credits / Schedule-Only Mode Active
          </div>
          <p className="text-slate-300 leading-relaxed">
            Outbound PSTN telephony credits are currently unavailable. Scheduled callbacks are safely saved and tracked in the system. When a scheduled time arrives, the background scheduler will set its status to{' '}
            <span className="font-bold text-amber-400">Waiting for Call Credits</span> without making outbound calls or consuming credits.
          </p>
        </div>
      </div>

      {/* Action Success Alert */}
      {actionSuccess && (
        <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center justify-between animate-fadeIn">
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>{actionSuccess}</span>
          </div>
          <button onClick={() => setActionSuccess(null)} className="text-slate-400 hover:text-white">
            <XCircle className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-extrabold text-white flex items-center space-x-2">
            <Calendar className="w-5 h-5 text-sky-400" />
            <span>Scheduled Callback Management</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Manage upcoming voice AI callbacks, customer follow-ups, and scheduling queues.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={fetchCallbacks}
            disabled={loading}
            className="p-2.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-300 hover:text-white hover:border-slate-700 transition-all"
            title="Refresh Callbacks"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>

          <button
            onClick={openCreateModal}
            className="flex items-center space-x-2 bg-gradient-to-r from-sky-500 to-emerald-500 hover:from-sky-400 hover:to-emerald-400 text-white font-semibold text-xs py-2.5 px-4 rounded-xl shadow-lg transition-all active:scale-[0.98]"
          >
            <Plus className="w-4 h-4" />
            <span>Schedule New Callback</span>
          </button>
        </div>
      </div>

      {/* Search & Status Filters */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="relative sm:col-span-2">
          <Search className="w-4 h-4 absolute left-3.5 top-3 text-slate-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by contact name, phone number, or reason..."
            className="w-full pl-10 pr-4 py-2 rounded-xl bg-slate-900/90 border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all"
          />
        </div>

        <div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="w-full px-3 py-2 rounded-xl bg-slate-900/90 border border-slate-800 text-xs text-slate-300 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all"
          >
            <option value="ALL">All Statuses</option>
            <option value="SCHEDULED">SCHEDULED</option>
            <option value="WAITING_FOR_CREDITS">WAITING FOR CREDITS</option>
            <option value="READY">READY FOR CALL</option>
            <option value="IN_PROGRESS">IN PROGRESS</option>
            <option value="COMPLETED">COMPLETED</option>
            <option value="CANCELLED">CANCELLED</option>
            <option value="FAILED">FAILED</option>
            <option value="EXPIRED">EXPIRED</option>
          </select>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center space-x-2">
          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Table Container */}
      <div className="bg-slate-900/80 rounded-2xl border border-slate-800 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-950/60 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                <th className="py-3 px-4">Contact</th>
                <th className="py-3 px-4">Phone Number</th>
                <th className="py-3 px-4">Scheduled Time</th>
                <th className="py-3 px-4">Reason</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-xs">
              {loading && callbacks.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-500">
                    <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-sky-400" />
                    <span>Loading scheduled callbacks...</span>
                  </td>
                </tr>
              ) : callbacks.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-500 space-y-2">
                    <Calendar className="w-8 h-8 mx-auto text-slate-600 mb-1" />
                    <div className="font-semibold text-slate-400">No scheduled callbacks found</div>
                    <p className="text-[11px] text-slate-500 max-w-sm mx-auto">
                      Click "Schedule New Callback" above or trigger a callback request during a live Voice AI conversation.
                    </p>
                  </td>
                </tr>
              ) : (
                callbacks.map((cb) => (
                  <tr key={cb.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-3.5 px-4 font-semibold text-slate-200">
                      <div className="flex items-center space-x-2">
                        <div className="w-7 h-7 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 font-bold text-xs shrink-0">
                          {cb.contact_name.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <div>{cb.contact_name}</div>
                          {cb.priority !== 'normal' && (
                            <span className="text-[9px] font-bold uppercase px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                              {cb.priority}
                            </span>
                          )}
                        </div>
                      </div>
                    </td>

                    <td className="py-3.5 px-4 font-mono text-slate-300">
                      {cb.phone_number}
                    </td>

                    <td className="py-3.5 px-4">
                      <div className="text-slate-200 font-medium">
                        {formatScheduledTime(cb.scheduled_at, cb.timezone)}
                      </div>
                      <div className="text-[10px] text-slate-500 flex items-center space-x-1 mt-0.5">
                        <Globe className="w-3 h-3" />
                        <span>{cb.timezone}</span>
                      </div>
                    </td>

                    <td className="py-3.5 px-4 text-slate-400 max-w-xs truncate" title={cb.callback_reason}>
                      {cb.callback_reason || '—'}
                    </td>

                    <td className="py-3.5 px-4">
                      {renderStatusBadge(cb.status)}
                    </td>

                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end space-x-1.5">
                        {(cb.status === 'SCHEDULED' || cb.status === 'WAITING_FOR_CREDITS' || cb.status === 'EXPIRED') && (
                          <button
                            onClick={() => openRescheduleModal(cb)}
                            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-sky-400 transition-all"
                            title="Reschedule Callback"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                        )}

                        {(cb.status === 'SCHEDULED' || cb.status === 'WAITING_FOR_CREDITS' || cb.status === 'READY') && (
                          <button
                            onClick={() => handleCancelCallback(cb)}
                            className="p-1.5 rounded-lg bg-slate-800 hover:bg-rose-950/60 text-rose-400 transition-all"
                            title="Cancel Callback"
                          >
                            <XCircle className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Footer Pagination */}
        <div className="px-4 py-3 bg-slate-950/40 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
          <div>
            Showing <span className="font-semibold text-slate-200">{callbacks.length}</span> of{' '}
            <span className="font-semibold text-slate-200">{total}</span> total callbacks
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1 || loading}
              className="p-1.5 rounded-lg bg-slate-800 border border-slate-700 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-700 transition-all text-slate-300"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="font-medium text-slate-300 px-2">Page {page}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page * limit >= total || loading}
              className="p-1.5 rounded-lg bg-slate-800 border border-slate-700 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-700 transition-all text-slate-300"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Modal Dialog for Create / Reschedule */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl w-full max-w-lg overflow-hidden shadow-2xl space-y-0">
            {/* Modal Header */}
            <div className="p-5 border-b border-slate-800 bg-slate-950/60 flex items-center justify-between">
              <div className="flex items-center space-x-2.5">
                <div className="p-2 rounded-xl bg-sky-500/10 border border-sky-500/30 text-sky-400">
                  <Calendar className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">
                    {editingCallback ? 'Reschedule Callback' : 'Schedule New Voice AI Callback'}
                  </h3>
                  <p className="text-xs text-slate-400">
                    {editingCallback ? `Modifying callback #${editingCallback.id.slice(0, 8)}` : 'Create a new scheduled phone callback'}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Form Body */}
            <form onSubmit={handleSubmitModal} className="p-6 space-y-4">
              {modalError && (
                <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center space-x-2">
                  <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                  <span>{modalError}</span>
                </div>
              )}

              {/* Contact Name & Phone */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center space-x-1">
                    <User className="w-3.5 h-3.5 text-sky-400" />
                    <span>Contact Name</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={contactName}
                    onChange={(e) => setContactName(e.target.value)}
                    placeholder="e.g. John Doe"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950/80 border border-slate-700 text-white text-xs placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center space-x-1">
                    <Phone className="w-3.5 h-3.5 text-sky-400" />
                    <span>Phone Number (E.164)</span>
                  </label>
                  <input
                    type="tel"
                    required
                    disabled={!!editingCallback}
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    placeholder="e.g. +919876543210"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950/80 border border-slate-700 text-white text-xs placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all disabled:opacity-60"
                  />
                </div>
              </div>

              {/* Date & Time */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center space-x-1">
                    <Calendar className="w-3.5 h-3.5 text-sky-400" />
                    <span>Scheduled Date</span>
                  </label>
                  <input
                    type="date"
                    required
                    value={scheduledDate}
                    onChange={(e) => setScheduledDate(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950/80 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center space-x-1">
                    <Clock className="w-3.5 h-3.5 text-sky-400" />
                    <span>Scheduled Time</span>
                  </label>
                  <input
                    type="time"
                    required
                    value={scheduledTime}
                    onChange={(e) => setScheduledTime(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950/80 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all"
                  />
                </div>
              </div>

              {/* Timezone & Priority */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center space-x-1">
                    <Globe className="w-3.5 h-3.5 text-sky-400" />
                    <span>Timezone</span>
                  </label>
                  <select
                    value={timezone}
                    onChange={(e) => setTimezone(e.target.value)}
                    className="w-full px-3 py-2.5 rounded-xl bg-slate-950/80 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all"
                  >
                    <option value="Asia/Kolkata">Asia/Kolkata (IST +05:30)</option>
                    <option value="UTC">UTC (Coordinated Universal Time)</option>
                    <option value="America/New_York">America/New_York (EST/EDT)</option>
                    <option value="Europe/London">Europe/London (GMT/BST)</option>
                    <option value="Asia/Dubai">Asia/Dubai (GST +04:00)</option>
                    <option value="Asia/Singapore">Asia/Singapore (SGT +08:00)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Priority
                  </label>
                  <select
                    value={priority}
                    onChange={(e) => setPriority(e.target.value)}
                    className="w-full px-3 py-2.5 rounded-xl bg-slate-950/80 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all"
                  >
                    <option value="low">Low Priority</option>
                    <option value="normal">Normal Priority</option>
                    <option value="high">High Priority</option>
                    <option value="urgent">Urgent</option>
                  </select>
                </div>
              </div>

              {/* Reason */}
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center space-x-1">
                  <FileText className="w-3.5 h-3.5 text-sky-400" />
                  <span>Callback Reason</span>
                </label>
                <textarea
                  rows={3}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="e.g. Discuss custom enterprise deployment options"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950/80 border border-slate-700 text-white text-xs placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all resize-none"
                />
              </div>

              {/* Submit Buttons */}
              <div className="pt-3 border-t border-slate-800 flex items-center justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 transition-all"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className={`flex items-center space-x-2 px-5 py-2.5 rounded-xl text-xs font-bold text-white transition-all shadow-lg ${
                    isSubmitting
                      ? 'bg-slate-800 border border-slate-700 text-slate-500 cursor-not-allowed'
                      : 'bg-gradient-to-r from-sky-500 to-emerald-500 hover:from-sky-400 hover:to-emerald-400 active:scale-[0.98]'
                  }`}
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin text-white" />
                      <span>Saving Callback...</span>
                    </>
                  ) : (
                    <>
                      <Calendar className="w-4 h-4" />
                      <span>{editingCallback ? 'Confirm Reschedule' : 'Confirm Schedule'}</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
