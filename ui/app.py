"""
JobRadar Enterprise Console - Career Intelligence Portal
=========================================================
Aesthetic: Modern Enterprise Dark Cloud Console (High Density)
- Dark Slate Cloud Palette (#131722, #181D29, #1B202E, #222838, #333B4F)
- Top App Bar with Project Selector, Search Bar & Avatar 'S'
- Compact Sidebar with Active Highlight (#24324D / #8AB4F8)
- Candidate Profile & Email Docked at the Bottom of the Sidebar
- Dense Material Data Tables for Job Matches & Recommendations
- Zero Bloat, Fast Rerender, Professional Enterprise UX
"""

import os
import sys
import json
import time
import re
from typing import Dict, Any, List, Optional

# Ensure project root and core directories are on sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_current_dir)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)
_core_dir = os.path.join(_root_dir, "core")
if _core_dir not in sys.path:
    sys.path.insert(0, _core_dir)

import requests
import streamlit as st
import streamlit.components.v1 as components
import yaml

try:
    from core.company_crawler import CompanyService
    from core.ai_role_generator import AIRoleGenerator
    from core.pdf_report_generator import build_pdf_report
    from core.profile_optimizer import (
        sanitize_filename,
        compile_tailored_pdf,
        save_to_cloud_backup,
        compile_markdown_to_pdf,
        markdown_to_live_preview_html,
        get_candidate_base_markdown,
        prompt_enhance_document_with_gemini,
        clean_markdown_links
    )
except ImportError:
    from company_crawler import CompanyService
    from ai_role_generator import AIRoleGenerator
    from pdf_report_generator import build_pdf_report
    from profile_optimizer import (
        sanitize_filename,
        compile_tailored_pdf,
        save_to_cloud_backup,
        compile_markdown_to_pdf,
        markdown_to_live_preview_html,
        get_candidate_base_markdown,
        prompt_enhance_document_with_gemini,
        clean_markdown_links
    )

# Backend URL (configurable via session state, Streamlit Secrets, environment variable, or in-UI input)
if "api_base_url" not in st.session_state:
    env_api = os.getenv("API_BASE_URL")
    if not env_api:
        try:
            env_api = st.secrets.get("API_BASE_URL", "")
        except Exception:
            env_api = ""
    st.session_state.api_base_url = env_api.strip() if env_api else "http://localhost:8000"

API_BASE = st.session_state.api_base_url

# Page Config
st.set_page_config(
    page_title="JobRadar Console | Career Intelligence",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

def render_html(html_str: str):
    """
    Renders pure HTML in Streamlit safely.
    Strips leading and trailing whitespace from each line before joining,
    ensuring that Markdown parsers NEVER treat indented lines as code blocks (<pre><code>).
    """
    clean_html = "".join(line.strip() for line in html_str.strip().split("\n") if line.strip())
    st.markdown(clean_html, unsafe_allow_html=True)

def resolve_career_url(item: Optional[Dict[str, Any]], company_name: str) -> str:
    """
    Guarantees official direct requisition URL.
    Never returns third-party boards (Arbeitnow, Jobicy) as a Career Page.
    Never returns expired Naukri links.
    """
    if item:
        raw_url = item.get("job_apply_url") or item.get("url") or ""
        if raw_url and "google.com" not in raw_url:
            raw_low = raw_url.lower()
            if any(b in raw_low for b in ["arbeitnow.com", "jobicy.com", "remotive.com", "remoteok.com"]):
                return CompanyService.get_official_career_url(company_name)
            if "naukri.com" in raw_low and ("expjd=true" in raw_low or "job-listings-" in raw_low):
                title = item.get("title", "")
                return CompanyService.get_official_naukri_url(company_name, title)
            return raw_url
    return CompanyService.get_official_career_url(company_name)

def get_source_pill_html(channel: Optional[str]) -> str:
    """Renders a styled badge indicating the originating source channel."""
    ch = (channel or "Career Page").strip()
    ch_low = ch.lower()
    if "linkedin" in ch_low:
        return '<span class="source-pill-linkedin">LinkedIn</span>'
    elif "naukri" in ch_low:
        return '<span class="source-pill-naukri">Naukri</span>'
    else:
        return '<span class="source-pill-career">Career Page</span>'

# -----------------------------------------------------------------------------
# Enterprise Dark Theme CSS (High Density & Compact Size)
# -----------------------------------------------------------------------------
CONSOLE_THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&family=Google+Sans:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* Global Reset for High-Density Console */
html, body, [class*="css"] {
    font-family: 'Roboto', -apple-system, BlinkMacSystemFont, sans-serif !important;
    font-size: 13px !important;
    color: #E8EAED !important;
}

/* Backgrounds */
.stApp {
    background-color: #1B202E !important;
}

/* Main Container Padding Reduction */
.block-container {
    padding-top: 4.2rem !important;
    padding-bottom: 2rem !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    max-width: 100% !important;
}

@media screen and (max-width: 768px) {
    .block-container {
        padding-top: 3.8rem !important;
        padding-bottom: 1.5rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
    }
}

/* Header Container retaining native Sidebar Controls */
header[data-testid="stHeader"] {
    background-color: #161B26 !important;
    border-bottom: 1px solid #282D3B !important;
    height: 50px !important;
    min-height: 50px !important;
    z-index: 100000 !important;
    display: flex !important;
    align-items: center !important;
    padding: 0 12px !important;
    overflow: visible !important;
}

/* Header Brand Title */
header[data-testid="stHeader"]::after {
    content: "JobRadar Console";
    font-family: 'Google Sans', 'Roboto', sans-serif;
    font-size: 15px;
    font-weight: 600;
    color: #E8EAED;
    margin-left: 10px;
    display: inline-block;
}

/* Keep Toolbar active so native Sidebar Toggle is fully interactive */
div[data-testid="stToolbar"] {
    display: flex !important;
    visibility: visible !important;
    align-items: center !important;
    height: 100% !important;
}

/* Hide Streamlit dev menu & deploy buttons only, keep sidebar controls */
#MainMenu,
div[data-testid="stToolbarActions"],
div[data-testid="stDecoration"],
div[data-testid="stStatusWidget"],
footer {
    display: none !important;
}

/* Native Sidebar Expand/Collapse Controls - Always Touch-Friendly & Visible */
[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] {
    display: inline-flex !important;
    visibility: visible !important;
    align-items: center !important;
    justify-content: center !important;
    z-index: 100001 !important;
    pointer-events: auto !important;
}

[data-testid="stExpandSidebarButton"] button,
[data-testid="stSidebarCollapsedControl"] button,
[data-testid="collapsedControl"] button {
    background: #1A73E8 !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 6px !important;
    width: 36px !important;
    height: 36px !important;
    min-width: 36px !important;
    min-height: 36px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    cursor: pointer !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.3) !important;
}

[data-testid="stExpandSidebarButton"] button:hover,
[data-testid="stSidebarCollapsedControl"] button:hover {
    background: #1765CC !important;
    color: #FFFFFF !important;
}

/* Console Sidebar Styling */
section[data-testid="stSidebar"] {
    background-color: #161B26 !important;
    border-right: 1px solid #282D3B !important;
}
section[data-testid="stSidebar"] > div {
    padding-top: 0.8rem !important;
    padding-bottom: 0.8rem !important;
    padding-left: 0.8rem !important;
    padding-right: 0.8rem !important;
}

/* Console Nav Header in Sidebar */
.console-side-brand {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px 14px 10px;
    border-bottom: 1px solid #282D3B;
    margin-bottom: 12px;
}
.console-brand-icon {
    font-size: 1.3rem;
}
.console-brand-title {
    font-family: 'Google Sans', 'Roboto', sans-serif !important;
    font-size: 15px !important;
    font-weight: 600 !important;
    color: #E8EAED;
    letter-spacing: -0.01em;
}

/* Sidebar Radio Menu: Transform into Compact Console Menu Items */
div[data-testid="stRadio"] > div {
    display: flex;
    flex-direction: column;
    gap: 2px;
}
div[data-testid="stRadio"] label {
    background: transparent !important;
    border: 1px solid transparent !important;
    border-radius: 4px !important;
    padding: 7px 12px !important;
    margin: 0 !important;
    cursor: pointer !important;
    color: #BDC1C6 !important;
    font-size: 13px !important;
    font-weight: 400 !important;
    transition: background-color 0.15s ease, color 0.15s ease;
    display: flex !important;
    align-items: center !important;
}
div[data-testid="stRadio"] label:hover {
    background: rgba(255, 255, 255, 0.04) !important;
    color: #E8EAED !important;
}
/* Active Nav Item: Pill Highlight */
div[data-testid="stRadio"] label[data-checked="true"],
div[data-testid="stRadio"] input:checked + div {
    background: #24324D !important;
    border: 1px solid rgba(138, 180, 248, 0.25) !important;
    color: #8AB4F8 !important;
    font-weight: 500 !important;
}
/* Hide the small circle radio input element */
div[data-testid="stRadio"] label > div:first-child {
    display: none !important;
}

