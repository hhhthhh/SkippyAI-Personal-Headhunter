import streamlit as st
from utils import setup_sidebar, enforce_onboarding

st.title("🦘 Skippy: AI Job Search & Career CRM")
st.markdown("---")
st.markdown("### Architecture & Design")
st.write(
    "Skippy is a 100% free, local-first Multi-Page AI Job Search & Career CRM. "
    "It combines unauthenticated job board search APIs, deterministic prompt-injection defense, "
    "multi-dimensional candidate scoring, a two-pass Drafter–Reviewer grounding engine, and "
    "automated market skill-gap intelligence."
)

st.markdown("### Technical Highlights")
st.markdown(
    "- **Core Stack:** Python, Streamlit, SQLite (WAL concurrency), Pydantic, python-docx\n"
    "- **Multi-Source Job Discovery:** Native LinkedIn Public Guest Search, FreeHire Global Tech API (with ghost-job/repost detection), Built In (`builtin.com`), and lazy Playwright SPA fallback\n"
    "- **AI Backend (Bring Your Own Key or Free Local):** Google Gemini (free tier supported), OpenAI, Anthropic, xAI Grok, or Local Ollama\n"
    "- **4-Pillar Weighted Scoring & Gates:** Deterministic `30% Technical + 25% Experience + 15% Behavioral + 30% Career Alignment` rubric with explicit Eligibility & Location gates\n"
    "- **2-Step Drafter–Reviewer & ATS Audit:** Cross-checks tailored resumes and cover letters against your Master Resume to eliminate hallucinations, normalize ASCII dates, and verify ATS keyword coverage\n"
    "- **Full Application Suite:** Tailored Resumes, Cover Letters, Character-Counted Application Portal Q&A Packs, Stage-Aware Interview Prep (with Honest Gap Bridges), Follow-Up Notes, and Personalized Upskill Roadmaps\n"
    "- **Security (`posting_guard.py`):** Deterministic HTML/CSS hidden-element stripping, zero-width & bidirectional Unicode sanitization, homoglyph detection, SSRF per-hop redirect validation, and XML-delimited prompt boundaries"
)

st.markdown("---")
st.info("Developed by **Hayden Tanaka** — B.S. Cyber Intelligence and Security, Embry-Riddle Aeronautical University")
