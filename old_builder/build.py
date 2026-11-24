#!/usr/bin/env python3
"""
Builder: Compiles profile.yaml into a Canva-identical ATS-compliant PDF via Typst.
Faithfully preserves the typography, centered wing-line headings, square bullets, and visual styling
of 'Boobesh - AI Engineer_old.pdf' while integrating the updated 10 work experience bullets
and personal projects/POCs.
"""

import sys
import yaml
import typst
from pathlib import Path

def load_profile_data(yaml_path: str = "profile.yaml") -> dict:
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def format_text(text: str) -> str:
    """Escapes Typst special characters and bolds key technical metrics."""
    if not text:
        return ""
    
    # 1. Escape Typst syntax triggers
    text = text.replace("@", "\\@")
    text = text.replace("<10s", "\\<10s")
    text = text.replace("~", "\\~")

    # 2. Key metric bolding (exact, non-overlapping phrases)
    targets = [
        ("\\~25s to \\<10s (\\~60% reduction)", "*\\~25s to \\<10s (\\~60% reduction)*"),
        ("100% factual fidelity against live records", "*100% factual fidelity against live records*"),
        ("200 KB to 2 MB", "*200 KB to 2 MB*"),
        ("78+ enterprise cloud tools", "*78+ enterprise cloud tools*"),
        ("78+ MCP tools", "*78+ MCP tools*"),
        ("75%", "*75%*"),
        ("\\~60%", "*\\~60%*"),
        ("up to 80%", "*up to 80%*"),
        ("20–30% projected compute cost savings", "*20–30% projected compute cost savings*"),
        ("20-30% projected compute cost savings", "*20-30% projected compute cost savings*"),
    ]
    for src, dst in targets:
        text = text.replace(src, dst)
        
    return text

# Mapping bullet IDs to crisp bold lead-in titles matching Boobesh_S_GenAI_Engineer
BULLET_TITLES = {
    "corent_orchestration_router": "Multi-Agent Orchestration",
    "corent_context_caching": "Context Caching",
    "corent_persistent_session_reuse": "Context Caching",
    "corent_anti_hallucination_grounding": "Anti-Hallucination Database Grounding",
    "corent_structural_payload_truncation": "Context-Window Payload Optimization",
    "corent_analytics_pipeline": "Automated Data Analytics Pipeline",
    "corent_self_healing_code_gen": "Automated Data Analytics Pipeline",
    "corent_bounded_session_hitl": "Bounded Session Memory & HITL",
    "corent_multi_provider_routing": "Multi-Provider LLM Routing",
    "corent_opentelemetry_observability": "OpenTelemetry Distributed Tracing",
    "corent_backend_architecture": "High-Performance Backend Engineering",
    "corent_multicloud_cost_migration": "Multi-Cloud Cost & Migration Intelligence",
}

