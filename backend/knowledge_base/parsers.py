import io
import json
import csv
import re
from abc import ABC, abstractmethod
from typing import List

from knowledge_base.exceptions import DocumentProcessingError
from app.utils.logging import logger


class ParsedPage:
    def __init__(self, page_number: int, content: str, section: str = ""):
        self.page_number = page_number
        self.content = content
        self.section = section


class DocumentParser(ABC):
    """Abstract base class for document format parsers."""

    @abstractmethod
    def parse(self, file_content: bytes, filename: str) -> List[ParsedPage]:
        """Parses document binary content and returns structured list of ParsedPage objects."""
        pass


class TextParser(DocumentParser):
    def parse(self, file_content: bytes, filename: str) -> List[ParsedPage]:
        try:
            text = file_content.decode("utf-8", errors="replace")
        except Exception as e:
            raise DocumentProcessingError(f"Failed to decode text file '{filename}': {e}")
        return [ParsedPage(page_number=1, content=text, section="Document Main")]


class MarkdownParser(DocumentParser):
    def parse(self, file_content: bytes, filename: str) -> List[ParsedPage]:
        try:
            text = file_content.decode("utf-8", errors="replace")
        except Exception as e:
            raise DocumentProcessingError(f"Failed to decode markdown file '{filename}': {e}")
        return [ParsedPage(page_number=1, content=text, section="Markdown Content")]


class PDFParser(DocumentParser):
    def parse(self, file_content: bytes, filename: str) -> List[ParsedPage]:
        pages = []
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_content))
            for idx, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                pages.append(ParsedPage(page_number=idx + 1, content=text, section=f"Page {idx + 1}"))
        except ImportError:
            # Fallback simple regex text extractor for PDF if pypdf is missing
            raw_text = file_content.decode("latin1", errors="replace")
            clean_text = " ".join(re.findall(r"[\x20-\x7E]{4,}", raw_text))
            pages.append(ParsedPage(page_number=1, content=clean_text, section="Extracted PDF Content"))
        except Exception as e:
            logger.warning(f"[PDF-PARSER] Primary pypdf parser notice for '{filename}': {e}. Using raw text extractor.")
            raw_text = file_content.decode("latin1", errors="replace")
            clean_text = " ".join(re.findall(r"[\x20-\x7E]{4,}", raw_text))
            pages.append(ParsedPage(page_number=1, content=clean_text, section="Extracted PDF Content"))

        if not pages:
            raise DocumentProcessingError(f"PDF document '{filename}' contained no extractable text.")
        return pages


class DocxParser(DocumentParser):
    def parse(self, file_content: bytes, filename: str) -> List[ParsedPage]:
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_content))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            full_text = "\n\n".join(paragraphs)
            return [ParsedPage(page_number=1, content=full_text, section="DOCX Content")]
        except ImportError:
            # Basic fallback for docx XML extraction
            raw = file_content.decode("latin1", errors="replace")
            texts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", raw)
            extracted = " ".join(texts)
            if not extracted.strip():
                extracted = file_content.decode("utf-8", errors="ignore")
            return [ParsedPage(page_number=1, content=extracted, section="DOCX Content")]
        except Exception as e:
            raise DocumentProcessingError(f"Failed to parse DOCX document '{filename}': {e}")


class CSVParser(DocumentParser):
    def parse(self, file_content: bytes, filename: str) -> List[ParsedPage]:
        try:
            text = file_content.decode("utf-8", errors="replace")
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)
            if not rows:
                return [ParsedPage(page_number=1, content="", section="CSV Header")]

            header = rows[0]
            formatted_lines = []
            for row in rows[1:]:
                row_str = ", ".join([f"{h}: {val}" for h, val in zip(header, row)])
                formatted_lines.append(row_str)

            content = "\n".join(formatted_lines)
            return [ParsedPage(page_number=1, content=content, section="CSV Records")]
        except Exception as e:
            raise DocumentProcessingError(f"Failed to parse CSV file '{filename}': {e}")


class JSONParser(DocumentParser):
    def parse(self, file_content: bytes, filename: str) -> List[ParsedPage]:
        try:
            data = json.loads(file_content.decode("utf-8", errors="replace"))
            formatted_str = json.dumps(data, indent=2)
            return [ParsedPage(page_number=1, content=formatted_str, section="JSON Root")]
        except Exception as e:
            raise DocumentProcessingError(f"Failed to parse JSON file '{filename}': {e}")


class HTMLParser(DocumentParser):
    def parse(self, file_content: bytes, filename: str) -> List[ParsedPage]:
        try:
            html_text = file_content.decode("utf-8", errors="replace")
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_text, "html.parser")
                for script_or_style in soup(["script", "style"]):
                    script_or_style.decompose()
                text = soup.get_text(separator="\n")
            except ImportError:
                # Basic regex tag stripper
                text = re.sub(r"<[^>]+>", " ", html_text)

            clean_text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])
            return [ParsedPage(page_number=1, content=clean_text, section="HTML Body")]
        except Exception as e:
            raise DocumentProcessingError(f"Failed to parse HTML file '{filename}': {e}")


class ParserFactory:
    @staticmethod
    def get_parser(filename: str, mime_type: str = "") -> DocumentParser:
        fname = filename.lower()
        if fname.endswith(".pdf") or "pdf" in mime_type:
            return PDFParser()
        if fname.endswith(".docx") or fname.endswith(".doc") or "word" in mime_type:
            return DocxParser()
        if fname.endswith(".txt") or "text/plain" in mime_type:
            return TextParser()
        if fname.endswith(".md") or fname.endswith(".markdown"):
            return MarkdownParser()
        if fname.endswith(".csv") or "csv" in mime_type:
            return CSVParser()
        if fname.endswith(".json") or "json" in mime_type:
            return JSONParser()
        if fname.endswith(".html") or fname.endswith(".htm") or "html" in mime_type:
            return HTMLParser()

        raise DocumentProcessingError(f"Unsupported file type for file '{filename}'. Supported types: PDF, DOCX, TXT, MD, CSV, JSON, HTML.")
