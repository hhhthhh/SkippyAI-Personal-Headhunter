import sys
import os
import io
import json
import time
import socket
import zipfile
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
import database as db
from evaluator import evaluate_job
from utils import (
    render_completion_card,
    check_and_handle_pipeline_completion,
    render_resume_selector,
    combine_selected_resumes,
)

from webhook import load_inbox_jobs, save_inbox_jobs, clear_inbox
from pipeline import pipeline_manager

WEBHOOK_PORT = int(os.environ.get("SKIPPY_WEBHOOK_PORT", "8000"))

# --- Helper: Check if FastAPI is running ---
def is_backend_live(port=WEBHOOK_PORT):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

st.title("🔗 LinkedIn Extension Inbox")
col_desc, col_back = st.columns([4, 1.4])
with col_desc:
    st.markdown(
        "**Send Jobs from LinkedIn:** Use our browser extension to send job listings straight from LinkedIn into Skippy with a right-click. "
        "They'll wait in this inbox until you're ready to review them with AI."
    )
with col_back:
    if st.button("⬅️ Back to Job Search", width="stretch"):
        st.switch_page("pages/1_scraper.py")
    if st.button("📋 Search Results", width="stretch", key="btn_goto_scraper_results_from_li"):
        st.switch_page("pages/7_scraper_results.py")
render_resume_selector(key_suffix="linkedin_page", in_sidebar=False)
st.markdown("---")

# Accessible Completion Card displayed if a run just completed
if "completion_batch" in st.session_state:
    render_completion_card(
        st.session_state["completion_batch"]["jobs"],
        source_label=st.session_state["completion_batch"]["source"]
    )
    st.markdown("---")

@st.cache_data
def _get_extension_zip_bytes() -> bytes | None:
    if os.path.exists("skippy_extension.zip"):
        try:
            with open("skippy_extension.zip", "rb") as f:
                return f.read()
        except OSError:
            pass
    if os.path.exists("skippy-extension"):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, strict_timestamps=False) as zf:
            for root, _, files in os.walk("skippy-extension"):
                for file in files:
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, ".")
                    zf.write(full_path, arcname)
        return buf.getvalue()
    return None


@st.fragment(run_every="3s")
def render_auto_inbox():
    check_and_handle_pipeline_completion()

    status = pipeline_manager.get_status()
    if status.get("is_running") and status.get("source") == "LinkedIn":
        with st.container(border=True):
            st.subheader("⚙️ Reviewing Jobs in the Background...")
            total = max(status.get("total", 1), 1)
            completed = status.get("completed", 0)
            prog = min(completed / total, 1.0)
            cur = status.get("current_job", "Working...")
            st.progress(prog, text=f"Reviewing ({completed}/{total}): {cur}")
            st.info("💡 **You can freely explore other pages:** Reviewing continues in the background while you browse.")
            if st.button("🛑 Stop Review", key="stop_linkedin_pipeline_main"):
                pipeline_manager.cancel()
                st.rerun()
        st.markdown("---")

    pending_jobs = load_inbox_jobs()
            
    if pending_jobs:
        st.info(f"You have **{len(pending_jobs)}** job(s) waiting in your inbox.")
        
        for i, job in enumerate(pending_jobs):
            title = job.get('title', 'Unknown Title')
            company = job.get('company', 'Unknown Company')
            
            with st.expander(f"💼 {title} at {company}", expanded=False):
                raw_url = str(job.get('url', '')).strip()
                if raw_url.startswith(("http://", "https://")):
                    st.markdown(f"**URL:** [{raw_url}]({raw_url})")
                else:
                    st.text(f"URL: {raw_url}")
                
                raw_text = job.get('raw_text', '')
                clean_text = raw_text.replace('\n', ' ').replace('\r', '').strip()
                while '  ' in clean_text:
                    clean_text = clean_text.replace('  ', ' ')
                    
                snippet = clean_text[:500] + "..." if len(clean_text) > 500 else clean_text
                st.markdown(f"**Description Snippet:**\n> {snippet}")
                
                if st.button("🗑️ Remove from Queue", key=f"remove_job_{i}_{hash(raw_url)}"):
                    if raw_url:
                        remove_inbox_job_by_url(raw_url)
                    else:
                        current_jobs = load_inbox_jobs()
                        if i < len(current_jobs):
                            current_jobs.pop(i)
                            save_inbox_jobs(current_jobs)
                    st.rerun()
        
        st.markdown("---")
        
        if status.get("is_running"):
            st.button("⚙️ Review Running in Background...", disabled=True, width="stretch")
        else:
            if st.button("🚀 Review All Inbox Jobs", type="primary", width="stretch"):
                chosen_resumes = st.session_state.get("selected_resumes", ["Master Resume"])
                combined_resume = combine_selected_resumes(chosen_resumes)
                st.session_state.resume_text = combined_resume
                started = pipeline_manager.start_inbox_pipeline(
                    pending_jobs=pending_jobs,
                    resume_text=combined_resume,
                    system_instructions=st.session_state.system_instructions,
                    model_choice=st.session_state.get("model_choice", "Google Gemini"),
                    api_key=st.session_state.get("user_api_key", ""),
                    local_base_url=st.session_state.get("local_base_url", ""),
                    local_model_name=st.session_state.get("local_model_name", ""),
                    model_override=st.session_state.get("model_override", ""),
                    source="LinkedIn",
                    matched_resumes=", ".join(chosen_resumes),
                )
                if started:
                    if "completion_batch" in st.session_state:
                        del st.session_state["completion_batch"]
                    st.rerun()
            
    else:
        # --- NEW EMPTY STATE ONBOARDING ---
        with st.container(border=True):
            st.subheader("⚡ Install the Browser Extension")
            st.write("Send jobs directly from your browser to this inbox in one click.")
            
            if is_backend_live():
                st.caption(f"🟢 Local Extension Listener: **Active** (Port {WEBHOOK_PORT})")
            else:
                st.error(f"🔴 Extension Listener Offline: Start Skippy with webhook enabled on port {WEBHOOK_PORT} to receive jobs.")
            
            col1, col2 = st.columns([1, 2])
            with col1:
                zip_data = _get_extension_zip_bytes()

                if zip_data:
                    st.download_button(
                        "📦 Download Extension (.zip)",
                        data=zip_data,
                        file_name="skippy_extension.zip",
                        mime="application/zip",
                        type="primary",
                        width="stretch"
                    )
                else:
                    st.error("Missing `skippy-extension/` or `skippy_extension.zip` in project root.")
            with col2:
                with st.expander("🛠️ Setup Instructions", expanded=True):
                    st.markdown("""
                    1. **Download & Extract:** Download the ZIP and extract the `skippy-extension` folder onto your machine (keep it in a permanent folder like your Skippy project folder so it isn't deleted by cleanup tools).
                    2. **Chromium Browsers (Chrome, Brave, Edge, Vivaldi):**
                       - Open `chrome://extensions` (or `edge://extensions` / `vivaldi://extensions`).
                       - Toggle **Developer mode** in the top-right corner, click **Load unpacked**, and select the `skippy-extension` folder.
                    3. **Firefox Browsers (Firefox, Zen, LibreWolf, Waterfox):**
                       - Open `about:debugging#/runtime/this-firefox`.
                       - Click **Load Temporary Add-on...** and select `manifest.json` inside the `skippy-extension` folder.
                    4. **Capture Postings:** Navigate to LinkedIn, click any job listing, right-click anywhere on the details pane, and select **⚡ Send Listing to Skippy**.
                    """)

render_auto_inbox()