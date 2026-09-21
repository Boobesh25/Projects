"""
Semantic chunking for documents.

Strategy: Split text into sentences, compute embeddings, then group consecutive
sentences into chunks based on semantic similarity. When similarity between
adjacent sentences drops below a threshold, a chunk boundary is created.

This produces chunks that are semantically coherent rather than just
fixed-size character splits.
"""

import io
import re
import numpy as np
from pathlib import Path

from src.rag.embeddings import embedder

def _get_embedder():
    """Return the Gemini embedder instance."""
    return embedder


# ─── Text Extraction ─────────────────────────────────────────────────────────


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract plain text from a .docx file (fallback, use extract_structured for better results)."""
    from docx import Document

    doc = Document(io.BytesIO(file_bytes))
    paragraphs = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract plain text from a PDF file (fallback, use extract_structured for better results)."""
    import fitz  # PyMuPDF

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text").strip()
        if text:
            pages.append(text)
    doc.close()
    return "\n\n".join(pages)


def extract_structured(filename: str, file_bytes: bytes) -> list[dict]:
    """
    Structure-aware extraction for PDFs and DOCX.
    - PDF: Uses PyMuPDF's built-in table detection + text extraction
    - DOCX: Uses python-docx heading styles + table extraction
    Returns typed elements: [{"type": "Title|Table|NarrativeText", "text": "..."}]
    """
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        return _extract_pdf_structured(file_bytes)
    elif ext == ".docx":
        return _extract_docx_structured(file_bytes)
    else:
        text = file_bytes.decode("utf-8", errors="replace")
        return [{"type": "NarrativeText", "text": text}]


def _extract_pdf_structured(file_bytes: bytes) -> list[dict]:
    """
    Extract PDF with structure awareness using PyMuPDF's built-in table detection.
    Produces typed elements with tables preserved as markdown.
    No extra dependencies needed — PyMuPDF handles everything.

    Optimized: skips expensive find_tables() on pages that have no line drawings
    (tables need ruled lines or grid patterns to exist).
    """
    import fitz  # PyMuPDF
    import structlog
    _logger = structlog.get_logger(__name__)

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        _logger.info("pymupdf_structured_extraction", pages=len(doc))

        elements: list[dict] = []
        tables_total = 0

        for page_num in range(len(doc)):
            page = doc[page_num]

            # ─── Fast table pre-check: only run find_tables() if page has line drawings ───
            # This avoids the expensive table detection on text-only pages
            tables = []
            table_rects = []

            has_drawings = len(page.get_drawings()) > 5  # Tables need rule lines
            if has_drawings:
                tables = page.find_tables()
                table_rects = [table.bbox for table in tables]
                tables_total += len(tables)

            # Get all text blocks with position info
            text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
            blocks = text_dict.get("blocks", [])

            # Process each block — determine if it's inside a table area or regular text
            page_text_parts: list[str] = []

            for block in blocks:
                if block.get("type") != 0:  # Skip non-text blocks (images)
                    continue

                block_rect = fitz.Rect(block["bbox"])
                block_text = ""
                for line in block.get("lines", []):
                    line_text = ""
                    for span in line.get("spans", []):
                        line_text += span.get("text", "")
                    block_text += line_text + "\n"

                block_text = block_text.strip()
                if not block_text:
                    continue

                # Check if this block is inside any table
                in_table = False
                if table_rects:
                    in_table = any(
                        block_rect.intersects(fitz.Rect(tr)) for tr in table_rects
                    )

                if not in_table:
                    # Detect headings by font size (larger = heading)
                    max_size = 0
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            max_size = max(max_size, span.get("size", 0))

                    if max_size >= 14:  # Likely a heading
                        # Save accumulated text first
                        if page_text_parts:
                            combined = "\n".join(page_text_parts).strip()
                            if combined:
                                elements.append({"type": "NarrativeText", "text": combined})
                            page_text_parts = []
                        elements.append({"type": "Title", "text": block_text})
                    else:
                        page_text_parts.append(block_text)

            # Save remaining text from page
            if page_text_parts:
                combined = "\n".join(page_text_parts).strip()
                if combined:
                    elements.append({"type": "NarrativeText", "text": combined})

            # Now extract tables as markdown
            for table in tables:
                try:
                    md = table.to_markdown()
                    if md and md.strip():
                        elements.append({"type": "Table", "text": md.strip()})
                except Exception:
                    # Fallback: extract table as plain text
                    try:
                        df = table.to_pandas()
                        header = "| " + " | ".join(str(c) for c in df.columns) + " |"
                        sep = "| " + " | ".join(["---"] * len(df.columns)) + " |"
                        rows = []
                        for _, row in df.iterrows():
                            rows.append("| " + " | ".join(str(v) for v in row) + " |")
                        md = "\n".join([header, sep] + rows)
                        elements.append({"type": "Table", "text": md})
                    except Exception:
                        pass

        doc.close()
        _logger.info("pymupdf_structured_done", elements=len(elements), tables=tables_total)
        return elements

    except Exception as e:
        import structlog
        structlog.get_logger(__name__).error("pymupdf_structured_failed", error=str(e))
        # Ultimate fallback: flat text
        text = extract_text_from_pdf(file_bytes)
        return [{"type": "NarrativeText", "text": text}]


