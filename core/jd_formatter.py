"""
Job Description Formatter & Intelligence Cleaner.
Cleans authentic ATS HTML markup (Greenhouse, Lever, etc.) into clean markdown/text.
Strictly grounded: NEVER fabricates or synthesizes fake job descriptions.
"""

import html
import re
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup


class JobDescriptionFormatter:
    """
    Cleans raw HTML descriptions from authentic ATS feeds (Greenhouse/Lever/Workday)
    and formats authentic text without fabricating content.
    """

    @staticmethod
    def clean_raw_html(raw_text: str) -> str:
        """Decodes HTML entities and normalizes markup into readable markdown/text."""
        if not raw_text:
            return ""

        # Step 1: Decode entities (&lt;p&gt; -> <p>, &amp; -> &)
        text = html.unescape(raw_text)
        # Double unescape if nested
        if "&lt;" in text or "&amp;" in text or "&#" in text:
            text = html.unescape(text)

        # Step 2: If HTML markup is present, parse with BeautifulSoup
        if "<" in text and ">" in text:
            try:
                soup = BeautifulSoup(text, "html.parser")
                # Format unordered lists
                for li in soup.find_all("li"):
                    li.replace_with(f"\n- {li.get_text().strip()}")
                # Add spacing after block elements
                for tag in soup.find_all(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "br"]):
                    tag.insert_after("\n\n")

                text = soup.get_text()
            except Exception:
                pass

        # Step 3: Normalize whitespace and excessive newlines
        lines = [line.rstrip() for line in text.split("\n")]
        
        # Step 4: Strip leading cookie banners and navigation boilerplate
        cleaned_lines = []
        started = False
        for line in lines:
            l_str = line.strip()
            l_low = l_str.lower()
            if not started:
                if any(l_low.startswith(b) for b in [
                    "we use cookies", "this website uses cookies", "modify cookie", "accept all cookies",
                    "[skip to main content", "skip to main content", "[language", "language",
                    "[view profile", "view profile", "[candidate login", "candidate login",
                    "[careers", "[about us", "[investors", "[media", "[sustainability",
                    "[recruitment fraud", "recruitment fraud"
                ]):
                    continue
                if re.match(r'^\[\!\[.*\]\]\(.*\)', l_str):
                    continue
                if l_low in ["language", "careers", "view profile", "candidate login", "search jobs", "menu"]:
                    continue
                if l_str.startswith("#") or len(l_str) > 25:
                    started = True
            
            if started:
                cleaned_lines.append(line)

        text_to_norm = "\n".join(cleaned_lines) if cleaned_lines else "\n".join(lines)
        normalized = re.sub(r"\n{3,}", "\n\n", text_to_norm).strip()
        return normalized

    @classmethod
    def get_full_job_description(cls, job: Dict[str, Any]) -> str:
        """
        Returns the genuine, authentic Job Description.
        If a full authentic description (> 150 chars) is present, cleans and returns it verbatim.
        If only a short snippet is available, returns the authentic snippet with a clear,
        honest disclosure that the full description was not retrieved from the feed.
        """
        raw_desc = (
            job.get("raw_description")
            or job.get("raw_markdown")
            or job.get("desc")
            or job.get("description")
            or ""
        ).strip()

        cleaned = cls.clean_raw_html(raw_desc)

        # Check if text is a generic catalog placeholder or feed query stub
        is_generic_placeholder = any(
            k in cleaned.lower()
            for k in [
                "active opportunity for",
                "monitored across official career portal",
                "target active opportunity for",
                "sourced from linkedin search query"
            ]
        )

        # If we have an authentic, substantial description from ATS / portal
        if cleaned and len(cleaned) >= 150 and not is_generic_placeholder:
            return cleaned

        # When only a brief snippet exists or full text was not scraped
        comp_name = (job.get("company_name") or job.get("company") or "the employer").strip()
        channel = (job.get("source_channel") or "Job Feed").strip()

        if cleaned and not is_generic_placeholder:
            return (
                f"{cleaned}\n\n"
                f"---\n"
                f"[Feed Notice]: The complete job description body was not retrieved from the {channel} feed. "
                f"Please use 'Apply on Official Portal' to view the full, original posting on {comp_name}'s official site."
            )

        return (
            f"Original posting details for {job.get('title', 'Role')} at {comp_name}.\n\n"
            f"---\n"
            f"[Feed Notice]: Full job specification body was not extracted from the external {channel} feed. "
            f"Please click 'Apply on Official Portal' above to review the complete, authentic requirements directly."
        )
