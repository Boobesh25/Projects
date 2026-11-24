"""
Excel Report Generator for Career Page Analyser
==============================================
Generates an executive-ready Excel workbook (.xlsx) containing:
1. All Evaluated Roles (Master View with Match Categories & Keyword Breakdowns)
2. Best Matches (>= 75%)
3. Nearest Matches (60% - 74%)
4. Matched Role, but JD Not Matched (<35%)
5. Candidate Profile Keywords Match Matrix
"""

from pathlib import Path
from typing import List, Dict, Any, Tuple
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from .models import MatchResult, JobPosting
from .matcher import JobMatcher

class ExcelReportGenerator:
    """Generates a styled .xlsx report comparing candidate profile against job postings."""

    COLOR_PRIMARY_NAVY = "1F4E79"
    COLOR_TEXT_WHITE = "FFFFFF"
    
    FILL_BEST = "D1E7DD"        # Soft Green
    TEXT_BEST = "0F5132"
    
    FILL_NEAREST = "FFF3CD"     # Soft Yellow/Amber
    TEXT_NEAREST = "664D03"
    
    FILL_DIVERGENT = "F8D7DA"   # Soft Red
    TEXT_DIVERGENT = "842029"
    
    FILL_HEADER_GRAY = "F1F5F9"
    FILL_ZEBRA_LIGHT = "F8FAFC"

    SKILL_ALIASES = {
        "Python": ["python", "python3", "technology->ai-data science->python - ai-data science"],
        "FastAPI": ["fastapi"],
        "REST APIs": ["rest api", "rest apis", "restful", "api"],
        "Generative AI": ["generative ai", "genai", "technology->ai-generative ai->generative ai for data analytics"],
        "Agentic AI / Workflows": ["agentic", "agent", "agents", "multi-agent"],
        "Model Context Protocol (MCP)": ["mcp", "model context protocol"],
        "ReAct Decision Loops": ["react", "react loops"],
        "RAG (Retrieval-Augmented Gen)": ["rag", "retrieval-augmented generation"],
        "LangChain": ["langchain"],
        "Prompt Engineering": ["prompt engineering", "prompt optimization"],
        "Vector Search & DBs": ["vector", "vector search", "vector databases", "chromadb", "pgvector", "qdrant"],
        "ChromaDB": ["chromadb"],
        "pgvector": ["pgvector"],
        "Qdrant": ["qdrant"],
        "PostgreSQL": ["postgresql", "postgres"],
        "SQL Grounding (Anti-Hallucination)": ["sql", "grounding", "database grounding"],
        "Multi-Provider LLM Routing": ["llm", "llms", "routing"],
        "Gemini AI / Vertex AI": ["gemini", "vertex ai"],
        "Azure / Azure OpenAI": ["azure", "azure openai"],
        "AWS / Bedrock": ["aws", "aws bedrock"],
        "GCP (Google Cloud)": ["gcp", "google cloud"],
        "Docker": ["docker"],
        "Kubernetes": ["kubernetes", "k8s"],
        "OpenTelemetry": ["opentelemetry", "tracing"],
        "Redis Caching": ["redis"],
        "Kafka": ["kafka"],
        "Git / Version Control": ["git", "version control"],
        "Pandas & NumPy": ["pandas", "numpy"],
        "WebSockets / SSE": ["websockets", "sse", "streaming"],
        "Linux & Shell": ["linux", "embedded linux", "shell"]
    }

    @classmethod
    def generate_report(
        cls,
        results: List[Tuple[str, MatchResult]],
        output_path: str = "Job_Match_Analysis.xlsx",
        profile_path: str = "profile.yaml"
    ) -> str:
        wb = openpyxl.Workbook()
        
        # 1. Master Sheet: All Evaluated Roles
        ws_master = wb.active
        ws_master.title = "All_Evaluated_Roles"
        cls._build_roles_sheet(ws_master, results, sheet_title="ALL EVALUATED CAREER ROLES - MASTER SUMMARY")

        # 2. Sheet 2: Best Matches (>= 75%)
        best_matches = [r for r in results if r[0] == "Best Match"]
        ws_best = wb.create_sheet(title="Best_Matches_High_Priority")
        cls._build_roles_sheet(ws_best, best_matches, sheet_title="PRIORITY BEST MATCHES (>= 75% - 80%+)")

        # 3. Sheet 3: Nearest Matches (60% - 74%)
        nearest_matches = [r for r in results if r[0] == "Nearest Match"]
        ws_nearest = wb.create_sheet(title="Nearest_Matches_Upskill")
        cls._build_roles_sheet(ws_nearest, nearest_matches, sheet_title="NEAREST MATCHES (60% - 74% - RAPID UPSKILL FIT)")

        # 4. Sheet 4: Matched Role, JD Divergent
        divergent_matches = [r for r in results if r[0] == "Matched Role, JD Not Matched"]
        ws_divergent = wb.create_sheet(title="Role_Matched_JD_Divergent")
        cls._build_roles_sheet(ws_divergent, divergent_matches, sheet_title="ROLE MATCHED IN TITLE, BUT JD DIVERGENT (<35%)")

        # 5. Sheet 5: Keywords Match Matrix
        ws_matrix = wb.create_sheet(title="Keywords_Match_Matrix")
        cls._build_matrix_sheet(ws_matrix, results)

        # Save workbook
        save_file = Path(output_path)
        wb.save(save_file)
        return str(save_file.resolve())

    @classmethod
    def _build_roles_sheet(cls, ws, results: List[Tuple[str, MatchResult]], sheet_title: str):
        ws.views.sheetView[0].showGridLines = True

        # Sheet Title Banner
        ws.merge_cells("A1:K1")
        title_cell = ws["A1"]
        title_cell.value = sheet_title
        title_cell.font = Font(name="Calibri", size=14, bold=True, color=cls.COLOR_TEXT_WHITE)
        title_cell.fill = PatternFill(start_color=cls.COLOR_PRIMARY_NAVY, end_color=cls.COLOR_PRIMARY_NAVY, fill_type="solid")
        title_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 36

        # Subtitle / Candidate Info Banner
        ws.merge_cells("A2:K2")
        sub_cell = ws["A2"]
        sub_cell.value = "Candidate: Boobesh S | Profile: GenAI Engineer (3+ Years Experience) | Target Fit: 75% - 80%+"
        sub_cell.font = Font(name="Calibri", size=10, italic=True, color="475569")
        sub_cell.fill = PatternFill(start_color=cls.FILL_HEADER_GRAY, end_color=cls.FILL_HEADER_GRAY, fill_type="solid")
        sub_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[2].height = 20

        # Headers
        headers = [
            "Category",
            "Company",
            "Job Title / Role",
            "Match Score",
            "Location",
            "Experience Fit",
            "Matched Profile Keywords",
            "Matched Count",
            "Missing / Gap Keywords",
            "Key Recommendation / Tailoring Tip",
            "Application / Portal URL"
        ]

        ws.append([]) # Row 3 blank for visual breathing room
        ws.row_dimensions[3].height = 8
        ws.append(headers) # Row 4
        ws.row_dimensions[4].height = 28

        header_font = Font(name="Calibri", size=11, bold=True, color=cls.COLOR_TEXT_WHITE)
        header_fill = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
        thin_border = Border(
            left=Side(style='thin', color="CBD5E1"),
            right=Side(style='thin', color="CBD5E1"),
            top=Side(style='thin', color="CBD5E1"),
            bottom=Side(style='thin', color="CBD5E1")
        )

        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=4, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = thin_border

        # Populate rows
        for row_idx, (cat, res) in enumerate(results, start=5):
            ws.row_dimensions[row_idx].height = 36
            matched_str = ", ".join(res.matched_skills) if res.matched_skills else "None"
            missing_str = ", ".join(res.missing_skills) if res.missing_skills else "None"
            tip = res.tailoring_tips[0] if res.tailoring_tips else "Apply standard profile."

            row_data = [
                cat,
                res.company,
                res.job_title,
                f"{res.overall_match_score}%",
                res.location,
                f"{res.exp_required_text} ({'Aligned' if res.experience_fit else 'Gap/Uncertain'})",
                matched_str,
                len(res.matched_skills),
                missing_str,
                tip,
                res.url
            ]
            ws.append(row_data)

            # Category cell styling
            cat_cell = ws.cell(row=row_idx, column=1)
            cat_cell.alignment = Alignment(horizontal="center", vertical="center")
            if cat == "Best Match":
                cat_cell.fill = PatternFill(start_color=cls.FILL_BEST, fill_type="solid")
                cat_cell.font = Font(name="Calibri", size=10, bold=True, color=cls.TEXT_BEST)
            elif cat == "Nearest Match":
                cat_cell.fill = PatternFill(start_color=cls.FILL_NEAREST, fill_type="solid")
                cat_cell.font = Font(name="Calibri", size=10, bold=True, color=cls.TEXT_NEAREST)
            else:
                cat_cell.fill = PatternFill(start_color=cls.FILL_DIVERGENT, fill_type="solid")
                cat_cell.font = Font(name="Calibri", size=10, bold=True, color=cls.TEXT_DIVERGENT)

            # Score cell styling
            score_cell = ws.cell(row=row_idx, column=4)
            score_cell.alignment = Alignment(horizontal="center", vertical="center")
            if res.overall_match_score >= 75:
                score_cell.fill = PatternFill(start_color=cls.FILL_BEST, fill_type="solid")
                score_cell.font = Font(name="Calibri", size=11, bold=True, color=cls.TEXT_BEST)
            elif res.overall_match_score >= 60:
                score_cell.fill = PatternFill(start_color=cls.FILL_NEAREST, fill_type="solid")
                score_cell.font = Font(name="Calibri", size=11, bold=True, color=cls.TEXT_NEAREST)
            else:
                score_cell.fill = PatternFill(start_color=cls.FILL_DIVERGENT, fill_type="solid")
                score_cell.font = Font(name="Calibri", size=11, bold=True, color=cls.TEXT_DIVERGENT)

            # URL hyperlink styling
            url_cell = ws.cell(row=row_idx, column=11)
            if res.url and res.url.startswith("http"):
                url_cell.hyperlink = res.url
                url_cell.font = Font(name="Calibri", size=10, color="0000EE", underline="single")
            url_cell.alignment = Alignment(horizontal="left", vertical="center")

            # Border for all row cells
            for col_idx in range(1, len(headers) + 1):
                c = ws.cell(row=row_idx, column=col_idx)
                c.border = thin_border
                if col_idx in [7, 9, 10]:
                    c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

        cls._adjust_column_widths(ws, min_widths={
            1: 22, # Category
            2: 20, # Company
            3: 32, # Title
            4: 14, # Score
            5: 18, # Location
            6: 22, # Exp Fit
            7: 42, # Matched Skills
            8: 14, # Matched Count
            9: 32, # Missing Skills
            10: 45, # Tip
            11: 40  # URL
        })

    @classmethod
    def _build_matrix_sheet(cls, ws, results: List[Tuple[str, MatchResult]]):
        ws.views.sheetView[0].showGridLines = True

        # Sheet Title Banner
        ws.merge_cells("A1:K1")
        title_cell = ws["A1"]
        title_cell.value = "CANDIDATE KEYWORDS MATCH MATRIX (BOOBESH S PROFILE VS TARGET JDs)"
        title_cell.font = Font(name="Calibri", size=14, bold=True, color=cls.COLOR_TEXT_WHITE)
        title_cell.fill = PatternFill(start_color=cls.COLOR_PRIMARY_NAVY, end_color=cls.COLOR_PRIMARY_NAVY, fill_type="solid")
        title_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 36

        # Subtitle
        ws.merge_cells("A2:K2")
        sub_cell = ws["A2"]
        sub_cell.value = "Cross-reference of Boobesh's 56+ verified profile skills against discovered job postings"
        sub_cell.font = Font(name="Calibri", size=10, italic=True, color="475569")
        sub_cell.fill = PatternFill(start_color=cls.FILL_HEADER_GRAY, end_color=cls.FILL_HEADER_GRAY, fill_type="solid")
        sub_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[2].height = 20

        # Matrix Headers
        headers = ["Candidate Skill Keyword", "Domain / Category", "Profile Source"]
        for _, r in results:
            short_title = f"{r.company}\n({r.job_title[:16]}...)"
            headers.append(short_title)
        headers.append("Market Demand Count")

        ws.append([]) # Row 3 blank
        ws.append(headers) # Row 4
        ws.row_dimensions[4].height = 32

        thin_border = Border(
            left=Side(style='thin', color="CBD5E1"),
            right=Side(style='thin', color="CBD5E1"),
            top=Side(style='thin', color="CBD5E1"),
            bottom=Side(style='thin', color="CBD5E1")
        )
        header_font = Font(name="Calibri", size=10, bold=True, color=cls.COLOR_TEXT_WHITE)
        header_fill = PatternFill(start_color="334155", fill_type="solid")

        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=4, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = thin_border

        profile_skills_inventory = [
            ("Python", "Programming & Backend", "Corent Tech (3+ yrs)"),
            ("FastAPI", "Programming & Backend", "Production APIs / SSE"),
            ("REST APIs", "Programming & Backend", "Core Microservices"),
            ("Generative AI", "AI & GenAI", "Production LLM Solutions"),
            ("Agentic AI / Workflows", "AI & GenAI", "Google ADK & LangGraph"),
            ("Model Context Protocol (MCP)", "AI & GenAI", "Custom Client/Server"),
            ("ReAct Decision Loops", "AI & GenAI", "Autonomous Agents"),
            ("RAG (Retrieval-Augmented Gen)", "AI & GenAI", "Enterprise Knowledge"),
            ("LangChain", "AI & GenAI", "AI Framework"),
            ("Prompt Engineering", "AI & GenAI", "Guardrails & Few-Shot"),
            ("Vector Search & DBs", "Databases & AI", "pgvector, Qdrant, ChromaDB"),
            ("ChromaDB", "Databases & AI", "Local Embeddings"),
            ("pgvector", "Databases & AI", "PostgreSQL AI Vector"),
            ("Qdrant", "Databases & AI", "Production Vector DB"),
            ("PostgreSQL", "Databases & AI", "Asyncpg & Schema Design"),
            ("SQL Grounding (Anti-Hallucination)", "AI & GenAI", "Deterministic Schema-SQL"),
            ("Multi-Provider LLM Routing", "AI & GenAI", "Gemini, Bedrock, Azure"),
            ("Gemini AI / Vertex AI", "Cloud & AI", "Vertex AI & 1.5 Pro"),
            ("Azure / Azure OpenAI", "Cloud & AI", "Enterprise Deployments"),
            ("AWS / Bedrock", "Cloud & AI", "Nova & Titan Models"),
            ("GCP (Google Cloud)", "Cloud & AI", "Cloud Run & Vertex"),
            ("Docker", "LLMOps & Infra", "Containerization"),
            ("Kubernetes", "LLMOps & Infra", "Deployments & HPA/KEDA"),
            ("OpenTelemetry", "LLMOps & Infra", "Distributed Tracing"),
            ("Redis Caching", "Messaging & Streaming", "Caching & Sessions"),
            ("Kafka", "Messaging & Streaming", "Async Event Processing"),
            ("WebSockets / SSE", "Programming & Backend", "Real-Time Streaming"),
            ("Git / Version Control", "Software Engineering", "GitHub / Branching"),
            ("Pandas & NumPy", "Data Engineering", "Dataset Cleaning"),
            ("Linux & Shell", "LLMOps & Infra", "Server Automation")
        ]

        row_start = 5
        for row_offset, (skill, domain, source) in enumerate(profile_skills_inventory):
            curr_row = row_start + row_offset
            ws.row_dimensions[curr_row].height = 22
            aliases = cls.SKILL_ALIASES.get(skill, [skill.lower()])

            row_data = [skill, domain, source]
            demand_count = 0

            for _, res in results:
                # Check if matched
                is_matched = False
                for a in aliases:
                    if any(a in ms or ms in a for ms in res.matched_skills):
                        is_matched = True
                        break

                if is_matched:
                    row_data.append("MATCHED")
                    demand_count += 1
                else:
                    # Check if missing
                    is_missing = False
                    for a in aliases:
                        if any(a in ms for ms in res.missing_skills):
                            is_missing = True
                            break
                    if is_missing:
                        row_data.append("MISSING IN PROFILE")
                    else:
                        row_data.append("-")

            row_data.append(demand_count)
            ws.append(row_data)

            # Cell styling
            ws.cell(row=curr_row, column=1).font = Font(name="Calibri", size=10, bold=True)
            ws.cell(row=curr_row, column=2).font = Font(name="Calibri", size=10, italic=True)
            ws.cell(row=curr_row, column=3).font = Font(name="Calibri", size=9, color="64748B")

            for c_idx in range(4, 4 + len(results)):
                c = ws.cell(row=curr_row, column=c_idx)
                c.alignment = Alignment(horizontal="center", vertical="center")
                val = c.value
                if val == "MATCHED":
                    c.fill = PatternFill(start_color=cls.FILL_BEST, fill_type="solid")
                    c.font = Font(name="Calibri", size=9, bold=True, color=cls.TEXT_BEST)
                elif val == "MISSING IN PROFILE":
                    c.fill = PatternFill(start_color=cls.FILL_DIVERGENT, fill_type="solid")
                    c.font = Font(name="Calibri", size=9, bold=True, color=cls.TEXT_DIVERGENT)
                else:
                    c.font = Font(name="Calibri", size=9, color="94A3B8")

            # Demand count styling
            count_cell = ws.cell(row=curr_row, column=len(headers))
            count_cell.alignment = Alignment(horizontal="center", vertical="center")
            count_cell.font = Font(name="Calibri", size=10, bold=True)
            if demand_count >= 3:
                count_cell.fill = PatternFill(start_color=cls.FILL_BEST, fill_type="solid")
            elif demand_count >= 1:
                count_cell.fill = PatternFill(start_color=cls.FILL_NEAREST, fill_type="solid")

            # Borders
            for col_idx in range(1, len(headers) + 1):
                ws.cell(row=curr_row, column=col_idx).border = thin_border

        cls._adjust_column_widths(ws, min_widths={
            1: 30, # Skill
            2: 24, # Domain
            3: 24, # Source
        })

    @staticmethod
    def _adjust_column_widths(ws, min_widths: Dict[int, int] = None):
        if min_widths is None:
            min_widths = {}
        for col in ws.columns:
            col_idx = col[0].column
            col_letter = get_column_letter(col_idx)
            max_len = 0
            for cell in col:
                if cell.row in [1, 2]:
                    continue
                if cell.value:
                    val_str = str(cell.value)
                    line_len = max([len(line) for line in val_str.split("\n")]) if "\n" in val_str else len(val_str)
                    if line_len > max_len:
                        max_len = line_len
            min_w = min_widths.get(col_idx, 12)
            calculated_w = max(max_len + 3, min_w)
            ws.column_dimensions[col_letter].width = min(calculated_w, 65)
