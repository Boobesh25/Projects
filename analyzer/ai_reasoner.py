"""
AI Reasoner Module for Career Page Analyser
==========================================
Supports:
1. Google AI Studio (Free Gemini API Key via GEMINI_API_KEY or GOOGLE_API_KEY)
2. LM Studio (Local LLM via http://localhost:1234/v1 - Zero cost, 100% private)
3. Ollama (Local LLM via http://localhost:11434/v1)

Provides AI-powered features:
- Deep Semantic Fit & Experience Reasoning
- Auto-tailored recruiter elevator pitch (strictly grounded in profile.yaml)
- Predicted technical interview questions based on the JD vs Profile delta
"""

import os
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
import requests

class AIReasoner:
    def __init__(self, api_key: Optional[str] = None, provider: str = "auto", local_base_url: str = "http://localhost:1234/v1"):
        """
        provider: 'auto', 'gemini', 'lm_studio', 'ollama'
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.local_base_url = local_base_url.rstrip("/")
        self.provider = self._detect_provider(provider)

    def _detect_provider(self, requested: str) -> str:
        if requested in ["gemini", "lm_studio", "ollama"]:
            return requested
        
        # 1. Check if Gemini API key exists
        if self.api_key:
            return "gemini"
        
        # 2. Check if local LM Studio is running
        try:
            r = requests.get(f"{self.local_base_url}/models", timeout=1.5)
            if r.status_code == 200:
                return "lm_studio"
        except Exception:
            pass

        return "none"

    def is_available(self) -> bool:
        return self.provider != "none"

    def get_status_info(self) -> str:
        if self.provider == "gemini":
            masked_key = self.api_key[:6] + "..." + self.api_key[-4:] if self.api_key and len(self.api_key) > 10 else "SET"
            return f"Google AI Studio (Gemini 2.0 / 1.5 Flash) [Key: {masked_key}]"
        elif self.provider == "lm_studio":
            return f"LM Studio (Local LLM @ {self.local_base_url})"
        elif self.provider == "ollama":
            return "Ollama (Local LLM @ http://localhost:11434)"
        else:
            return "No AI provider configured (Set GEMINI_API_KEY or start LM Studio)"

    def generate_deep_fit_analysis(self, job_title: str, company: str, jd_text: str, candidate_summary: str, matched_skills: List[str], missing_skills: List[str]) -> Dict[str, Any]:
        """
        Uses the LLM to perform deep semantic evaluation, generate tailored pitch, and predict interview questions.
        """
        if not self.is_available():
            return {
                "error": "No AI provider active. Set GEMINI_API_KEY or launch LM Studio.",
                "status": "offline"
            }

        prompt = f"""
You are an expert Principal AI Engineer and Technical Hiring Bar Raiser.
Analyze the alignment between this candidate's verified profile and the target job description.

Target Role: {job_title} @ {company}
Matched Skills: {', '.join(matched_skills)}
Missing / Gap Skills: {', '.join(missing_skills)}

Candidate Profile Summary:
{candidate_summary}

Job Description:
{jd_text[:2500]}

Respond ONLY in valid, parseable JSON with this exact schema:
{{
  "semantic_fit_verdict": "2-3 sentences evaluating architectural fit, experience depth, and real-world alignment.",
  "transferable_strengths": ["Strength 1 explaining how candidate's background solves a core JD requirement", "Strength 2"],
  "recruiter_elevator_pitch": "A 3-4 sentence high-impact, professional introduction pitch tailored specifically for this role, citing strictly verified metrics from the candidate profile without any hallucination.",
  "top_interview_questions": [
    "Predict question 1 the hiring manager will ask based on the JD vs Profile delta",
    "Predict question 2",
    "Predict question 3"
  ]
}}
"""

        try:
            if self.provider == "gemini":
                return self._call_gemini(prompt)
            elif self.provider in ["lm_studio", "ollama"]:
                return self._call_openai_compatible(prompt, base_url=self.local_base_url, api_key="local-llm")
        except Exception as e:
            return {"error": str(e), "status": "failed"}

        return {"error": "Unhandled provider", "status": "failed"}

    def _call_gemini(self, prompt: str) -> Dict[str, Any]:
        """Calls Google AI Studio via REST API or official SDK"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.2
            }
        }
        r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=20)
        if r.status_code != 200:
            # Fallback to gemini-1.5-flash
            url_fallback = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
            r = requests.post(url_fallback, json=payload, headers={"Content-Type": "application/json"}, timeout=20)
            if r.status_code != 200:
                raise RuntimeError(f"Gemini API error (HTTP {r.status_code}): {r.text}")

        resp_data = r.json()
        raw_text = resp_data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(raw_text)

    def _call_openai_compatible(self, prompt: str, base_url: str, api_key: str = "none") -> Dict[str, Any]:
        """Calls LM Studio or Ollama OpenAI-compatible endpoint"""
        url = f"{base_url}/chat/completions"
        payload = {
            "model": "default",
            "messages": [
                {"role": "system", "content": "You are a technical bar-raiser assistant. Output valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        r = requests.post(url, json=payload, headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"Local LLM API error (HTTP {r.status_code}): {r.text}")

        resp_data = r.json()
        content = resp_data["choices"][0]["message"]["content"]
        # Strip potential markdown code fences
        cleaned = content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return json.loads(cleaned.strip())

