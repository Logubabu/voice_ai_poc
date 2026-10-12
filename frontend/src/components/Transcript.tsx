import React from 'react';
import type { TranscriptItem } from '../services/voice';
import { User, Bot, Wrench, Globe, ExternalLink, BookOpen } from 'lucide-react';

interface TranscriptProps {
  items: TranscriptItem[];
}

export const Transcript: React.FC<TranscriptProps> = ({ items }) => {
  return (
    <div className="transcript-panel glass-panel p-6 rounded-2xl flex-1 overflow-y-auto max-h-[380px] min-h-[220px]">
      <div className="text-xs uppercase tracking-wider text-gray-400 font-semibold mb-4">
        Conversation Transcript & Live Tool Calls
      </div>

      {items.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-40 text-gray-500 text-sm">
          <p>Click "Start Call" and begin speaking to start conversation.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {items.map((item) => (
            <div
              key={item.id}
              className={`flex space-x-3 ${item.sender === 'user' ? 'justify-start' : 'justify-start'}`}
            >
              <div
                className={`p-2 rounded-xl shrink-0 ${
                  item.sender === 'user'
                    ? 'bg-blue-600/30 text-blue-400 border border-blue-500/30'
                    : item.sender === 'tool'
                    ? item.toolName === 'web_search'
                      ? 'bg-cyan-600/30 text-cyan-300 border border-cyan-500/30'
                      : 'bg-amber-600/30 text-amber-400 border border-amber-500/30'
                    : 'bg-purple-600/30 text-purple-400 border border-purple-500/30'
                }`}
              >
                {item.sender === 'user' ? (
                  <User className="w-5 h-5" />
                ) : item.sender === 'tool' ? (
                  item.toolName === 'web_search' ? (
                    <Globe className="w-5 h-5 text-cyan-300" />
                  ) : item.toolName === 'knowledge_search' ? (
                    <BookOpen className="w-5 h-5 text-amber-300" />
                  ) : (
                    <Wrench className="w-5 h-5" />
                  )
                ) : (
                  <Bot className="w-5 h-5" />
                )}
              </div>
              <div
                className={`p-4 rounded-2xl border text-sm max-w-xl ${
                  item.sender === 'tool'
                    ? item.toolName === 'web_search'
                      ? 'bg-cyan-950/30 border-cyan-500/30 text-cyan-200'
                      : 'bg-amber-950/30 border-amber-500/30 text-amber-200'
                    : 'bg-gray-900/70 border-gray-800 text-gray-200'
                }`}
              >
                <div className="flex justify-between items-center mb-1">
                  <span className="font-semibold text-xs text-gray-400">
                    {item.sender === 'user'
                      ? 'User'
                      : item.sender === 'tool'
                      ? item.toolName === 'web_search'
                        ? '🌐 Live Web Search'
                        : item.toolName === 'knowledge_search'
                        ? '📚 Knowledge Base Search'
                        : 'Tool Call Executed'
                      : 'AI Assistant'}
                  </span>
                  <span className="text-[10px] text-gray-500">{item.timestamp}</span>
                </div>
                {item.sender === 'tool' ? (
                  item.toolName === 'knowledge_search' ? (
                    <div className="space-y-1.5 font-mono text-xs">
                      <div className="font-bold text-amber-300 flex items-center justify-between">
                        <span>📚 knowledge_search</span>
                        {item.toolResult && (
                          <span
                            className={`px-2 py-0.5 rounded-md text-[11px] font-bold ${
                              (item.toolResult.confidence || 0) >= 0.75
                                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                                : (item.toolResult.confidence || 0) >= 0.45
                                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                                : 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                            }`}
                          >
                            🎯 Accuracy: {((item.toolResult.confidence || 0) * 100).toFixed(1)} pts
                          </span>
                        )}
                      </div>
                      <div className="text-amber-400/90">Query: "{item.toolArgs?.query}"</div>
                      {item.toolResult?.results && item.toolResult.results.length > 0 && (
                        <div className="mt-2 text-[11px] bg-black/50 p-2.5 rounded-xl border border-amber-500/20 space-y-1.5 font-sans">
                          <div className="font-semibold text-amber-300 text-[11px] flex items-center justify-between">
                            <span>Retrieved Knowledge Chunks ({item.toolResult.results.length}):</span>
                          </div>
                          <div className="space-y-1">
                            {item.toolResult.results.map((res: any, rIdx: number) => (
                              <div key={rIdx} className="flex items-center justify-between text-[11px] bg-amber-950/40 px-2.5 py-1 rounded-lg border border-amber-500/20">
                                <span className="text-amber-200 truncate font-semibold" title={res.document_name}>
                                  📄 {res.document_name || 'Document'}
                                </span>
                                <span className="text-emerald-400 font-mono font-bold shrink-0 ml-2">
                                  {((res.score || 0) * 100).toFixed(1)} pts
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-1 font-mono text-xs">
                      <div className="font-bold text-cyan-300 flex items-center space-x-1">
                        {item.toolName === 'web_search' ? <span>🌐 web_search</span> : <span>⚙️ {item.toolName}</span>}
                      </div>
                      <div className="text-cyan-400/80">Query: "{item.toolArgs?.query}"</div>
                      {item.sources && item.sources.length > 0 && (
                        <div className="mt-2 text-[11px] bg-black/40 p-2 rounded border border-cyan-500/20 space-y-1">
                          <div className="font-semibold text-cyan-300">Sources / Citations:</div>
                          <div className="space-y-1">
                            {item.sources.map((src, idx) => (
                              <a
                                key={idx}
                                href={src.url}
                                target="_blank"
                                rel="noreferrer"
                                className="flex items-center space-x-1 text-cyan-400 hover:underline truncate"
                              >
                                <ExternalLink className="w-3 h-3 shrink-0" />
                                <span className="truncate">{src.title || src.url}</span>
                              </a>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )
                ) : (
                  <p className="leading-relaxed">{item.text}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
