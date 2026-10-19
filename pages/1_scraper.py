import sys
import os
import time
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
from playwright.sync_api import sync_playwright

from utils import setup_sidebar, enforce_onboarding, render_completion_card, check_and_handle_pipeline_completion
import database as db
from scraper import scrape_job_text, scrape_universal_search_results, is_safe_url
from evaluator import evaluate_job
from pipeline import pipeline_manager

if "system_instructions" not in st.session_state:
    if os.path.exists("custom_prompt.txt"):
        try:
            with open("custom_prompt.txt", "r", encoding="utf-8") as f:
                st.session_state.system_instructions = f.read()
        except Exception:
            st.session_state.system_instructions = "You are an advanced automated job-matching engine..."
    else:
        st.session_state.system_instructions = "You are an advanced automated job-matching engine..."

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Settings & Filters")
max_jobs = st.sidebar.slider("Max Postings to Evaluate", min_value=1, max_value=50, value=5, step=1)

def process_evaluations(urls: list[str]):
    if pipeline_manager.is_running:
        st.warning("⚠️ An evaluation pipeline is already running in the background. Please wait for it to complete or stop it from the sidebar.")
        return

    started = pipeline_manager.start_url_pipeline(
        urls=urls,
        resume_text=st.session_state.resume_text,
        system_instructions=st.session_state.system_instructions,
        model_choice=st.session_state.get("model_choice", "Google Gemini"),
        api_key=st.session_state.get("user_api_key", ""),
        local_base_url=st.session_state.get("local_base_url", ""),
        local_model_name=st.session_state.get("local_model_name", ""),
        model_override=st.session_state.get("model_override", ""),
        source="Scraper"
    )
    if started:
        if "completion_batch" in st.session_state:
            del st.session_state["completion_batch"]
        st.rerun()

@st.fragment(run_every="2s")
def render_active_scraper_pipeline():
    check_and_handle_pipeline_completion()
    status = pipeline_manager.get_status()
    if status.get("is_running") and status.get("source") == "Scraper":
        with st.container(border=True):
            st.subheader("⚙️ Background Evaluation Pipeline Active")
            total = max(status.get("total", 1), 1)
            completed = status.get("completed", 0)
            prog = min(completed / total, 1.0)
            cur = status.get("current_job", "Initializing...")
            if len(cur) > 60:
                cur = cur[:57] + "..."
            st.progress(prog, text=f"Evaluating ({completed}/{total}): {cur}")
            st.info("💡 **Page persistence active:** You can freely switch to other pages (History, Metrics, etc.). Evaluation continues running in the background and you will be notified when complete!")
            if st.button("🛑 Stop Pipeline", key="stop_scraper_pipeline_main"):
                pipeline_manager.cancel()
                st.rerun()

render_active_scraper_pipeline()

# Accessible Completion Card displayed if a run just completed
if "completion_batch" in st.session_state:
    render_completion_card(
        st.session_state["completion_batch"]["jobs"],
        source_label=st.session_state["completion_batch"]["source"]
    )
    st.markdown("---")

selected_mode = st.radio(
    "Select Scraper Mode", 
    ["Paste a Job Description", "Multi-URL Posting", "Universal Search"], 
    horizontal=True
)

def render_verified_sites_guide():
    with st.expander("ℹ️ Supported Sites & Scraping Tips", expanded=False):
        st.markdown("""
        - **Supported Job Site:** **Built In** (`builtin.com`) is officially verified and supported for automated scraping. You can use Built In search URLs (in Universal Search) or individual job posting URLs (in Multi-URL Posting).
        - **LinkedIn:** Use Skippy's official **LinkedIn Extension** (see the `LinkedIn Evaluator` page) to send postings with 1 click directly from your browser.
        - **Other Job Boards (Indeed, Glassdoor, Workday, etc.):** Most other sites use aggressive bot blocks or login screens that prevent automated scraping. For those, use **Paste a Job Description** for instant AI evaluation.
        """)

render_verified_sites_guide()
st.markdown("---")