/* Docked User Profile Widget at Bottom of Sidebar */
.console-sidebar-user-dock {
    margin-top: 24px;
    padding: 12px;
    background: #1B202E;
    border: 1px solid #2D3345;
    border-radius: 8px;
    display: flex;
    align-items: center;
    gap: 10px;
}
.user-avatar-circle {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: #8430CE;
    color: #FFFFFF;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
    font-size: 13px;
    flex-shrink: 0;
}
.user-meta-name {
    font-weight: 500;
    color: #E8EAED;
    font-size: 12.5px;
    line-height: 1.2;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.user-meta-email {
    font-size: 11px;
    color: #9AA0A6;
    line-height: 1.2;
    margin-top: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.user-status-indicator {
    font-size: 10.5px;
    color: #81C995;
    margin-top: 3px;
    display: flex;
    align-items: center;
    gap: 4px;
}

/* Top App Bar (Spanning Top of Main Window) */
.console-top-bar {
    background: #161B26;
    border: 1px solid #282D3B;
    border-radius: 6px;
    height: 44px;
    padding: 0 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
}
.console-top-left {
    display: flex;
    align-items: center;
    gap: 12px;
}
.console-hamburger-btn {
    background: transparent;
    border: 1px solid #282D3B;
    border-radius: 4px;
    padding: 4px 6px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: #BDC1C6;
    transition: all 0.15s ease;
}
.console-hamburger-btn:hover {
    background: #202534;
    border-color: #8AB4F8;
    color: #FFFFFF;
}
.console-logo-title {
    font-family: 'Google Sans', 'Roboto', sans-serif;
    font-size: 15px;
    font-weight: 600;
    color: #E8EAED;
    letter-spacing: -0.01em;
}
.console-project-pill {
    background: #202534;
    border: 1px solid #363D4E;
    border-radius: 14px;
    padding: 3px 10px;
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11.5px;
    color: #BDC1C6;
}
.project-dot {
    width: 7px;
    height: 7px;
    background: #81C995;
    border-radius: 50%;
    display: inline-block;
}
.console-top-right {
    display: flex;
    align-items: center;
    gap: 14px;
}
.console-sys-status {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11.5px;
    color: #9AA0A6;
    background: #202534;
    border: 1px solid #2D3345;
    border-radius: 14px;
    padding: 3px 10px;
}
.console-user-dock-top {
    display: flex;
    align-items: center;
    gap: 8px;
}
.console-top-avatar {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: #1A73E8;
    color: #FFFFFF;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11.5px;
    font-weight: 600;
}
.console-user-email-top {
    font-size: 12px;
    color: #BDC1C6;
    font-weight: 400;
}

/* Breadcrumbs & Sub-Header */
.console-sub-header {
    margin-bottom: 16px;
}
.console-breadcrumb {
    font-size: 11.5px;
    color: #9AA0A6;
    margin-bottom: 4px;
}
.console-breadcrumb a {
    color: #8AB4F8;
    text-decoration: none;
}
.console-page-title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid #2B3141;
    padding-bottom: 12px;
    margin-bottom: 12px;
}
.console-title {
    font-family: 'Google Sans', 'Roboto', sans-serif;
    font-size: 19px;
    font-weight: 500;
    color: #E8EAED;
    letter-spacing: -0.01em;
}
.console-desc-text {
    font-size: 12.5px;
    color: #9AA0A6;
    margin-top: 2px;
}
.console-desc-text a {
    color: #8AB4F8;
    text-decoration: none;
}
.console-desc-text a:hover {
    text-decoration: underline;
}

/* Action Buttons */
.stButton > button {
    border-radius: 4px !important;
    font-size: 12.5px !important;
    font-weight: 500 !important;
    padding: 5px 14px !important;
    min-height: 32px !important;
    transition: all 0.15s ease !important;
}
.stButton > button[kind="primary"] {
    background: #1A73E8 !important;
    color: #FFFFFF !important;
    border: 1px solid transparent !important;
}
.stButton > button[kind="primary"]:hover {
    background: #1B66C9 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.3) !important;
}
.stButton > button[kind="secondary"] {
    background: #202534 !important;
    color: #BDC1C6 !important;
    border: 1px solid #363D4E !important;
}
.stButton > button[kind="secondary"]:hover {
    background: #272D3E !important;
    color: #E8EAED !important;
    border-color: #4B5569 !important;
}

/* Material Data Table Containers */
.console-table-container {
    background: #202534;
    border: 1px solid #2D3345;
    border-radius: 4px;
    margin-bottom: 20px;
    overflow-x: auto;
}
.console-table-header {
    padding: 10px 14px;
    border-bottom: 1px solid #2D3345;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.console-table-title {
    font-size: 14px;
    font-weight: 500;
    color: #E8EAED;
    display: flex;
    align-items: center;
    gap: 8px;
}
.console-table-counter {
    background: #293043;
    padding: 2px 7px;
    border-radius: 10px;
    font-size: 11px;
    color: #8AB4F8;
    font-weight: 500;
}

/* Dense Material Table Rows */
.console-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12.5px;
    text-align: left;
}
.console-table th {
    background: #1A1F2C;
    color: #9AA0A6;
    font-weight: 500;
    font-size: 11.5px;
    padding: 8px 12px;
    border-bottom: 1px solid #2D3345;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}
.console-table td {
    padding: 9px 12px;
    border-bottom: 1px solid #262B3B;
    color: #E8EAED;
    vertical-align: middle;
}
.console-table tr:hover td {
    background-color: #242A3A;
}

/* Status Badges with Pure CSS Dots */
.status-pill-green {
    background: rgba(129, 201, 149, 0.12);
    color: #81C995;
    border: 1px solid rgba(129, 201, 149, 0.3);
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
}
.status-pill-green::before {
    content: "";
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #81C995;
    margin-right: 5px;
}
.status-pill-yellow {
    background: rgba(253, 214, 99, 0.12);
    color: #FDD663;
    border: 1px solid rgba(253, 214, 99, 0.3);
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
}
.status-pill-yellow::before {
    content: "";
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #FDD663;
    margin-right: 5px;
}
.status-pill-red {
    background: rgba(242, 139, 130, 0.12);
    color: #F28B82;
    border: 1px solid rgba(242, 139, 130, 0.3);
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
}
.status-pill-red::before {
    content: "";
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #F28B82;
    margin-right: 5px;
}
.status-pill-purple {
    background: rgba(168, 85, 247, 0.12);
    color: #C084FC;
    border: 1px solid rgba(168, 85, 247, 0.3);
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
}
.status-pill-purple::before {
    content: "";
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #C084FC;
    margin-right: 5px;
}
.status-pill-gray {
    background: rgba(154, 160, 166, 0.12);
    color: #9AA0A6;
    border: 1px solid rgba(154, 160, 166, 0.3);
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    display: inline-flex;
    align-items: center;
}
.status-pill-gray::before {
    content: "";
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #9AA0A6;
    margin-right: 5px;
}

/* Source Channel Badges */
.source-pill-career {
    background: rgba(66, 133, 244, 0.12);
    color: #8AB4F8;
    border: 1px solid rgba(66, 133, 244, 0.3);
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    white-space: nowrap;
}
.source-pill-career::before {
    content: "";
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #8AB4F8;
    margin-right: 5px;
}
.source-pill-linkedin {
    background: rgba(10, 102, 194, 0.16);
    color: #70B5F9;
    border: 1px solid rgba(10, 102, 194, 0.4);
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    white-space: nowrap;
}
.source-pill-linkedin::before {
    content: "";
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #0A66C2;
    margin-right: 5px;
}
.source-pill-naukri {
    background: rgba(255, 122, 0, 0.14);
    color: #FF9E67;
    border: 1px solid rgba(255, 122, 0, 0.35);
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    white-space: nowrap;
}
.source-pill-naukri::before {
    content: "";
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #FF7A00;
    margin-right: 5px;
}

/* Skill Chips */
.chip-green {
    background: rgba(129, 201, 149, 0.1);
    color: #81C995;
    border: 1px solid rgba(129, 201, 149, 0.2);
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 11px;
    font-family: 'JetBrains Mono', monospace;
    margin-right: 4px;
    margin-bottom: 2px;
    display: inline-block;
}
.chip-red {
    background: rgba(242, 139, 130, 0.1);
    color: #F28B82;
    border: 1px solid rgba(242, 139, 130, 0.2);
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 11px;
    font-family: 'JetBrains Mono', monospace;
    margin-right: 4px;
    margin-bottom: 2px;
    display: inline-block;
}
.chip-purple {
    background: rgba(168, 85, 247, 0.1);
    color: #C084FC;
    border: 1px solid rgba(168, 85, 247, 0.2);
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 11px;
    font-family: 'JetBrains Mono', monospace;
    margin-right: 4px;
    margin-bottom: 2px;
    display: inline-block;
}

/* Metric KPI Mini Cards */
.console-metric-box {
    background: #202534;
    border: 1px solid #2D3345;
    border-radius: 4px;
    padding: 10px 14px;
}
.console-metric-val {
    font-size: 20px;
    font-weight: 600;
    color: #E8EAED;
}
.console-metric-lbl {
    font-size: 11px;
    color: #9AA0A6;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-top: 2px;
}

/* Career Job ID Pill Badge */
.job-id-pill {
    background: rgba(26, 115, 232, 0.12);
    color: #8AB4F8 !important;
    border: 1px solid rgba(138, 180, 248, 0.35);
    padding: 3px 8px;
    border-radius: 4px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 600;
    text-decoration: none !important;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    white-space: nowrap;
    transition: all 0.15s ease;
}
.job-id-pill:hover {
    background: rgba(26, 115, 232, 0.25);
    border-color: #8AB4F8;
    color: #FFFFFF !important;
    text-decoration: underline !important;
}

/* Direct Job Apply Button */
.btn-direct-apply {
    background: #1A73E8;
    color: #FFFFFF !important;
    padding: 5px 12px;
    border-radius: 4px;
    font-size: 11.5px;
    font-weight: 500;
    text-decoration: none !important;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    white-space: nowrap;
    border: 1px solid #1A73E8;
    transition: all 0.15s ease;
}
.btn-direct-apply:hover {
    background: #1B66C9;
    border-color: #1B66C9;
    color: #FFFFFF !important;
}

/* Deep Analyse & Optimize Button */
.btn-deep-tailor {
    background: #1E3A8A;
    color: #FFFFFF !important;
    padding: 5px 11px;
    border-radius: 4px;
    font-size: 11.5px;
    font-weight: 500;
    text-decoration: none !important;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    white-space: nowrap;
    border: 1px solid #3B82F6;
    margin-left: 6px;
    transition: all 0.15s ease;
}
.btn-deep-tailor:hover {
    background: #2563EB;
    border-color: #60A5FA;
    color: #FFFFFF !important;
}

/* Framing Opportunity Callout Card */
.framing-card {
    background: rgba(30, 58, 138, 0.2);
    border: 1px solid #3B82F6;
    border-radius: 6px;
    padding: 14px 18px;
    margin-bottom: 16px;
}
.framing-badge {
    background: #2563EB;
    color: #FFFFFF;
    font-size: 10.5px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 3px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    display: inline-block;
    margin-bottom: 6px;
}
.framing-item {
    background: #202534;
    border: 1px solid #2D3345;
    border-radius: 4px;
    padding: 10px 14px;
    margin-top: 8px;
}

/* Streamlit Inputs Dark Material styling */
div[data-baseweb="select"] > div {
    background-color: #202534 !important;
    border-color: #363D4E !important;
    border-radius: 4px !important;
    font-size: 13px !important;
    color: #E8EAED !important;
}
div[data-baseweb="input"] > div {
    background-color: #202534 !important;
    border-color: #363D4E !important;
    border-radius: 4px !important;
    font-size: 13px !important;
    color: #E8EAED !important;
}

/* ATS Document Paper Preview Sheet (Live Render) */
.ats-preview-sheet {
    background: #FFFFFF !important;
    color: #0F172A !important;
    border-radius: 4px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
    padding: 30px 34px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 11.5px;
    line-height: 1.5;
    border: 1px solid #CBD5E1;
    max-height: 850px;
    overflow-y: auto;
}
.ats-preview-header-bar {
    background: #EFF6FF;
    border: 1px solid #BFDBFE;
    border-radius: 3px;
    padding: 5px 8px;
    text-align: center;
    font-size: 9.5px;
    font-weight: 700;
    color: #1D4ED8;
    letter-spacing: 0.05em;
    margin-bottom: 14px;
}
.ats-name {
    font-size: 18px;
    font-weight: 700;
    color: #0F172A;
    text-align: center;
    margin: 0 0 3px 0;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
.ats-contact-line {
    font-size: 10px;
    color: #475569;
    text-align: center;
    margin-bottom: 8px;
}
.ats-hr {
    border: none;
    border-top: 1px solid #CBD5E1;
    margin: 8px 0;
}
.ats-section-title {
    font-size: 11px;
    font-weight: 700;
    color: #1E3A8A;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-top: 12px;
    margin-bottom: 4px;
    border-bottom: 1px solid #CBD5E1;
    padding-bottom: 2px;
}
.ats-job-header {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    font-weight: 700;
    color: #0F172A;
    margin-top: 7px;
    margin-bottom: 2px;
}
.ats-bullet {
    display: flex;
    align-items: flex-start;
    margin-bottom: 3.5px;
    font-size: 10.8px;
    color: #334155;
    line-height: 1.45;
}
.ats-bullet-dot {
    margin-right: 6px;
    color: #1E3A8A;
    font-size: 9px;
    line-height: 1.5;
}
.ats-body-p {
    font-size: 10.8px;
    color: #334155;
    margin: 3px 0 6px 0;
    line-height: 1.45;
}

/* =========================================================================
   Mobile Viewport Responsive Alignment & Controls (< 768px)
   ========================================================================= */
@media screen and (max-width: 768px) {
    /* Mobile main container margins & padding */
    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.6rem !important;
        padding-right: 0.6rem !important;
        max-width: 100% !important;
    }

    /* Top App Bar on Mobile */
    .console-top-bar {
        height: auto !important;
        min-height: 44px !important;
        padding: 6px 10px !important;
        flex-wrap: wrap !important;
        gap: 6px !important;
        margin-bottom: 12px !important;
    }
    .console-project-pill {
        display: none !important;
    }
    .console-user-email-top {
        display: none !important;
    }
    .console-logo-title {
        font-size: 14px !important;
    }
    .console-hamburger-btn {
        width: 36px !important;
        height: 36px !important;
        min-width: 36px !important;
        min-height: 36px !important;
    }

    /* Streamlit Columns responsive stacking on Mobile */
    [data-testid="column"] {
        width: 100% !important;
        flex: 1 1 100% !important;
        min-width: 100% !important;
        margin-bottom: 6px !important;
    }

    /* Metric Boxes Grid on Mobile (2 per row instead of 6 squished columns) */
    [data-testid="stHorizontalBlock"]:has(.console-metric-box) {
        display: grid !important;
        grid-template-columns: repeat(2, 1fr) !important;
        gap: 6px !important;
    }
    [data-testid="stHorizontalBlock"]:has(.console-metric-box) > div {
        width: 100% !important;
        min-width: 0 !important;
    }
    .console-metric-box {
        padding: 8px 10px !important;
        margin-bottom: 4px !important;
    }
    .console-metric-val {
        font-size: 1.2rem !important;
    }
    .console-metric-lbl {
        font-size: 10px !important;
    }

    /* Responsive Data Tables with smooth horizontal touch-scrolling */
    .console-table-wrap,
    .console-table-container,
    .job-table-wrap,
    table {
        display: block !important;
        width: 100% !important;
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch !important;
    }

    /* Action buttons: full-width and touch-friendly */
    .stButton > button {
        width: 100% !important;
        min-height: 40px !important;
        font-size: 13px !important;
    }

    /* Mobile Sidebar overlay */
    section[data-testid="stSidebar"] {
        width: 85vw !important;
        max-width: 320px !important;
        box-shadow: 4px 0 20px rgba(0,0,0,0.7) !important;
    }

    /* Page title & subheader */
    .console-title {
        font-size: 16px !important;
    }
    .console-page-title-row {
        flex-direction: column !important;
        align-items: flex-start !important;
        gap: 6px !important;
    }
    .console-desc-text {
        font-size: 11.5px !important;
    }
}

/* In-Column Table Filters Compact Alignment */
div[data-testid="column"] div[data-testid="stTextInput"] input,
div[data-testid="column"] div[data-testid="stSelectbox"] div[data-baseweb="select"] {
    background-color: #151A26 !important;
    border: 1px solid #28354E !important;
    border-radius: 4px !important;
    font-size: 11.5px !important;
    color: #E8EAED !important;
    height: 32px !important;
    min-height: 32px !important;
}
div[data-testid="column"] div[data-testid="stTextInput"] input:focus,
div[data-testid="column"] div[data-testid="stSelectbox"] div[data-baseweb="select"]:focus-within {
    border-color: #4285F4 !important;
    box-shadow: 0 0 0 1px #4285F4 !important;
}
div[data-testid="column"] div[data-testid="stTextInput"],
div[data-testid="column"] div[data-testid="stSelectbox"] {
    margin-bottom: 3px !important;
}

/* 3/4 Screen Modal for Job Details & Complete JD */
.jd-modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(10, 14, 22, 0.85);
    backdrop-filter: blur(6px);
    z-index: 9999999;
    display: none;
    align-items: center;
    justify-content: center;
    padding: 24px;
    box-sizing: border-box;
}
.jd-modal-overlay:target {
    display: flex !important;
}
.jd-modal-backdrop {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 1;
    cursor: default;
}
.jd-modal-box {
    position: relative;
    z-index: 2;
    width: 75vw !important;
    max-width: 75vw !important;
    max-height: 85vh !important;
    background: #171C28 !important;
    border: 1px solid #28354E !important;
    border-radius: 8px !important;
    padding: 24px 28px !important;
    overflow-y: auto !important;
    box-shadow: 0 16px 50px rgba(0, 0, 0, 0.85) !important;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: 14px;
}
@media screen and (max-width: 900px) {
    .jd-modal-box {
        width: 94vw !important;
        max-width: 94vw !important;
        padding: 16px !important;
    }
}
.jd-modal-header {
    border-bottom: 1px solid #28354E;
    padding-bottom: 12px;
}
.jd-modal-close {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid #374151;
    color: #E8EAED !important;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 15px;
    font-weight: 700;
    text-decoration: none !important;
    transition: all 0.2s ease;
    cursor: pointer;
    flex-shrink: 0;
}
.jd-modal-close:hover {
    background: #DC2626;
    border-color: #EF4444;
    color: #FFFFFF !important;
    transform: scale(1.1);
}
.role-info-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: rgba(66, 133, 244, 0.16);
    color: #8AB4F8 !important;
    border: 1px solid rgba(138, 180, 248, 0.35);
    font-size: 11px;
    font-weight: 700;
    text-decoration: none !important;
    margin-left: 6px;
    transition: all 0.15s ease;
    vertical-align: middle;
    cursor: pointer;
    flex-shrink: 0;
}
.role-info-icon:hover {
    background: #1A73E8;
    color: #FFFFFF !important;
    border-color: #8AB4F8;
    transform: scale(1.15);
}
.jd-meta-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid #28354E;
    border-radius: 6px;
    padding: 12px 16px;
}
@media screen and (max-width: 768px) {
    .jd-meta-grid {
        grid-template-columns: repeat(2, 1fr);
    }
}
.jd-meta-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
}
.jd-meta-label {
    font-size: 10px;
    color: #9AA0A6;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.jd-meta-value {
    font-size: 12.5px;
    font-weight: 500;
    color: #E8EAED;
}
.jd-raw-text {
    white-space: pre-wrap;
    font-family: 'Roboto', sans-serif;
    font-size: 12px;
    line-height: 1.6;
    color: #D1D5DB;
    background: #111622;
    border: 1px solid #232B3E;
    border-radius: 6px;
    padding: 16px 20px;
    max-height: 380px;
    overflow-y: auto;
}
</style>
"""
render_html(CONSOLE_THEME_CSS)

# -----------------------------------------------------------------------------
# Session State Initialization
# -----------------------------------------------------------------------------
DEFAULT_USER_EMAIL = os.getenv("DEFAULT_USER_EMAIL")
if not DEFAULT_USER_EMAIL:
    try:
        DEFAULT_USER_EMAIL = st.secrets.get("DEFAULT_USER_EMAIL", "boobesh2509@gmail.com")
    except Exception:
        DEFAULT_USER_EMAIL = "boobesh2509@gmail.com"

if "token" not in st.session_state:
    st.session_state.token = None
if "user_info" not in st.session_state:
    st.session_state.user_info = None
if "is_onboarded" not in st.session_state:
    st.session_state.is_onboarded = False
if "daily_jobs" not in st.session_state:
    st.session_state.daily_jobs = []
if "daily_groups" not in st.session_state:
    st.session_state.daily_groups = ["All"]
if "daily_companies" not in st.session_state:
    st.session_state.daily_companies = []
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None

# Auto-authenticate single designated enterprise user unless explicitly logged out
if not st.session_state.token and not st.session_state.get("logged_out"):
    try:
        r_auth = requests.post(f"{API_BASE}/api/auth/dev-login", json={"email": DEFAULT_USER_EMAIL}, timeout=5)
        if r_auth.status_code == 200:
            auth_data = r_auth.json()
            st.session_state.token = auth_data.get("token")
            st.session_state.user_info = auth_data
            st.session_state.is_onboarded = auth_data.get("is_onboarded", True)
    except Exception:
        pass

def get_auth_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}

def load_daily_companies(target_count: int = 5000, force_refresh: bool = False):
    try:
        url = f"{API_BASE}/api/companies?count={target_count}"
        if force_refresh:
            url += "&refresh=true"
        r = requests.get(url, headers=get_auth_headers(), timeout=25)
        if r.status_code == 200:
            data = r.json()
            st.session_state.daily_jobs = data.get("jobs", [])
            st.session_state.daily_groups = data.get("available_groups", ["All"])
            st.session_state.daily_companies = data.get("available_companies", [])
            st.session_state.daily_channels = data.get("available_channels", ["All", "Career Page", "LinkedIn", "Naukri"])
    except Exception:
        pass

# -----------------------------------------------------------------------------
# Component: Deep Analysis & Document Tailoring Workbench (Split-Screen Mode)
# -----------------------------------------------------------------------------
def render_deep_analysis_tab(user_email: str, user_name: str):
    st.markdown("<div style='font-size: 15px; font-weight: 500; color: #E8EAED; margin-bottom: 2px;'>Document Tailoring & Split-Screen Live Editor</div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size: 12px; color: #9AA0A6; margin-bottom: 14px;'>Interactive side-by-side workbench: modify your authentic existing document with AI prompting and direct editing on the left, while watching the live ATS document preview update in real-time on the right.</div>", unsafe_allow_html=True)

    # 1. Collect analyzed jobs
    res = st.session_state.analysis_results
    if not res:
        try:
            with st.spinner("Evaluating profile against active requisitions..."):
                r = requests.post(f"{API_BASE}/api/analyze", json={"selected_group": "All"}, headers=get_auth_headers(), timeout=35)
                if r.status_code == 200:
                    st.session_state.analysis_results = r.json()
                    res = st.session_state.analysis_results
        except Exception:
            pass

    all_jobs = []
    if res:
        all_jobs = res.get("exact_matches", []) + res.get("action_needed", []) + res.get("cross_domain", []) + res.get("divergent", [])
    if not all_jobs and st.session_state.daily_jobs:
        all_jobs = [j for j in st.session_state.daily_jobs if j.get("job_id") != "NO-ROLE-FOUND"]

    # Determine default selected job
    selected_jid = st.session_state.get("selected_tailor_job_id")
    if selected_jid and not any(j.get("job_id") == selected_jid for j in all_jobs):
        matched_in_daily = [j for j in (st.session_state.daily_jobs or []) if j.get("job_id") == selected_jid]
        if matched_in_daily:
            all_jobs = matched_in_daily + all_jobs
        else:
            try:
                r_comp = requests.get(f"{API_BASE}/api/companies?count=5000", headers=get_auth_headers(), timeout=10)
                if r_comp.status_code == 200:
                    d_jobs = r_comp.json().get("jobs", [])
                    st.session_state.daily_jobs = d_jobs
                    matched = [j for j in d_jobs if j.get("job_id") == selected_jid]
                    if matched:
                        all_jobs = matched + all_jobs
            except Exception:
                pass

    if not all_jobs:
        st.warning("No analyzed jobs available. Please go to 'Results & Recommendations' or 'Analyse Companies' and run an analysis first.")
        return

    default_idx = 0
    job_options = []
    for idx, j in enumerate(all_jobs):
        jid = j.get("job_id", f"JOB-{idx}")
        label = f"[{j.get('match_score', 0)}%] {j.get('company_name')} — {j.get('title')} (#{jid})"
        job_options.append((label, j))
        if selected_jid and jid == selected_jid:
            default_idx = idx

    selected_tuple = st.selectbox(
        "Target Requisition for Document Tailoring",
        options=job_options,
        index=default_idx,
        format_func=lambda x: x[0],
        help="Select any target role from your matches to tailor your existing document."
    )
    selected_job = selected_tuple[1]
    j_id = selected_job.get("job_id", "N/A")
    st.session_state.selected_tailor_job_id = j_id

    # Target Job Context Card
    j_title = selected_job.get("title", "Target Position")
    j_comp = selected_job.get("company_name", "Target Company")
    j_group = selected_job.get("company_group", "MNC")
    j_chan = selected_job.get("source_channel") or CompanyService.get_channel_from_url(selected_job.get("job_apply_url", ""))
    j_score = selected_job.get("match_score", 0.0)
    j_loc = selected_job.get("location", "Global")
    j_mode = selected_job.get("work_mode", "Remote")
    j_exp = selected_job.get("experience_asked", "N/A")
    j_url = selected_job.get("job_apply_url") or selected_job.get("url") or "#"

    score_color = "#81C995" if j_score >= 75 else ("#FDD663" if j_score >= 60 else "#F28B82")
    source_pill = get_source_pill_html(j_chan)

    job_card_html = f"""
    <div style="background: #202534; border: 1px solid #2D3345; border-radius: 6px; padding: 12px 16px; margin-bottom: 14px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
            <div>
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 2px;">
                    {source_pill}
                    <span class="status-pill-gray">{j_group}</span>
                    <span style="font-size: 11px; color: #9AA0A6;">#{j_id}</span>
                    <span style="font-size: 11px; color: #9AA0A6;">• {j_loc} • {j_mode} • Exp: {j_exp}</span>
                </div>
                <div style="font-size: 14.5px; font-weight: 600; color: #FFFFFF;">
                    {j_title} &nbsp;<span style="color: #8AB4F8; font-weight: 500;">@ {j_comp}</span>
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 14px;">
                <div style="text-align: right;">
                    <span style="font-size: 10px; color: #9AA0A6; text-transform: uppercase;">Alignment</span>
                    <div style="font-size: 19px; font-weight: 700; color: {score_color}; line-height: 1;">{j_score}%</div>
                </div>
                <a href="{j_url}" target="_blank" class="btn-direct-apply" style="font-size: 11px;" title="Direct Requisition Link #{j_id}">
                    View Requisition #{j_id} ↗
                </a>
            </div>
        </div>
    </div>
    """
    render_html(job_card_html)

    # Load candidate's authentic base document into session state for this job
    doc_state_key = f"active_doc_md_{j_id}"
    cur_doc = st.session_state.get(doc_state_key, "")
    if not cur_doc or "Targeted Focus (" in cur_doc or "(tel:" in cur_doc or "[+" in cur_doc:
        base_md = ""
        try:
            r = requests.get(f"{API_BASE}/api/profile/markdown", headers=get_auth_headers(), timeout=5)
            if r.status_code == 200:
                base_md = r.json().get("markdown", "")
        except Exception:
            pass
        if not base_md:
            base_md = get_candidate_base_markdown(user_email, "")
        st.session_state[doc_state_key] = clean_markdown_links(base_md)

    # Fetch framing analysis to guide user
    cache_key = f"tailor_analysis_{j_id}"
    if cache_key not in st.session_state:
        try:
            r = requests.post(
                f"{API_BASE}/api/tailor/analyze",
                json={"job_data": selected_job, "api_key": st.session_state.get("user_gemini_key")},
                headers=get_auth_headers(),
                timeout=15
            )
            if r.status_code == 200:
                st.session_state[cache_key] = r.json()
        except Exception:
            pass

    analysis_data = st.session_state.get(cache_key, {})
    framing_opps = analysis_data.get("framing_opportunities", [])

    # Top Gemini Key & Framing Hints Bar
    with st.expander("Gemini 2.0 Flash Configuration & Framing Advice", expanded=bool(framing_opps)):
        col_k1, col_k2 = st.columns([3, 1])
        with col_k1:
            entered_key = st.text_input(
                "Gemini API Key",
                value=st.session_state.get("user_gemini_key", ""),
                type="password",
                placeholder="Paste Gemini API Key (starts with AIza...)",
                key=f"api_key_input_{j_id}"
            )
        with col_k2:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            if st.button("Save API Key", use_container_width=True, type="secondary", key=f"save_k_{j_id}"):
                if entered_key.strip():
                    try:
                        r = requests.post(f"{API_BASE}/api/user/api-key", json={"api_key": entered_key.strip()}, headers=get_auth_headers(), timeout=5)
                        if r.status_code == 200:
                            st.session_state.user_gemini_key = entered_key.strip()
                            st.success("Gemini API Key saved.")
                    except Exception as e:
                        st.error(f"Error: {e}")

        if framing_opps:
            opp_text = " • ".join([f"<b>{f['candidate_skill']}</b> ➔ expose as <b>{f['jd_skill']}</b>" for f in framing_opps])
            render_html(f"""
            <div style="background: rgba(30, 58, 138, 0.25); border: 1px solid #3B82F6; border-radius: 4px; padding: 10px 14px; margin-top: 8px;">
                <span class="framing-badge">Semantic Framing Opportunities</span>
                <div style="font-size: 11.5px; color: #E8EAED; margin-top: 4px;">{opp_text}</div>
                <div style="font-size: 11px; color: #9AA0A6; margin-top: 2px;">Your profile already has verified competency in these areas. Use the prompt box below or click 'Auto-Apply Framing Synonyms' to update your document wording.</div>
            </div>
            """)

    # -------------------------------------------------------------------------
    # SPLIT SCREEN LAYOUT: Left Editor & Prompting | Right Live View Preview
    # -------------------------------------------------------------------------
    col_editor, col_preview = st.columns([1.06, 1.14], gap="large")

    sanitized_portal = (j_chan or "Career_Page").replace(" ", "_")
    sanitized_filename = sanitize_filename(j_title, j_comp, sanitized_portal)

    with col_editor:
        st.markdown("<div style='font-size: 13.5px; font-weight: 500; color: #8AB4F8; margin-bottom: 2px;'>Document Intelligence & Conversational ATS Agent</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-size: 11px; color: #9AA0A6; margin-bottom: 8px;'>Interactive AI assistant for <b>{j_title}</b> at <b>{j_comp}</b>. Ask questions, request ATS suggestions, or instruct document edits.</div>", unsafe_allow_html=True)

        # 1. Action Toolbar: Download PDF, Save to Drive, Reset
        col_act1, col_act2, col_act3 = st.columns([1.1, 1.3, 0.8])
        with col_act1:
            if st.button("Download Tailored PDF", type="primary", use_container_width=True, key=f"dl_pdf_btn_{j_id}"):
                with st.spinner("Compiling ATS PDF..."):
                    try:
                        pdf_bytes = compile_markdown_to_pdf(
                            md_text=st.session_state.get(doc_state_key, ""),
                            role_title=j_title,
                            company_name=j_comp,
                            portal=sanitized_portal
                        )
                        st.download_button(
                            label=f"Click to Save {sanitized_filename}",
                            data=pdf_bytes,
                            file_name=sanitized_filename,
                            mime="application/pdf",
                            type="primary",
                            use_container_width=True,
                            key=f"dl_actual_pdf_{j_id}"
                        )
                    except Exception as e:
                        st.error(f"PDF Error: {e}")

        with col_act2:
            if st.button("Save to Google Drive Backup", type="secondary", use_container_width=True, key=f"gdrive_save_btn_{j_id}"):
                with st.spinner("Syncing to Google Drive via Server API..."):
                    try:
                        r = requests.post(
                            f"{API_BASE}/api/tailor/drive-upload",
                            json={
                                "markdown_text": st.session_state.get(doc_state_key, ""),
                                "role_title": j_title,
                                "company_name": j_comp,
                                "portal": sanitized_portal
                            },
                            headers=get_auth_headers(),
                            timeout=45
                        )
                        if r.status_code == 200:
                            meta = r.json()
                            st.session_state[f"last_gdrive_meta_{j_id}"] = meta
                            st.rerun()
                        else:
                            st.error(f"Server upload error: {r.text}")
                    except Exception as e:
                        st.error(f"Google Drive Save Error: {e}")

        with col_act3:
            if st.button("Reset Document", type="secondary", use_container_width=True, key=f"reset_doc_{j_id}"):
                base_md = get_candidate_base_markdown(user_email, "")
                st.session_state[doc_state_key] = clean_markdown_links(base_md)
                st.info("Reset to authentic base document.")
                st.rerun()

        # Google Drive status card if upload was initiated
        meta = st.session_state.get(f"last_gdrive_meta_{j_id}")
        if meta:
            if meta.get("drive_status") == "success":
                st.success(f"Synced directly to Google Drive folder '{meta.get('drive_folder_name')}'!")
                f_url = meta.get("drive_file_url") or "#"
                d_url = meta.get("drive_folder_url") or "#"
                st.markdown(f"""
                <div style="background: rgba(30, 58, 138, 0.25); border: 1px solid #3B82F6; border-radius: 6px; padding: 10px 14px; margin-top: 6px; margin-bottom: 10px;">
                    <div style="font-size: 12.5px; font-weight: 600; color: #8AB4F8; margin-bottom: 4px;">Google Drive Cloud Document Ready</div>
                    <div style="font-size: 11px; color: #E8EAED; margin-bottom: 8px;">
                        Folder: <b>{meta.get('drive_folder_name')}</b><br>
                        File: <code>{meta.get('filename')}</code>
                    </div>
                    <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                        <a href="{f_url}" target="_blank" class="btn-direct-apply" style="font-size: 11px; text-decoration: none;">
                            View File in Drive ↗
                        </a>
                        <a href="{d_url}" target="_blank" class="btn-direct-apply" style="font-size: 11px; background: #334155; text-decoration: none;">
                            Open Drive Folder ↗
                        </a>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            elif meta.get("drive_status") == "needs_auth":
                st.warning("Google Drive authentication required for direct cloud synchronization.")

        # 2. Strategic Prompts Pills
        st.markdown("<div style='font-size: 11px; font-weight: 500; color: #9AA0A6; margin-top: 8px; margin-bottom: 4px;'>Quick Strategy Actions:</div>", unsafe_allow_html=True)
        qcol1, qcol2 = st.columns(2)
        with qcol1:
            btn_ats = st.button("Improve ATS Score Strategy", key=f"q_ats_{j_id}", use_container_width=True)
            btn_syn = st.button("Apply Framing Synonyms", key=f"q_syn_{j_id}", use_container_width=True)
        with qcol2:
            btn_gap = st.button("Show Missing Technical Skills", key=f"q_gap_{j_id}", use_container_width=True)
            btn_sum = st.button(f"Tune Summary for {j_comp}", key=f"q_sum_{j_id}", use_container_width=True)

        # 3. Chat History Container
        chat_key = f"chat_history_{j_id}"
        if chat_key not in st.session_state or not st.session_state[chat_key]:
            matched_str = ", ".join(analysis_data.get("matched_skills", [])[:6]) or "Python, FastAPI, RAG"
            missing_str = ", ".join(analysis_data.get("missing_skills", [])[:5]) or "None detected"
            welcome_content = (
                f"Hello! I am your **JobRadar Career & ATS Optimization Agent** for **{j_title}** at **{j_comp}** ({j_chan}).\n\n"
                f"### Requisition Match & ATS Diagnosis\n"
                f"- **Alignment Score**: **{j_score}%**\n"
                f"- **Verified Passing Keywords**: `{matched_str}`\n"
                f"- **High-Impact Missing Keywords**: `{missing_str}`\n\n"
                f"### How I Can Help You\n"
                f"1. **ATS Score Strategy**: Ask me how to maximize your score and what corporate ATS parsers look for.\n"
                f"2. **Keyword Optimization**: Tell me *'Add ChromaDB to technical skills'* or *'Include Docker'*, and I will place it under **Core Technical Skills**.\n"
                f"3. **Company Alignment**: I can tailor your summary or highlight Corent Technology achievements for {j_comp}.\n\n"
                f"Ask me any question below, or click one of the quick strategy prompts!"
            )
            st.session_state[chat_key] = [
                {"role": "assistant", "content": welcome_content}
            ]

        chat_container = st.container(height=340)
        with chat_container:
            for msg in st.session_state[chat_key]:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

        # 4. Chat Input & Real-Time Streaming
        user_prompt = st.chat_input("Ask about this JD, request ATS advice, or instruct edits (e.g. 'Add ChromaDB')...", key=f"chat_in_{j_id}")
        
        action_prompt = None
        if btn_ats:
            action_prompt = "How can I improve my ATS score for this role?"
        elif btn_gap:
            action_prompt = "What skills are missing in my profile for this requisition?"
        elif btn_syn:
            action_prompt = "Apply framing synonyms to improve ATS keyword matching."
        elif btn_sum:
            action_prompt = f"Tune my professional summary for {j_comp}."

        prompt_to_run = user_prompt or action_prompt
        if prompt_to_run:
            st.session_state[chat_key].append({"role": "user", "content": prompt_to_run})
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(prompt_to_run)
                
                with st.chat_message("assistant"):
                    payload = {
                        "message": prompt_to_run,
                        "history": [{"role": m["role"], "content": m["content"]} for m in st.session_state[chat_key][:-1]],
                        "job_data": selected_job,
                        "existing_markdown": st.session_state.get(doc_state_key, ""),
                        "api_key": st.session_state.get("user_gemini_key")
                    }

                    def _api_stream():
                        r = requests.post(f"{API_BASE}/api/tailor/chat", json=payload, headers=get_auth_headers(), stream=True, timeout=60)
                        if r.status_code != 200:
                            yield f"Server Error: {r.text}"
                            return
                        doc_tag = "<<<UPDATED_DOCUMENT>>>"
                        end_tag = "<<<END_UPDATED_DOCUMENT>>>"
                        buf = ""
                        in_doc = False
                        doc_buf = ""
                        for chunk in r.iter_content(chunk_size=64, decode_unicode=True):
                            if not chunk:
                                continue
                            buf += chunk
                            if not in_doc:
                                if doc_tag in buf:
                                    in_doc = True
                                    parts = buf.split(doc_tag, 1)
                                    yield parts[0]
                                    doc_buf = parts[1]
                                else:
                                    yield chunk
                            else:
                                doc_buf += chunk
                        if in_doc and doc_buf:
                            new_doc = doc_buf.split(end_tag)[0].strip()
                            if new_doc:
                                st.session_state["_pending_new_doc"] = new_doc

                    reply_text = st.write_stream(_api_stream())
                    st.session_state[chat_key].append({"role": "assistant", "content": reply_text})
                    
                    if "_pending_new_doc" in st.session_state:
                        st.session_state[doc_state_key] = clean_markdown_links(st.session_state.pop("_pending_new_doc"))
                        st.rerun()

        # 5. Hidden-by-default Manual Markdown Editor
        st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
        show_manual = st.checkbox("Manual Edit (Show Markdown Source)", value=False, key=f"manual_edit_{j_id}")
        if show_manual:
            st.markdown("<div style='font-size: 11px; color: #9AA0A6; margin-bottom: 2px;'><b>Markdown Source Editor</b> (Direct manual edits reflect in live preview immediately):</div>", unsafe_allow_html=True)
            cur_md = st.session_state.get(doc_state_key, "")
            direct_text = st.text_area("Markdown Source", value=cur_md, height=360, key=f"manual_text_{j_id}", label_visibility="collapsed")
            if direct_text != cur_md:
                st.session_state[doc_state_key] = direct_text
                st.rerun()

    with col_preview:
        live_header_html = """
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div>
                <span style="font-size: 13.5px; font-weight: 500; color: #81C995;">Live ATS Document Preview</span>
                <span style="font-size: 11px; color: #9AA0A6; margin-left: 6px;">(Real-Time Render)</span>
            </div>
            <span class="status-pill-green" style="font-size: 10px;">Live Sync Active</span>
        </div>
        """
        render_html(live_header_html)

        active_md = st.session_state.get(doc_state_key, "")
        preview_html = markdown_to_live_preview_html(
            md_text=active_md,
            role_title=j_title,
            company_name=j_comp,
            portal=sanitized_portal
        )
        render_html(preview_html)

