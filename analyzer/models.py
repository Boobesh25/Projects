"""
Data Models for Career Page Analyser
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class JobPosting(BaseModel):
    """Normalized Canonical Job Description Schema"""
    url: str
    company: str
    title: str
    location: str = "Unspecified"
    job_id: Optional[str] = None
    source_channel: str = "Career Page"  # "Career Page", "LinkedIn", "Naukri"
    posted_date: Optional[str] = None
    service_line: Optional[str] = None
    min_experience_years: Optional[float] = None
    max_experience_years: Optional[float] = None
    educational_requirements: List[str] = Field(default_factory=list)
    must_have_skills: List[str] = Field(default_factory=list)
    nice_to_have_skills: List[str] = Field(default_factory=list)
    tech_stack: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    raw_markdown: str = ""

class MatchResult(BaseModel):
    """Detailed Match Evaluation Result against Candidate Profile"""
    job_title: str
    company: str
    url: str
    location: str
    job_id: Optional[str] = None
    source_channel: str = "Career Page"
    experience_fit: bool
    exp_required_text: str
    overall_match_score: float  # 0.0 - 100.0%
    skill_match_score: float
    semantic_match_score: float
    matched_skills: List[str]
    missing_skills: List[str]
    framing_opportunities: List[Dict[str, str]] = Field(default_factory=list)
    is_high_match: bool  # >= 75.0%
    is_cross_domain: bool = False
    job_domain: str = "General"
    candidate_domain: str = "General"
    recommendation: str
    tailoring_tips: List[str]

    def format_terminal_summary(self) -> str:
        status_icon = "[STRONG MATCH (>= 75%)]" if self.is_high_match else ("[MODERATE (60-74%)]" if self.overall_match_score >= 60 else "[LOW MATCH (< 60%)]")
        lines = [
            f"{'='*60}",
            f"Job: {self.job_title} @ {self.company}",
            f"Location: {self.location} | Ref ID: {self.job_id or 'N/A'}",
            f"Overall Match Score: {self.overall_match_score}% [{status_icon}]",
            f"Experience Alignment: {'Matched' if self.experience_fit else 'Mismatch'} ({self.exp_required_text})",
            f"Matched Skills ({len(self.matched_skills)}): {', '.join(self.matched_skills[:8])}{'...' if len(self.matched_skills) > 8 else ''}",
            f"Missing / Unmatched ({len(self.missing_skills)}): {', '.join(self.missing_skills) if self.missing_skills else 'None'}",
            f"Recommendation: {self.recommendation}",
        ]
        if self.tailoring_tips:
            lines.append("Tailoring Suggestions:")
            for tip in self.tailoring_tips:
                lines.append(f"  * {tip}")
        lines.append(f"{'='*60}")
        return "\n".join(lines)