def _extract_docx_structured(file_bytes: bytes) -> list[dict]:
    """Extract DOCX with structure awareness using python-docx."""
    from docx import Document as DocxDocument

    try:
        doc = DocxDocument(io.BytesIO(file_bytes))
        elements: list[dict] = []

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue

            # Detect headings by style
            if para.style and para.style.name.startswith("Heading"):
                elements.append({"type": "Title", "text": text})
            else:
                elements.append({"type": "NarrativeText", "text": text})

        # Extract tables
        for table in doc.tables:
            rows = []
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                rows.append("| " + " | ".join(cells) + " |")

            if rows:
                header = rows[0]
                sep = "| " + " | ".join(["---"] * len(table.rows[0].cells)) + " |"
                md = "\n".join([header, sep] + rows[1:])
                elements.append({"type": "Table", "text": md})

        return elements if elements else [{"type": "NarrativeText", "text": extract_text_from_docx(file_bytes)}]

    except Exception:
        text = extract_text_from_docx(file_bytes)
        return [{"type": "NarrativeText", "text": text}]


def _markdown_to_elements(markdown: str) -> list[dict]:
    """
    Parse markdown into typed elements (Title, Table, NarrativeText).
    Splits on heading boundaries and detects markdown tables.
    """
    elements: list[dict] = []
    lines = markdown.split("\n")

    current_block: list[str] = []
    current_type = "NarrativeText"

    for line in lines:
        # Detect headings
        if re.match(r"^#{1,6}\s+", line):
            # Save current block
            if current_block:
                block_text = "\n".join(current_block).strip()
                if block_text:
                    elements.append({"type": current_type, "text": block_text})
                current_block = []

            elements.append({"type": "Title", "text": line.lstrip("#").strip()})
            current_type = "NarrativeText"
            continue

        # Detect table rows (lines starting with |)
        if line.strip().startswith("|"):
            if current_type != "Table":
                # Save previous block before starting table
                if current_block:
                    block_text = "\n".join(current_block).strip()
                    if block_text:
                        elements.append({"type": current_type, "text": block_text})
                    current_block = []
                current_type = "Table"
            current_block.append(line)
            continue

        # If we were in a table and hit a non-table line, save the table
        if current_type == "Table" and not line.strip().startswith("|"):
            if current_block:
                block_text = "\n".join(current_block).strip()
                if block_text:
                    elements.append({"type": "Table", "text": block_text})
                current_block = []
            current_type = "NarrativeText"

        # Regular text
        current_block.append(line)

    # Save last block
    if current_block:
        block_text = "\n".join(current_block).strip()
        if block_text:
            elements.append({"type": current_type, "text": block_text})

    return elements


