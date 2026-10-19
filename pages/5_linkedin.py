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
from utils import render_completion_card, check_and_handle_pipeline_completion

from webhook import load_inbox_jobs, save_inbox_jobs, clear_inbox
from pipeline import pipeline_manager

WEBHOOK_PORT = int(os.environ.get("SKIPPY_WEBHOOK_PORT", "8000"))

# --- Helper: Check if FastAPI is running ---
def is_backend_live(port=WEBHOOK_PORT):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

st.title("🔗 LinkedIn Integration")
st.markdown("Manage and evaluate jobs sent directly from the LinkedIn browser extension.")
st.markdown("---")

# Accessible Completion Card displayed if a run just completed
if "completion_batch" in st.session_state:
    render_completion_card(
        st.session_state["completion_batch"]["jobs"],
        source_label=st.session_state["completion_batch"]["source"]
    )
    st.markdown("---")

@st.fragment(run_every="3s")
def render_auto_inbox():
    check_and_handle_pipeline_completion()

    status = pipeline_manager.get_status()
    if status.get("is_running") and status.get("source") == "LinkedIn":
        with st.container(border=True):
            st.subheader("⚙️ Background Evaluation Pipeline Active")
            total = max(status.get("total", 1), 1)
            completed = status.get("completed", 0)
            prog = min(completed / total, 1.0)
            cur = status.get("current_job", "Working...")
            st.progress(prog, text=f"Evaluating ({completed}/{total}): {cur}")
            st.info("💡 **Page persistence active:** You can freely switch to other pages (History, Metrics, etc.). Evaluation continues running in the background and you will be notified when complete!")
            if st.button("🛑 Stop Pipeline", key="stop_linkedin_pipeline_main"):
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
                
                if st.button("🗑️ Remove from Queue", key=f"remove_job_{i}"):
                    current_jobs = load_inbox_jobs()
                    if i < len(current_jobs):
                        current_jobs.pop(i)
                        save_inbox_jobs(current_jobs)
                    st.rerun()
        
        st.markdown("---")
        
        if status.get("is_running"):
            st.button("⚙️ Evaluation Running in Background...", disabled=True, use_container_width=True)
        else:
            if st.button("🚀 Evaluate All Inbox Jobs", type="primary", use_container_width=True):
                started = pipeline_manager.start_inbox_pipeline(
                    pending_jobs=pending_jobs,
                    resume_text=st.session_state.resume_text,
                    system_instructions=st.session_state.system_instructions,
                    model_choice=st.session_state.get("model_choice", "Google Gemini"),
                    api_key=st.session_state.get("user_api_key", ""),
                    local_base_url=st.session_state.get("local_base_url", ""),
                    local_model_name=st.session_state.get("local_model_name", ""),
                    model_override=st.session_state.get("model_override", ""),
                    source="LinkedIn"
                )
                if started:
                    if "completion_batch" in st.session_state:
                        del st.session_state["completion_batch"]
                    st.rerun()
            
    else:
        # --- NEW EMPTY STATE ONBOARDING ---
        with st.container(border=True):
            st.subheader("⚡ Connect the LinkedIn Extension")
            st.write("Send jobs directly from your browser to this queue in one click.")
            
            if is_backend_live():
                st.caption(f"🟢 Local Ingestion Server: **Active** (Port {WEBHOOK_PORT})")
            else:
                st.error(f"🔴 Ingestion Server Offline: Start your FastAPI backend (`uvicorn ...`) on port {WEBHOOK_PORT} to receive jobs.")
            
            col1, col2 = st.columns([1, 2])
            with col1:
                zip_data = None
                if os.path.exists("skippy-extension"):
                    buf = io.BytesIO()
                    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, strict_timestamps=False) as zf:
                        for root, _, files in os.walk("skippy-extension"):
                            for file in files:
                                full_path = os.path.join(root, file)
                                arcname = os.path.relpath(full_path, ".")
                                zf.write(full_path, arcname)
                    zip_data = buf.getvalue()
                elif os.path.exists("skippy_extension.zip"):
                    with open("skippy_extension.zip", "rb") as f:
                        zip_data = f.read()

                if zip_data:
                    st.download_button(
                        "📦 Download Extension (.zip)",
                        data=zip_data,
                        file_name="skippy_extension.zip",
                        mime="application/zip",
                        type="primary",
                        use_container_width=True
                    )
                else:
                    st.error("Missing `skippy-extension/` or `skippy_extension.zip` in project root.")
            with col2:
                with st.expander("🛠️ Setup Instructions", expanded=True):
                    st.markdown("""
                    1. **Download & Extract:** Download the ZIP and extract the `skippy-extension` folder onto your machine (keep it in a permanent folder like your Skippy project folder so it isn't deleted by cleanup tools).
                    2. **Open Extensions:** In your Chromium browser (Chrome, Brave, Edge, Vivaldi), go to `chrome://extensions` or `vivaldi://extensions`.
                    3. **Enable Developer Mode:** Toggle the **Developer mode** switch in the top-right corner.
                    4. **Load Unpacked:** Click **Load unpacked** and select the extracted `skippy-extension` folder.
                    5. **Capture Postings:** Navigate to LinkedIn, click any job listing, right-click anywhere on the details pane, and select **⚡ Send Listing to Skippy**.
                    """)

render_auto_inbox()