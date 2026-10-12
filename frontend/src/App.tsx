import { useEffect, useState } from 'react';
import { CallStatus } from './components/CallStatus';
import { CallControls } from './components/CallControls';
import { Transcript } from './components/Transcript';
import { NoiseCancellationPanel } from './components/NoiseCancellationPanel';
import { TransportSelector, type VoiceMode } from './components/TransportSelector';
import { OutboundDialer } from './components/OutboundDialer';
import { KnowledgeBaseManager } from './components/KnowledgeBaseManager';
import { ScheduledCallbacksPanel } from './components/ScheduledCallbacksPanel';
import { voiceService, type CallState, type TranscriptItem } from './services/voice';
import { Radio, Mic, BookOpen, Calendar } from 'lucide-react';
import './styles/App.css';

export function App() {
  const [activeTab, setActiveTab] = useState<'voice' | 'kb' | 'callbacks'>('voice');
  const [callState, setCallState] = useState<CallState>('idle');
  const [voiceMode, setVoiceMode] = useState<VoiceMode>('webrtc');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [micActive, setMicActive] = useState<boolean>(false);
  const [transcript, setTranscript] = useState<TranscriptItem[]>([]);

  useEffect(() => {
    // Subscribe to voice call state changes
    voiceService.onStateUpdate = (newState: CallState) => {
      setCallState(newState);
      if (newState === 'listening' || newState === 'processing' || newState === 'speaking' || newState === 'connected') {
        setMicActive(true);
      } else if (newState === 'idle' || newState === 'disconnected' || newState === 'error') {
        setMicActive(false);
      }
    };

    // Subscribe to real-time conversation transcripts
    voiceService.onTranscriptUpdate = (item: TranscriptItem) => {
      setTranscript((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.sender === item.sender && item.sender === 'ai') {
          return [...prev.slice(0, -1), item];
        }
        return [...prev, item];
      });
    };
  }, []);

  const handleStartCall = async () => {
    setErrorMessage(null);
    setTranscript([]);
    setCallState('connecting');

    try {
      const { sessionId } = await voiceService.startCall();
      console.log(`[APP] Call session started (${voiceMode}): ${sessionId}`);
    } catch (err: any) {
      console.error('[APP] Start call error:', err);
      setCallState('error');
      setMicActive(false);
      setErrorMessage(err.message || 'Unable to connect to the Voice AI service. Please check backend logs.');
    }
  };

  const handleEndCall = async () => {
    setCallState('ending');
    try {
      await voiceService.endCall();
    } catch (err) {
      console.error('[APP] End call error:', err);
    } finally {
      setMicActive(false);
    }
  };

  return (
    <div className="w-full max-w-4xl px-4 py-8 mx-auto">
      <header className="text-center mb-6">
        <div className="inline-flex items-center space-x-3 bg-slate-900/80 px-4 py-2 rounded-full border border-slate-800 mb-3 shadow-md">
          <Radio className="w-5 h-5 text-emerald-400 animate-pulse" />
          <span className="text-xs font-semibold tracking-wider text-slate-300 uppercase">
            Production Voice AI & Knowledge Base RAG
          </span>
        </div>
        <h1 className="text-4xl font-extrabold text-white tracking-tight sm:text-5xl">
          SharyX Voice AI Platform
        </h1>
        <p className="text-sm text-slate-400 mt-2">
          Real-Time Voice Assistant, Multi-Tenant Knowledge Base (RAG) & Scheduled Callbacks
        </p>

        {/* Tab Navigation */}
        <div className="flex justify-center mt-6">
          <div className="inline-flex p-1 bg-slate-900/90 rounded-2xl border border-slate-800 shadow-inner">
            <button
              onClick={() => setActiveTab('voice')}
              className={`flex items-center space-x-2 px-5 py-2.5 rounded-xl text-xs font-bold transition-all ${
                activeTab === 'voice'
                  ? 'bg-emerald-600 text-white shadow-lg'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Mic className="w-4 h-4" />
              <span>Voice AI Call</span>
            </button>
            <button
              onClick={() => setActiveTab('kb')}
              className={`flex items-center space-x-2 px-5 py-2.5 rounded-xl text-xs font-bold transition-all ${
                activeTab === 'kb'
                  ? 'bg-emerald-600 text-white shadow-lg'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <BookOpen className="w-4 h-4" />
              <span>Knowledge Base (RAG)</span>
            </button>
            <button
              onClick={() => setActiveTab('callbacks')}
              className={`flex items-center space-x-2 px-5 py-2.5 rounded-xl text-xs font-bold transition-all ${
                activeTab === 'callbacks'
                  ? 'bg-emerald-600 text-white shadow-lg'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Calendar className="w-4 h-4" />
              <span>Scheduled Callbacks</span>
            </button>
          </div>
        </div>
      </header>

      <main className="glass-card rounded-3xl p-6 sm:p-8 relative overflow-hidden">
        {activeTab === 'voice' ? (
          <>
            <CallStatus state={callState} errorMessage={errorMessage} micActive={micActive} />

            <TransportSelector mode={voiceMode} onModeChange={setVoiceMode} />

            {voiceMode === 'freeswitch' ? (
              <OutboundDialer />
            ) : (
              <div className="mt-6">
                <CallControls
                  state={callState}
                  onStartCall={handleStartCall}
                  onEndCall={handleEndCall}
                />
              </div>
            )}

            <Transcript items={transcript} />

            <NoiseCancellationPanel />
          </>
        ) : activeTab === 'kb' ? (
          <KnowledgeBaseManager />
        ) : (
          <ScheduledCallbacksPanel />
        )}
      </main>

      <footer className="text-center text-xs text-slate-500 mt-6">
        Sharyx Voice AI POC &bull; Built with Pipecat, Qdrant Vector DB, FreeSWITCH ESL, WebRTC & React + Vite
      </footer>
    </div>
  );
}

export default App;