def extract_text_from_txt(file_bytes: bytes) -> str:
    """Extract text from a plain text file."""
    return file_bytes.decode("utf-8", errors="replace")


def extract_text_from_csv(file_bytes: bytes) -> str:
    """
    Extract text from a CSV file by converting groups of rows into
    markdown table chunks. Each chunk contains the header + a batch of rows,
    preserving the tabular structure for better embedding context.

    Example output chunk:
        | name | age | city |
        |------|-----|------|
        | Alice | 30 | New York |
        | Bob | 25 | London |
    """
    import csv

    text = file_bytes.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))

    rows = list(reader)
    if not rows:
        return ""

    # First row as headers
    headers = [h.strip() for h in rows[0]]

    # If headers look like data (all numeric), treat as headerless
    if all(h.replace(".", "").replace("-", "").isdigit() for h in headers if h):
        headers = [f"col_{i+1}" for i in range(len(headers))]
        data_rows = rows
    else:
        data_rows = rows[1:]

    if not data_rows:
        return ""

    # Build markdown table chunks (batch rows to keep tables readable)
    ROWS_PER_CHUNK = 15
    chunks = []

    for start in range(0, len(data_rows), ROWS_PER_CHUNK):
        batch = data_rows[start : start + ROWS_PER_CHUNK]

        # Header row
        table_lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
        ]

        # Data rows
        for row in batch:
            # Pad or trim row to match header count
            padded = row + [""] * (len(headers) - len(row))
            cells = [c.strip() for c in padded[: len(headers)]]
            table_lines.append("| " + " | ".join(cells) + " |")

        chunk_text = f"Table (rows {start+1}-{start+len(batch)}):\n" + "\n".join(table_lines)
        chunks.append(chunk_text)

    return "\n\n".join(chunks)


def extract_text(filename: str, file_bytes: bytes) -> str:
    """Route to the correct extractor based on file extension."""
    ext = Path(filename).suffix.lower()
    if ext == ".docx":
        return extract_text_from_docx(file_bytes)
    elif ext == ".pdf":
        return extract_text_from_pdf(file_bytes)
    elif ext == ".csv":
        return extract_text_from_csv(file_bytes)
    elif ext in (".txt", ".md", ".log"):
        return extract_text_from_txt(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: {ext}. Supported: .docx, .pdf, .txt, .md, .csv, .log")


def extract_csv_schema(filename: str, file_bytes: bytes) -> dict | None:
    """
    Extract schema metadata from a CSV file.
    Returns a dict with columns, data types, sample values, and row count.
    Returns None if not a CSV file.
    """
    import csv

    ext = Path(filename).suffix.lower()
    if ext != ".csv":
        return None

    text = file_bytes.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)

    if not rows:
        return None

    headers = [h.strip() for h in rows[0]]

    # Detect if first row is actually data
    if all(h.replace(".", "").replace("-", "").isdigit() for h in headers if h):
        headers = [f"col_{i+1}" for i in range(len(headers))]
        data_rows = rows
    else:
        data_rows = rows[1:]

    if not data_rows:
        return {"columns": headers, "row_count": 0, "dtypes": {}, "sample_values": {}}

    # Infer data types and collect sample values
    dtypes = {}
    sample_values = {}

    for col_idx, col_name in enumerate(headers):
        values = []
        for row in data_rows[:50]:  # Sample first 50 rows
            if col_idx < len(row) and row[col_idx].strip():
                values.append(row[col_idx].strip())

        sample_values[col_name] = values[:5]

        # Infer type
        if not values:
            dtypes[col_name] = "empty"
        elif all(_is_numeric(v) for v in values):
            if all("." in v for v in values if _is_numeric(v)):
                dtypes[col_name] = "float"
            else:
                dtypes[col_name] = "integer"
        elif all(_is_date(v) for v in values[:10]):
            dtypes[col_name] = "date"
        else:
            # Check cardinality for categorical detection
            unique_count = len(set(values))
            if unique_count <= 10 and len(values) > 5:
                dtypes[col_name] = "categorical"
            else:
                dtypes[col_name] = "text"

    return {
        "filename": filename,
        "columns": headers,
        "row_count": len(data_rows),
        "dtypes": dtypes,
        "sample_values": sample_values,
    }


