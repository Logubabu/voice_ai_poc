import React from 'react';
import { Phone, Globe, Server, CheckCircle2 } from 'lucide-react';

export type VoiceMode = 'webrtc' | 'freeswitch';

interface TransportSelectorProps {
  mode: VoiceMode;
  onModeChange: (mode: VoiceMode) => void;
}

export const TransportSelector: React.FC<TransportSelectorProps> = ({ mode, onModeChange }) => {
  return (
    <div className="mt-6 p-4 rounded-2xl bg-slate-900/60 border border-slate-800">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <Server className="w-4 h-4 text-emerald-400" />
          <h3 className="text-sm font-semibold text-slate-200">Voice Mode Transport</h3>
        </div>
        <span className="text-xs text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded-full border border-slate-700">
          {mode === 'webrtc' ? 'Mode A: WebCall' : 'Mode B: Phone Call'}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <button
          type="button"
          onClick={() => onModeChange('webrtc')}
          className={`flex items-center justify-between p-3 rounded-xl text-left border transition-all ${
            mode === 'webrtc'
              ? 'bg-emerald-500/10 border-emerald-500/50 text-white shadow-sm'
              : 'bg-slate-800/40 border-slate-700/50 text-slate-400 hover:text-slate-200 hover:bg-slate-800/80'
          }`}
        >
          <div className="flex items-center space-x-2.5">
            <Globe className={`w-4 h-4 ${mode === 'webrtc' ? 'text-emerald-400' : 'text-slate-400'}`} />
            <div>
              <div className="text-xs font-semibold">WebCall (WebRTC)</div>
              <div className="text-[10px] text-slate-400">Direct Browser Audio</div>
            </div>
          </div>
          {mode === 'webrtc' && <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />}
        </button>

        <button
          type="button"
          onClick={() => onModeChange('freeswitch')}
          className={`flex items-center justify-between p-3 rounded-xl text-left border transition-all ${
            mode === 'freeswitch'
              ? 'bg-sky-500/10 border-sky-500/50 text-white shadow-sm'
              : 'bg-slate-800/40 border-slate-700/50 text-slate-400 hover:text-slate-200 hover:bg-slate-800/80'
          }`}
        >
          <div className="flex items-center space-x-2.5">
            <Phone className={`w-4 h-4 ${mode === 'freeswitch' ? 'text-sky-400' : 'text-slate-400'}`} />
            <div>
              <div className="text-xs font-semibold">Phone (FreeSWITCH)</div>
              <div className="text-[10px] text-slate-400">SIP / PSTN WebSocket Stream</div>
            </div>
          </div>
          {mode === 'freeswitch' && <CheckCircle2 className="w-4 h-4 text-sky-400 shrink-0" />}
        </button>
      </div>
    </div>
  );
};
