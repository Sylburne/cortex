"""Document parser: extract text from .docx, .pdf, .md, .txt, .pptx files."""
import io


def detect_and_parse(content: bytes, filename: str) -> str:
    """Parse document content to plain text based on file extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext in ("md", "mdx", "txt"):
        return content.decode("utf-8", errors="replace")

    if ext == "docx":
        return _parse_docx(content)

    if ext == "pdf":
        return _parse_pdf(content)

    if ext == "pptx":
        return _parse_pptx(content)

    # Fallback: try as text
    return content.decode("utf-8", errors="replace")


def _parse_docx(content: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(content))
        paragraphs = []
        for para in doc.paragraphs:
            if para.text.strip():
                paragraphs.append(para.text)
        # Also extract tables
        for table in doc.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                if any(cells):
                    paragraphs.append(" | ".join(cells))
        return "\n\n".join(paragraphs)
    except ImportError as e:
        print(f"[docx_parser] ImportError: {e}")
        raise
    except Exception as e:
        print(f"[docx_parser] Error: {e}")
        raise


def _parse_pdf(content: bytes) -> str:
    import fitz  # pymupdf
    doc = fitz.open(stream=content, filetype="pdf")
    texts = []
    for page in doc:
        texts.append(page.get_text())
    doc.close()
    return "\n\n".join(texts)


def _parse_pptx(content: bytes) -> str:
    from pptx import Presentation
    prs = Presentation(io.BytesIO(content))
    texts = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    if para.text.strip():
                        texts.append(para.text)
    return "\n\n".join(texts)