def _is_numeric(value: str) -> bool:
    """Check if a string value is numeric."""
    try:
        float(value.replace(",", ""))
        return True
    except ValueError:
        return False


def _is_date(value: str) -> bool:
    """Basic check if a value looks like a date."""
    date_patterns = [
        r"\d{4}-\d{2}-\d{2}",
        r"\d{2}/\d{2}/\d{4}",
        r"\d{2}-\d{2}-\d{4}",
    ]
    return any(re.match(p, value) for p in date_patterns)


# ─── Sentence Splitting ──────────────────────────────────────────────────────


def _split_into_sentences(text: str) -> list[str]:
    """
    Split text into sentences using regex.
    Handles common abbreviations and edge cases.
    """
    # Normalize whitespace
    text = re.sub(r"\n{2,}", " [PARA] ", text)
    text = re.sub(r"\n", " ", text)

    # Split on sentence boundaries
    # Handles: period/question/exclamation followed by space and uppercase
    # Avoids splitting on: Mr. Mrs. Dr. etc.
    sentences = re.split(
        r"(?<=[.!?])\s+(?=[A-Z\"\'\(\[])|(?<=\[PARA\])\s*",
        text,
    )

    # Clean up and filter
    cleaned = []
    for s in sentences:
        s = s.replace("[PARA]", "").strip()
        if s and len(s) > 10:  # Skip very short fragments
            cleaned.append(s)

    return cleaned


# ─── Semantic Chunking ────────────────────────────────────────────────────────


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def chunk_document(
    text: str,
    similarity_threshold: float | None = None,
    max_chunk_size: int = 1000,
    min_chunk_size: int = 100,
) -> list[str]:
    """
    Semantic chunking with adaptive thresholds based on content type.

    For large documents (>50,000 chars), uses fast recursive text splitting
    instead of embedding-based semantic chunking to avoid excessive API calls.

    If similarity_threshold is None, auto-detects:
    - Technical/code content (lots of special chars) → 0.4 (larger chunks, preserve context)
    - Narrative/prose → 0.55 (tighter semantic boundaries)
    - Mixed/general → 0.5 (default)
    """
    # ─── Large document fast path ────────────────────────────────────────
    LARGE_DOC_THRESHOLD = 50_000  # ~12-15 pages of text
    if len(text) > LARGE_DOC_THRESHOLD:
        return _chunk_large_document(text, max_chunk_size=max_chunk_size, min_chunk_size=min_chunk_size)

    # Split into sentences
    sentences = _split_into_sentences(text)

    if not sentences:
        return [text.strip()] if text.strip() else []

    if len(sentences) <= 3:
        return [" ".join(sentences)]

    # ─── Adaptive threshold ──────────────────────────────────────────────
    if similarity_threshold is None:
        # Detect content type from character distribution
        special_ratio = sum(1 for c in text[:2000] if c in "{}[]()<>;:=|/\\") / max(len(text[:2000]), 1)
        avg_sentence_len = sum(len(s) for s in sentences) / len(sentences)

        if special_ratio > 0.03:
            # Technical/code-heavy → keep larger chunks for context
            similarity_threshold = 0.4
        elif avg_sentence_len > 150:
            # Long sentences (academic/legal) → moderate splitting
            similarity_threshold = 0.45
        else:
            # Normal prose → standard semantic splitting
            similarity_threshold = 0.55

    # Compute embeddings for all sentences via Gemini
    emb = _get_embedder()
    embeddings = np.array(emb.embed(sentences))

    # Find chunk boundaries using similarity between adjacent sentences
    # We use a sliding window: compare sentence[i] with sentence[i+1]
    breakpoints: list[int] = []

    for i in range(len(sentences) - 1):
        sim = _cosine_similarity(embeddings[i], embeddings[i + 1])
        if sim < similarity_threshold:
            breakpoints.append(i + 1)

    # Build chunks from breakpoints
    chunks: list[str] = []
    start = 0

    for bp in breakpoints:
        chunk_text = " ".join(sentences[start:bp])

        # If chunk exceeds max size, split it further
        if len(chunk_text) > max_chunk_size:
            sub_chunks = _split_large_chunk(sentences[start:bp], max_chunk_size)
            chunks.extend(sub_chunks)
        else:
            chunks.append(chunk_text)

        start = bp

    # Don't forget the last chunk
    if start < len(sentences):
        chunk_text = " ".join(sentences[start:])
        if len(chunk_text) > max_chunk_size:
            sub_chunks = _split_large_chunk(sentences[start:], max_chunk_size)
            chunks.extend(sub_chunks)
        else:
            chunks.append(chunk_text)

    # Merge very small chunks with their neighbors
    chunks = _merge_small_chunks(chunks, min_chunk_size, max_chunk_size)

    return chunks


