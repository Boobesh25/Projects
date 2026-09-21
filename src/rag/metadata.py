"""Generate metadata summaries for uploaded documents using Gemini."""

from google import genai
from src.config.settings import settings


def generate_document_summary(filename: str, doc_type: str, api_key: str = "", **kwargs) -> str:
    """
    Generate a brief summary of what the document contains.
    Used for routing decisions (CSV vs text, which doc to query).

    For CSV: uses column names + 3 sample rows (that's all you need).
    For Text: uses beginning + middle + end of document for full coverage.
    """
    key = (api_key or settings.gemini_api_key).strip()
    if not key:
        if doc_type == "csv":
            columns = kwargs.get("columns", [])
            return f"CSV data with columns: {', '.join(columns)}."
        return f"Document: {filename}"

    client = genai.Client(api_key=key)

    if doc_type == "csv":
        prompt = _build_csv_prompt(filename, **kwargs)
    else:
        prompt = _build_text_prompt(filename, **kwargs)

    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        # Fallback if Gemini fails
        if doc_type == "csv":
            columns = kwargs.get("columns", [])
            return f"CSV data with columns: {', '.join(columns)}."
        return f"Document: {filename}"


def _build_csv_prompt(filename: str, columns: list[str] = None, sample_rows: list[list[str]] = None, row_count: int = 0, **_) -> str:
    """
    Build prompt for CSV summary.
    Only needs: column names + 3 sample rows. That's enough to understand the data.
    """
    columns = columns or []
    sample_rows = sample_rows or []

    prompt = (
        f"Describe in 2-3 sentences what this CSV file '{filename}' contains.\n\n"
        f"Columns: {', '.join(columns)}\n"
        f"Total rows: {row_count}\n"
    )

    if sample_rows:
        prompt += "\nSample rows (first 3):\n"
        for i, row in enumerate(sample_rows[:3], 1):
            row_str = " | ".join(str(v) for v in row)
            prompt += f"  {i}. {row_str}\n"

    prompt += "\nWrite a concise description of what data this file contains and what it could be used to answer."
    return prompt


def _build_text_prompt(filename: str, full_text: str = "", **_) -> str:
    """
    Build prompt for text document summary.
    Samples beginning + middle + end to cover the full document scope.
    """
    text = full_text.strip()
    if not text:
        return f"Describe the document '{filename}'. No content available."

    total_len = len(text)

    # Sample 3 sections: beginning, middle, end (each ~300 chars)
    section_size = 300

    beginning = text[:section_size]

    mid_start = max(0, (total_len // 2) - (section_size // 2))
    middle = text[mid_start : mid_start + section_size]

    end = text[max(0, total_len - section_size):]

    prompt = (
        f"Describe in 2-3 sentences what this document '{filename}' is about.\n"
        f"Document length: {total_len} characters.\n\n"
        f"--- BEGINNING ---\n{beginning}\n\n"
        f"--- MIDDLE ---\n{middle}\n\n"
        f"--- END ---\n{end}\n\n"
        f"Write a concise summary covering the full scope of the document "
        f"(not just the beginning). What topics does it cover? What could it be used to answer?"
    )
    return prompt