def generate_typst_code(data: dict) -> str:
    c = data["candidate"]
    contact = c["contact"]
    links = c["links"]
    summary = format_text(data["summaries"].get("classic_ai_engineer", data["summaries"]["primary"]))
    
    classic_skills = data.get("skills_classic")
    experience = data["experience"][0]
    projects = data["projects"]
    education = data["education"]

    typst_lines = []

    # Document & Page Setup matching old Canva resume
    typst_lines.append("""// ==============================================================================
// Boobesh S - AI Engineer (Typst)
// Styled to exactly match 'Boobesh - AI Engineer_old.pdf'
// ==============================================================================

#set page(
  paper: "a4",
  margin: (top: 24pt, bottom: 24pt, left: 28pt, right: 28pt),
  header: none,
  footer: none
)

#set text(
  font: "Times New Roman",
  size: 10pt,
  fill: rgb("#25303d"),
  lang: "en",
  spacing: 105%
)

#set par(justify: true, leading: 0.53em)

// Centered Section Heading with 0.75pt horizontal line wings on both sides
#let section_heading(title) = [
  #v(0.70em)
  #grid(
    columns: (1fr, auto, 1fr),
    align: (center + horizon),
    gutter: 0.8em,
    line(length: 100%, stroke: 0.75pt + rgb("#25303d")),
    text(weight: "bold", size: 13.5pt, fill: rgb("#25303d"))[#title],
    line(length: 100%, stroke: 0.75pt + rgb("#25303d"))
  )
  #v(0.45em)
]

// Bullet Item matching old resume style (vector square bullet optically centered with first line)
#let bullet_item(body) = block(width: 100%, inset: (left: 1.25em, bottom: 0.28em))[
  #place(left, dx: -1.25em, dy: 0.20em)[#box(width: 3.2pt, height: 3.2pt, fill: rgb("#25303d"))]
  #body
]

// Page 2 Bullet Item with slightly more vertical breathing room
#let bullet_item_p2(body) = block(width: 100%, inset: (left: 1.25em, bottom: 0.36em))[
  #place(left, dx: -1.25em, dy: 0.20em)[#box(width: 3.2pt, height: 3.2pt, fill: rgb("#25303d"))]
  #body
]

// Skill Item: Clean inline layout WITHOUT bullets (ATS-friendly, no bullet characters)
#let skill_item(category, items) = block(width: 100%, inset: (bottom: 0.25em))[
  #text(weight: "bold", size: 10.2pt, fill: rgb("#25303d"))[#category:] #h(0.35em) #text(size: 10pt)[#items]
]
""")

    # Candidate Header
    phone = contact.get("phone", "")
    email = contact.get("email", "")
    email_escaped = email.replace("@", "\\@")
    linkedin_url = links.get("linkedin", "https://linkedin.com/in/boobesh-s-8a8387201")
    github_url = links.get("github", "https://github.com/Boobesh25")

    header_block = f"""
// ----------------- HEADER -----------------
#align(center)[
  #text(weight: "bold", size: 25pt, fill: rgb("#25303d"))[BOOBESH S] \\
  #v(0.12em)
  #text(weight: "bold", size: 13.5pt, fill: rgb("#25303d"))[AI ENGINEER] \\
  #v(0.32em)
  #text(size: 9.0pt, fill: rgb("#25303d"))[
    Chennai, India #h(0.35em) | #h(0.35em)
    #link("tel:{phone}")[{phone}] #h(0.35em) | #h(0.35em)
    #link("mailto:{email}")[{email_escaped}] #h(0.35em) | #h(0.35em)
    #link("{linkedin_url}")[{linkedin_url}] #h(0.35em) | #h(0.35em)
    #link("{github_url}")[{github_url}]
  ]
]
"""
    typst_lines.append(header_block)

    # Profile Summary
    summary_block = f"""
// ----------------- PROFILE SUMMARY -----------------
#section_heading("Profile Summary")
#text(size: 10.2pt)[
{summary}
]
"""
    typst_lines.append(summary_block)

    # Technical Skills Section (from base_resume.yaml, Machine Learning removed, NO bullets)
    skills_block = """
// ----------------- TECHNICAL SKILLS -----------------
#section_heading("Technical Skills")
"""
    if classic_skills:
        for sk_k, sk_v in classic_skills.items():
            if sk_k == "machine_learning" or "machine learning" in sk_v["title"].lower():
                continue
            skills_block += f'#skill_item("{sk_v["title"]}", "{sk_v["items"]}")\n'
    else:
        classic_items = [
            ("Programming & Backend", "Python (asyncio, asyncpg), FastAPI, REST APIs, WebSockets, SQLAlchemy, Pandas, NumPy, Gunicorn, Nginx"),
            ("AI / GenAI", "Agentic AI (Google ADK, LangGraph), Model Context Protocol (MCP - Client & Server Integration), ReAct Decision Loops, RAG, Vector Search, Embeddings, Semantic Search, Cross-Encoders, Prompt Engineering, Multi-Provider LLM Routing"),
            ("Databases", "PostgreSQL (pgvector), MySQL, Qdrant, ChromaDB"),
            ("Messaging & Streaming", "Kafka, Redis, Server-Sent Events (SSE)"),
            ("Cloud & AI Platforms", "Azure OpenAI, AWS Bedrock, Vertex AI, Gemini AI, Google Cloud Run"),
            ("Infrastructure & Observability", "Docker, Kubernetes (HPA & KEDA Autoscaling), OpenTelemetry, OpenLIT, Fluent Bit, Loki, Grafana, LangSmith, ArgoCD, Linux"),
            ("Software Engineering Fundamentals", "Object-Oriented Design & Classic Design Patterns (Factory, Strategy, Observer, Singleton, Adapter, Builder), Distributed Tracing & Reliability Engineering, API Contract Design & Schema Validation (Pydantic)"),
        ]
        for cat, itms in classic_items:
            skills_block += f'#skill_item("{cat}", "{itms}")\n'
    typst_lines.append(skills_block)

    # Professional Experience Section (Company Work: Corent Technology)
    exp_header = f"""
// ----------------- PROFESSIONAL EXPERIENCE -----------------
#section_heading("Professional Experience")

#block(width: 100%, inset: (bottom: 0.2em))[
  #grid(
    columns: (1fr, auto),
    align: (left, right),
    [#text(weight: "bold", size: 11.5pt, fill: rgb("#25303d"))[Software Engineer (AI / GenAI) - Corent Technology]],
    [#text(weight: "bold", size: 10.5pt, fill: rgb("#25303d"))[2023 - Present (3+ Years)]]
  )
  #v(-0.35em)
  #grid(
    columns: (1fr, auto),
    align: (left, right),
    [#text(style: "italic", size: 10pt, fill: rgb("#4b5563"))[Python Backend & AI Engineering Team]],
    [#text(size: 10pt, fill: rgb("#4b5563"))[Chennai, India]]
  )
]

#v(0.1em)
#block(width: 100%, inset: (left: 0.5em, bottom: 0.35em))[
  #text(style: "italic", size: 9.8pt, fill: rgb("#374151"))[Worked as part of the founding AI/ML engineering team, developing enterprise-grade GenAI applications, AI workflow orchestration systems, and cloud intelligence platforms.]
]
"""
    typst_lines.append(exp_header)

    # Bullets 0-6 on Page 1 (7 bullets to fill Page 1 gracefully without white space),
    # Pagebreak, Bullets 7-9 on Page 2 (3 bullets + Projects + Education)
    bullets = experience["bullet_pool"]
    for i, bullet in enumerate(bullets):
        b_id = bullet.get("id", "")
        lead_in = BULLET_TITLES.get(b_id, "")
        claim = format_text(bullet["claim"])
        if lead_in:
            claim_text = f"*{lead_in}:* {claim}"
        else:
            claim_text = claim
        
        if i < 7:
            typst_lines.append(f"#bullet_item[{claim_text}]\n")
        else:
            typst_lines.append(f"#bullet_item_p2[{claim_text}]\n")

        # After bullet 7 (index 6), pagebreak so Page 1 is fully filled and Page 2 is well-balanced
        if i == 6:
            typst_lines.append("\n#pagebreak()\n")

    # Personal Projects & POCs Section (Differentiating Company vs Personal Learning)
    proj_block = """
#section_heading("Personal Projects & POCs")
"""
    for p_idx, proj in enumerate(projects):
        tech_str = ", ".join(proj["tech_stack"])
        repo_url = proj.get("repo", "")
        live_url = proj.get("live_url", "")
        link_items = []
        if repo_url:
            link_items.append(f'#link("{repo_url}")[{repo_url}]')
        if live_url:
            link_items.append(f'#link("{live_url}")[{live_url}]')
        links_str = " #h(0.5em) | #h(0.5em) ".join(link_items)

        proj_block += f"""
#block(width: 100%, inset: (bottom: 0.25em))[
  #text(weight: "bold", size: 10.8pt, fill: rgb("#25303d"))[{proj["name"]}] \\
  #v(-0.35em)
  #text(style: "italic", size: 9.2pt, fill: rgb("#4b5563"))[{tech_str}] \\
  #v(-0.30em)
  #text(size: 8.8pt)[{links_str}]
]
"""
        for b in proj["bullets"]:
            b_text = format_text(b)
            proj_block += f"#bullet_item_p2[{b_text}]\n"
        if p_idx < len(projects) - 1:
            proj_block += "#v(0.5em)\n"
    typst_lines.append(proj_block)

    # Education Section
    edu_block = """
#section_heading("Education")
"""
    for i, edu in enumerate(education):
        period_str = edu["period"].replace("August 2022 – May 2024", "2022 - 2024").replace("August 2019 – May 2022", "2019 - 2022")
        edu_block += f"""
#block(width: 100%, inset: (bottom: 0.42em))[
  #grid(
    columns: (1fr, auto),
    align: (left, right),
    [#text(weight: "bold", size: 10.2pt, fill: rgb("#25303d"))[{edu["degree"]} credentials]],
    [#text(weight: "bold", size: 9.8pt, fill: rgb("#25303d"))[{period_str}]]
  )
  #v(-0.35em)
  #grid(
    columns: (1fr, auto),
    align: (left, right),
    [#text(style: "italic", size: 9.5pt, fill: rgb("#4b5563"))[{edu["institution"]}]],
    [#text(size: 9.5pt, fill: rgb("#4b5563"))[{edu["location"]}]]
  )
]
""".replace(" credentials", "")
    typst_lines.append(edu_block)

    return "\n".join(typst_lines)

