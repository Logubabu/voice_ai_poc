import React from 'react';
import type { CallState } from '../services/voice';
import { Mic, MicOff, Volume2, Loader2, AlertCircle } from 'lucide-react';

interface CallStatusProps {
  state: CallState;
  errorMessage?: string | null;
  micActive: boolean;
}

export const CallStatus: React.FC<CallStatusProps> = ({ state, errorMessage, micActive }) => {
  const getStatusBadge = () => {
    switch (state) {
      case 'idle':
        return { text: 'Ready', color: 'bg-gray-500/20 text-gray-300 border-gray-500/30' };
      case 'connecting':
        return { text: 'Connecting...', color: 'bg-amber-500/20 text-amber-300 border-amber-500/30' };
      case 'connected':
        return { text: 'Connected', color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' };
      case 'listening':
        return { text: 'Listening...', color: 'bg-blue-500/20 text-blue-300 border-blue-500/30' };
      case 'processing':
        return { text: 'Thinking...', color: 'bg-purple-500/20 text-purple-300 border-purple-500/30' };
      case 'searching':
        return { text: '🌐 Searching the web...', color: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30 animate-pulse' };
      case 'speaking':
        return { text: 'AI Speaking...', color: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30' };
      case 'ending':
        return { text: 'Ending...', color: 'bg-amber-500/20 text-amber-300 border-amber-500/30' };
      case 'disconnected':
        return { text: 'Disconnected', color: 'bg-gray-500/20 text-gray-400 border-gray-500/30' };
      case 'error':
        return { text: 'Error', color: 'bg-rose-500/20 text-rose-400 border-rose-500/30' };
    }
  };

  const badge = getStatusBadge();

  return (
    <div className="status-container glass-panel p-6 rounded-2xl mb-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="relative">
            <span
              className={`status-indicator ${
                state === 'connected' || state === 'listening' || state === 'speaking'
                  ? 'status-indicator-active'
                  : ''
              }`}
            />
          </div>
          <div>
            <span className="text-xs uppercase tracking-wider text-gray-400">Connection Status</span>
            <div className="flex items-center space-x-2 mt-1">
              <span className={`px-3 py-1 text-sm font-medium rounded-full border ${badge.color}`}>
                {badge.text}
              </span>
              {state === 'connecting' && <Loader2 className="w-4 h-4 animate-spin text-amber-400" />}
              {state === 'speaking' && <Volume2 className="w-4 h-4 animate-pulse text-indigo-400" />}
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-3 bg-gray-900/60 px-4 py-2 rounded-xl border border-gray-800">
          {micActive ? (
            <Mic className="w-5 h-5 text-emerald-400 animate-pulse" />
          ) : (
            <MicOff className="w-5 h-5 text-gray-500" />
          )}
          <span className="text-sm font-medium text-gray-300">
            🎙 Microphone: {micActive ? 'Active' : 'Inactive'}
          </span>
        </div>
      </div>

      {state === 'error' && errorMessage && (
        <div className="mt-4 p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl flex items-center space-x-2 text-rose-300 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}
    </div>
  );
};