# -----------------------------------------------------------------------------
# Auth / Sign-In View (JobRadar Console Style)
# -----------------------------------------------------------------------------
def render_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        login_header = """
        <div style="text-align: center; margin-bottom: 20px;">
            <div style="display: inline-flex; align-items: center; justify-content: center; width: 44px; height: 44px; background: #1A73E8; border-radius: 6px; margin-bottom: 12px; font-weight: 700; color: #FFFFFF; font-size: 16px; letter-spacing: 0.05em;">
                JR
            </div>
            <div style="font-family: 'Google Sans', sans-serif; font-size: 1.6rem; font-weight: 600; color: #E8EAED;">
                JobRadar Console
            </div>
            <div style="font-size: 12.5px; color: #9AA0A6; margin-top: 4px;">
                Authorized Account Sign In
            </div>
        </div>
        """
        render_html(login_header)

        with st.container(border=True):
            st.markdown("<div style='font-weight: 500; font-size: 14px; margin-bottom: 4px;'>Enterprise Account Login</div>", unsafe_allow_html=True)
            st.markdown("<div style='font-size: 12px; color: #9AA0A6; margin-bottom: 14px;'>Only pre-authorized email accounts can access this console. New users must be added by the administrator.</div>", unsafe_allow_html=True)
            
            with st.form("signin_form"):
                email = st.text_input("Account Email", value="", placeholder="Enter your authorized email (e.g. name@domain.com)")
                submitted = st.form_submit_button("Sign In to Console", use_container_width=True, type="primary")
                if submitted:
                    clean_email = (email or "").strip().lower()
                    if not clean_email:
                        st.error("Please enter your account email.")
                    else:
                        active_api = st.session_state.get("api_base_url", API_BASE).rstrip("/")
                        try:
                            r = requests.post(f"{active_api}/api/auth/dev-login", json={"email": clean_email}, timeout=8)
                            if r.status_code == 200:
                                data = r.json()
                                st.session_state.token = data["token"]
                                st.session_state.user_info = data
                                st.session_state.is_onboarded = data["is_onboarded"]
                                st.session_state.logged_out = False
                                st.session_state.onboard_yaml = None
                                st.session_state.onboard_meta = None
                                st.session_state.reupload_yaml = None
                                st.session_state.reupload_meta = None
                                st.session_state.analysis_results = None
                                st.session_state.last_uploaded_doc_name = None
                                st.session_state.last_reuploaded_doc_name = None
                                st.rerun()
                            elif r.status_code == 403:
                                st.error("Access Denied: Account is not authorized. Please contact your system administrator for access.")
                            else:
                                st.error(f"Sign-in failed ({r.status_code}): {r.text}")
                        except Exception as e:
                            st.error(f"""
                            **Cannot connect to API service at `{active_api}`**
                            
                            **Error:** {e}
                            
                            **Tips:**
                            - If running on Streamlit Cloud, expand the **API Server Connection Settings** below and enter your active Cloudflare tunnel URL.
                            - Or configure `API_BASE_URL` in your Streamlit Cloud Secrets.
                            """)

            # Direct In-UI API Server Connection Settings
            curr_endpoint = st.session_state.get("api_base_url", API_BASE)
            is_local = "localhost" in curr_endpoint or "127.0.0.1" in curr_endpoint
            with st.expander("API Server Connection Settings (Cloudflare Tunnel / Custom URL)", expanded=is_local):
                st.caption("Configure the backend API URL when deploying frontend on Streamlit Cloud:")
                custom_url = st.text_input("Backend API Endpoint", value=curr_endpoint, placeholder="https://<tunnel-id>.trycloudflare.com", key="login_api_url_input")
                if st.button("Apply & Test Endpoint", key="apply_api_endpoint_btn", use_container_width=True):
                    sanitized_url = custom_url.strip().rstrip("/")
                    if sanitized_url:
                        st.session_state.api_base_url = sanitized_url
                        try:
                            t_r = requests.get(f"{sanitized_url}/api/health", timeout=5)
                            if t_r.status_code == 200:
                                st.success(f"Connection OK: {t_r.json().get('status', 'healthy')}")
                            else:
                                st.warning(f"Server responded with status {t_r.status_code}")
                        except Exception as conn_err:
                            st.warning(f"Endpoint saved, but test request failed: {conn_err}")
                        time.sleep(0.5)
                        st.rerun()