def build_pdf(yaml_path: str = "profile.yaml", typ_path: str = "main.typ", pdf_path: str = "exports/Boobesh_S_GenAI_Engineer.pdf"):
    import os
    os.makedirs("exports", exist_ok=True)
    os.makedirs("exports/archive", exist_ok=True)

    # Check data/profile.yaml fallback
    if not os.path.exists(yaml_path) and os.path.exists(os.path.join("data", yaml_path)):
        yaml_path = os.path.join("data", yaml_path)

    print(f"Loading data from {yaml_path}...")
    data = load_profile_data(yaml_path)

    print("Generating Typst code...")
    typst_content = generate_typst_code(data)
    with open(typ_path, "w", encoding="utf-8") as f:
        f.write(typst_content)
    print(f"Wrote Typst file to {typ_path}")

    # Compile target PDFs into exports/ directory
    target_pdfs = [
        pdf_path,
        "exports/archive/Boobesh - AI Engineer.pdf",
        "exports/archive/Boobesh_S_GenAI_Engineer_Latest.pdf",
        "exports/archive/Boobesh_S_GenAI_Engineer_v2.pdf"
    ]
    for target in target_pdfs:
        try:
            typst.compile(typ_path, output=target)
            print(f"Successfully compiled {target}!")
        except Exception as e:
            print(f"Notice: {target} locked or failed ({e}).")

    # Render PNG pages for visual inspection into exports/archive
    print("Rendering PNG pages for preview...")
    try:
        typst.compile(typ_path, output="exports/archive/page_{n}.png", format="png", ppi=150)
        print("Rendered PNG pages to exports/archive/.")
    except Exception as e:
        print(f"Notice: PNG render skipped ({e}).")

if __name__ == "__main__":
    build_pdf()
