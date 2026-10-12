import React, { useState } from 'react';
import { PhoneCall, PhoneForwarded, CheckCircle2, AlertCircle, Loader2, Signal } from 'lucide-react';
import { voiceService } from '../services/voice';

export const OutboundDialer: React.FC = () => {
  const [phoneNumber, setPhoneNumber] = useState('');
  const [gateway, setGateway] = useState('default');
  const [loading, setLoading] = useState(false);
  const [callResult, setCallResult] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleMakeCall = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!phoneNumber.trim()) {
      setError('Please enter a valid phone number');
      return;
    }

    setError(null);
    setLoading(true);
    setCallResult(null);

    try {
      const res = await voiceService.makeOutboundCall(phoneNumber.trim(), gateway);
      console.log('[OUTBOUND-DIALER] Outbound call response:', res);
      setCallResult(res);
    } catch (err: any) {
      console.error('[OUTBOUND-DIALER] Call initiation error:', err);
      setError(err.message || 'Failed to initiate outbound call to phone number');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-6 p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2.5">
          <div className="p-2 rounded-xl bg-sky-500/10 border border-sky-500/30 text-sky-400">
            <PhoneCall className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-100">Outbound AI Phone Dialer</h3>
            <p className="text-xs text-slate-400">Dial any phone number to connect it to the live Voice AI agent</p>
          </div>
        </div>
        <span className="flex items-center space-x-1.5 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2.5 py-1 rounded-full">
          <Signal className="w-3.5 h-3.5 animate-pulse" />
          <span className="font-semibold">FreeSWITCH Gateway Active</span>
        </span>
      </div>

      <form onSubmit={handleMakeCall} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="sm:col-span-2">
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Target Phone Number
            </label>
            <input
              type="tel"
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value)}
              placeholder="e.g. +919876543210 or 9876543210"
              className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950/80 border border-slate-700 text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              SIP Gateway / Trunk
            </label>
            <select
              value={gateway}
              onChange={(e) => setGateway(e.target.value)}
              className="w-full px-3 py-2.5 rounded-xl bg-slate-950/80 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all"
            >
              <option value="default">Default Gateway</option>
              <option value="twilio">Twilio SIP Trunk</option>
              <option value="telnyx">Telnyx Gateway</option>
              <option value="signalwire">SignalWire PSTN</option>
              <option value="local_sip">Local SIP Server</option>
            </select>
          </div>
        </div>

        {error && (
          <div className="flex items-center space-x-2 text-xs text-rose-400 bg-rose-500/10 border border-rose-500/30 p-3 rounded-xl">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <button
          type="submit"
          disabled={loading || !phoneNumber.trim()}
          className={`w-full flex items-center justify-center space-x-2 py-3 px-4 rounded-xl font-semibold text-sm transition-all shadow-lg ${
            loading || !phoneNumber.trim()
              ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
              : 'bg-gradient-to-r from-sky-500 to-emerald-500 hover:from-sky-400 hover:to-emerald-400 text-white shadow-sky-500/20 active:scale-[0.99]'
          }`}
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin text-white" />
              <span>Dialing Outbound Call via FreeSWITCH...</span>
            </>
          ) : (
            <>
              <PhoneForwarded className="w-4 h-4" />
              <span>Make AI Phone Call to {phoneNumber.trim() || 'Number'}</span>
            </>
          )}
        </button>
      </form>

      {callResult && (
        <div className="mt-4 p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 space-y-2 animate-fadeIn">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2 text-emerald-400 font-semibold text-xs">
              <CheckCircle2 className="w-4 h-4" />
              <span>Call Successfully Originated & Answered</span>
            </div>
            <span className="text-[10px] bg-slate-900/90 text-slate-300 px-2 py-0.5 rounded border border-slate-700">
              UUID: {callResult.freeswitch_result?.uuid || 'channel-outbound-active'}
            </span>
          </div>
          <div className="text-xs text-slate-300 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800 font-mono">
            {callResult.freeswitch_result?.body || 'Outbound call bridged to AI Agent pipeline.'}
          </div>
          <p className="text-[11px] text-emerald-300/80">
            The Voice AI agent is active on the call and responding to caller queries in real-time.
          </p>
        </div>
      )}
    </div>
  );
};
