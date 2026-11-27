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

    # Enterprise ATS Shortlisting & Tracking Intelligence
    ats_score: float = 0.0  # 0.0 - 100.0%
    ats_verdict: str = "REVIEWABLE"  # "SHORTLISTED", "REVIEWABLE", "POTENTIAL GAP", "KNOCKED OUT"
    knockout_passed: bool = True
    knockout_reasons: List[str] = Field(default_factory=list)
    must_have_matched: List[str] = Field(default_factory=list)
    must_have_missing: List[str] = Field(default_factory=list)
    nice_to_have_matched: List[str] = Field(default_factory=list)
    nice_to_have_missing: List[str] = Field(default_factory=list)
    must_have_score: float = 0.0
    preferred_score: float = 0.0
    context_score: float = 0.0  # Skills validated in actual work experience
    recency_score: float = 0.0  # Recency in latest positions
    quantification_score: float = 0.0  # STAR / Metric quantification density
    seniority_score: float = 0.0  # Role hierarchy alignment
    ats_action_plan: List[str] = Field(default_factory=list)
    ats_breakdown: Dict[str, Any] = Field(default_factory=dict)

    def format_terminal_summary(self) -> str:
        status_icon = f"[{self.ats_verdict} ({self.ats_score}% ATS)]"
        lines = [
            f"{'='*60}",
            f"Job: {self.job_title} @ {self.company}",
            f"Location: {self.location} | Ref ID: {self.job_id or 'N/A'}",
            f"ATS Shortlist Verdict: {self.ats_verdict} (Score: {self.ats_score}%)",
            f"Knockout Filter: {'PASSED' if self.knockout_passed else 'FAILED'}",
            f"Experience Alignment: {'Matched' if self.experience_fit else 'Mismatch'} ({self.exp_required_text})",
            f"Must-Have Skills ({len(self.must_have_matched)}/{len(self.must_have_matched)+len(self.must_have_missing)}): {', '.join(self.must_have_matched) if self.must_have_matched else 'None'}",
            f"Missing Must-Haves: {', '.join(self.must_have_missing) if self.must_have_missing else 'None'}",
            f"Experience Context Proof: {self.context_score}% | STAR Metric Density: {self.quantification_score}%",
            f"Recommendation: {self.recommendation}",
        ]
        if self.ats_action_plan:
            lines.append("ATS Action Plan to Guarantee Shortlisting:")
            for plan in self.ats_action_plan:
                lines.append(f"  * {plan}")
        lines.append(f"{'='*60}")
        return "\n".join(lines)

