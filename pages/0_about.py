import streamlit as st
from utils import setup_sidebar, enforce_onboarding

st.title("🦘 Skippy: AI Headhunter")
st.markdown("---")
st.markdown("### Architecture & Design")
st.write(
    "Skippy is a local-first, Multi-Page Application designed to automate the job search workflow. "
    "It leverages event-driven web scraping and multiple LLM APIs to evaluate role alignment, "
    "identify skill gaps, and dynamically tailor application documents."
)

st.markdown("### Technical Highlights")
st.markdown(
    "- **Core:** Python, Streamlit, SQLite\n"
    "- **Data Extraction:** Playwright (with `domcontentloaded` bypass for SPA job boards)\n"
    "- **AI Backend:** Google Gemini, OpenAI, Anthropic, or Local Ollama\n"
    "- **Security:** Credentials isolated in `.env`; XML-delimited prompt defenses against injection."
)

st.markdown("### 🌐 Supported Job Sites")
st.markdown(
    "- **Built In (`builtin.com`):** Officially supported and verified for automated searching and batch scraping\n"
    "- **LinkedIn Extension:** Ingest jobs directly from your browser session in 1 click\n"
    "- **Direct Fallback:** Paste a Job Description mode for all other career portals"
)

st.markdown("---")
st.info("Developed by **Hayden Tanaka** — B.S. Cyber Intelligence and Security, Embry-Riddle Aeronautical University")