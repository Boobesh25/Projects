"""
Legacy entry point - redirects to modular 'analyzer' package.
"""

from analyzer import (
    JobPosting,
    MatchResult,
    CareerPageExtractor,
    JobMatcher,
    analyze_url,
    analyze_json_file
)

__all__ = [
    "JobPosting",
    "MatchResult",
    "CareerPageExtractor",
    "JobMatcher",
    "analyze_url",
    "analyze_json_file"
]

if __name__ == "__main__":
    from analyze import main
    main()
