"""
Database Models for Career Analyser & Matching Portal
=====================================================
PostgreSQL Models (SQLAlchemy ORM):
- User
- CandidateProfile
- CompanyJob
- AnalysisJobResult
"""

import uuid
from datetime import datetime, date, timezone
from typing import List, Optional
from sqlalchemy import (
    Column,
    String,
    Float,
    Boolean,
    DateTime,
    Date,
    Text,
    ForeignKey,
    JSON,
    Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now_naive() -> datetime:
    """Returns a UTC datetime without tzinfo for cross-dialect PostgreSQL/SQLite compatibility."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    email = Column(String(256), unique=True, index=True, nullable=False)
    display_name = Column(String(256), nullable=False)
    avatar_url = Column(String(512), nullable=True)
    auth_provider = Column(String(32), default="google")
    api_key = Column(Text, nullable=True)  # Gemini or LLM API Key
    llm_endpoint = Column(String(256), default="https://generativelanguage.googleapis.com/v1beta/openai/")
    created_at = Column(DateTime, default=utc_now_naive)

    # Relationships
    profile = relationship("CandidateProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    analysis_results = relationship("AnalysisJobResult", back_populates="user", cascade="all, delete-orphan")

class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    candidate_name = Column(String(256), nullable=False)
    professional_title = Column(String(256), nullable=False)
    experience_years = Column(Float, default=3.0)
    location = Column(String(256), default="Chennai, India")
    verified_skills = Column(JSON, default=list)  # List of normalized skill strings
    profile_yaml = Column(Text, nullable=False)    # Full YAML text (Ground truth)
    source_filename = Column(String(256), nullable=True)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

    # Relationships
    user = relationship("User", back_populates="profile")

class CompanyJob(Base):
    __tablename__ = "company_jobs"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    job_id = Column(String(128), index=True, nullable=True)  # Requisition ID (e.g. INFSYS-EXTERNAL-255682)
    company_name = Column(String(256), index=True, nullable=False)
    company_group = Column(String(64), index=True, default="MNC")  # MNC, AI_Startup, Remote_First, Enterprise
    source_channel = Column(String(64), index=True, default="Career Page")  # Career Page, LinkedIn, Naukri
    title = Column(String(256), nullable=False)
    location = Column(String(256), default="Remote")
    work_mode = Column(String(64), default="Remote")  # Remote, Hybrid, On-site
    experience_text = Column(String(128), default="1 - 3 Years")
    min_exp = Column(Float, default=1.0)
    max_exp = Column(Float, default=3.0)
    url = Column(String(1024), nullable=False)
    skills_required = Column(JSON, default=list)
    raw_description = Column(Text, nullable=True)
    fetched_date = Column(Date, default=lambda: datetime.now(timezone.utc).date(), index=True)
    created_at = Column(DateTime, default=utc_now_naive)

class AnalysisJobResult(Base):
    __tablename__ = "analysis_job_results"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    job_id = Column(String(64), ForeignKey("company_jobs.id", ondelete="CASCADE"), index=True, nullable=False)
    
    match_score = Column(Float, nullable=False)  # 0.0 - 100.0%
    match_category = Column(String(64), nullable=False)  # Exact Match, Action Needed, Role Matched JD Divergent
    experience_fit = Column(Boolean, default=True)
    
    matched_skills = Column(JSON, default=list)
    lag_skills = Column(JSON, default=list)  # Missing / skills to be improved
    suggestion = Column(String(64), nullable=False)  # Apply Directly, Action Needed, Skill has to be improved
    
    tailoring_tip = Column(Text, nullable=True)
    analyzed_at = Column(DateTime, default=utc_now_naive)

    # Relationships
    user = relationship("User", back_populates="analysis_results")
    job = relationship("CompanyJob")