# -----------------------------------------------------------------------------
# Main Application Console (High-Density JobRadar Console)
# -----------------------------------------------------------------------------
def render_main_dashboard():
    # Automatically ensure full company catalog is loaded without limits (2,000+ companies)
    if not st.session_state.daily_jobs or len(st.session_state.daily_companies) < 2000:
        load_daily_companies(target_count=5000, force_refresh=True)

    u_info = st.session_state.user_info or {}
    user_name = u_info.get("display_name", "Candidate")
    user_email = u_info.get("email", "")
    current_uid = u_info.get("id") or user_email
    first_letter = user_name[0].upper() if user_name else "U"

    # Check deep-link query parameters
    if "nav" in st.query_params:
        target_nav = str(st.query_params.get("nav", "")).replace("+", " ")
        valid_navs = [
            "Analyse Companies",
            "Results & Recommendations",
            "Deep Analysis & Tailoring",
            "Candidate Profile",
            "Settings & Re-upload",
            "Monitored Companies",
            "Job Sync Engine"
        ]
        for v in valid_navs:
            if v.lower() == target_nav.lower() or ("deep" in target_nav.lower() and "tailor" in v.lower()) or ("sync" in target_nav.lower() and "sync" in v.lower()):
                st.session_state.nav_selection = v
                break
    if "job_id" in st.query_params:
        st.session_state.selected_tailor_job_id = st.query_params.get("job_id")

    # Enforce strict user session isolation
    if st.session_state.get("active_user_uid") != current_uid:
        st.session_state.active_user_uid = current_uid
        st.session_state.analysis_results = None
        st.session_state.onboard_yaml = None
        st.session_state.onboard_meta = None
        st.session_state.reupload_yaml = None
        st.session_state.reupload_meta = None
        st.session_state.last_uploaded_doc_name = None
        st.session_state.last_reuploaded_doc_name = None

    # Synchronize onboarding verification and candidate domain with backend
    if "target_keyword" not in st.session_state:
        st.session_state.target_keyword = "cloud devops"

    try:
        r_prof_chk = requests.get(f"{API_BASE}/api/profile", headers=get_auth_headers(), timeout=4)
        if r_prof_chk.status_code == 200:
            st.session_state.is_onboarded = True
            p_data = r_prof_chk.json()
            cand_title = (p_data.get("professional_title") or "").lower()
            cand_skills = " ".join(p_data.get("verified_skills") or []).lower()
            if any(k in cand_title or k in cand_skills for k in ["cloud", "devops", "aws", "azure", "kubernetes", "terraform"]):
                st.session_state.target_keyword = "cloud devops"
            elif any(k in cand_title or k in cand_skills for k in ["ai", "genai", "llm", "langchain", "machine learning"]):
                st.session_state.target_keyword = "python genai"
            elif any(k in cand_title or k in cand_skills for k in ["data engineer", "spark", "hadoop", "etl"]):
                st.session_state.target_keyword = "data engineer"
    except Exception:
        pass

    # -------------------------------------------------------------------------
    # LEFT SIDEBAR: Authentic Console Navigation
    # -------------------------------------------------------------------------
    sidebar_brand_html = """
    <div class="console-side-brand">
        <div style="display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; background: #1A73E8; border-radius: 4px; font-weight: 700; color: #FFFFFF; font-size: 11px;">
            JR
        </div>
        <span class="console-brand-title">JobRadar</span>
    </div>
    <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #9AA0A6; font-weight: 500; margin: 0 0 8px 8px;">
        Career Intelligence & Radar
    </div>
    """
    with st.sidebar:
        render_html(sidebar_brand_html)

    # Enforce mandatory onboarding: Lock navigation until document is uploaded and profile is saved
    if not st.session_state.is_onboarded:
        sidebar_gate_html = """
        <div style="background: rgba(234, 67, 53, 0.08); border: 1px solid rgba(234, 67, 53, 0.3); border-radius: 4px; padding: 10px; margin: 0 0 12px 0;">
            <div style="color: #F28B82; font-weight: 500; font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em;">Profile Setup Required</div>
            <div style="color: #BDC1C6; font-size: 11px; margin-top: 4px; line-height: 1.3;">Upload your document to complete candidate profile setup. Other console tabs remain locked until your profile is active.</div>
        </div>
        """
        with st.sidebar:
            render_html(sidebar_gate_html)
        menu_options = ["Candidate Profile Setup (Mandatory)"]
        st.session_state.nav_selection = menu_options[0]
    else:
        menu_options = [
            "Analyse Companies",
            "Results & Recommendations",
            "Deep Analysis & Tailoring",
            "Candidate Profile",
            "Settings & Re-upload",
            "Monitored Companies"
        ]
        # Admin menu item restricted exclusively to system administrator
        if (user_email or "").strip().lower() == "boobesh2509@gmail.com":
            menu_options.append("Job Sync Engine")

        if "nav_selection" not in st.session_state or st.session_state.nav_selection not in menu_options:
            st.session_state.nav_selection = menu_options[0]

    current_nav_idx = menu_options.index(st.session_state.nav_selection) if st.session_state.nav_selection in menu_options else 0
    raw_selection = st.sidebar.radio(
        "Navigation Menu",
        options=menu_options,
        index=current_nav_idx,
        label_visibility="collapsed"
    )
    st.session_state.nav_selection = raw_selection
    selected_menu = raw_selection.strip()

    st.sidebar.markdown("<br>", unsafe_allow_html=True)

    # Secondary action in sidebar: Live Sync
    if st.sidebar.button("Sync 2,000+ Feeds", use_container_width=True, type="secondary"):
        with st.sidebar:
            with st.spinner("Syncing all companies from live feeds..."):
                load_daily_companies(target_count=5000, force_refresh=True)
                st.success(f"Synced {len(st.session_state.daily_jobs)} jobs across {len(st.session_state.daily_companies)} companies!")
                time.sleep(1)
                st.rerun()

    # DOCKED CANDIDATE PROFILE AT THE BOTTOM OF THE SIDEBAR
    user_dock_html = f"""
    <div style="margin-top: 140px;"></div>
    <div class="console-sidebar-user-dock">
        <div class="user-avatar-circle">{first_letter}</div>
        <div style="overflow: hidden; width: 150px;">
            <div class="user-meta-name" title="{user_name}">{user_name}</div>
            <div class="user-meta-email" title="{user_email}">{user_email}</div>
            <div class="user-status-indicator">
                <span class="project-dot"></span> Active
            </div>
        </div>
    </div>
    """
    with st.sidebar:
        render_html(user_dock_html)

    if st.sidebar.button("Sign out", use_container_width=True, type="secondary"):
        st.session_state.logged_out = True
        st.session_state.token = None
        st.session_state.user_info = None
        st.session_state.is_onboarded = False
        st.session_state.analysis_results = None
        st.session_state.onboard_yaml = None
        st.session_state.onboard_meta = None
        st.session_state.reupload_yaml = None
        st.session_state.reupload_meta = None
        st.session_state.last_uploaded_doc_name = None
        st.session_state.last_reuploaded_doc_name = None
        st.rerun()

    # -------------------------------------------------------------------------
    # BREADCRUMB & SUB-HEADER
    # -------------------------------------------------------------------------
    page_clean_title = selected_menu
    sub_header_html = f"""
    <div class="console-sub-header">
        <div class="console-breadcrumb">
            <a href="#">JobRadar Console</a> &nbsp;&gt;&nbsp; <span style="color: #E8EAED;">{page_clean_title}</span>
        </div>
        <div class="console-page-title-row">
            <div>
                <div class="console-title">{page_clean_title}</div>
                <div class="console-desc-text">
                    Candidate Profile Matcher & Automated Career Discovery. <a href="#" target="_blank">Learn more ↗</a>
                </div>
            </div>
        </div>
    </div>
    """
    render_html(sub_header_html)

    # -------------------------------------------------------------------------
    # MANDATORY ONBOARDING: Strict Document Upload Gate
    # -------------------------------------------------------------------------
    if not st.session_state.is_onboarded:
        st.markdown("<div style='font-weight: 500; font-size: 16px; margin-bottom: 4px; color: #E8EAED;'>Mandatory Candidate Profile Setup</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-size: 12.5px; color: #9AA0A6; margin-bottom: 18px;'>Welcome to JobRadar Console, <b style='color: #8AB4F8;'>{user_name}</b>! Document upload is mandatory. You must upload your base candidate document (PDF, DOCX, TXT) to compile your verified YAML profile ground truth before accessing company analysis or job tracking.</div>", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("<div style='font-size: 13.5px; font-weight: 500; color: #E8EAED; margin-bottom: 6px;'>1. Upload Candidate Document</div>", unsafe_allow_html=True)
            st.caption("Upload your latest CV or technical profile document to automatically extract your skills, title, and experience.")
            
            doc_file = st.file_uploader("Choose Candidate Document (PDF, DOCX, TXT, MD, YAML)", type=["pdf", "docx", "txt", "md", "yaml", "yml"], key="mandatory_onboarding_doc")
            if doc_file:
                if st.session_state.get("last_uploaded_doc_name") != doc_file.name:
                    st.session_state.onboard_yaml = None
                    st.session_state.onboard_meta = None
                    st.session_state.last_uploaded_doc_name = doc_file.name
            if doc_file and st.button("Extract Skills & Compile Candidate Profile", type="primary"):
                with st.spinner("Extracting text and compiling candidate YAML schema..."):
                    try:
                        active_api = st.session_state.get("api_base_url", API_BASE).rstrip("/")
                        files = {"file": (doc_file.name, doc_file.getvalue(), doc_file.type)}
                        r = requests.post(f"{active_api}/api/profile/upload", files=files, headers=get_auth_headers(), timeout=30)
                        if r.status_code == 200:
                            data = r.json()
                            st.session_state.onboard_yaml = data["profile_yaml"]
                            st.session_state.onboard_meta = data
                            st.success(f"Successfully extracted {len(data.get('verified_skills', []))} verified skills!")
                        else:
                            st.error(f"Extraction failed: {r.text}")
                    except Exception as e:
                        st.error(f"Error connecting to extraction service: {e}")

            if "onboard_yaml" in st.session_state and st.session_state.onboard_yaml:
                meta = st.session_state.onboard_meta
                st.markdown("<hr style='border-color: #282D3B; margin: 18px 0;'>", unsafe_allow_html=True)
                
                # -------------------------------------------------------------
                # 2. MANDATORY PERSONAL GEMINI API KEY CONFIGURATION
                # -------------------------------------------------------------
                st.markdown("<div style='font-size: 13.5px; font-weight: 500; color: #E8EAED; margin-bottom: 4px;'>2. Configure Personal Google Gemini API Key (Mandatory)</div>", unsafe_allow_html=True)
                st.markdown("<div style='font-size: 12px; color: #9AA0A6; margin-bottom: 12px;'>Every user must configure their own personal Gemini API key. Keys are private, user-isolated, and strictly never shared with other candidates. Used to power AI direct/cross-domain role generation and authentic profile tailoring.<br>Get your free key from <a href='https://aistudio.google.com/app/apikey' target='_blank' style='color: #8AB4F8;'>Google AI Studio ↗</a></div>", unsafe_allow_html=True)

                k_col1, k_col2 = st.columns([3, 1])
                with k_col1:
                    user_gemini_key = st.text_input("Enter Google Gemini API Key", type="password", value=st.session_state.get("gemini_api_key", ""), placeholder="AIzaSy...", key="onboard_gemini_key_input")
                with k_col2:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    test_key_btn = st.button("Validate Key", type="secondary", use_container_width=True)

                parsed_preview = {}
                try:
                    parsed_preview = yaml.safe_load(st.session_state.onboard_yaml) or {}
                except Exception:
                    pass

                if test_key_btn or (user_gemini_key and not st.session_state.get("gemini_key_validated")):
                    if user_gemini_key and user_gemini_key.strip():
                        with st.spinner("Validating key with Google AI Studio..."):
                            is_valid, v_msg = AIRoleGenerator.validate_gemini_key(user_gemini_key.strip())
                            if is_valid:
                                st.session_state.gemini_key_validated = True
                                st.session_state.gemini_api_key = user_gemini_key.strip()
                                st.session_state.ai_roles_info = AIRoleGenerator.generate_roles(parsed_preview, api_key=user_gemini_key.strip())
                                st.success(f"{v_msg}")
                            else:
                                st.session_state.gemini_key_validated = False
                                st.error(f"{v_msg}")
                    elif test_key_btn:
                        st.warning("Please enter your Gemini API key.")

                # Render AI Inferred Career Profile once key is validated
                if st.session_state.get("gemini_key_validated") and "ai_roles_info" in st.session_state:
                    ai_info = st.session_state.ai_roles_info
                    p_domain = ai_info.get("primary_domain", "Engineering")
                    d_roles = ai_info.get("direct_roles", [])
                    x_roles = ai_info.get("cross_roles", [])

                    st.markdown("<div style='background: #182030; border: 1px solid #2D3D5E; border-radius: 6px; padding: 14px; margin: 12px 0;'>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size: 13px; font-weight: 600; color: #8AB4F8; margin-bottom: 6px;'>AI Inferred Primary Domain: <span style='color: #FFFFFF;'>{p_domain}</span></div>", unsafe_allow_html=True)

                    st.markdown("<div style='font-size: 11.5px; font-weight: 600; color: #81C995; margin-top: 8px;'>AI DIRECT TARGET ROLES (Core Qualifying):</div>", unsafe_allow_html=True)
                    d_chips = " ".join([f"<span class='chip-green' title='{r.get('fit_reason', '')}'>{r.get('title')}</span>" for r in d_roles])
                    st.markdown(f"<div style='margin-bottom: 8px;'>{d_chips}</div>", unsafe_allow_html=True)

                    st.markdown("<div style='font-size: 11.5px; font-weight: 600; color: #FDD663; margin-top: 8px;'>AI CROSS-DOMAIN ROLES (Adjacent Opportunities):</div>", unsafe_allow_html=True)
                    x_chips = " ".join([f"<span class='chip-yellow' title='{r.get('fit_reason', '')}'>{r.get('title')}</span>" for r in x_roles])
                    st.markdown(f"<div style='margin-bottom: 4px;'>{x_chips}</div>", unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)

                st.markdown("<hr style='border-color: #282D3B; margin: 18px 0;'>", unsafe_allow_html=True)
                st.markdown("<div style='font-size: 13.5px; font-weight: 500; color: #E8EAED; margin-bottom: 6px;'>3. Review Extracted Candidate Profile (All Sections)</div>", unsafe_allow_html=True)

                exp_list = parsed_preview.get("experience", [])
                proj_list = parsed_preview.get("projects", [])
                edu_list = parsed_preview.get("education", [])
                skills_list = meta.get("verified_skills", [])

                col_n1, col_n2 = st.columns(2)
                with col_n1:
                    c_name_input = st.text_input("Candidate Display Name", value=meta.get("candidate_name", user_name), key="onboard_name")
                with col_n2:
                    c_title_input = st.text_input("Professional Title", value=meta.get("professional_title", "AI Engineer"), key="onboard_title")

                # Section Tabs for comprehensive visibility
                tab_skills, tab_exp, tab_proj, tab_edu, tab_yaml = st.tabs([
                    f"Skills ({len(skills_list)})",
                    f"Experience ({len(exp_list)})",
                    f"Projects ({len(proj_list)})",
                    f"Education ({len(edu_list)})",
                    "Raw YAML Truth"
                ])

                with tab_skills:
                    skill_chips = "".join([f'<span class="chip-green">{s}</span>' for s in skills_list])
                    st.markdown(f"<div style='font-size: 11.5px; color: #9AA0A6; margin: 6px 0 8px 0;'>VERIFIED EXTRACTED SKILLS ({len(skills_list)}):</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='margin-bottom: 12px;'>{skill_chips}</div>", unsafe_allow_html=True)

                with tab_exp:
                    if exp_list:
                        for exp_item in exp_list:
                            c_role = exp_item.get("role", "Engineer")
                            c_comp = exp_item.get("company", "Company")
                            c_per = exp_item.get("period", {})
                            c_per_str = c_per.get("display", "") if isinstance(c_per, dict) else str(c_per)
                            st.markdown(f"**{c_role}** @ **{c_comp}** *({c_per_str})*")
                            for b in exp_item.get("bullets", []):
                                st.markdown(f"- {b}")
                            st.markdown("---")
                    else:
                        st.info("No employment experience found in document.")

                with tab_proj:
                    if proj_list:
                        for proj_item in proj_list:
                            p_name = proj_item.get("name", "Project")
                            p_stack = proj_item.get("tech_stack", "")
                            st.markdown(f"**{p_name}**" + (f" *({p_stack})*" if p_stack else ""))
                            if proj_item.get("repo"):
                                st.markdown(f"Repository: {proj_item.get('repo')}")
                            for b in proj_item.get("bullets", []):
                                st.markdown(f"- {b}")
                            st.markdown("---")
                    else:
                        st.info("No projects section found in document.")

                with tab_edu:
                    if edu_list:
                        for edu_item in edu_list:
                            deg = edu_item.get("degree", "Degree")
                            inst = edu_item.get("institution", "University")
                            yr = edu_item.get("period") or edu_item.get("year", "")
                            st.markdown(f"**{deg}** — {inst} *({yr})*")
                            if edu_item.get("relevance"):
                                st.caption(edu_item.get("relevance"))
                    else:
                        st.info("No education section found in document.")

                with tab_yaml:
                    revised_yaml = st.text_area("Review Extracted YAML Profile Ground Truth", value=st.session_state.onboard_yaml, height=260)
                
                if st.button("Confirm & Activate Profile", type="primary"):
                    if not st.session_state.get("gemini_key_validated"):
                        st.error("Mandatory: Please enter and validate your personal Google Gemini API key in Step 2 above before activating your profile.")
                    else:
                        try:
                            active_api = st.session_state.get("api_base_url", API_BASE).rstrip("/")
                            payload = {
                                "candidate_name": c_name_input or meta.get("candidate_name", user_name),
                                "professional_title": c_title_input or meta.get("professional_title", "AI Engineer"),
                                "experience_years": meta.get("experience_years", 3.0),
                                "verified_skills": skills_list,
                                "profile_yaml": revised_yaml if 'revised_yaml' in locals() else st.session_state.onboard_yaml,
                                "api_key": st.session_state.get("gemini_api_key", "")
                            }
                            r_save = requests.post(f"{active_api}/api/profile/save", json=payload, headers=get_auth_headers(), timeout=10)
                            if r_save.status_code == 200:
                                st.session_state.is_onboarded = True
                                st.session_state.onboard_yaml = None
                                st.session_state.onboard_meta = None
                                st.session_state.nav_selection = "Analyse Companies"
                                st.success("Candidate Profile activated successfully! Unlocking full console access...")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"Failed to save profile: {r_save.text}")
                        except Exception as e:
                            st.error(f"Error saving profile: {e}")

        # Stop execution here so un-onboarded users CANNOT see or access other tabs
        return

    # -------------------------------------------------------------------------
    # TAB 1: ANALYSE COMPANIES (Scope Selector & Resilient Career Links)
    # -------------------------------------------------------------------------
    if "Analyse Companies" in selected_menu:
        # Action Toolbar
        t_col1, t_col2, t_col3, t_col4 = st.columns([2, 1.2, 1.2, 3])
        with t_col1:
            start_btn = st.button("Start Profile Analysis", type="primary", use_container_width=True)
        with t_col2:
            sync_btn = st.button("Sync Live Feeds", type="secondary", use_container_width=True)
        with t_col3:
            reset_sel_btn = st.button("Clear Filters", type="secondary", use_container_width=True)

        if sync_btn:
            with st.spinner("Syncing all live companies..."):
                load_daily_companies(target_count=5000, force_refresh=True)
                st.success("Refreshed catalog across all employers!")
                time.sleep(1)
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # ---------------------------------------------------------------------
        # AI Profile Target Roles & Domain Showcase
        # ---------------------------------------------------------------------
        if "ai_roles_info" in st.session_state and st.session_state.ai_roles_info:
            ai_r = st.session_state.ai_roles_info
            p_dom = ai_r.get("primary_domain", "Engineering")
            d_list = ai_r.get("direct_roles", [])
            x_list = ai_r.get("cross_roles", [])
            d_pills = " ".join([f"<span class='chip-green' title='{r.get('fit_reason', '')}'>{r.get('title')}</span>" for r in d_list])
            x_pills = " ".join([f"<span class='chip-yellow' title='{r.get('fit_reason', '')}'>{r.get('title')}</span>" for r in x_list])

            st.markdown(f"""
            <div style="background: #182030; border: 1px solid #283754; border-radius: 6px; padding: 12px 16px; margin: 8px 0 16px 0;">
                <div style="font-size: 13px; font-weight: 600; color: #8AB4F8; margin-bottom: 6px;">
                    AI Inferred Target Domain: <span style="color: #FFFFFF;">{p_dom}</span>
                </div>
                <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-size: 12px; margin-bottom: 6px;">
                    <b style="color: #81C995;">Direct Target Roles:</b> {d_pills}
                </div>
                <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-size: 12px;">
                    <b style="color: #FDD663;">Cross-Domain Targets:</b> {x_pills}
                </div>
            </div>
            """, unsafe_allow_html=True)

        # ---------------------------------------------------------------------
        # Instant On-Demand Evaluation for ANY Company (Global Scope)
        # ---------------------------------------------------------------------
        st.markdown("""
        <div style="background: #1B2232; border: 1px solid #28354E; border-radius: 6px; padding: 12px 16px; margin-bottom: 14px;">
            <div style="font-size: 13.5px; font-weight: 600; color: #E8EAED;">Instant On-Demand Evaluation for ANY Company</div>
            <div style="font-size: 11.5px; color: #9AA0A6; margin-bottom: 8px;">Enter ANY company name (Startup, MNC, Mid-market). Evaluates lively on-demand with direct official Career Portal, LinkedIn (latest), and Naukri links against your profile.</div>
        </div>
        """, unsafe_allow_html=True)
        od_col1, od_col2 = st.columns([3, 1.2])
        with od_col1:
            od_input_comp = st.text_input("Company Name to Evaluate", placeholder="e.g. Datadog, Anthropic, CrowdStrike, BHEL, Zoho, Stripe, Snowflake...", key="quick_od_comp_name", label_visibility="collapsed")
        with od_col2:
            od_eval_btn = st.button("Evaluate On-Demand", type="primary", use_container_width=True)

        if od_eval_btn and od_input_comp and od_input_comp.strip():
            with st.spinner(f"Evaluating '{od_input_comp.strip()}' across Career Portal, LinkedIn & Naukri..."):
                try:
                    payload = {
                        "selected_companies": [od_input_comp.strip()],
                        "selected_group": "All",
                        "selected_channel": "All"
                    }
                    r_od = requests.post(f"{API_BASE}/api/analyze", json=payload, headers=get_auth_headers(), timeout=35)
                    if r_od.status_code == 200:
                        st.session_state.analysis_results = r_od.json()
                        st.session_state.nav_selection = "Results & Recommendations"
                        st.rerun()
                    else:
                        st.error(f"Analysis error: {r_od.text}")
                except Exception as e:
                    st.error(f"API Error: {e}")

        # Compact Filter Bar with Sector & Channel
        f_col1, f_col2, f_col3 = st.columns([1, 1, 2])
        with f_col1:
            selected_grp = st.selectbox(
                "Filter by Market Sector",
                options=st.session_state.daily_groups,
                index=0,
                help="Filter companies by enterprise group (MNC, AI_Startup, Remote_First, or All)"
            )

        with f_col2:
            selected_chan = st.selectbox(
                "Filter by Source Channel",
                options=["All Channels", "Career Page", "LinkedIn", "Naukri"],
                index=0,
                help="Filter requisitions by platform (Direct Career ATS, LinkedIn, or Naukri)"
            )

        with f_col3:
            if selected_grp == "All":
                available_comps = st.session_state.daily_companies
            else:
                available_comps = sorted(list(set(
                    j.get("company_name", "") for j in st.session_state.daily_jobs if j.get("company_group") == selected_grp
                )))

            # If channel selected, further restrict company candidates
            if selected_chan != "All Channels":
                chan_comps = set(
                    j.get("company_name", "") for j in st.session_state.daily_jobs
                    if (j.get("source_channel") or CompanyService.get_channel_from_url(j.get("url", ""))) == selected_chan
                )
                available_comps = [c for c in available_comps if c in chan_comps] or available_comps

            # Compact multi-select with placeholder
            selected_comps = st.multiselect(
                "Select Specific Companies (Leave blank to evaluate ALL in sector)",
                options=available_comps,
                default=[] if not reset_sel_btn else [],
                placeholder="All companies in this sector will be evaluated..."
            )

        target_pool = selected_comps if selected_comps else available_comps
        eval_count = len(target_pool)

        # Compact Scope Information Pill
        total_real_synced_count = sum(1 for j in st.session_state.daily_jobs if not (j.get("job_id") or "").startswith("OPP-") and j.get("job_id") != "NO-ROLE-FOUND")
        scope_pill_html = f"""
        <div style="background: #202534; border: 1px solid #2D3345; border-radius: 4px; padding: 8px 14px; margin: 12px 0 16px 0; display: flex; align-items: center; justify-content: space-between;">
            <div style="display: flex; align-items: center; gap: 8px; font-size: 12.5px;">
                <span>Target Evaluation: <b style="color: #8AB4F8;">{eval_count} Companies</b> (<b style="color: #81C995;">{total_real_synced_count:,} Live Synced Positions</b> | {selected_grp} Sector | {selected_chan}) against verified YAML profile.</span>
            </div>
            <span style="font-size: 11.5px; color: #9AA0A6;">Cross-platform search enabled across Career Pages, LinkedIn & Naukri.</span>
        </div>
        """
        render_html(scope_pill_html)

        # Trigger Analysis
        if start_btn:
            with st.spinner(f"Evaluating {eval_count} companies across Career Pages, LinkedIn & Naukri in database..."):
                try:
                    payload = {
                        "selected_companies": selected_comps if selected_comps else None,
                        "selected_group": selected_grp,
                        "selected_channel": selected_chan if selected_chan != "All Channels" else "All"
                    }
                    r = requests.post(f"{API_BASE}/api/analyze", json=payload, headers=get_auth_headers(), timeout=35)
                    if r.status_code == 200:
                        st.session_state.analysis_results = r.json()
                        st.session_state.nav_selection = "Results & Recommendations"
                        st.rerun()
                    else:
                        st.error(f"Analysis error: {r.text}")
                except Exception as e:
                    st.error(f"API Error: {e}")

        # Smart fuzzy and alias search
        def match_company_query(query: str, target: str) -> bool:
            q = query.strip().lower()
            t = target.strip().lower()
            if not q:
                return True
            if q in t:
                return True
            # Alias and spelling variants (e.g. laren & turbo, l&t, ltts -> Larsen & Toubro)
            alias_clusters = [
                {"larsen", "toubro", "l&t", "ltts", "laren", "turbo"},
                {"tcs", "tata consultancy"},
                {"hcl", "hcltech"},
                {"ibm", "international business machines"},
                {"ge", "general electric"},
                {"palo alto", "panw"},
                {"bel", "bharat electronics"},
                {"hal", "hindustan aeronautics"}
            ]
            for cluster in alias_clusters:
                if any(k in q for k in cluster) and any(k in t for k in cluster):
                    return True
            # Token match
            q_words = [w for w in re.findall(r"[a-z0-9]+", q) if len(w) >= 3 and w not in ["and", "the", "for", "ltd", "inc"]]
            if any(w in t for w in q_words):
                return True
            return False

        # Precompute set of employers with real synced positions
        synced_comp_names = set(
            j.get("company_name") for j in st.session_state.daily_jobs
            if not (j.get("job_id") or "").startswith("OPP-") and j.get("job_id") != "NO-ROLE-FOUND"
        )

        # In-Column Filters for Scope Employers Table (Zero standalone filters above the table)
        ac_c1, ac_c2, ac_c3, ac_c4, ac_c5, ac_c6 = st.columns([0.4, 2.8, 1.4, 1.8, 1.8, 1.4])
        with ac_c1:
            st.markdown("<div style='height: 38px;'></div>", unsafe_allow_html=True)
        with ac_c2:
            f_ac_comp = st.text_input("Filter Company", "", placeholder="Filter Company...", label_visibility="collapsed", key="ac_f_comp")
        with ac_c3:
            f_ac_sec = st.selectbox("Filter Sector", ["All", "MNC", "AI_Startup", "Remote_First"], index=0, label_visibility="collapsed", key="ac_f_sec")
        with ac_c4:
            f_ac_chan = st.selectbox("Filter Channel", ["All", "Career Page", "LinkedIn", "Naukri"], index=0, label_visibility="collapsed", key="ac_f_chan")
        with ac_c5:
            f_ac_open = st.selectbox("Filter Openings", ["All", "Live Synced Roles", "Directory Monitored"], index=0, label_visibility="collapsed", key="ac_f_open")
        with ac_c6:
            display_limit_sel = st.selectbox("Show Rows", ["All", 25, 50, 100, 250, 500], index=0, label_visibility="collapsed", key="ac_f_limit")

        # Apply Column Filters simultaneously
        filtered_pool = target_pool
        if f_ac_comp.strip():
            filtered_pool = [c for c in filtered_pool if match_company_query(f_ac_comp, c)]

        if f_ac_sec != "All":
            filtered_pool = [
                c for c in filtered_pool
                if any(j.get("company_group") == f_ac_sec for j in st.session_state.daily_jobs if j.get("company_name") == c)
            ]

        if f_ac_chan != "All":
            filtered_pool = [
                c for c in filtered_pool
                if any(
                    (j.get("source_channel") or CompanyService.get_channel_from_url(j.get("url", ""))) == f_ac_chan
                    for j in st.session_state.daily_jobs if j.get("company_name") == c
                )
            ]

        if f_ac_open == "Live Synced Roles":
            filtered_pool = [c for c in filtered_pool if c in synced_comp_names]
        elif f_ac_open == "Directory Monitored":
            filtered_pool = [c for c in filtered_pool if c not in synced_comp_names]

        # Dynamic On-Demand Company Ingestion if not found
        if f_ac_comp and not filtered_pool:
            st.info(f"No pre-configured company directly matches '{f_ac_comp}'. You can add and monitor it right now without limits.")
            add_c1, add_c2 = st.columns([3, 1])
            with add_c1:
                custom_comp_name = st.text_input("Company Name to Monitor", value=f_ac_comp.title(), key="new_custom_company_input")
            with add_c2:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                if st.button("Add & Monitor", type="primary", use_container_width=True):
                    with st.spinner(f"Registering '{custom_comp_name}' across Career Pages, LinkedIn & Naukri..."):
                        try:
                            r_add = requests.post(f"{API_BASE}/api/companies/add", json={"company_name": custom_comp_name}, headers=get_auth_headers(), timeout=15)
                            if r_add.status_code == 200:
                                st.success(f"Successfully registered '{custom_comp_name}'! Refreshing...")
                                load_daily_companies(target_count=5000, force_refresh=True)
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"Failed to add: {r_add.text}")
                        except Exception as e:
                            st.error(f"Error: {e}")

        # Quick Add Any Employer expander for complete flexibility
        with st.expander("Register Custom Employer to Scope (No limits)"):
            c_add_c1, c_add_c2, c_add_c3 = st.columns([2.5, 1.2, 1])
            with c_add_c1:
                manual_cname = st.text_input("Employer Name (e.g. Larsen & Toubro, CrowdStrike, BHEL...)", key="manual_comp_name_exp")
            with c_add_c2:
                manual_cgrp = st.selectbox("Sector", ["MNC", "AI_Startup", "Remote_First"], index=0, key="manual_comp_grp_exp")
            with c_add_c3:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                if st.button("Add Employer", type="secondary", use_container_width=True):
                    if manual_cname.strip():
                        with st.spinner(f"Registering '{manual_cname.strip()}'..."):
                            try:
                                r_add = requests.post(f"{API_BASE}/api/companies/add", json={"company_name": manual_cname.strip(), "company_group": manual_cgrp}, headers=get_auth_headers(), timeout=15)
                                if r_add.status_code == 200:
                                    st.success(f"Added '{manual_cname.strip()}'! Refreshing...")
                                    load_daily_companies(target_count=5000, force_refresh=True)
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(f"Could not add: {r_add.text}")
                            except Exception as e:
                                st.error(f"Error: {e}")

        # Sort companies: employers with newly synced live positions appear FIRST!
        sorted_pool = sorted(
            filtered_pool,
            key=lambda c: (0 if c in synced_comp_names else 1, c.lower())
        )
        limit_count = len(sorted_pool) if display_limit_sel == "All" else int(display_limit_sel)
        viewing_pool = sorted_pool[:limit_count]

        # Render preview table of target companies
        preview_rows = []
        for c_name in viewing_pool:
            matched_jobs = [j for j in st.session_state.daily_jobs if j.get("company_name") == c_name]
            real_jobs = [j for j in matched_jobs if not (j.get("job_id") or "").startswith("OPP-") and j.get("job_id") != "NO-ROLE-FOUND"]
            has_real_job = len(real_jobs) > 0
            job_cnt = len(real_jobs) if has_real_job else len(matched_jobs)
            grp = matched_jobs[0].get("company_group", "Enterprise") if matched_jobs else "Enterprise"
            career_url = resolve_career_url(matched_jobs[0] if matched_jobs else None, c_name)

            # Compute channel badges for available roles
            channels_present = set()
            for mj in (real_jobs if has_real_job else matched_jobs):
                ch = mj.get("source_channel") or CompanyService.get_channel_from_url(mj.get("url", ""))
                channels_present.add(ch)
            if not channels_present:
                channel_pills = '<span class="status-pill-gray">Careers Portal</span>'
            else:
                channel_pills = " ".join([get_source_pill_html(c) for c in sorted(list(channels_present))])

            if has_real_job:
                # Direct links for up to 3 live requisitions
                badges = []
                for j in real_jobs[:3]:
                    jid = j.get("job_id", "REQ")
                    jurl = j.get("url") or career_url
                    jurl_low = jurl.lower()
                    if "arbeitnow.com" in jurl_low or "jobicy.com" in jurl_low:
                        jurl = career_url
                    elif "naukri.com" in jurl_low and ("job-listings-" in jurl_low or "expjd=true" in jurl_low):
                        jurl = CompanyService.get_official_naukri_url(c_name, j.get("title", ""))
                    ch = j.get("source_channel") or CompanyService.get_channel_from_url(jurl)
                    jtitle = (j.get("title") or "").replace('"', '&quot;')
                    badges.append(f'<a href="{jurl}" target="_blank" class="job-id-pill" title="{ch}: {jtitle} (#{jid})">#{jid} ↗</a>')
                id_badge = " ".join(badges)
                openings_cell = f'<b style="color: #81C995;">{len(real_jobs)} live positions</b>'
            else:
                id_badge = f'<a href="{career_url}" target="_blank" class="job-id-pill" title="Official Careers Portal">Career Portal ↗</a>'
                openings_cell = '<span style="color: #9AA0A6;">Directory Monitored</span>'

            preview_rows.append(f"""
            <tr>
                <td style="width: 30px;"><input type="checkbox" checked disabled></td>
                <td><b style="color: #8AB4F8;">{c_name}</b>{" <span class='chip-green' style='font-size: 10px; padding: 1px 5px;'>Live Synced</span>" if has_real_job else ""}</td>
                <td><span class="status-pill-gray">{grp}</span></td>
                <td>{channel_pills}</td>
                <td>{openings_cell}</td>
                <td>{id_badge}</td>
            </tr>
            """)

        full_preview_table = f"""
        <div class="console-table-container">
            <div class="console-table-header">
                <div class="console-table-title">
                    <span>Scope Employers ({len(filtered_pool)} Matching — {len(synced_comp_names)} with Live Synced Roles)</span>
                </div>
                <div style="font-size: 11.5px; color: #9AA0A6;">
                    Showing {len(viewing_pool)} of {len(filtered_pool)} companies (employers with live synced requisitions displayed first)
                </div>
            </div>
            <table class="console-table">
                <thead>
                    <tr>
                        <th style="width: 30px;">[x]</th>
                        <th>Company Name</th>
                        <th>Market Sector</th>
                        <th>Channels Monitored</th>
                        <th>Active Openings</th>
                        <th>Direct Requisition Link</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(preview_rows)}
                </tbody>
            </table>
        </div>
        """
        render_html(full_preview_table)

    # -------------------------------------------------------------------------
    # TAB 2: RESULTS & RECOMMENDATIONS (Dense Data Tables)
    # -------------------------------------------------------------------------
    elif "Results & Recommendations" in selected_menu:
        # Automatic analysis loading if not already in session state
        if not st.session_state.analysis_results:
            with st.spinner("Analyzing candidate profile against 2,000+ tracked employers in PostgreSQL database..."):
                try:
                    payload = {"selected_group": "All"}
                    r = requests.post(f"{API_BASE}/api/analyze", json=payload, headers=get_auth_headers(), timeout=35)
                    if r.status_code == 200:
                        st.session_state.analysis_results = r.json()
                        st.rerun()
                    else:
                        st.error(f"Analysis engine response: {r.text}")
                except Exception as e:
                    st.error(f"API Error: {e}")

        res = st.session_state.analysis_results
        if not res:
            empty_panel = """
            <div style="background: #202534; border: 1px solid #2D3345; border-radius: 4px; padding: 24px; text-align: center;">
                <div style="font-size: 14px; font-weight: 500; color: #E8EAED;">No Active Analysis Job Found</div>
                <div style="font-size: 12px; color: #9AA0A6; margin-top: 4px; margin-bottom: 16px;">
                    Select target companies in 'Analyse Companies' and run the analysis to view match scores and gaps.
                </div>
            </div>
            """
            render_html(empty_panel)
            if st.button("Start Analysis for All Companies", type="primary"):
                with st.spinner("Analyzing profile..."):
                    try:
                        r = requests.post(f"{API_BASE}/api/analyze", json={"selected_group": "All"}, headers=get_auth_headers(), timeout=35)
                        if r.status_code == 200:
                            st.session_state.analysis_results = r.json()
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        else:
            # Action Toolbar with Re-evaluate Profile Action
            hdr_c1, hdr_c2 = st.columns([4, 1.2])
            with hdr_c1:
                st.markdown("""
                <div style="font-size: 13.5px; font-weight: 600; color: #E8EAED;">Evaluated Tech Requisitions against Verified Profile</div>
                <div style="font-size: 11.5px; color: #9AA0A6; margin-top: 1px;">
                    Multi-channel candidate matching across Career Pages, LinkedIn, and Naukri.
                </div>
                """, unsafe_allow_html=True)
            with hdr_c2:
                if st.button("Re-evaluate Profile", use_container_width=True, type="primary"):
                    with st.spinner("Re-evaluating employers across Career Pages, LinkedIn & Naukri..."):
                        try:
                            payload = {"selected_group": "All"}
                            r = requests.post(f"{API_BASE}/api/analyze", json=payload, headers=get_auth_headers(), timeout=35)
                            if r.status_code == 200:
                                st.session_state.analysis_results = r.json()
                                st.rerun()
                            else:
                                st.error(f"Analysis error: {r.text}")
                        except Exception as e:
                            st.error(f"API Error: {e}")

            # Metric Bar
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            with m1:
                render_html(f"""
                <div class="console-metric-box">
                    <div class="console-metric-val">{res['total_analyzed']}</div>
                    <div class="console-metric-lbl">Total Evaluated</div>
                </div>
                """)
            with m2:
                render_html(f"""
                <div class="console-metric-box" style="border-left: 3px solid #81C995;">
                    <div class="console-metric-val" style="color: #81C995;">{res['exact_matches_count']}</div>
                    <div class="console-metric-lbl">Exact Matches (&ge;75%)</div>
                </div>
                """)
            with m3:
                render_html(f"""
                <div class="console-metric-box" style="border-left: 3px solid #FDD663;">
                    <div class="console-metric-val" style="color: #FDD663;">{res['action_needed_count']}</div>
                    <div class="console-metric-lbl">Action Needed (60-74%)</div>
                </div>
                """)
            with m4:
                render_html(f"""
                <div class="console-metric-box" style="border-left: 3px solid #C084FC;">
                    <div class="console-metric-val" style="color: #C084FC;">{res.get('cross_domain_count', len(res.get('cross_domain', [])))}</div>
                    <div class="console-metric-lbl">Cross-Domain Overlap</div>
                </div>
                """)
            with m5:
                render_html(f"""
                <div class="console-metric-box" style="border-left: 3px solid #F28B82;">
                    <div class="console-metric-val" style="color: #F28B82;">{res['divergent_count']}</div>
                    <div class="console-metric-lbl">Role Divergent (&lt;50%)</div>
                </div>
                """)
            with m6:
                render_html(f"""
                <div class="console-metric-box" style="border-left: 3px solid #9AA0A6;">
                    <div class="console-metric-val" style="color: #9AA0A6;">{res.get('no_openings_count', 0)}</div>
                    <div class="console-metric-lbl">0 Openings Found</div>
                </div>
                """)

            # Channel Distribution Summary Pill
            career_cnt = sum(1 for i in res.get("all_results", []) if (i.get("source_channel") or CompanyService.get_channel_from_url(i.get("job_apply_url", ""))) == "Career Page")
            li_cnt = sum(1 for i in res.get("all_results", []) if (i.get("source_channel") or CompanyService.get_channel_from_url(i.get("job_apply_url", ""))) == "LinkedIn")
            nk_cnt = sum(1 for i in res.get("all_results", []) if (i.get("source_channel") or CompanyService.get_channel_from_url(i.get("job_apply_url", ""))) == "Naukri")

            channel_summary_html = f"""
            <div style="background: #181D2A; border: 1px solid #282D3D; border-radius: 4px; padding: 7px 14px; margin: 10px 0 16px 0; display: flex; align-items: center; justify-content: space-between;">
                <div style="display: flex; align-items: center; gap: 14px; font-size: 12px;">
                    <span style="color: #9AA0A6; font-weight: 500;">Discovered Openings by Channel:</span>
                    <span><span class="source-pill-career">Career Page</span> <b style="color: #8AB4F8; margin-left: 4px;">{career_cnt} roles</b></span>
                    <span><span class="source-pill-linkedin">LinkedIn</span> <b style="color: #70B5F9; margin-left: 4px;">{li_cnt} roles</b></span>
                    <span><span class="source-pill-naukri">Naukri</span> <b style="color: #FF9E67; margin-left: 4px;">{nk_cnt} roles</b></span>
                </div>
                <span style="font-size: 11px; color: #9AA0A6;">Direct platform requisitions with exact Job IDs</span>
            </div>
            """
            render_html(channel_summary_html)

            # Export to PDF Panel with Interactive Filters
            with st.expander("Export Evaluation Report to PDF (Customizable Criteria)", expanded=False):
                st.markdown("<div style='font-size: 12.5px; color: #9AA0A6; margin-bottom: 8px;'>Select categories and source channels to include in your exported PDF dossier:</div>", unsafe_allow_html=True)
                exp_col1, exp_col2 = st.columns(2)
                with exp_col1:
                    st.markdown("<b style='font-size: 12px; color: #E8EAED;'>Include Categories:</b>", unsafe_allow_html=True)
                    pdf_inc_exact = st.checkbox("Exact Matches (>=75%)", value=True, key="pdf_chk_exact")
                    pdf_inc_action = st.checkbox("Action Needed (60%-74%)", value=True, key="pdf_chk_action")
                    pdf_inc_cross = st.checkbox("Cross-Domain Opportunities (Adjacent Disciplines)", value=True, key="pdf_chk_cross")
                    pdf_inc_div = st.checkbox("Role Divergent (<50%)", value=False, key="pdf_chk_div")
                    pdf_inc_noop = st.checkbox("Monitored 0 Openings Employers", value=False, key="pdf_chk_noop")

                with exp_col2:
                    st.markdown("<b style='font-size: 12px; color: #E8EAED;'>Include Source Channels:</b>", unsafe_allow_html=True)
                    pdf_inc_career = st.checkbox("Career Page Openings", value=True, key="pdf_chk_career")
                    pdf_inc_li = st.checkbox("LinkedIn Openings", value=True, key="pdf_chk_li")
                    pdf_inc_nk = st.checkbox("Naukri Openings", value=True, key="pdf_chk_nk")

                # Build the filtered list for PDF
                pdf_selected_cats = []
                pdf_pool = []
                if pdf_inc_exact:
                    pdf_selected_cats.append("Exact Matches")
                    pdf_pool.extend(res.get("exact_matches", []))
                if pdf_inc_action:
                    pdf_selected_cats.append("Action Needed")
                    pdf_pool.extend(res.get("action_needed", []))
                if pdf_inc_cross:
                    pdf_selected_cats.append("Cross-Domain")
                    pdf_pool.extend(res.get("cross_domain", []))
                if pdf_inc_div:
                    pdf_selected_cats.append("Role Divergent")
                    pdf_pool.extend(res.get("divergent", []))
                if pdf_inc_noop:
                    pdf_selected_cats.append("0 Openings Monitored")
                    pdf_pool.extend(res.get("no_openings", []))

                pdf_selected_chans = []
                if pdf_inc_career:
                    pdf_selected_chans.append("Career Page")
                if pdf_inc_li:
                    pdf_selected_chans.append("LinkedIn")
                if pdf_inc_nk:
                    pdf_selected_chans.append("Naukri")

                # Filter pdf_pool by channel
                pdf_final_items = [
                    item for item in pdf_pool
                    if (item.get("source_channel") or CompanyService.get_channel_from_url(item.get("job_apply_url", ""))) in pdf_selected_chans
                ]

                # Candidate info for header
                cand_name = "Candidate"
                cand_title = "Software Engineer"
                cand_exp = 3.0
                try:
                    r_p = requests.get(f"{API_BASE}/api/profile", headers=get_auth_headers(), timeout=4)
                    if r_p.status_code == 200:
                        p_data = r_p.json()
                        cand_name = p_data.get("candidate_name", "Candidate")
                        cand_title = p_data.get("professional_title", "Software Engineer")
                        cand_exp = float(p_data.get("experience_years", 3.0))
                except Exception:
                    pass

                pdf_metrics = {
                    "exact_matches_count": res.get("exact_matches_count", len(res.get("exact_matches", []))),
                    "action_needed_count": res.get("action_needed_count", len(res.get("action_needed", []))),
                    "cross_domain_count": res.get("cross_domain_count", len(res.get("cross_domain", []))),
                    "divergent_count": res.get("divergent_count", len(res.get("divergent", []))),
                    "no_openings_count": res.get("no_openings_count", len(res.get("no_openings", []))),
                }

                try:
                    pdf_data = build_pdf_report(
                        candidate_name=cand_name,
                        professional_title=cand_title,
                        experience_years=cand_exp,
                        items=pdf_final_items,
                        metrics_summary=pdf_metrics,
                        selected_categories=pdf_selected_cats,
                        selected_channels=pdf_selected_chans
                    )
                    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', cand_name)
                    st.download_button(
                        label=f"Download PDF Report ({len(pdf_final_items)} Roles)",
                        data=pdf_data,
                        file_name=f"JobRadar_Evaluation_Report_{safe_name}.pdf",
                        mime="application/pdf",
                        type="primary"
                    )
                except Exception as pdf_err:
                    st.error(f"Error compiling PDF: {pdf_err}")

            # In-Column Filters for Results Tables (Zero bulky standalone filters above table)
            rf_c1, rf_c2, rf_c3, rf_c4, rf_c5, rf_c6, rf_c7 = st.columns([1.8, 2.2, 1.2, 1.2, 1.1, 1.6, 1.0])
            with rf_c1:
                res_f_comp = st.text_input("Filter Company", "", placeholder="Filter Company...", label_visibility="collapsed", key="rf_comp")
            with rf_c2:
                res_f_title = st.text_input("Filter Title", "", placeholder="Filter Role Title...", label_visibility="collapsed", key="rf_title")
            with rf_c3:
                res_f_chan = st.selectbox("Filter Channel", ["All", "Career Page", "LinkedIn", "Naukri"], index=0, label_visibility="collapsed", key="rf_chan")
            with rf_c4:
                res_f_sec = st.selectbox("Filter Sector", ["All", "MNC", "AI_Startup", "Remote_First"], index=0, label_visibility="collapsed", key="rf_sec")
            with rf_c5:
                res_f_mode = st.selectbox("Filter Work Mode", ["All", "Hybrid", "Remote", "On-site"], index=0, label_visibility="collapsed", key="rf_mode")
            with rf_c6:
                res_f_skill = st.text_input("Filter Skill/ID", "", placeholder="Filter Skills or ID...", label_visibility="collapsed", key="rf_skill")
            with rf_c7:
                if st.button("Reset", use_container_width=True, key="rf_reset"):
                    st.session_state["rf_comp"] = ""
                    st.session_state["rf_title"] = ""
                    st.session_state["rf_chan"] = "All"
                    st.session_state["rf_sec"] = "All"
                    st.session_state["rf_mode"] = "All"
                    st.session_state["rf_skill"] = ""
                    st.rerun()

            def filter_result_items(items):
                if not items:
                    return []
                out = items
                if res_f_comp.strip():
                    q_c = res_f_comp.strip().lower()
                    out = [i for i in out if q_c in (i.get("company_name") or "").lower()]
                if res_f_title.strip():
                    q_t = res_f_title.strip().lower()
                    out = [i for i in out if q_t in (i.get("title") or "").lower()]
                if res_f_chan != "All":
                    out = [i for i in out if (i.get("source_channel") or CompanyService.get_channel_from_url(i.get("job_apply_url", ""))) == res_f_chan]
                if res_f_sec != "All":
                    out = [i for i in out if i.get("company_group") == res_f_sec]
                if res_f_mode != "All":
                    out = [i for i in out if res_f_mode.lower() in (i.get("work_mode") or "").lower()]
                if res_f_skill.strip():
                    q_s = res_f_skill.strip().lower()
                    out = [
                        i for i in out if (
                            any(q_s in s.lower() for s in (i.get("matched_skills") or [])) or
                            any(q_s in s.lower() for s in (i.get("lag_skills") or [])) or
                            any(q_s in s.lower() for s in (i.get("skills_required") or [])) or
                            q_s in (i.get("job_id") or "").lower()
                        )
                    ]
                return out

            exact_items = filter_result_items(res.get("exact_matches", []))
            action_items = filter_result_items(res.get("action_needed", []))
            cross_items = filter_result_items(res.get("cross_domain", []))
            divergent_items = filter_result_items(res.get("divergent", []))
            no_op_items = filter_result_items(res.get("no_openings", []))

            # 1. Exact Matches Table (>= 75%)
            render_console_matches_table(
                title="Exact Matches (>= 75% Score) — Direct Requisitions",
                subtitle="Roles with verified high skill overlap and compatible experience. Recommended for immediate application.",
                items=exact_items,
                pill_class="status-pill-green",
                status_label="Exact Match"
            )

            # 2. Action Needed Table (60% - 74%)
            render_console_matches_table(
                title="Action Needed Before Applying (60% - 74% Score)",
                subtitle="High alignment with minor skill gaps. Address missing skills in tailoring tips before applying.",
                items=action_items,
                pill_class="status-pill-yellow",
                status_label="Action Needed"
            )

            # 3. Cross-Domain Opportunities Table (Adjacent Disciplines)
            render_console_matches_table(
                title="Cross-Domain Opportunities (Adjacent Disciplines)",
                subtitle="Roles outside your primary specialization matching your tooling/infrastructure stack (e.g. Docker, Microservices, Cloud). Requires discipline transition.",
                items=cross_items,
                pill_class="status-pill-purple",
                status_label="Cross-Domain Match"
            )

            # 4. Role Divergent Table (< 50%)
            render_console_matches_table(
                title="Role Matches Title, but Technical Stack Divergent (< 50% Score)",
                subtitle="Title contains AI/Engineer keywords, but technical requirements diverge (e.g. C++, CUDA kernel development, Swift iOS).",
                items=divergent_items,
                pill_class="status-pill-red",
                status_label="Divergent"
            )

            # 5. Companies with 0 Openings (Collapsible Expander)
            with st.expander(f"Monitored Companies with 0 Active Requisitions ({len(no_op_items)} Tracked Employers - Click to view)", expanded=False):
                render_no_openings_table(
                    title="Monitored Companies with 0 Current AI/Python Openings",
                    subtitle="These companies were checked during this run, but currently have 0 active GenAI / Python requisitions. Monitored on daily cron.",
                    items=no_op_items
                )

    # -------------------------------------------------------------------------
    # TAB: DEEP ANALYSIS & TAILORING WORKBENCH
    # -------------------------------------------------------------------------
    elif "Deep Analysis & Tailoring" in selected_menu:
        render_deep_analysis_tab(user_email, user_name)

    # -------------------------------------------------------------------------
    # TAB 3: CANDIDATE PROFILE (YAML Ground Truth)
    # -------------------------------------------------------------------------
    elif "Candidate Profile" in selected_menu:
        try:
            r = requests.get(f"{API_BASE}/api/profile", headers=get_auth_headers(), timeout=5)
            if r.status_code == 200:
                p_data = r.json()
                
                skill_chips = "".join([f'<span class="chip-green">{s}</span>' for s in p_data['verified_skills']])
                profile_card_html = f"""
                <div class="console-table-container" style="padding: 16px 20px;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
                        <div>
                            <div style="font-size: 16px; font-weight: 500; color: #E8EAED;">{p_data['candidate_name']}</div>
                            <div style="font-size: 12px; color: #9AA0A6; margin-top: 2px;">{p_data['professional_title']} • {p_data['experience_years']} Years Experience</div>
                        </div>
                        <span class="status-pill-green">Verified YAML Truth</span>
                    </div>
                    <div style="font-size: 11.5px; color: #9AA0A6; margin-bottom: 8px;">VERIFIED EXTRACTED SKILLS ({len(p_data['verified_skills'])}):</div>
                    <div>
                        {skill_chips}
                    </div>
                </div>
                """
                render_html(profile_card_html)

                st.markdown("<div style='font-size: 13px; font-weight: 500; margin-bottom: 6px;'>Stored YAML Schema (PostgreSQL):</div>", unsafe_allow_html=True)
                st.code(p_data["profile_yaml"], language="yaml")
            else:
                st.info("No candidate profile found. Please upload your document in 'Settings & Re-upload'.")
        except Exception as e:
            st.error(f"API Error: {e}")

    # -------------------------------------------------------------------------
    # TAB 4: SETTINGS & RE-UPLOAD
    # -------------------------------------------------------------------------
    elif "Settings & Re-upload" in selected_menu:
        st.markdown("<div style='font-weight: 500; font-size: 14px; margin-bottom: 4px;'>1. LLM Studio / Gemini API Key Configuration</div>", unsafe_allow_html=True)
        st.caption("Provide an API Key for deep LLM reasoning, or leave blank to use the built-in deterministic engine.")

        c1, c2 = st.columns([2, 1])
        with c1:
            g_key = st.text_input("Google AI Studio (Gemini) API Key", type="password", placeholder="AIzaSy...")
        with c2:
            endpoint = st.text_input("Endpoint URL", value="https://generativelanguage.googleapis.com/v1beta/openai/")

        if st.button("Save API Configuration", type="primary"):
            if g_key:
                try:
                    r = requests.post(f"{API_BASE}/api/user/api-key", json={"api_key": g_key, "llm_endpoint": endpoint}, headers=get_auth_headers(), timeout=5)
                    if r.status_code == 200:
                        st.success("API Key saved in PostgreSQL!")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.info("Using built-in deterministic extraction engine.")

        st.markdown("<hr style='border-color: #282D3B; margin: 20px 0;'>", unsafe_allow_html=True)

        st.markdown("<div style='font-weight: 500; font-size: 14px; margin-bottom: 4px;'>2. Re-upload Base Document & Recompile YAML</div>", unsafe_allow_html=True)
        st.caption("Upload a new PDF, DOCX, or TXT file to recompile your candidate YAML ground truth.")

        new_doc = st.file_uploader("Choose Base Document", type=["pdf", "docx", "txt", "md", "yaml", "yml"], key="reupload_doc_uploader")
        if new_doc:
            if st.session_state.get("last_reuploaded_doc_name") != new_doc.name:
                st.session_state.reupload_yaml = None
                st.session_state.reupload_meta = None
                st.session_state.last_reuploaded_doc_name = new_doc.name
        if new_doc and st.button("Extract Text & Recompile YAML", type="primary"):
            with st.spinner("Extracting text and compiling fresh YAML schema..."):
                try:
                    active_api = st.session_state.get("api_base_url", API_BASE).rstrip("/")
                    files = {"file": (new_doc.name, new_doc.getvalue(), new_doc.type)}
                    r = requests.post(f"{active_api}/api/profile/upload", files=files, headers=get_auth_headers(), timeout=30)
                    if r.status_code == 200:
                        data = r.json()
                        st.session_state.reupload_yaml = data["profile_yaml"]
                        st.session_state.reupload_meta = data
                        st.success(f"Successfully extracted {len(data['verified_skills'])} verified skills across all sections!")
                    else:
                        st.error(f"Extraction failed: {r.text}")
                except Exception as e:
                    st.error(f"Error: {e}")

        if "reupload_yaml" in st.session_state and st.session_state.reupload_yaml:
            meta = st.session_state.reupload_meta
            re_parsed = {}
            try:
                re_parsed = yaml.safe_load(st.session_state.reupload_yaml) or {}
            except Exception:
                pass

            re_exp = re_parsed.get("experience", [])
            re_proj = re_parsed.get("projects", [])
            re_edu = re_parsed.get("education", [])
            re_skills = meta.get("verified_skills", [])

            t_sk, t_ex, t_pr, t_ed, t_ym = st.tabs([
                f"Skills ({len(re_skills)})",
                f"Experience ({len(re_exp)})",
                f"Projects ({len(re_proj)})",
                f"Education ({len(re_edu)})",
                "Review YAML"
            ])

            with t_sk:
                chips = "".join([f'<span class="chip-green">{s}</span>' for s in re_skills])
                st.markdown(f"<div style='margin-bottom: 12px;'>{chips}</div>", unsafe_allow_html=True)

            with t_ex:
                for exp_item in re_exp:
                    st.markdown(f"**{exp_item.get('role')}** @ **{exp_item.get('company')}**")
                    for b in exp_item.get("bullets", []):
                        st.markdown(f"- {b}")
                    st.markdown("---")

            with t_pr:
                for pr in re_proj:
                    st.markdown(f"**{pr.get('name')}**" + (f" *({pr.get('tech_stack')})*" if pr.get('tech_stack') else ""))
                    for b in pr.get("bullets", []):
                        st.markdown(f"- {b}")
                    st.markdown("---")

            with t_ed:
                for ed in re_edu:
                    st.markdown(f"**{ed.get('degree')}** — {ed.get('institution')} *({ed.get('period') or ed.get('year')})*")

            with t_ym:
                revised_yaml = st.text_area("Review Extracted YAML Profile", value=st.session_state.reupload_yaml, height=240)

            if st.button("Confirm & Save to PostgreSQL", type="primary"):
                try:
                    active_api = st.session_state.get("api_base_url", API_BASE).rstrip("/")
                    payload = {
                        "candidate_name": meta["candidate_name"],
                        "professional_title": meta["professional_title"],
                        "experience_years": meta["experience_years"],
                        "verified_skills": meta["verified_skills"],
                        "profile_yaml": revised_yaml if 'revised_yaml' in locals() else st.session_state.reupload_yaml
                    }
                    r = requests.post(f"{active_api}/api/profile/save", json=payload, headers=get_auth_headers(), timeout=10)
                    if r.status_code == 200:
                        st.success("Candidate Profile updated successfully in database!")
                        st.session_state.reupload_yaml = None
                        time.sleep(1)
                        st.rerun()
                except Exception as e:
                    st.error(f"Error saving: {e}")

        st.markdown("<hr style='border-color: #282D3B; margin: 20px 0;'>", unsafe_allow_html=True)

        st.markdown("<div style='font-weight: 500; font-size: 14px; margin-bottom: 4px;'>3. Reset Profile</div>", unsafe_allow_html=True)
        st.caption("Wipe the active profile to re-trigger the initial upload sequence.")
        if st.button("Reset Candidate Profile", type="secondary"):
            try:
                r = requests.post(f"{API_BASE}/api/profile/reset", headers=get_auth_headers(), timeout=5)
                if r.status_code == 200:
                    st.session_state.is_onboarded = False
                    st.session_state.analysis_results = None
                    st.warning("Profile reset successfully.")
                    time.sleep(1)
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

        # ---------------------------------------------------------------------
        # 4. User Access Management (Visible only to boobesh2509@gmail.com)
        # ---------------------------------------------------------------------
        if (user_email or "").strip().lower() == "boobesh2509@gmail.com":
            st.markdown("<hr style='border-color: #282D3B; margin: 20px 0;'>", unsafe_allow_html=True)
            st.markdown("<div style='font-weight: 500; font-size: 14px; margin-bottom: 4px;'>4. User Access Management (Administrator Only)</div>", unsafe_allow_html=True)
            st.caption("Manage authorized enterprise users. Only accounts explicitly authorized below can sign in.")

            with st.expander("Authorize New User Email", expanded=False):
                with st.form("admin_add_user_form"):
                    col_u1, col_u2 = st.columns(2)
                    with col_u1:
                        new_u_email = st.text_input("New User Email", placeholder="colleague@domain.com")
                    with col_u2:
                        new_u_name = st.text_input("Display Name", placeholder="Colleague Name")
                    btn_add = st.form_submit_button("Authorize User Email", type="primary")
                    if btn_add:
                        clean_add = (new_u_email or "").strip().lower()
                        if clean_add and "@" in clean_add:
                            try:
                                r_add = requests.post(
                                    f"{API_BASE}/api/admin/users",
                                    json={"email": clean_add, "name": new_u_name or clean_add.split("@")[0].title()},
                                    headers=get_auth_headers(),
                                    timeout=6
                                )
                                if r_add.status_code == 200:
                                    st.success(f"User '{clean_add}' has been authorized successfully.")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    err_msg = r_add.text
                                    try:
                                        err_msg = r_add.json().get("detail", err_msg)
                                    except Exception:
                                        pass
                                    st.error(f"Failed to authorize: {err_msg}")
                            except Exception as e:
                                st.error(f"API Error: {e}")
                        else:
                            st.warning("Please provide a valid email address.")

            # Display Authorized Users Table
            try:
                r_users = requests.get(f"{API_BASE}/api/admin/users", headers=get_auth_headers(), timeout=6)
                if r_users.status_code == 200:
                    user_list = r_users.json()
                    st.markdown(f"<div style='font-size: 12.5px; color: #BDC1C6; margin: 12px 0 6px 0; font-weight: 500;'>Authorized Accounts ({len(user_list)}):</div>", unsafe_allow_html=True)
                    
                    user_rows_html = []
                    for u in user_list:
                        u_mail = u.get("email", "")
                        u_disp = u.get("display_name", "")
                        is_super = u.get("is_superadmin", False)
                        role_pill = '<span class="status-pill-green">Superadmin</span>' if is_super else '<span class="status-pill-blue">Authorized</span>'
                        created_str = (u.get("created_at") or "N/A")[:19]
                        user_rows_html.append(f"""
                        <tr>
                            <td><b style="color: #E8EAED;">{u_mail}</b></td>
                            <td>{u_disp}</td>
                            <td>{role_pill}</td>
                            <td>{created_str}</td>
                        </tr>
                        """)

                    u_table = f"""
                    <table class="console-table" style="margin-bottom: 14px;">
                        <thead>
                            <tr>
                                <th>Account Email</th>
                                <th>Display Name</th>
                                <th>Role</th>
                                <th>Authorized Date</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join(user_rows_html)}
                        </tbody>
                    </table>
                    """
                    render_html(u_table)

                    # Revoke controls for non-superadmin accounts
                    non_super_emails = [u.get("email") for u in user_list if not u.get("is_superadmin")]
                    if non_super_emails:
                        with st.form("revoke_user_form"):
                            st.markdown("<div style='font-size: 12px; color: #9AA0A6;'>Revoke Access for Account:</div>", unsafe_allow_html=True)
                            c_del1, c_del2 = st.columns([3, 1])
                            with c_del1:
                                target_del = st.selectbox("Select Account", options=non_super_emails, label_visibility="collapsed")
                            with c_del2:
                                btn_del = st.form_submit_button("Revoke Access", type="secondary")
                            if btn_del and target_del:
                                try:
                                    r_del = requests.delete(f"{API_BASE}/api/admin/users/{target_del}", headers=get_auth_headers(), timeout=6)
                                    if r_del.status_code == 200:
                                        st.success(f"Access revoked for '{target_del}'.")
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        st.error(f"Revocation failed: {r_del.text}")
                                except Exception as e:
                                    st.error(f"API Error: {e}")
                else:
                    st.error(f"Cannot load users: {r_users.text}")
            except Exception as e:
                st.error(f"API connection failed: {e}")

    # -------------------------------------------------------------------------
    # TAB 5: MONITORED COMPANIES DIRECTORY (2,000+)
    # -------------------------------------------------------------------------
    elif "Monitored Companies" in selected_menu:
        # Search & Display Filter
        dir_c1, dir_c2 = st.columns([3, 1])
        with dir_c1:
            dir_search = st.text_input("Filter Monitored Employers...", "", placeholder="Type company name e.g. OpenAI, Microsoft, Stripe...")
        with dir_c2:
            dir_limit_sel = st.selectbox("Display Limit", [50, 100, 250, "All"], index=1)

        all_jobs_pool = st.session_state.daily_jobs
        if dir_search:
            all_jobs_pool = [j for j in all_jobs_pool if dir_search.lower() in j.get('company_name', '').lower()]

        dir_limit_val = len(all_jobs_pool) if dir_limit_sel == "All" else int(dir_limit_sel)
        viewing_jobs = all_jobs_pool[:dir_limit_val]

        all_rows = []
        for job in viewing_jobs:
            c_name = job.get('company_name', 'Company')
            job_title = job.get('title', 'Role')
            grp = job.get('company_group', 'Enterprise')
            loc = job.get('location', 'Global')
            mode = job.get('work_mode', 'Remote')
            apply_link = resolve_career_url(job, c_name)
            ch = job.get('source_channel') or CompanyService.get_channel_from_url(apply_link)
            source_pill = get_source_pill_html(ch)
            all_rows.append(f"""
            <tr>
                <td style="width: 30px;"><input type="checkbox"></td>
                <td><b style="color: #8AB4F8;">{c_name}</b></td>
                <td><span class="status-pill-gray">{grp}</span></td>
                <td>{source_pill}</td>
                <td>{job_title}</td>
                <td>{loc} ({mode})</td>
                <td><a href="{apply_link}" target="_blank" style="color: #8AB4F8; text-decoration: none;">{ch} Requisition ↗</a></td>
            </tr>
            """)

        full_monitored_table = f"""
        <div class="console-table-container">
            <div class="console-table-header">
                <div class="console-table-title">
                    <span>Global Tracked Employers Registry ({len(all_jobs_pool)} Matching)</span>
                </div>
                <div style="font-size: 11.5px; color: #9AA0A6;">
                    Showing {len(viewing_jobs)} of {len(all_jobs_pool)} total monitored employers across MNCs, AI Startups & Remote SaaS
                </div>
            </div>
            <table class="console-table">
                <thead>
                    <tr>
                        <th style="width: 30px;">[ ]</th>
                        <th>Company Name</th>
                        <th>Sector</th>
                        <th>Channel</th>
                        <th>Representative Role</th>
                        <th>Location / Mode</th>
                        <th>Platform Requisition Link</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(all_rows)}
                </tbody>
            </table>
        </div>
        """
        render_html(full_monitored_table)

    # -------------------------------------------------------------------------
    # TAB 6: JOB SYNC ENGINE (Admin Only: boobesh2509@gmail.com)
    # -------------------------------------------------------------------------
    elif "Job Sync Engine" in selected_menu:
        render_job_sync_engine_tab(user_email)

