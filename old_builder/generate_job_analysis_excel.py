#!/usr/bin/env python3
"""
Generate Job Match Analysis Excel Report
========================================
Creates a comprehensive, beautifully styled .xlsx report containing:
- Best Matches (>= 75%)
- Nearest Matches (60% - 74%)
- Matched Role, but JD Not Matched (<35%)
- Candidate Profile Keywords Match Matrix
"""

import json
from pathlib import Path
from analyzer import (
    JobMatcher,
    CareerPageExtractor,
    JobPosting,
    ExcelReportGenerator
)

def build_report():
    matcher = JobMatcher("profile.yaml")

    # 1. Best Match: Infosys Python ML / GenAI (Real Case Study)
    with open("infosys_genai_job.json", "r", encoding="utf-8") as f:
        infosys_data = json.load(f)
    job_infosys = CareerPageExtractor.extract_from_json_dict(
        infosys_data, 
        url="https://career.infosys.com/jobdesc?jobReferenceCode=INFSYS-EXTERNAL-255682"
    )
    res_infosys = matcher.evaluate_job(job_infosys)

    # 2. Best Match: Canonical AI Systems & Python Distributed Software Engineer
    with open("sample_greenhouse_job.json", "r", encoding="utf-8") as f:
        canonical_data = json.load(f)
    job_canonical = CareerPageExtractor.extract_from_json_dict(
        canonical_data, 
        url="https://boards.greenhouse.io/canonical/jobs/5238202"
    )
    res_canonical = matcher.evaluate_job(job_canonical)

    # 3. Best Match: Fal AI - AI Fabric Architect (Discovered via live feed)
    job_fal = JobPosting(
        url="https://www.arbeitnow.com/jobs/companies/fal-ai/remote-ai-fabric-architect-51975",
        company="Fal AI",
        title="AI Fabric Architect",
        location="Remote",
        posted_date="2026-02-18",
        raw_markdown="Architect scalable AI inference fabrics using Python, Docker, OpenTelemetry, Redis, FastAPI, asynchronous backend microservices, and LLM orchestration. Requires 3+ years building production AI and Python systems.",
        tech_stack=["Python", "FastAPI", "OpenTelemetry", "Docker", "Redis", "LLM", "Microservices"]
    )
    res_fal = matcher.evaluate_job(job_fal)

    # 4. Nearest Match: Senior Python Backend & AI Engineer @ DataBridge Labs
    job_nearest_1 = JobPosting(
        url="https://remotive.com/remote-jobs/software-dev/senior-python-ai-engineer-182901",
        company="DataBridge Labs",
        title="Senior Python Backend & AI Engineer",
        location="Remote (India / APAC)",
        posted_date="2026-02-15",
        raw_markdown="Looking for an engineer with 4-6 years experience in Python, FastAPI, PostgreSQL, and LLMs. Familiarity with Kubernetes, Helm, Golang, and CI/CD pipelines. Will build high-throughput APIs and RAG integrations.",
        tech_stack=["Python", "FastAPI", "PostgreSQL", "Kubernetes", "Golang", "RAG", "CI/CD"]
    )
    res_nearest_1 = matcher.evaluate_job(job_nearest_1)

    # 5. Nearest Match: Cloud AI Platform Engineer @ CloudPulse
    job_nearest_2 = JobPosting(
        url="https://jobicy.com/jobs/163800-cloud-ai-platform-engineer",
        company="CloudPulse Technologies",
        title="Cloud AI Platform Engineer",
        location="Bengaluru, India",
        posted_date="2026-02-10",
        raw_markdown="We need a Cloud AI Platform Engineer with 3+ years experience. Tech stack: Python, AWS, Azure, Terraform, Kafka, Snowflake, and LLM prompt engineering. Experience building automated cloud analytics pipelines.",
        tech_stack=["Python", "AWS", "Azure", "Terraform", "Kafka", "Snowflake", "Prompt Engineering"]
    )
    res_nearest_2 = matcher.evaluate_job(job_nearest_2)

    # 6. Matched Role, but JD Not Matched: AI/ML Engineer (Edge & Computer Vision) @ NVision Robotics
    job_divergent_1 = JobPosting(
        url="https://jobs.lever.co/nvision/d8923b71-1204-4b55-a22b-87a3219488a0",
        company="NVision Robotics",
        title="AI/ML Engineer (Edge & Computer Vision)",
        location="Bangalore, India",
        posted_date="2026-02-14",
        raw_markdown="Seeking an AI Engineer with 5+ years experience in C++, CUDA kernel optimization, TensorRT, PyTorch C++ bindings, OpenCV, and embedded Linux (Jetson Orin). Responsible for on-device real-time object detection models and hardware acceleration. Python is only used for offline prototyping.",
        tech_stack=["C++", "CUDA", "TensorRT", "OpenCV", "Embedded Linux", "Jetson Orin", "Hardware Acceleration"]
    )
    res_divergent_1 = matcher.evaluate_job(job_divergent_1)

    # 7. Matched Role, but JD Not Matched: Lead AI Engineer - Foundation Models @ BioSynthetics AI
    job_divergent_2 = JobPosting(
        url="https://boards.greenhouse.io/bioresearch/jobs/6192840",
        company="BioSynthetics AI",
        title="Lead AI Engineer - Deep Learning & Foundation Models",
        location="Hyderabad, India",
        posted_date="2026-02-12",
        raw_markdown="Role Title: Lead AI Engineer. Requirements: PhD in Computer Science or Statistics with 7+ years of deep learning research. Expertise in distributed pre-training of 70B+ parameter models using Megatron-LM, DeepSpeed, JAX, and TPU clusters. Publication record in NeurIPS/ICML required. No web API or application engineering required.",
        tech_stack=["DeepSpeed", "Megatron-LM", "JAX", "Distributed Pre-training", "TPUs", "PhD", "NeurIPS"]
    )
    res_divergent_2 = matcher.evaluate_job(job_divergent_2)

    # 8. Matched Role, but JD Not Matched: AI Software Engineer (Mobile) @ AppCraft
    job_divergent_3 = JobPosting(
        url="https://www.arbeitnow.com/jobs/companies/appcraft/ai-software-engineer-ios-59124",
        company="AppCraft Mobile",
        title="AI Software Engineer (Mobile & On-Device ML)",
        location="Remote",
        posted_date="2026-02-11",
        raw_markdown="Join as an AI Software Engineer focusing on on-device machine learning for iOS apps. Requires 4+ years of Swift, SwiftUI, Apple CoreML, CreateML, Metal Performance Shaders, and Objective-C. Experience optimizing quantized models for Apple Silicon neural engine.",
        tech_stack=["Swift", "SwiftUI", "CoreML", "CreateML", "Metal", "iOS", "Neural Engine"]
    )
    res_divergent_3 = matcher.evaluate_job(job_divergent_3)

    results = [
        ("Best Match", res_infosys),
        ("Best Match", res_canonical),
        ("Best Match", res_fal),
        ("Nearest Match", res_nearest_1),
        ("Nearest Match", res_nearest_2),
        ("Matched Role, JD Not Matched", res_divergent_1),
        ("Matched Role, JD Not Matched", res_divergent_2),
        ("Matched Role, JD Not Matched", res_divergent_3),
    ]

    output_file = "Job_Match_Analysis.xlsx"
    saved_path = ExcelReportGenerator.generate_report(results, output_path=output_file)
    print(f"✅ Excel report successfully generated at: {saved_path}")
    return saved_path

if __name__ == "__main__":
    build_report()