def _chunk_large_document(
    text: str,
    max_chunk_size: int = 1000,
    min_chunk_size: int = 100,
    overlap: int = 100,
) -> list[str]:
    """
    Fast recursive text splitting for large documents.
    Splits on paragraph boundaries first, then sentences, then character limits.
    Includes overlap between chunks for context continuity.
    No embedding API calls — purely text-based.
    """
    # Split into paragraphs first
    paragraphs = re.split(r"\n{2,}", text)
    paragraphs = [p.strip() for p in paragraphs if p.strip() and len(p.strip()) > 20]

    if not paragraphs:
        # Fallback: just split by character count
        return [text[i:i + max_chunk_size] for i in range(0, len(text), max_chunk_size - overlap)]

    chunks: list[str] = []
    current_chunk = ""

    for para in paragraphs:
        # If adding this paragraph stays within limits, accumulate
        if len(current_chunk) + len(para) + 2 <= max_chunk_size:
            current_chunk = f"{current_chunk}\n\n{para}".strip()
        else:
            # Save current chunk if it's big enough
            if current_chunk and len(current_chunk) >= min_chunk_size:
                chunks.append(current_chunk)
            elif current_chunk:
                # Too small — carry it forward
                current_chunk = f"{current_chunk}\n\n{para}".strip()
                continue

            # If single paragraph exceeds max, split it by sentences
            if len(para) > max_chunk_size:
                sub_sentences = re.split(r"(?<=[.!?])\s+", para)
                sub_chunk = ""
                for sent in sub_sentences:
                    if len(sub_chunk) + len(sent) + 1 <= max_chunk_size:
                        sub_chunk = f"{sub_chunk} {sent}".strip()
                    else:
                        if sub_chunk and len(sub_chunk) >= min_chunk_size:
                            chunks.append(sub_chunk)
                        sub_chunk = sent
                current_chunk = sub_chunk
            else:
                current_chunk = para

    # Don't forget the last chunk
    if current_chunk and len(current_chunk) >= min_chunk_size:
        chunks.append(current_chunk)
    elif current_chunk and chunks:
        # Merge tiny trailing text with previous chunk
        chunks[-1] = f"{chunks[-1]}\n\n{current_chunk}"

    return chunks


def _is_noise_chunk(text: str) -> bool:
    """
    Detect TOC/index noise chunks that are mostly page references.
    These contain patterns like ". . . . . . . . . 2-28" and add no retrieval value.
    """
    # Count dot sequences (TOC patterns)
    dot_sequences = len(re.findall(r"\.{3,}", text))
    # Count actual words
    words = re.findall(r'\w{3,}', text)

    if not words:
        return True

    # If more than 30% of "lines" are dot-heavy, it's a TOC page
    lines = text.split('\n')
    dot_lines = sum(1 for line in lines if line.count('.') > 10 and '. .' in line)

    if lines and dot_lines / max(len(lines), 1) > 0.3:
        return True

    return False


