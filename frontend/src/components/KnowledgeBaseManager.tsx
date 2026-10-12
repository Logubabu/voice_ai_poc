import React, { useEffect, useState } from 'react';
import {
  BookOpen,
  Plus,
  Upload,
  Search,
  Trash2,
  RefreshCw,
  FileText,
  CheckCircle2,
  AlertCircle,
  Clock,
  Layers,
  Sparkles,
} from 'lucide-react';
import {
  kbApiService,
  type KnowledgeBase,
  type KBDocument,
  type SearchTestResponse,
} from '../services/kb';

export const KnowledgeBaseManager: React.FC = () => {
  const [tenantId] = useState<string>('default_tenant');
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [selectedKbId, setSelectedKbId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<KBDocument[]>([]);
  
  // UI States
  const [newKbName, setNewKbName] = useState<string>('');
  const [newKbDesc, setNewKbDesc] = useState<string>('');
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Search Workbench state
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [searching, setSearching] = useState<boolean>(false);
  const [searchResult, setSearchResult] = useState<SearchTestResponse | null>(null);

  useEffect(() => {
    loadKnowledgeBases();
  }, []);

  useEffect(() => {
    if (selectedKbId) {
      loadDocuments(selectedKbId);
    } else {
      setDocuments([]);
    }
  }, [selectedKbId]);

  const loadKnowledgeBases = async () => {
    try {
      const data = await kbApiService.listKnowledgeBases(tenantId);
      setKbs(data);
      if (data.length > 0 && !selectedKbId) {
        setSelectedKbId(data[0].id);
      }
    } catch (err) {
      console.error('Error loading Knowledge Bases:', err);
    }
  };

  const loadDocuments = async (kbId: string) => {
    try {
      const docs = await kbApiService.listDocuments(kbId, tenantId);
      setDocuments(docs);
    } catch (err) {
      console.error('Error loading documents:', err);
    }
  };

  const handleCreateKb = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKbName.trim()) return;

    try {
      const created = await kbApiService.createKnowledgeBase(newKbName.trim(), newKbDesc.trim(), tenantId);
      setKbs((prev) => [created, ...prev]);
      setSelectedKbId(created.id);
      setNewKbName('');
      setNewKbDesc('');
      setShowCreateModal(false);
    } catch (err: any) {
      alert(err.message || 'Failed to create Knowledge Base');
    }
  };

  const handleDeleteKb = async (kbId: string) => {
    if (!confirm('Are you sure you want to delete this Knowledge Base and all its documents?')) return;
    try {
      await kbApiService.deleteKnowledgeBase(kbId, tenantId);
      setKbs((prev) => prev.filter((k) => k.id !== kbId));
      if (selectedKbId === kbId) {
        setSelectedKbId(null);
      }
    } catch (err: any) {
      alert(err.message || 'Failed to delete Knowledge Base');
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0 || !selectedKbId) return;

    setUploading(true);
    setUploadError(null);

    try {
      const file = files[0];
      await kbApiService.uploadDocument(selectedKbId, file, tenantId);
      await loadDocuments(selectedKbId);
      await loadKnowledgeBases();
    } catch (err: any) {
      setUploadError(err.message || 'Failed to upload document');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const handleDeleteDoc = async (docId: string) => {
    if (!selectedKbId) return;
    try {
      await kbApiService.deleteDocument(selectedKbId, docId, tenantId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
      await loadKnowledgeBases();
    } catch (err: any) {
      alert(err.message || 'Failed to delete document');
    }
  };

  const handleReindexDoc = async (docId: string) => {
    if (!selectedKbId) return;
    try {
      await kbApiService.reindexDocument(selectedKbId, docId, tenantId);
      await loadDocuments(selectedKbId);
    } catch (err: any) {
      alert(err.message || 'Failed to reindex document');
    }
  };

  const handleSearchTest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedKbId || !searchQuery.trim()) return;

    setSearching(true);
    try {
      const res = await kbApiService.searchTest(selectedKbId, searchQuery.trim(), 5, tenantId);
      setSearchResult(res);
    } catch (err: any) {
      alert(err.message || 'Search test failed');
    } finally {
      setSearching(false);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'indexed':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-950 text-emerald-300 border border-emerald-800">
            <CheckCircle2 className="w-3 h-3 mr-1 text-emerald-400" /> Indexed
          </span>
        );
      case 'processing':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-950 text-amber-300 border border-amber-800 animate-pulse">
            <Clock className="w-3 h-3 mr-1 text-amber-400" /> Processing
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-rose-950 text-rose-300 border border-rose-800">
            <AlertCircle className="w-3 h-3 mr-1 text-rose-400" /> Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-slate-800 text-slate-300">
            {status}
          </span>
        );
    }
  };

  const selectedKb = kbs.find((k) => k.id === selectedKbId);

  return (
    <div className="space-y-6 text-slate-200">
      {/* Top Header & Selector */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-slate-900/90 p-4 rounded-2xl border border-slate-800">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-emerald-500/10 rounded-xl border border-emerald-500/20 text-emerald-400">
            <BookOpen className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Knowledge Bases (RAG)</h2>
            <p className="text-xs text-slate-400">Multi-tenant document vector index & search testing workbench</p>
          </div>
        </div>

        <div className="flex items-center space-x-2 w-full sm:w-auto">
          <select
            value={selectedKbId || ''}
            onChange={(e) => setSelectedKbId(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-white text-xs rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-500 flex-1 sm:w-64"
          >
            {kbs.length === 0 ? (
              <option value="">No Knowledge Bases found</option>
            ) : (
              kbs.map((kb) => (
                <option key={kb.id} value={kb.id}>
                  {kb.name} ({kb.document_count} docs, {kb.total_chunks} chunks)
                </option>
              ))
            )}
          </select>

          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center space-x-1 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold px-3 py-2 rounded-xl transition-all shadow-md"
          >
            <Plus className="w-4 h-4" />
            <span>New KB</span>
          </button>
        </div>
      </div>

      {/* Main Grid: Document Management & Search Workbench */}
      {selectedKb ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Document Management Column */}
          <div className="bg-slate-900/60 p-5 rounded-2xl border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-white flex items-center space-x-2">
                  <Layers className="w-4 h-4 text-emerald-400" />
                  <span>Documents ({documents.length})</span>
                </h3>
                <p className="text-xs text-slate-400">PDF, DOCX, TXT, MD, CSV, JSON, HTML</p>
              </div>

              <div className="flex items-center space-x-2">
                <label className="flex items-center space-x-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium px-3 py-1.5 rounded-lg border border-slate-700 cursor-pointer transition-all">
                  <Upload className="w-3.5 h-3.5 text-emerald-400" />
                  <span>{uploading ? 'Uploading...' : 'Upload File'}</span>
                  <input
                    type="file"
                    onChange={handleFileUpload}
                    disabled={uploading}
                    accept=".pdf,.docx,.doc,.txt,.md,.csv,.json,.html"
                    className="hidden"
                  />
                </label>
                <button
                  onClick={() => handleDeleteKb(selectedKb.id)}
                  title="Delete Knowledge Base"
                  className="p-1.5 text-slate-400 hover:text-rose-400 rounded-lg hover:bg-rose-500/10 transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            {uploadError && (
              <div className="bg-rose-950/80 border border-rose-800 text-rose-300 text-xs p-3 rounded-xl flex items-center justify-between">
                <span>{uploadError}</span>
                <button onClick={() => setUploadError(null)} className="text-rose-400 font-bold">
                  &times;
                </button>
              </div>
            )}

            {/* Document List */}
            <div className="space-y-2.5 max-h-96 overflow-y-auto pr-1 scrollbar-thin">
              {documents.length === 0 ? (
                <div className="text-center py-8 border border-dashed border-slate-800 rounded-xl">
                  <FileText className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                  <p className="text-xs text-slate-400">No documents uploaded to this Knowledge Base yet.</p>
                </div>
              ) : (
                documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="p-3 bg-slate-800/60 rounded-xl border border-slate-800 flex items-center justify-between hover:border-slate-700 transition-colors"
                  >
                    <div className="min-w-0 flex-1 pr-3">
                      <div className="flex items-center space-x-2">
                        <FileText className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                        <span className="text-xs font-semibold text-white truncate" title={doc.original_filename}>
                          {doc.original_filename}
                        </span>
                      </div>
                      <div className="flex items-center space-x-3 text-[11px] text-slate-400 mt-1">
                        <span>{formatBytes(doc.size_bytes)}</span>
                        <span>&bull;</span>
                        <span>{doc.chunk_count} Chunks</span>
                        <span>&bull;</span>
                        {getStatusBadge(doc.status)}
                      </div>
                    </div>

                    <div className="flex items-center space-x-1">
                      <button
                        onClick={() => handleReindexDoc(doc.id)}
                        title="Reindex Document"
                        className="p-1.5 text-slate-400 hover:text-emerald-400 rounded-lg hover:bg-slate-700/50 transition-colors"
                      >
                        <RefreshCw className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => handleDeleteDoc(doc.id)}
                        title="Delete Document"
                        className="p-1.5 text-slate-400 hover:text-rose-400 rounded-lg hover:bg-rose-500/10 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Search Workbench Column */}
          <div className="bg-slate-900/60 p-5 rounded-2xl border border-slate-800 space-y-4">
            <div>
              <h3 className="text-sm font-semibold text-white flex items-center space-x-2">
                <Sparkles className="w-4 h-4 text-emerald-400" />
                <span>RAG Quality Search Tester</span>
              </h3>
              <p className="text-xs text-slate-400">Test vector retrieval and confidence scoring without making calls</p>
            </div>

            <form onSubmit={handleSearchTest} className="flex gap-2">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Ask a question (e.g. What is the refund policy?)"
                className="flex-1 bg-slate-800 border border-slate-700 text-white text-xs rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
              <button
                type="submit"
                disabled={searching || !searchQuery.trim()}
                className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition-all flex items-center space-x-1.5 shadow-md"
              >
                <Search className="w-3.5 h-3.5" />
                <span>{searching ? 'Searching...' : 'Search'}</span>
              </button>
            </form>

            {/* Results Output */}
            {searchResult && (
              <div className="space-y-3 pt-2">
                <div className="flex items-center justify-between text-xs border-b border-slate-800 pb-2">
                  <div className="flex items-center space-x-2">
                    <span className="text-slate-400">🎯 Match Accuracy:</span>
                    <span className={`font-bold ${searchResult.confidence >= 0.75 ? 'text-emerald-400' : searchResult.confidence >= 0.45 ? 'text-amber-400' : 'text-rose-400'}`}>
                      {(searchResult.confidence * 100).toFixed(1)} pts ({(searchResult.confidence * 100).toFixed(1)}%)
                    </span>
                  </div>
                  <div className="text-slate-400">
                    Latency: <span className="font-semibold text-slate-200">{searchResult.latency_ms} ms</span>
                  </div>
                </div>

                {!searchResult.found ? (
                  <div className="bg-amber-950/40 border border-amber-900/50 p-3 rounded-xl text-amber-300 text-xs">
                    {searchResult.message || 'No sufficiently relevant knowledge chunks found.'}
                  </div>
                ) : (
                  <div className="space-y-2 max-h-80 overflow-y-auto pr-1 scrollbar-thin">
                    {searchResult.results.map((res, idx) => (
                      <div key={idx} className="p-3 bg-slate-800/80 rounded-xl border border-slate-700 space-y-1.5">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="font-bold text-emerald-300">{res.document_name}</span>
                          <div className="flex items-center space-x-2 text-slate-400">
                            {res.section && <span>Section: {res.section}</span>}
                            <span>Page {res.page || 1}</span>
                            <span className="bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-1.5 py-0.5 rounded font-mono font-bold">
                              {(res.score * 100).toFixed(1)} pts
                            </span>
                          </div>
                        </div>
                        <p className="text-xs text-slate-300 leading-relaxed bg-slate-900/60 p-2 rounded-lg font-mono">
                          {res.content}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="text-center py-12 bg-slate-900/40 rounded-2xl border border-slate-800">
          <BookOpen className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-white">No Knowledge Base Selected</h3>
          <p className="text-xs text-slate-400 mt-1 mb-4">Create a new Knowledge Base to start indexing company documents.</p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold px-4 py-2 rounded-xl transition-all shadow-md inline-flex items-center space-x-1.5"
          >
            <Plus className="w-4 h-4" />
            <span>Create First Knowledge Base</span>
          </button>
        </div>
      )}

      {/* Modal for Creating KB */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 max-w-md w-full shadow-2xl space-y-4">
            <h3 className="text-base font-bold text-white">Create Knowledge Base</h3>

            <form onSubmit={handleCreateKb} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Knowledge Base Name</label>
                <input
                  type="text"
                  required
                  value={newKbName}
                  onChange={(e) => setNewKbName(e.target.value)}
                  placeholder="e.g. Customer Support & Refund Policies"
                  className="w-full bg-slate-800 border border-slate-700 text-white text-xs rounded-xl p-2.5 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Description</label>
                <textarea
                  value={newKbDesc}
                  onChange={(e) => setNewKbDesc(e.target.value)}
                  placeholder="Optional description..."
                  rows={3}
                  className="w-full bg-slate-800 border border-slate-700 text-white text-xs rounded-xl p-2.5 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-xl"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