if selected_mode == "Paste a Job Description":
    st.subheader("📝 Paste a Job Description")
    with st.form("manual_paste_form"):
        job_description = st.text_area("Paste Job Description Here:", height=250)
        submitted = st.form_submit_button("Evaluate Posting", type="primary")

    if submitted:
        if not job_description.strip() or not st.session_state.resume_text.strip():
            st.warning("Please provide both the master resume and job description.")
        else:
            with st.spinner("Analyzing alignment with AI..."):
                try:
                    result = evaluate_job(
                        st.session_state.resume_text, job_description, st.session_state.system_instructions,
                        st.session_state.get("model_choice"), st.session_state.get("user_api_key"),
                        st.session_state.get("local_base_url"), st.session_state.get("local_model_name")
                    )
                    match_data = {
                        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "Position": result.position_name,
                        "URL": f"Manual_Paste_{int(time.time())}",
                        "Eligible": result.is_eligible,
                        "Disqualification Reason": result.disqualification_reason,
                        "Score": result.match_score,
                        "Summary": result.summary,
                        "Matching Skills": ", ".join(result.matching_skills),
                        "Missing Skills": ", ".join(result.missing_skills),
                        "Red Flags": " | ".join(result.red_flags_or_caveats),
                        "Job Text": job_description,
                        "Application Status": "Not Applied",
                        "Source": "Manual" # <-- Tags this for the Manual tab
                    }
                    db.save_job_result(match_data)
                    st.session_state["completion_batch"] = {
                        "source": "Manual",
                        "jobs": [match_data]
                    }
                    st.rerun()
                except Exception as e:
                    st.error(f"Error evaluating posting: {e}")

elif selected_mode == "Multi-URL Posting":
    st.subheader("🌐 Multi-URL Posting")
    
    col_samp, _ = st.columns([3, 7])
    with col_samp:
        if st.button("📋 Load Sample BuiltIn URLs", key="btn_sample_urls"):
            st.session_state["batch_urls_input"] = (
                "https://builtin.com/job/cyber-security/information-security-analyst/224561\n"
                "https://builtin.com/job/developer/software-engineer/224562\n"
                "https://builtin.com/job/devops/cloud-engineer/224563"
            )
            st.rerun()

    sample_val = st.session_state.get("batch_urls_input", "")
    with st.form("batch_url_form"):
        urls_input = st.text_area("Job URLs (one per line):", value=sample_val, height=150)
        submitted = st.form_submit_button("Scrape & Evaluate All URLs", type="primary")
        
    if submitted:
        all_urls = [u.strip() for u in urls_input.splitlines() if u.strip()]
        if not all_urls:
            st.warning("Please enter at least one valid URL.")
        else:
            safe_urls = []
            for u in all_urls:
                if is_safe_url(u):
                    safe_urls.append(u)
                else:
                    st.warning(f"Skipping disallowed or unsafe URL: {u}")
                    
            if not safe_urls:
                st.warning("No valid public HTTP/HTTPS URLs provided.")
            else:
                seen_urls = db.load_job_urls()
                new_urls = [u for u in safe_urls if u not in seen_urls]
                skipped = len(safe_urls) - len(new_urls)
                if skipped > 0:
                    st.info(f"⏭ Skipped {skipped} previously evaluated postings.")
                if not new_urls:
                    st.warning("All provided URLs have already been evaluated. Check your History tab!")
                else:
                    process_evaluations(new_urls[:max_jobs])

elif selected_mode == "Universal Search":
    st.subheader("🔍 Universal Search")
    st.caption("⚡ **Quick-Fill Built In Search Categories:**")
    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
        if st.button("🏢 Built In: Cybersecurity", key="preset_builtin_cyber", use_container_width=True):
            st.session_state["search_url_preset"] = "https://builtin.com/jobs/cyber-security/entry-level"
            st.rerun()
    with col_p2:
        if st.button("💻 Built In: Software Engineering", key="preset_builtin_dev", use_container_width=True):
            st.session_state["search_url_preset"] = "https://builtin.com/jobs/dev-engineering/entry-level"
            st.rerun()
    with col_p3:
        if st.button("☁️ Built In: Cloud & DevOps", key="preset_builtin_cloud", use_container_width=True):
            st.session_state["search_url_preset"] = "https://builtin.com/jobs/devops-cloud/entry-level"
            st.rerun()

    preset_search = st.session_state.get("search_url_preset", "https://builtin.com/jobs/cyber-security/entry-level")
    with st.form("search_form"):
        search_url = st.text_input("Search URL:", value=preset_search, placeholder="https://builtin.com/jobs/cyber-security/entry-level")
        submitted = st.form_submit_button("Auto-Discover & Evaluate Jobs", type="primary")
        
    if submitted:
        clean_search = search_url.strip()
        if not clean_search:
            st.warning("Please provide a search URL.")
        elif not is_safe_url(clean_search):
            st.error("Disallowed or unsafe search URL. Only public HTTP/HTTPS URLs are allowed.")
        else:
            with st.spinner("Harvesting job posting links..."):
                discovered_urls = scrape_universal_search_results(clean_search)
            if not discovered_urls:
                st.warning("No job posting links could be extracted from this page.")
            else:
                seen_urls = db.load_job_urls()
                new_urls = [u for u in discovered_urls if u not in seen_urls]
                skipped = len(discovered_urls) - len(new_urls)
                if skipped > 0:
                    st.info(f"⏭️ Skipped {skipped} previously evaluated postings.")
                if not new_urls:
                    st.warning("All discovered jobs on this page have already been evaluated.")
                else:
                    process_evaluations(new_urls[:max_jobs])