def chunk_structured_document(
    elements: list[dict],
    parent_size: int = 2000,
    parent_overlap: int = 400,
    child_size: int = 500,
    min_chunk_size: int = 100,
) -> list[dict]:
    """
    Structure-aware hierarchical chunking.

    Handles tables, headings, and prose differently:
    - Tables: kept whole (with caption) as one parent. Never split mid-row.
    - Headings: attached to the content that follows as context.
    - Prose: paragraph-based parent-child with overlap.

    Returns: list of dicts with parent_id, parent_content, child_content, etc.
    """
    import uuid as _uuid

    results: list[dict] = []
    parent_idx = 0

    # Group elements into logical blocks (heading + content)
    i = 0
    while i < len(elements):
        el = elements[i]

        # ─── Table: NEVER split. Always keep whole with heading ────
        if el["type"] == "Table":
            table_text = el["text"]

            # Look backward for a title/caption
            caption = ""
            if i > 0 and elements[i - 1]["type"] == "Title":
                caption = elements[i - 1]["text"] + "\n\n"

            full_table = f"{caption}{table_text}".strip()

            if _is_noise_chunk(full_table):
                i += 1
                continue

            parent_id = str(_uuid.uuid4())

            # Table is ALWAYS stored as one unit — parent and child are the same
            # No splitting regardless of size
            results.append({
                "parent_id": parent_id,
                "parent_content": full_table,
                "child_content": full_table,
                "parent_index": parent_idx,
                "child_index": 0,
            })

            parent_idx += 1
            i += 1
            continue

        # ─── Title/Header: collect with following content ─────────
        if el["type"] == "Title":
            heading = el["text"]
            # Gather following prose/list items until next title or table
            body_parts = [heading]
            i += 1
            while i < len(elements) and elements[i]["type"] not in ("Title", "Table"):
                body_parts.append(elements[i]["text"])
                i += 1

            section_text = "\n\n".join(body_parts)

            if _is_noise_chunk(section_text):
                continue

            # Chunk this section into parents with overlap
            if len(section_text) <= parent_size:
                parent_id = str(_uuid.uuid4())
                children = _split_into_children(section_text, child_size, min_chunk_size)
                for child_idx, child in enumerate(children):
                    if not _is_noise_chunk(child):
                        results.append({
                            "parent_id": parent_id,
                            "parent_content": section_text,
                            "child_content": child,
                            "parent_index": parent_idx,
                            "child_index": child_idx,
                        })
                parent_idx += 1
            else:
                # Large section: use parent overlap chunking
                parents = _chunk_parents_with_overlap(section_text, parent_size, parent_overlap, min_chunk_size)
                for p_text in parents:
                    if _is_noise_chunk(p_text):
                        continue
                    parent_id = str(_uuid.uuid4())
                    children = _split_into_children(p_text, child_size, min_chunk_size)
                    for child_idx, child in enumerate(children):
                        if not _is_noise_chunk(child):
                            results.append({
                                "parent_id": parent_id,
                                "parent_content": p_text,
                                "child_content": child,
                                "parent_index": parent_idx,
                                "child_index": child_idx,
                            })
                    parent_idx += 1
            continue

        # ─── NarrativeText/ListItem: accumulate and chunk ─────────
        body_parts = []
        while i < len(elements) and elements[i]["type"] not in ("Title", "Table"):
            body_parts.append(elements[i]["text"])
            i += 1

        section_text = "\n\n".join(body_parts)

        if not section_text.strip() or _is_noise_chunk(section_text):
            continue

        if len(section_text) <= parent_size:
            parent_id = str(_uuid.uuid4())
            children = _split_into_children(section_text, child_size, min_chunk_size)
            for child_idx, child in enumerate(children):
                if not _is_noise_chunk(child):
                    results.append({
                        "parent_id": parent_id,
                        "parent_content": section_text,
                        "child_content": child,
                        "parent_index": parent_idx,
                        "child_index": child_idx,
                    })
            parent_idx += 1
        else:
            parents = _chunk_parents_with_overlap(section_text, parent_size, parent_overlap, min_chunk_size)
            for p_text in parents:
                if _is_noise_chunk(p_text):
                    continue
                parent_id = str(_uuid.uuid4())
                children = _split_into_children(p_text, child_size, min_chunk_size)
                for child_idx, child in enumerate(children):
                    if not _is_noise_chunk(child):
                        results.append({
                            "parent_id": parent_id,
                            "parent_content": p_text,
                            "child_content": child,
                            "parent_index": parent_idx,
                            "child_index": child_idx,
                        })
                parent_idx += 1

    return results


