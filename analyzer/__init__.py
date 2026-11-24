"""
Career Page Analyser Package
"""

import json
from pathlib import Path
from typing import Optional, Union, Dict, Any
from .models import JobPosting, MatchResult
from .extractor import CareerPageExtractor
from .matcher import JobMatcher
from .discovery import JobDiscoveryEngine
from .reporter import ExcelReportGenerator
from .ai_reasoner import AIReasoner

__all__ = [
    "JobPosting",
    "MatchResult",
    "CareerPageExtractor",
    "JobMatcher",
    "JobDiscoveryEngine",
    "ExcelReportGenerator",
    "AIReasoner",
    "analyze_url",
    "analyze_json_file"
]

def analyze_url(url: str, profile_path: str = "profile.yaml") -> Optional[MatchResult]:
    """Scrapes/extracts job from URL and matches against candidate profile."""
    job = CareerPageExtractor.extract_from_url(url)
    if not job:
        return None
    matcher = JobMatcher(profile_path=profile_path)
    return matcher.evaluate_job(job)

def analyze_json_file(file_path: Union[str, Path], profile_path: str = "profile.yaml") -> MatchResult:
    """Loads a structured JD JSON and evaluates match score."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    job = CareerPageExtractor.extract_from_json_dict(data, url=str(file_path))
    matcher = JobMatcher(profile_path=profile_path)
    return matcher.evaluate_job(job)

