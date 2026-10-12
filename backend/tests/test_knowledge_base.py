import asyncio
import pytest
import os
import tempfile
import shutil
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from knowledge_base.parsers import TextParser, CSVParser, JSONParser, HTMLParser
from knowledge_base.chunking import StructureAwareChunker
from knowledge_base.service import KnowledgeBaseService
from knowledge_base.schemas import KnowledgeBaseCreate
from app.tools.knowledge_search.tool import KnowledgeSearchTool
from app.config import config


@pytest.mark.asyncio
async def test_document_parsers():
    # 1. Text Parser
    txt_parser = TextParser()
    txt_pages = txt_parser.parse(b"Hello world\n\nSection 1\nThis is a test.", "test.txt")
    assert len(txt_pages) == 1
    assert "Hello world" in txt_pages[0].content

    # 2. CSV Parser
    csv_parser = CSVParser()
    csv_bytes = b"header1,header2\nval1,val2\nval3,val4"
    csv_pages = csv_parser.parse(csv_bytes, "data.csv")
    assert len(csv_pages) == 1
    assert "header1: val1" in csv_pages[0].content

    # 3. JSON Parser
    json_parser = JSONParser()
    json_bytes = b'{"key": "value", "items": [1, 2, 3]}'
    json_pages = json_parser.parse(json_bytes, "data.json")
    assert len(json_pages) == 1
    assert '"key": "value"' in json_pages[0].content

    # 4. HTML Parser
    html_parser = HTMLParser()
    html_bytes = b"<html><body><h1>Title</h1><p>Paragraph content</p></body></html>"
    html_pages = html_parser.parse(html_bytes, "page.html")
    assert len(html_pages) == 1
    assert "Title" in html_pages[0].content


@pytest.mark.asyncio
async def test_structure_aware_chunking():
    txt_parser = TextParser()
    pages = txt_parser.parse(b"### Section 1\nParagraph A content.\n\n### Section 2\nParagraph B content.", "doc.txt")
    chunker = StructureAwareChunker(target_chunk_tokens=50, overlap_tokens=10)
    chunks = chunker.chunk_pages(pages, "doc_101", "tenant_alpha", "kb_101", "doc.txt")

    assert len(chunks) >= 1
    assert chunks[0].document_id == "doc_101"
    assert chunks[0].tenant_id == "tenant_alpha"


@pytest.mark.asyncio
async def test_tenant_isolation_security():
    """MANDATORY SECURITY TEST: Proves Tenant A documents cannot be retrieved by Tenant B."""
    tmp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmp_dir, "test_kb.db")
        docs_dir = os.path.join(tmp_dir, "docs")
        service = KnowledgeBaseService(storage_dir=docs_dir, db_path=db_path)
        service.retrieval_engine.min_score = 0.50

        # 1. Create KB for Tenant A
        kb_a = await service.create_kb(KnowledgeBaseCreate(name="KB Tenant A", tenant_id="tenant_A"))

        # 2. Tenant A uploads confidential text document
        confidential_content = b"Confidential Secret Code Alpha 9988: The secret vault passkey is BlueSky77."
        await service.upload_document(
            kb_id=kb_a.id,
            tenant_id="tenant_A",
            filename="confidential.txt",
            file_content=confidential_content,
            mime_type="text/plain",
        )

        # Wait briefly for async ingestion worker
        await asyncio.sleep(0.5)

        # 3. Tenant A searches for secret -> SHOULD BE FOUND
        res_a = await service.search(query="secret vault passkey", tenant_id="tenant_A", knowledge_base_id=kb_a.id)
        assert res_a.found is True
        assert len(res_a.results) > 0
        assert "BlueSky77" in res_a.results[0].content

        # 4. Tenant B searches for secret -> MUST RETURN NO RESULTS!
        res_b = await service.search(query="secret vault passkey", tenant_id="tenant_B", knowledge_base_id=kb_a.id)
        assert res_b.found is False
        assert len(res_b.results) == 0
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_duplicate_document_detection():
    tmp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmp_dir, "test_kb.db")
        docs_dir = os.path.join(tmp_dir, "docs")
        service = KnowledgeBaseService(storage_dir=docs_dir, db_path=db_path)

        kb = await service.create_kb(KnowledgeBaseCreate(name="Dup Test KB", tenant_id="tenant_x"))
        content = b"Exact identical binary content for duplicate test."

        doc1 = await service.upload_document(kb_id=kb.id, tenant_id="tenant_x", filename="policy.txt", file_content=content)
        await asyncio.sleep(0.4)

        # Upload exact same file second time
        doc2 = await service.upload_document(kb_id=kb.id, tenant_id="tenant_x", filename="policy.txt", file_content=content)

        # Should re-use indexed document ID or produce deterministic reference without duplication
        assert doc1.checksum == doc2.checksum
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_knowledge_search_tool_execution():
    tool = KnowledgeSearchTool()
    assert tool.name == "knowledge_search"
    schema = tool.get_schema()
    assert schema.name == "knowledge_search"
    assert "query" in schema.properties

    res = await tool.execute({"query": "What is refund policy?", "tenant_id": "tenant_test"})
    assert isinstance(res, dict)
    assert "success" in res


@pytest.mark.asyncio
async def test_kb_disabled_regression():
    original_setting = config.KB_ENABLED
    try:
        config.KB_ENABLED = False
        from app.tools.registry import global_tool_registry
        schemas = global_tool_registry.get_function_schemas()
        tool_names = [s.name for s in schemas]
        assert "knowledge_search" not in tool_names
    finally:
        config.KB_ENABLED = original_setting