def _split_table_by_rows(table_text: str, max_size: int = 500) -> list[str]:
    """
    Split a large markdown table into row groups.
    Always includes the header row in each chunk.
    """
    lines = table_text.split("\n")

    # Find the header (first two lines: header row + separator)
    header_lines = []
    data_lines = []
    found_separator = False

    for line in lines:
        if not found_separator:
            header_lines.append(line)
            if line.strip().startswith("|") and "---" in line:
                found_separator = True
        else:
            data_lines.append(line)

    if not found_separator:
        # Not a markdown table format, just split by size
        header_lines = lines[:2] if len(lines) > 2 else lines[:1]
        data_lines = lines[len(header_lines):]

    header = "\n".join(header_lines)

    if not data_lines:
        return [table_text]

    # Group data rows into chunks
    chunks: list[str] = []
    current_rows: list[str] = []
    current_size = len(header)

    for row in data_lines:
        if current_size + len(row) + 1 > max_size and current_rows:
            chunks.append(header + "\n" + "\n".join(current_rows))
            current_rows = []
            current_size = len(header)

        current_rows.append(row)
        current_size += len(row) + 1

    if current_rows:
        chunks.append(header + "\n" + "\n".join(current_rows))

    return chunks


def chunk_document_hierarchical(
    text: str,
    parent_size: int = 2000,
    parent_overlap: int = 400,
    child_size: int = 500,
    min_chunk_size: int = 100,
) -> list[dict]:
    """
    Hierarchical chunking: produces parent-child pairs.

    1. Split text into PARENTS (~2000 chars, with 400 char overlap between adjacent parents)
    2. Split each parent into CHILDREN (~500 chars, on sentence boundaries)

    The overlap ensures that content at parent boundaries (like tables spanning
    the boundary) is fully captured in at least one parent.

    Returns: list of dicts, each with:
        - parent_id: UUID linking children to their parent
        - parent_content: full parent text (stored in PostgreSQL)
        - child_content: child text (embedded and stored in Qdrant)
        - parent_index: position of parent in document
        - child_index: position of child within parent
    """
    import uuid

    # Step 1: Create parent chunks with overlap
    parents = _chunk_parents_with_overlap(text, parent_size, parent_overlap, min_chunk_size)

    if not parents:
        parents = [text.strip()] if text.strip() else []

    # Step 2: Split each parent into children, filtering out TOC/index noise
    results: list[dict] = []

    for parent_idx, parent_text in enumerate(parents):
        # Skip entire parent if it's mostly TOC/index noise
        if _is_noise_chunk(parent_text):
            continue

        parent_id = str(uuid.uuid4())

        # Split parent into children on sentence boundaries
        children = _split_into_children(parent_text, child_size, min_chunk_size)

        for child_idx, child_text in enumerate(children):
            # Skip noisy children too
            if _is_noise_chunk(child_text):
                continue
            results.append({
                "parent_id": parent_id,
                "parent_content": parent_text,
                "child_content": child_text,
                "parent_index": parent_idx,
                "child_index": child_idx,
            })

    return results


