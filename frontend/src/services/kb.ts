export interface KnowledgeBase {
  id: string;
  tenant_id: string;
  name: string;
  description?: string;
  status: string;
  document_count: number;
  total_chunks: number;
  created_at: string;
  updated_at: string;
}

export interface KBDocument {
  id: string;
  knowledge_base_id: string;
  tenant_id: string;
  filename: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  checksum: string;
  status: 'uploaded' | 'processing' | 'indexed' | 'failed' | 'deleted';
  version: number;
  language?: string;
  page_count?: number;
  chunk_count: number;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface SearchResultItem {
  document_id: string;
  document_name: string;
  chunk_id: string;
  content: string;
  score: number;
  page?: number;
  section?: string;
  metadata?: Record<string, any>;
}

export interface SearchTestResponse {
  success: boolean;
  found: boolean;
  query: string;
  confidence: number;
  latency_ms: number;
  results: SearchResultItem[];
  message?: string;
}

const API_BASE = (import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000').replace(/\/$/, '');

export const kbApiService = {
  async listKnowledgeBases(tenantId: string = 'default_tenant'): Promise<KnowledgeBase[]> {
    const res = await fetch(`${API_BASE}/api/v1/knowledge-bases?tenant_id=${encodeURIComponent(tenantId)}`);
    if (!res.ok) throw new Error('Failed to fetch Knowledge Bases');
    return res.json();
  },

  async createKnowledgeBase(name: string, description?: string, tenantId: string = 'default_tenant'): Promise<KnowledgeBase> {
    const res = await fetch(`${API_BASE}/api/v1/knowledge-bases`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description, tenant_id: tenantId }),
    });
    if (!res.ok) throw new Error('Failed to create Knowledge Base');
    return res.json();
  },

  async deleteKnowledgeBase(kbId: string, tenantId: string = 'default_tenant'): Promise<void> {
    const res = await fetch(`${API_BASE}/api/v1/knowledge-bases/${kbId}?tenant_id=${encodeURIComponent(tenantId)}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error('Failed to delete Knowledge Base');
  },

  async listDocuments(kbId: string, tenantId: string = 'default_tenant'): Promise<KBDocument[]> {
    const res = await fetch(`${API_BASE}/api/v1/knowledge-bases/${kbId}/documents?tenant_id=${encodeURIComponent(tenantId)}`);
    if (!res.ok) throw new Error('Failed to fetch documents');
    return res.json();
  },

  async uploadDocument(kbId: string, file: File, tenantId: string = 'default_tenant'): Promise<KBDocument> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('tenant_id', tenantId);

    const res = await fetch(`${API_BASE}/api/v1/knowledge-bases/${kbId}/documents`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(err.detail || 'Upload failed');
    }
    return res.json();
  },

  async deleteDocument(kbId: string, docId: string, tenantId: string = 'default_tenant'): Promise<void> {
    const res = await fetch(`${API_BASE}/api/v1/knowledge-bases/${kbId}/documents/${docId}?tenant_id=${encodeURIComponent(tenantId)}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error('Failed to delete document');
  },

  async reindexDocument(kbId: string, docId: string, tenantId: string = 'default_tenant'): Promise<KBDocument> {
    const res = await fetch(`${API_BASE}/api/v1/knowledge-bases/${kbId}/documents/${docId}/reindex?tenant_id=${encodeURIComponent(tenantId)}`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to reindex document');
    return res.json();
  },

  async searchTest(kbId: string, query: string, topK: number = 5, tenantId: string = 'default_tenant'): Promise<SearchTestResponse> {
    const res = await fetch(`${API_BASE}/api/v1/knowledge-bases/${kbId}/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Tenant-ID': tenantId,
      },
      body: JSON.stringify({ query, top_k: topK, tenant_id: tenantId }),
    });
    if (!res.ok) throw new Error('Knowledge Base search test failed');
    return res.json();
  },
};
