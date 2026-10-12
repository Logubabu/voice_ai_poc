import hashlib
import re
from typing import List

from knowledge_base.parsers import ParsedPage
from knowledge_base.models import DocumentChunkModel
from app.utils.logging import logger


def estimate_token_count(text: str) -> int:
    """Estimates token count for a text string (approx 4 chars per token)."""
    return max(1, len(text) // 4)


class StructureAwareChunker:
    """Structure-aware document chunker preserving headers, paragraphs, lists, and page boundaries."""

    def __init__(self, target_chunk_tokens: int = 600, overlap_tokens: int = 80):
        self.target_chunk_tokens = target_chunk_tokens
        self.overlap_tokens = overlap_tokens
        self.target_chunk_chars = target_chunk_tokens * 4
        self.overlap_chars = overlap_tokens * 4

    def chunk_pages(
        self,
        pages: List[ParsedPage],
        document_id: str,
        tenant_id: str,
        knowledge_base_id: str,
        source_name: str,
        source_type: str = "file",
        document_version: int = 1,
    ) -> List[DocumentChunkModel]:
        chunks: List[DocumentChunkModel] = []
        chunk_index = 0

        current_section = "General"
        header_pattern = re.compile(r"^(#{1,6}\s+|[A-Z0-9\s]{3,40}:|[0-9]+\.\s+[A-Z])", re.MULTILINE)

        for page in pages:
            text = page.content.strip()
            if not text:
                continue

            # Split text by structural block separators (double linebreaks, headings, paragraph breaks)
            paragraphs = re.split(r"\n\s*\n", text)
            current_buffer = []
            current_length = 0

            for para in paragraphs:
                para_clean = para.strip()
                if not para_clean:
                    continue

                # Detect potential section headers
                lines = para_clean.splitlines()
                if lines and (header_pattern.match(lines[0]) or (len(lines[0]) < 60 and lines[0].endswith(":"))):
                    current_section = lines[0].strip("#: ").strip()

                para_len = len(para_clean)

                if current_length + para_len > self.target_chunk_chars and current_buffer:
                    # Flush current buffer to chunk
                    chunk_text = "\n\n".join(current_buffer)
                    header_prefix = f"[Document: {source_name} | Section: {current_section} | Page: {page.page_number}]\n"
                    full_content = f"{header_prefix}{chunk_text}" if not chunk_text.startswith("[Document:") else chunk_text

                    token_count = estimate_token_count(full_content)
                    content_hash = hashlib.sha256(full_content.encode("utf-8")).hexdigest()

                    metadata = {
                        "document_id": document_id,
                        "tenant_id": tenant_id,
                        "knowledge_base_id": knowledge_base_id,
                        "page_number": page.page_number,
                        "section": current_section,
                        "chunk_index": chunk_index,
                        "source_name": source_name,
                        "source_type": source_type,
                        "document_version": document_version,
                        "content_hash": content_hash,
                    }

                    chunk_model = DocumentChunkModel(
                        document_id=document_id,
                        tenant_id=tenant_id,
                        chunk_index=chunk_index,
                        content=full_content,
                        page_number=page.page_number,
                        section_title=current_section,
                        token_count=token_count,
                        content_hash=content_hash,
                        metadata=metadata,
                    )
                    chunks.append(chunk_model)
                    chunk_index += 1

                    # Keep overlap for smooth semantic context continuation
                    overlap_buffer = []
                    overlap_len = 0
                    for prev_para in reversed(current_buffer):
                        if overlap_len + len(prev_para) <= self.overlap_chars:
                            overlap_buffer.insert(0, prev_para)
                            overlap_len += len(prev_para)
                        else:
                            break
                    current_buffer = overlap_buffer
                    current_length = overlap_len

                current_buffer.append(para_clean)
                current_length += para_len

            # Flush remaining buffer for page
            if current_buffer:
                chunk_text = "\n\n".join(current_buffer)
                header_prefix = f"[Document: {source_name} | Section: {current_section} | Page: {page.page_number}]\n"
                full_content = f"{header_prefix}{chunk_text}" if not chunk_text.startswith("[Document:") else chunk_text

                token_count = estimate_token_count(full_content)
                content_hash = hashlib.sha256(full_content.encode("utf-8")).hexdigest()

                metadata = {
                    "document_id": document_id,
                    "tenant_id": tenant_id,
                    "knowledge_base_id": knowledge_base_id,
                    "page_number": page.page_number,
                    "section": current_section,
                    "chunk_index": chunk_index,
                    "source_name": source_name,
                    "source_type": source_type,
                    "document_version": document_version,
                    "content_hash": content_hash,
                }

                chunk_model = DocumentChunkModel(
                    document_id=document_id,
                    tenant_id=tenant_id,
                    chunk_index=chunk_index,
                    content=full_content,
                    page_number=page.page_number,
                    section_title=current_section,
                    token_count=token_count,
                    content_hash=content_hash,
                    metadata=metadata,
                )
                chunks.append(chunk_model)
                chunk_index += 1

        logger.info(f"[CHUNKER] Created {len(chunks)} structure-aware chunks for document '{document_id}' (source: {source_name})")
        return chunks