def _chunk_parents_with_overlap(
    text: str,
    max_size: int = 2000,
    overlap: int = 400,
    min_size: int = 100,
) -> list[str]:
    """
    Create parent chunks with overlap between adjacent chunks.
    Splits on paragraph boundaries where possible.
    """
    paragraphs = re.split(r"\n{2,}", text)
    paragraphs = [p.strip() for p in paragraphs if p.strip() and len(p.strip()) > 20]

    if not paragraphs:
        # Fallback: fixed-size sliding window with overlap
        step = max_size - overlap
        return [text[i:i + max_size] for i in range(0, len(text), step) if text[i:i + max_size].strip()]

    # Build parent chunks on paragraph boundaries
    parents: list[str] = []
    current_chunk = ""
    current_paragraphs: list[str] = []  # Track paragraphs in current chunk

    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 <= max_size:
            current_chunk = f"{current_chunk}\n\n{para}".strip()
            current_paragraphs.append(para)
        else:
            # Save current chunk
            if current_chunk and len(current_chunk) >= min_size:
                parents.append(current_chunk)

            # Start new chunk with overlap: carry tail paragraphs from previous chunk
            # Take paragraphs from the end of the previous chunk until we hit overlap size
            overlap_text = ""
            overlap_paras: list[str] = []
            for p in reversed(current_paragraphs):
                if len(overlap_text) + len(p) + 2 <= overlap:
                    overlap_text = f"{p}\n\n{overlap_text}".strip()
                    overlap_paras.insert(0, p)
                else:
                    break

            # New chunk starts with overlap + current paragraph
            if overlap_text:
                current_chunk = f"{overlap_text}\n\n{para}".strip()
                current_paragraphs = overlap_paras + [para]
            else:
                current_chunk = para
                current_paragraphs = [para]

            # Handle oversized single paragraph
            if len(current_chunk) > max_size:
                # Split by sentences
                sentences = re.split(r"(?<=[.!?])\s+", current_chunk)
                current_chunk = ""
                current_paragraphs = []
                for sent in sentences:
                    if len(current_chunk) + len(sent) + 1 <= max_size:
                        current_chunk = f"{current_chunk} {sent}".strip()
                    else:
                        if current_chunk and len(current_chunk) >= min_size:
                            parents.append(current_chunk)
                        current_chunk = sent
                current_paragraphs = [current_chunk] if current_chunk else []

    # Last chunk
    if current_chunk and len(current_chunk) >= min_size:
        parents.append(current_chunk)
    elif current_chunk and parents:
        parents[-1] = f"{parents[-1]}\n\n{current_chunk}"

    return parents


def _split_into_children(text: str, max_size: int = 500, min_size: int = 100) -> list[str]:
    """Split a parent chunk into smaller children on sentence boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    if not sentences:
        return [text] if text.strip() else []

    children: list[str] = []
    current = ""

    for sent in sentences:
        if len(current) + len(sent) + 1 <= max_size:
            current = f"{current} {sent}".strip()
        else:
            if current and len(current) >= min_size:
                children.append(current)
            elif current:
                # Too small, keep accumulating
                current = f"{current} {sent}".strip()
                continue
            current = sent

    # Last piece
    if current and len(current) >= min_size:
        children.append(current)
    elif current and children:
        children[-1] = f"{children[-1]} {current}"
    elif current:
        children.append(current)

    # If no valid children (text too short for splitting), return the whole text
    if not children:
        children = [text]

    return children


def _split_large_chunk(sentences: list[str], max_size: int) -> list[str]:
    """Split a group of sentences that exceeds max_size into smaller pieces."""
    chunks = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_size:
            current = f"{current} {sentence}".strip()
        else:
            if current:
                chunks.append(current)
            current = sentence

    if current:
        chunks.append(current)

    return chunks


def _merge_small_chunks(
    chunks: list[str], min_size: int, max_size: int
) -> list[str]:
    """Merge chunks that are too small with adjacent chunks."""
    if len(chunks) <= 1:
        return chunks

    merged: list[str] = []
    buffer = ""

    for chunk in chunks:
        if not buffer:
            buffer = chunk
        elif len(buffer) < min_size:
            # Current buffer is too small, merge with next chunk
            combined = f"{buffer} {chunk}"
            if len(combined) <= max_size:
                buffer = combined
            else:
                merged.append(buffer)
                buffer = chunk
        else:
            merged.append(buffer)
            buffer = chunk

    if buffer:
        merged.append(buffer)

    return merged