# -----------------------------------------------------------------------------
# Component: Admin Job Sync Engine Module
# -----------------------------------------------------------------------------
def render_job_sync_engine_tab(user_email: str):
    """
    Dedicated Job Sync Engine Console for System Administrator.
    Provides live progress monitoring, mutual exclusion state, manual trigger,
    and ingestion rule matrix.
    """
    if (user_email or "").strip().lower() != "boobesh2509@gmail.com":
        st.error("Access Restricted: This administration module is exclusively available to boobesh2509@gmail.com.")
        return

    st.markdown("""
    <div style="margin-bottom: 16px;">
        <div style="font-size: 16px; font-weight: 600; color: #E8EAED;">Autonomous Job Sync Engine & Real-Time Orchestration</div>
        <div style="font-size: 12px; color: #9AA0A6; margin-top: 2px;">
            Multi-channel ingestion across official ATS career pages, LinkedIn (30-day window), Naukri, and remote networks. Enforces mutual-exclusion locking against concurrent executions.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Query current sync status
    try:
        r_stat = requests.get(f"{API_BASE}/api/jobs/sync/status", headers=get_auth_headers(), timeout=5)
        if r_stat.status_code == 200:
            sync_data = r_stat.json()
        else:
            sync_data = {"status": "UNKNOWN", "stage": f"Error loading status ({r_stat.status_code})"}
    except Exception as ex:
        sync_data = {"status": "UNKNOWN", "stage": f"Connection error: {ex}"}

    cur_status = sync_data.get("status", "IDLE")
    cur_stage = sync_data.get("stage", "System Ready")
    progress_pct = sync_data.get("progress_pct", 0)
    total_ingested = sync_data.get("total_ingested", 0)
    new_jobs_added = sync_data.get("new_jobs_added", 0)
    pruned_jobs = sync_data.get("pruned_jobs", 0)
    triggered_by = sync_data.get("triggered_by") or "System"
    started_at = sync_data.get("started_at") or "N/A"
    completed_at = sync_data.get("completed_at") or "N/A"
    elapsed_seconds = sync_data.get("elapsed_seconds", 0)
    active_jobs_in_db = sync_data.get("active_jobs_in_db", 0)
    error_message = sync_data.get("error_message")

    # -------------------------------------------------------------------------
    # STATE 1: RUNNING (Live Progress Bar & Auto-polling)
    # -------------------------------------------------------------------------
    if cur_status == "RUNNING":
        st.markdown(f"""
        <div style="background: rgba(26, 115, 232, 0.12); border: 1px solid #1A73E8; border-radius: 6px; padding: 14px 18px; margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 13.5px; font-weight: 600; color: #8AB4F8; text-transform: uppercase; letter-spacing: 0.04em;">Job Sync In Progress</span>
                <span style="font-size: 12px; background: #1A73E8; color: #FFFFFF; padding: 2px 8px; border-radius: 4px; font-weight: 500;">RUNNING</span>
            </div>
            <div style="font-size: 13px; color: #FFFFFF; font-weight: 500; margin-bottom: 4px;">{cur_stage}</div>
            <div style="font-size: 11.5px; color: #9AA0A6;">
                Triggered By: <b style="color: #E8EAED;">{triggered_by}</b> &nbsp;|&nbsp; Elapsed: <b style="color: #E8EAED;">{elapsed_seconds}s</b> &nbsp;|&nbsp; Ingested in this run: <b style="color: #81C995;">{total_ingested}</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.progress(progress_pct / 100.0, text=f"Sync Progress: {progress_pct}% — {cur_stage}")

        st.markdown("""
        <div style="background: rgba(242, 139, 130, 0.08); border: 1px solid rgba(242, 139, 130, 0.3); border-radius: 6px; padding: 10px 14px; margin-top: 14px; font-size: 12px; color: #F28B82;">
            <b>Execution Locked:</b> A background job sync is currently executing. Double execution is prohibited via mutual exclusion. This page will automatically update as tasks complete.
        </div>
        """, unsafe_allow_html=True)

        # Auto-refresh interval while sync is running
        time.sleep(2)
        st.rerun()

    # -------------------------------------------------------------------------
    # STATE 2: IDLE, COMPLETED, or FAILED
    # -------------------------------------------------------------------------
    else:
        # Status header badge
        badge_color = "#81C995" if cur_status == "COMPLETED" else ("#F28B82" if cur_status == "FAILED" else "#8AB4F8")
        st.markdown(f"""
        <div style="background: #182030; border: 1px solid #283754; border-radius: 6px; padding: 12px 16px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center;">
            <div>
                <span style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #9AA0A6; font-weight: 600;">Engine Status</span>
                <div style="font-size: 14px; font-weight: 600; color: {badge_color}; margin-top: 2px;">{cur_status}: {cur_stage}</div>
            </div>
            <div style="font-size: 11.5px; color: #9AA0A6; text-align: right;">
                Last Source: <b style="color: #FFFFFF;">{triggered_by}</b><br>
                Completed: <b style="color: #FFFFFF;">{completed_at}</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if error_message:
            st.error(f"Previous Sync Error: {error_message}")

        # Metrics Row
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        with m_col1:
            st.metric("Active Tech Roles in DB", f"{active_jobs_in_db:,}")
        with m_col2:
            st.metric("Total Ingested (Last Run)", f"{total_ingested:,}", f"+{new_jobs_added} new" if new_jobs_added else None)
        with m_col3:
            st.metric("Pruned Expired (>30d)", f"{pruned_jobs:,}")
        with m_col4:
            st.metric("Sync Duration", f"{elapsed_seconds}s")

        st.markdown("<br>", unsafe_allow_html=True)

        # Trigger Action Card
        st.markdown("""
        <div style="background: #1B2232; border: 1px solid #28354E; border-radius: 6px; padding: 14px 18px; margin-bottom: 16px;">
            <div style="font-size: 13.5px; font-weight: 600; color: #E8EAED;">Manual Ingestion Dispatcher</div>
            <div style="font-size: 12px; color: #9AA0A6; margin-top: 2px; margin-bottom: 12px;">
                Triggers an asynchronous job sync cycle across all configured channels. Automatically locks execution to prevent concurrent conflicts.
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Trigger Job Ingestion Now", type="primary", use_container_width=False):
            with st.spinner("Submitting background sync request to engine..."):
                try:
                    r_trig = requests.post(f"{API_BASE}/api/jobs/sync", headers=get_auth_headers(), timeout=10)
                    if r_trig.status_code == 202:
                        st.success("Job sync initiated successfully in background!")
                        time.sleep(1)
                        st.rerun()
                    elif r_trig.status_code == 409:
                        st.warning("A job sync is already active. Please wait for completion.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Failed to initiate sync ({r_trig.status_code}): {r_trig.text}")
                except Exception as ex:
                    st.error(f"Request failed: {ex}")

    # -------------------------------------------------------------------------
    # Ingestion Rules & Data Freshness Matrix
    # -------------------------------------------------------------------------
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div style="background: #182030; border: 1px solid #283754; border-radius: 6px; padding: 14px 18px;">
        <div style="font-size: 13.5px; font-weight: 600; color: #8AB4F8; margin-bottom: 8px;">Configured Ingestion Rules & Data Matrix</div>
        <table style="width: 100%; border-collapse: collapse; font-size: 12px; color: #BDC1C6;">
            <thead>
                <tr style="border-bottom: 1px solid #283754; text-align: left; color: #9AA0A6;">
                    <th style="padding: 6px 8px;">Channel</th>
                    <th style="padding: 6px 8px;">Freshness / Retention Rule</th>
                    <th style="padding: 6px 8px;">Role Scope</th>
                    <th style="padding: 6px 8px;">Geographic Constraint</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom: 1px solid #222B3D;">
                    <td style="padding: 8px; font-weight: 500; color: #FFFFFF;">Official Career ATS (Greenhouse, Lever, etc.)</td>
                    <td style="padding: 8px; color: #81C995;">NO 30-day cutoff. 100% taken as long as listed open on ATS.</td>
                    <td style="padding: 8px;">Technical engineering roles only.</td>
                    <td style="padding: 8px;">India (Any mode) OR Abroad (Remote only).</td>
                </tr>
                <tr style="border-bottom: 1px solid #222B3D;">
                    <td style="padding: 8px; font-weight: 500; color: #FFFFFF;">LinkedIn Jobs (Guest API)</td>
                    <td style="padding: 8px; color: #FDD663;">Filtered to past 30 days (f_TPR=r2592000). Expired pruned.</td>
                    <td style="padding: 8px;">AI Developer, FDE, GenAI, Cloud, Systems, FinTech Tech.</td>
                    <td style="padding: 8px;">India (Any mode) OR Abroad (Remote only).</td>
                </tr>
                <tr style="border-bottom: 1px solid #222B3D;">
                    <td style="padding: 8px; font-weight: 500; color: #FFFFFF;">Naukri IT Portals</td>
                    <td style="padding: 8px; color: #FDD663;">Filtered to past 30 days. Older pruned.</td>
                    <td style="padding: 8px;">Cloud, DevOps, GenAI, Quant, Systems Tech.</td>
                    <td style="padding: 8px;">India (Bengaluru, Hyderabad, Pune, Chennai, etc.).</td>
                </tr>
                <tr>
                    <td style="padding: 8px; font-weight: 500; color: #FFFFFF;">Global Remote APIs (Arbeitnow, Remotive, Jobicy)</td>
                    <td style="padding: 8px; color: #FDD663;">Fresh active feeds only.</td>
                    <td style="padding: 8px;">Full Stack, Backend, Systems, DevOps, AI.</td>
                    <td style="padding: 8px;">Global Remote / Worldwide only.</td>
                </tr>
            </tbody>
        </table>
        <div style="margin-top: 10px; font-size: 11px; color: #9AA0A6;">
            Stored Fields: Company Name, Job Title, Experience (Min/Max Years), Posting Date, Full Description (JD), Verified Apply URL.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # Explorer: Newly Synced Positions in Database
    # -------------------------------------------------------------------------
    st.markdown("<br>", unsafe_allow_html=True)
    real_synced = [
        j for j in st.session_state.daily_jobs
        if not (j.get("job_id") or "").startswith("OPP-") and j.get("job_id") != "NO-ROLE-FOUND"
    ]

    st.markdown(f"""
    <div style="background: #1B2232; border: 1px solid #28354E; border-radius: 6px; padding: 14px 18px; margin-bottom: 12px;">
        <div style="font-size: 14px; font-weight: 600; color: #E8EAED;">Newly Synced Tech Positions Explorer ({len(real_synced):,} Active Requisitions)</div>
        <div style="font-size: 12px; color: #9AA0A6; margin-top: 2px;">
            Authentic live openings ingested across official ATS portals, LinkedIn (past 30 days), Naukri, and remote networks.
        </div>
    </div>
    """, unsafe_allow_html=True)

    if real_synced:
        # Per-Column Filters (Zero filters above table - every column has its own filter)
        f_c1, f_c2, f_c3, f_c4, f_c5, f_c6, f_c7 = st.columns([1.7, 2.3, 1.2, 1.1, 1.0, 1.5, 0.9])
        with f_c1:
            f_sp_comp = st.text_input("Filter Company", "", placeholder="Filter Company...", label_visibility="collapsed", key="sp_f_comp")
        with f_c2:
            f_sp_title = st.text_input("Filter Title", "", placeholder="Filter Job Title...", label_visibility="collapsed", key="sp_f_title")
        with f_c3:
            f_sp_chan = st.selectbox("Filter Channel", ["All", "Career Page", "LinkedIn", "Naukri"], index=0, label_visibility="collapsed", key="sp_f_chan")
        with f_c4:
            f_sp_exp = st.selectbox("Filter Experience", ["All", "0 - 2 Yrs", "2 - 5 Yrs", "5+ Yrs"], index=0, label_visibility="collapsed", key="sp_f_exp")
        with f_c5:
            f_sp_mode = st.selectbox("Filter Work Mode", ["All", "Remote", "Hybrid", "On-site"], index=0, label_visibility="collapsed", key="sp_f_mode")
        with f_c6:
            f_sp_loc = st.text_input("Filter Location", "", placeholder="Filter Location...", label_visibility="collapsed", key="sp_f_loc")
        with f_c7:
            f_sp_limit = st.selectbox("Show Rows", [50, 100, 250, "All"], index=0, label_visibility="collapsed", key="sp_f_limit")

        # Multi-filter execution across all columns simultaneously
        filtered_pos = real_synced
        if f_sp_comp.strip():
            q_c = f_sp_comp.strip().lower()
            filtered_pos = [j for j in filtered_pos if q_c in (j.get("company_name") or "").lower()]
        if f_sp_title.strip():
            q_t = f_sp_title.strip().lower()
            filtered_pos = [j for j in filtered_pos if q_t in (j.get("title") or "").lower()]
        if f_sp_chan != "All":
            filtered_pos = [j for j in filtered_pos if (j.get("source_channel") or "").lower() == f_sp_chan.lower()]
        if f_sp_exp != "All":
            if "0 - 2" in f_sp_exp:
                filtered_pos = [j for j in filtered_pos if (j.get("min_exp") or 0) <= 2]
            elif "2 - 5" in f_sp_exp:
                filtered_pos = [j for j in filtered_pos if ((j.get("min_exp") or 0) >= 1.5 and (j.get("max_exp") or 5) <= 6) or any(k in (j.get("experience_text") or "") for k in ["2", "3", "4", "5"])]
            elif "5+" in f_sp_exp:
                filtered_pos = [j for j in filtered_pos if (j.get("min_exp") or 0) >= 5 or (j.get("max_exp") or 0) >= 5]
        if f_sp_mode != "All":
            filtered_pos = [j for j in filtered_pos if (j.get("work_mode") or "").lower() == f_sp_mode.lower()]
        if f_sp_loc.strip():
            q_l = f_sp_loc.strip().lower()
            filtered_pos = [j for j in filtered_pos if q_l in (j.get("location") or "").lower()]

        pos_display_count = len(filtered_pos) if f_sp_limit == "All" else int(f_sp_limit)
        pos_display = filtered_pos[:pos_display_count]

        active_filters = sum([
            1 if f_sp_comp.strip() else 0,
            1 if f_sp_title.strip() else 0,
            1 if f_sp_chan != "All" else 0,
            1 if f_sp_exp != "All" else 0,
            1 if f_sp_mode != "All" else 0,
            1 if f_sp_loc.strip() else 0
        ])
        filter_badge = f" — {active_filters} Column Filters Active" if active_filters > 0 else ""

        pos_rows = []
        sync_modals = []
        import html, re
        for j in pos_display:
            cname = j.get("company_name", "Tech Employer")
            title = j.get("title", "Engineering Role")
            chan = j.get("source_channel", "Career Page")
            loc = j.get("location", "Remote")
            wmode = j.get("work_mode", "Remote")
            exp = j.get("experience_text", "2 - 5 Years")
            url = j.get("url") or j.get("job_apply_url") or "#"
            url_low = url.lower()
            if "arbeitnow.com" in url_low or "jobicy.com" in url_low:
                url = CompanyService.get_official_career_url(cname)
            elif "naukri.com" in url_low and ("job-listings-" in url_low or "expjd=true" in url_low):
                url = CompanyService.get_official_naukri_url(cname, title)
            jid = j.get("job_id", "REQ")
            chan_pill = get_source_pill_html(chan)
            clean_jid = re.sub(r'[^a-zA-Z0-9_-]', '_', str(jid))

            from core.jd_formatter import JobDescriptionFormatter
            full_jd_text = JobDescriptionFormatter.get_full_job_description({
                "company_name": cname,
                "title": title,
                "location": loc,
                "work_mode": wmode,
                "experience_text": exp,
                "source_channel": chan,
                "job_id": jid,
                "skills_required": j.get("skills_required") or [],
                "raw_description": j.get("raw_description") or j.get("raw_markdown") or ""
            })
            safe_jd = html.escape(full_jd_text)

            pos_rows.append(f"""
            <tr>
                <td><b style="color: #8AB4F8;">{cname}</b></td>
                <td>
                    <div style="display: flex; align-items: center; justify-content: space-between; gap: 6px;">
                        <span style="color: #FFFFFF; font-weight: 500;">{title}</span>
                        <a href="#sync_modal_{clean_jid}" class="role-info-icon" title="View Full Role Details & Job Description (JD)">ⓘ</a>
                    </div>
                </td>
                <td>{chan_pill}</td>
                <td><span class="status-pill-gray">{exp}</span></td>
                <td>{wmode}</td>
                <td style="color: #9AA0A6; font-size: 11.5px;">{loc}</td>
                <td><a href="{url}" target="_blank" class="job-id-pill" title="Apply via {chan} (#{jid})">#{jid} ↗</a></td>
            </tr>
            """)

            sync_modals.append(f"""
            <div id="sync_modal_{clean_jid}" class="jd-modal-overlay">
                <a href="#close" class="jd-modal-backdrop"></a>
                <div class="jd-modal-box">
                    <div class="jd-modal-header">
                        <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 14px;">
                            <div>
                                <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                                    <span style="font-size: 18px; font-weight: 700; color: #FFFFFF;">{cname}</span>
                                    <span class="status-pill-gray">{j.get("company_group", "Tech_Enterprise")}</span>
                                    {chan_pill}
                                    <span class="chip-green">Live Synced Role</span>
                                </div>
                                <h2 style="margin: 8px 0 0 0; font-size: 20px; font-weight: 600; color: #8AB4F8;">{title}</h2>
                            </div>
                            <a href="#close" class="jd-modal-close" title="Close Specification">✕</a>
                        </div>
                    </div>

                    <div class="jd-meta-grid">
                        <div class="jd-meta-item"><span class="jd-meta-label">Location</span><span class="jd-meta-value">{loc}</span></div>
                        <div class="jd-meta-item"><span class="jd-meta-label">Work Mode</span><span class="jd-meta-value">{wmode}</span></div>
                        <div class="jd-meta-item"><span class="jd-meta-label">Experience Bracket</span><span class="jd-meta-value">{exp}</span></div>
                        <div class="jd-meta-item"><span class="jd-meta-label">Requisition ID</span><span class="jd-meta-value">#{jid}</span></div>
                        <div class="jd-meta-item"><span class="jd-meta-label">Source Channel</span><span class="jd-meta-value">{chan}</span></div>
                        <div class="jd-meta-item"><span class="jd-meta-label">Status</span><span class="jd-meta-value" style="color: #81C995;">Verified Open Requisition</span></div>
                    </div>

                    <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                        <a href="{url}" target="_blank" class="btn-direct-apply" style="padding: 6px 14px; font-size: 12px;">Apply on Official Portal ↗</a>
                        <a href="?nav=Deep+Analysis+%26+Tailoring&job_id={jid}" target="_self" class="btn-deep-tailor" style="padding: 6px 14px; font-size: 12px;">Deep Analyse & Tailor CV ↗</a>
                        <a href="#close" style="background: rgba(255,255,255,0.06); color: #9AA0A6; border: 1px solid #374151; border-radius: 4px; padding: 6px 14px; font-size: 12px; text-decoration: none; margin-left: auto;">Close Window</a>
                    </div>

                    <div class="jd-content-section">
                        <div style="font-size: 12px; font-weight: 600; color: #9AA0A6; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.05em;">Complete Job Description (JD)</div>
                        <div class="jd-raw-text">{safe_jd}</div>
                    </div>
                </div>
            </div>
            """)

        full_synced_table = f"""
        <div class="console-table-container">
            <div class="console-table-header">
                <div class="console-table-title">
                    <span>Live Synced Positions ({len(filtered_pos)} Matching{filter_badge})</span>
                </div>
                <div style="font-size: 11.5px; color: #9AA0A6;">
                    Showing {len(pos_display)} of {len(filtered_pos)} positions in scope
                </div>
            </div>
            <table class="console-table">
                <thead>
                    <tr>
                        <th>Company</th>
                        <th>Job Title</th>
                        <th>Channel</th>
                        <th>Experience</th>
                        <th>Work Mode</th>
                        <th>Location</th>
                        <th>Apply Link</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(pos_rows)}
                </tbody>
            </table>
            {''.join(sync_modals)}
        </div>
        """
        render_html(full_synced_table)
    else:
        st.info("No newly synced positions found in active memory. Click 'Trigger Job Ingestion Now' above to run a sync cycle.")


# -----------------------------------------------------------------------------
# Component: Dense Match Data Table
# -----------------------------------------------------------------------------
def render_console_matches_table(title: str, subtitle: str, items: List[Dict[str, Any]], pill_class: str, status_label: str):
    count = len(items)
    if not items:
        empty_table_html = f"""
        <div class="console-table-container">
            <div class="console-table-header">
                <div class="console-table-title">
                    <span>{title}</span>
                    <span class="console-table-counter">0</span>
                </div>
                <div style="font-size: 11.5px; color: #9AA0A6;">
                    {subtitle}
                </div>
            </div>
            <div style="padding: 20px; color: #9AA0A6; font-size: 12.5px; text-align: center;">
                No roles match the active filter criteria in this score bracket.
            </div>
        </div>
        """
        render_html(empty_table_html)
        return

    table_rows = []
    modals_html = []
    import html, re
    for item in items:
        matched = item.get("matched_skills", [])
        lag = item.get("lag_skills", [])
        matched_chips = "".join([f'<span class="chip-green">{s}</span>' for s in matched[:4]]) if matched else '<span style="color:#64748B;">None</span>'
        lag_chips = "".join([f'<span class="chip-red">{s}</span>' for s in lag[:3]]) if lag else '<span style="color:#64748B;">None</span>'
        
        score_val = item.get("match_score", 0)
        apply_url = item.get("job_apply_url") or item.get("url") or "#"
        tip = item.get("tailoring_tip", "")
        role_title = item.get("title", "Role")
        comp_name = item.get("company_name", "Company")
        comp_group = item.get("company_group", "MNC")
        source_channel = item.get("source_channel") or CompanyService.get_channel_from_url(apply_url)
        source_pill = get_source_pill_html(source_channel)
        job_id = item.get("job_id") or f"REQ-{abs(hash(apply_url)) % 100000}"
        loc = item.get("location", "Global")
        exp_asked = item.get("experience_asked", "N/A")
        work_mode = item.get("work_mode", "Remote")
        clean_jid = re.sub(r'[^a-zA-Z0-9_-]', '_', str(job_id))

        import urllib.parse
        career_url = resolve_career_url(item, comp_name)
        google_jobs_hub = f"https://www.google.com/search?q={urllib.parse.quote(comp_name + ' jobs openings')}&ibp=htl;jobs"
        li_url = item.get("linkedin_jobs_url") or CompanyService.get_official_linkedin_url(comp_name, role_title)
        nk_url = item.get("naukri_jobs_url") or CompanyService.get_official_naukri_url(comp_name, role_title)

        # Dynamic score color
        score_color = "#81C995" if score_val >= 75 else ("#FDD663" if score_val >= 60 else "#F28B82")

        from core.jd_formatter import JobDescriptionFormatter
        full_jd_text = JobDescriptionFormatter.get_full_job_description({
            "company_name": comp_name,
            "title": role_title,
            "location": loc,
            "work_mode": work_mode,
            "experience_text": exp_asked,
            "source_channel": source_channel,
            "job_id": job_id,
            "skills_required": item.get("skills_required") or item.get("matched_skills", []),
            "raw_description": item.get("raw_description") or item.get("raw_markdown") or ""
        })
        safe_jd = html.escape(full_jd_text)

        table_rows.append(f"""
        <tr>
            <td style="width: 30px;"><input type="checkbox"></td>
            <td>{source_pill}</td>
            <td><span class="{pill_class}">{status_label}</span></td>
            <td>
                <a href="{career_url}" target="_blank" class="job-id-pill" title="{source_channel} Requisition #{job_id}">
                    #{job_id} ↗
                </a>
            </td>
            <td>
                <div>
                    <b style="color: #FFFFFF; font-size: 13px;">{comp_name}</b>
                </div>
                <div style="font-size: 11px; color: #9AA0A6; margin-top: 2px;">
                    <span class="status-pill-gray">{comp_group}</span> • {loc}
                </div>
            </td>
            <td>
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 6px;">
                    <a href="{career_url}" target="_blank" style="color: #8AB4F8; font-weight: 600; text-decoration: none; font-size: 13px;" title="Open {source_channel} Requisition #{job_id}">
                        {role_title} ↗
                    </a>
                    <a href="#modal_{clean_jid}" class="role-info-icon" title="View Full Role Details & Job Description (JD)">ⓘ</a>
                </div>
            </td>
            <td><b style="font-size: 13px; color: {score_color};">{score_val}%</b></td>
            <td style="font-size: 11.5px; white-space: nowrap;">{exp_asked}</td>
            <td style="font-size: 11.5px;"><span class="status-pill-gray">{work_mode}</span></td>
            <td style="max-width: 170px;">{matched_chips}</td>
            <td style="max-width: 140px;">{lag_chips}</td>
            <td style="font-size: 11px; color: #CBD5E1; max-width: 200px; line-height: 1.4;">{tip}</td>
            <td style="white-space: nowrap;">
                <div style="display: flex; flex-direction: column; gap: 4px;">
                    <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                        <a href="{career_url}" target="_blank" class="source-pill-career" style="text-decoration: none; padding: 2px 6px; font-size: 10.5px;" title="Official Direct Career Portal">Career Portal ↗</a>
                        <a href="{google_jobs_hub}" target="_blank" style="background: rgba(52, 168, 83, 0.15); color: #81C995; border: 1px solid rgba(52, 168, 83, 0.3); border-radius: 3px; padding: 2px 6px; font-size: 10.5px; text-decoration: none;" title="View ALL live open positions for {comp_name} on one master page">All Positions Hub ↗</a>
                        <a href="{li_url}" target="_blank" class="source-pill-linkedin" style="text-decoration: none; padding: 2px 6px; font-size: 10.5px;" title="LinkedIn Requisitions (Sorted by Date DD)">LinkedIn ↗</a>
                        <a href="{nk_url}" target="_blank" class="source-pill-naukri" style="text-decoration: none; padding: 2px 6px; font-size: 10.5px;" title="Naukri Direct Query">Naukri ↗</a>
                    </div>
                    <a href="?nav=Deep+Analysis+%26+Tailoring&job_id={job_id}" target="_self" class="btn-deep-tailor" style="text-align: center; padding: 2px 6px; font-size: 11px;" title="Deep Analyse & Optimize profile for {role_title}">
                        Tailor Document ↗
                    </a>
                </div>
            </td>
        </tr>
        """)

        modals_html.append(f"""
        <div id="modal_{clean_jid}" class="jd-modal-overlay">
            <a href="#close" class="jd-modal-backdrop"></a>
            <div class="jd-modal-box">
                <div class="jd-modal-header">
                    <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 14px;">
                        <div>
                            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                                <span style="font-size: 18px; font-weight: 700; color: #FFFFFF;">{comp_name}</span>
                                <span class="status-pill-gray">{comp_group}</span>
                                {source_pill}
                                <span class="{pill_class}">{status_label}</span>
                                <span style="font-size: 12px; font-weight: 600; color: {score_color}; background: rgba(255,255,255,0.06); padding: 2px 8px; border-radius: 12px; border: 1px solid {score_color};">{score_val}% Match</span>
                            </div>
                            <h2 style="margin: 8px 0 0 0; font-size: 20px; font-weight: 600; color: #8AB4F8;">{role_title}</h2>
                        </div>
                        <a href="#close" class="jd-modal-close" title="Close Specification">✕</a>
                    </div>
                </div>

                <div class="jd-meta-grid">
                    <div class="jd-meta-item"><span class="jd-meta-label">Location</span><span class="jd-meta-value">{loc}</span></div>
                    <div class="jd-meta-item"><span class="jd-meta-label">Work Mode</span><span class="jd-meta-value">{work_mode}</span></div>
                    <div class="jd-meta-item"><span class="jd-meta-label">Experience Bracket</span><span class="jd-meta-value">{exp_asked}</span></div>
                    <div class="jd-meta-item"><span class="jd-meta-label">Requisition ID</span><span class="jd-meta-value">#{job_id}</span></div>
                    <div class="jd-meta-item"><span class="jd-meta-label">Match Category</span><span class="jd-meta-value">{status_label} ({score_val}%)</span></div>
                    <div class="jd-meta-item"><span class="jd-meta-label">Domain</span><span class="jd-meta-value">{item.get('job_domain', 'Engineering')}</span></div>
                </div>

                <div class="jd-skills-box">
                    <div style="margin-bottom: 8px;">
                        <b style="color: #81C995; font-size: 11.5px; text-transform: uppercase;">Matched Candidate Skills:</b>
                        <div style="margin-top: 4px;">{matched_chips}</div>
                    </div>
                    <div style="margin-bottom: 8px;">
                        <b style="color: #F28B82; font-size: 11.5px; text-transform: uppercase;">Skill Gaps (Lag Skills):</b>
                        <div style="margin-top: 4px;">{lag_chips}</div>
                    </div>
                    <div style="background: rgba(255,255,255,0.02); border: 1px solid #28354E; border-radius: 4px; padding: 10px; margin-top: 8px;">
                        <b style="color: #FDD663; font-size: 11.5px; text-transform: uppercase;">Tailoring Recommendation:</b>
                        <p style="margin: 4px 0 0 0; color: #E8EAED; font-size: 12px; line-height: 1.5;">{tip}</p>
                    </div>
                </div>

                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                    <a href="{career_url}" target="_blank" class="btn-direct-apply" style="padding: 6px 14px; font-size: 12px;">Apply on Official Portal ↗</a>
                    <a href="?nav=Deep+Analysis+%26+Tailoring&job_id={job_id}" target="_self" class="btn-deep-tailor" style="padding: 6px 14px; font-size: 12px;">Deep Analyse & Tailor Profile ↗</a>
                    <a href="{google_jobs_hub}" target="_blank" style="background: #202534; color: #81C995; border: 1px solid rgba(52, 168, 83, 0.3); border-radius: 4px; padding: 6px 14px; font-size: 12px; text-decoration: none;">All Company Positions ↗</a>
                    <a href="#close" style="background: rgba(255,255,255,0.06); color: #9AA0A6; border: 1px solid #374151; border-radius: 4px; padding: 6px 14px; font-size: 12px; text-decoration: none; margin-left: auto;">Close Window</a>
                </div>

                <div class="jd-content-section">
                    <div style="font-size: 12px; font-weight: 600; color: #9AA0A6; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.05em;">Complete Job Description (JD)</div>
                    <div class="jd-raw-text">{safe_jd}</div>
                </div>
            </div>
        </div>
        """)

    full_table = f"""
    <div class="console-table-container">
        <div class="console-table-header">
            <div class="console-table-title">
                <span>{title}</span>
                <span class="console-table-counter">{count}</span>
            </div>
            <div style="font-size: 11.5px; color: #9AA0A6;">
                {subtitle}
            </div>
        </div>
        <table class="console-table">
            <thead>
                <tr>
                    <th style="width: 30px;">[x]</th>
                    <th>Channel</th>
                    <th>Status</th>
                    <th>Career Job ID</th>
                    <th>Company Name</th>
                    <th>Role Title</th>
                    <th>Match</th>
                    <th>Exp Asked</th>
                    <th>Work Mode</th>
                    <th>Matched Skills</th>
                    <th>Missing Skills</th>
                    <th>Tailoring Recommendation</th>
                    <th>Requisition & Optimization Actions</th>
                </tr>
            </thead>
            <tbody>
                {''.join(table_rows)}
            </tbody>
        </table>
        {''.join(modals_html)}
    </div>
    """
    render_html(full_table)

# -----------------------------------------------------------------------------
# Component: 0 Openings Table
# -----------------------------------------------------------------------------
def render_no_openings_table(title: str, subtitle: str, items: List[Dict[str, Any]]):
    count = len(items)
    if not items:
        empty_no_ops = f"""
        <div class="console-table-container">
            <div class="console-table-header">
                <div class="console-table-title">
                    <span>{title}</span>
                    <span class="console-table-counter">0</span>
                </div>
                <div style="font-size: 11.5px; color: #9AA0A6;">
                    {subtitle}
                </div>
            </div>
            <div style="padding: 16px; color: #9AA0A6; font-size: 12px; text-align: center;">
                All selected companies had active requisitions.
            </div>
        </div>
        """
        render_html(empty_no_ops)
        return

    table_rows = []
    import urllib.parse
    for item in items:
        c_name = item.get("company_name", "N/A")
        grp = item.get("company_group", "MNC")
        portal_url = item.get("career_portal_url") or resolve_career_url(item, c_name)
        google_hub = f"https://www.google.com/search?q={urllib.parse.quote(c_name + ' jobs openings')}&ibp=htl;jobs"
        tip = item.get("tailoring_tip", "0 active openings listed in local database.")
        cand_target = st.session_state.get("onboard_meta", {}).get("professional_title", "Engineer")
        li_link = item.get("linkedin_jobs_url") or CompanyService.get_official_linkedin_url(c_name, cand_target)
        nk_link = item.get("naukri_jobs_url") or CompanyService.get_official_naukri_url(c_name, cand_target)

        table_rows.append(f"""
        <tr>
            <td style="width: 30px;"><input type="checkbox"></td>
            <td><b style="color: #BDC1C6;">{c_name}</b></td>
            <td><span class="status-pill-gray">{grp}</span></td>
            <td><span class="status-pill-gray">0 Active Roles</span></td>
            <td style="font-size: 11.5px; color: #9AA0A6;">{tip}</td>
            <td style="white-space: nowrap;">
                <a href="{portal_url}" target="_blank" class="source-pill-career" style="text-decoration: none; margin-right: 4px;">Career Portal ↗</a>
                <a href="{google_hub}" target="_blank" style="background: rgba(52, 168, 83, 0.15); color: #81C995; border: 1px solid rgba(52, 168, 83, 0.3); border-radius: 3px; padding: 2px 6px; font-size: 10.5px; text-decoration: none; margin-right: 4px;" title="View ALL live open positions for {c_name} on one master page">All Positions Hub ↗</a>
                <a href="{li_link}" target="_blank" class="source-pill-linkedin" style="text-decoration: none; margin-right: 4px;">LinkedIn ↗</a>
                <a href="{nk_link}" target="_blank" class="source-pill-naukri" style="text-decoration: none;">Naukri ↗</a>
            </td>
        </tr>
        """)

    full_table = f"""
    <div class="console-table-container">
        <div class="console-table-header">
            <div class="console-table-title">
                <span>{title}</span>
                <span class="console-table-counter">{count}</span>
            </div>
            <div style="font-size: 11.5px; color: #9AA0A6;">
                {subtitle}
            </div>
        </div>
        <table class="console-table">
            <thead>
                <tr>
                    <th style="width: 30px;">[ ]</th>
                    <th>Company Name</th>
                    <th>Sector</th>
                    <th>Status</th>
                    <th>Evaluation Finding</th>
                    <th>Cross-Platform Direct Search Shortcuts</th>
                </tr>
            </thead>
            <tbody>
                {''.join(table_rows)}
            </tbody>
        </table>
    </div>
    """
    render_html(full_table)

# -----------------------------------------------------------------------------
# Main Routing
# -----------------------------------------------------------------------------
def main():
    if not st.session_state.token and not st.session_state.get("logged_out"):
        try:
            r_auth = requests.post(f"{API_BASE}/api/auth/dev-login", json={"email": DEFAULT_USER_EMAIL}, timeout=5)
            if r_auth.status_code == 200:
                auth_data = r_auth.json()
                st.session_state.token = auth_data.get("token")
                st.session_state.user_info = auth_data
                st.session_state.is_onboarded = auth_data.get("is_onboarded", True)
        except Exception:
            pass

    if not st.session_state.token:
        render_login()
    else:
        render_main_dashboard()

if __name__ == "__main__":
    main()
