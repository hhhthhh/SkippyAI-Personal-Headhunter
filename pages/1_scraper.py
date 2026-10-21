import sys
import os
import time
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import streamlit as st
from playwright.sync_api import sync_playwright

from utils import (
    setup_sidebar,
    enforce_onboarding,
    render_completion_card,
    check_and_handle_pipeline_completion,
    render_resume_selector,
    combine_selected_resumes,
)
import database as db
from scraper import (
    scrape_job_text,
    scrape_universal_search_results,
    is_safe_url,
    search_linkedin_guest,
    search_freehire_jobs,
)
from posting_guard import guard as run_posting_guard
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


def process_evaluations(items: list):
    """Starts the background evaluation pipeline for a list of URLs or pre-fetched job dicts."""
    if pipeline_manager.is_running:
        st.warning("⚠️ An evaluation pipeline is already running in the background. Please wait for it to complete or stop it from the sidebar.")
        return

    chosen_resumes = st.session_state.get("selected_resumes", ["Master Resume"])
    combined_resume = combine_selected_resumes(chosen_resumes)
    st.session_state.resume_text = combined_resume

    started = pipeline_manager.start_url_pipeline(
        urls=items,
        resume_text=combined_resume,
        system_instructions=st.session_state.system_instructions,
        model_choice=st.session_state.get("model_choice", "Google Gemini"),
        api_key=st.session_state.get("user_api_key", ""),
        local_base_url=st.session_state.get("local_base_url", ""),
        local_model_name=st.session_state.get("local_model_name", ""),
        model_override=st.session_state.get("model_override", ""),
        source="Scraper",
        matched_resumes=", ".join(chosen_resumes),
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
    [
        "🔎 Job Board Search",
        "Paste a Job Description",
        "Multi-URL Posting",
        "Universal Search",
    ],
    horizontal=True
)


def render_verified_sites_guide():
    with st.expander("ℹ️ Supported Sites, Free Search APIs & Security Gate", expanded=False):
        st.markdown("""
        - **🔎 Job Board Search (100% Free, No Login / API Key Needed):**
          - **LinkedIn Public Guest Search:** Search live LinkedIn postings by role, location, workplace mode (`Remote`/`Hybrid`/`On-site`), and recency without logging in.
          - **FreeHire Global Tech Search:** Search tech & engineering postings worldwide with full job descriptions returned immediately.
        - **🌐 Multi-URL & Universal Search:** Supports **Built In** (`builtin.com`), direct **LinkedIn** job URLs (`linkedin.com/jobs/view/...`), and public company career pages.
        - **🧩 LinkedIn Evaluator (Fallback):** If LinkedIn ever rate-limits guest search or you prefer browsing logged-in, use the **🔗 LinkedIn Evaluator (Fallback)** submenu tucked under **Scraper** in the sidebar.
        - **🛡️ Deterministic Posting Guard:** Every scraped or pasted job posting is automatically sanitized before reaching your AI model—stripping hidden CSS elements (`display:none`, `font-size:0`, `opacity:0`), invisible Unicode tampering characters, and flagging prompt-injection attempts at zero token cost.
        """)


render_verified_sites_guide()
render_resume_selector(key_suffix="scraper_page", in_sidebar=False)
st.markdown("---")

DATE_POSTED_MAP = {
    "Any Time": 0,
    "Past 24 Hours": 1,
    "Past 7 Days": 7,
    "Past 14 Days": 14,
    "Past 30 Days": 30,
}

if selected_mode == "🔎 Job Board Search":
    st.subheader("🔎 Native Job Board Search")
    st.caption("Search live postings across LinkedIn and FreeHire for free—no account or extra API key required.")

    portal_choice = st.radio(
        "Job Portal Source:",
        [
            "🔗 LinkedIn (Public Guest Search — Global & All Industries)",
            "🌍 FreeHire (Global Tech & Engineering Aggregator — Instant Full Text)",
        ],
        horizontal=True,
        key="native_portal_choice"
    )

    is_linkedin = portal_choice.startswith("🔗")

    if is_linkedin:
        with st.form("linkedin_guest_search_form"):
            col_q, col_loc = st.columns(2)
            with col_q:
                li_query = st.text_input(
                    "Keywords / Role Title:",
                    value=st.session_state.get("li_search_query", "Cybersecurity Analyst"),
                    placeholder="e.g., SOC Analyst, Software Engineer, Data Scientist"
                )
            with col_loc:
                li_location = st.text_input(
                    "Location:",
                    value=st.session_state.get("li_search_location", "United States"),
                    placeholder="e.g., United States, Remote, New York, London"
                )

            col_wt, col_age, col_lim = st.columns(3)
            with col_wt:
                li_work_mode = st.selectbox("Workplace Type:", ["Any", "Remote", "Hybrid", "On-site"])
            with col_age:
                li_age_label = st.selectbox("Date Posted:", list(DATE_POSTED_MAP.keys()), index=2)
            with col_lim:
                li_limit = st.selectbox("Max Search Results:", [10, 20, 30, 50], index=1)

            search_submitted = st.form_submit_button("🔍 Search LinkedIn Jobs", type="primary", use_container_width=True)

        if search_submitted:
            st.session_state["li_search_query"] = li_query
            st.session_state["li_search_location"] = li_location
            if not li_location.strip() and not li_query.strip():
                st.warning("Please provide at least a keyword or location to search.")
            else:
                with st.spinner("Searching LinkedIn public job board..."):
                    try:
                        remote_param = "" if li_work_mode == "Any" else li_work_mode.lower()
                        results = search_linkedin_guest(
                            query=li_query.strip(),
                            location=li_location.strip() or "United States",
                            remote=remote_param,
                            jobage_days=DATE_POSTED_MAP.get(li_age_label, 0),
                            limit=int(li_limit),
                        )
                        st.session_state["native_search_results"] = results
                        st.session_state["native_search_source_label"] = "LinkedIn Guest Search"
                        if not results:
                            st.info("No matching LinkedIn postings found. Try broadening your keywords, location, or date filter.")
                    except Exception as e:
                        st.error(f"LinkedIn search failed: {e}")

    else:
        with st.form("freehire_search_form"):
            col_q, col_reg, col_sen = st.columns([2, 1, 1])
            with col_q:
                fh_query = st.text_input(
                    "Keywords / Tech Stack / Role:",
                    value=st.session_state.get("fh_search_query", "Security Engineer"),
                    placeholder="e.g., Security, Python, Backend, DevOps, AI Engineer"
                )
            with col_reg:
                fh_region = st.selectbox(
                    "Region:",
                    ["Any", "north_america", "global", "eu", "uk", "apac", "latam", "mena"]
                )
            with col_sen:
                fh_seniority = st.selectbox(
                    "Seniority:",
                    ["Any", "entry", "mid", "senior", "staff", "lead"]
                )

            col_wt, col_age, col_lim = st.columns(3)
            with col_wt:
                fh_work_mode = st.selectbox("Workplace Type:", ["Any", "Remote", "Hybrid", "Onsite"])
            with col_age:
                fh_age_label = st.selectbox("Date Posted:", list(DATE_POSTED_MAP.keys()), index=2)
            with col_lim:
                fh_limit = st.selectbox("Max Search Results:", [10, 25, 50], index=1)

            search_submitted = st.form_submit_button("🔍 Search FreeHire Jobs", type="primary", use_container_width=True)

        if search_submitted:
            st.session_state["fh_search_query"] = fh_query
            with st.spinner("Querying FreeHire API (with full job descriptions)..."):
                try:
                    results = search_freehire_jobs(
                        query=fh_query.strip(),
                        work_mode="" if fh_work_mode == "Any" else fh_work_mode.lower(),
                        region="" if fh_region == "Any" else fh_region,
                        seniority="" if fh_seniority == "Any" else fh_seniority,
                        jobage_days=DATE_POSTED_MAP.get(fh_age_label, 0),
                        limit=int(fh_limit),
                    )
                    st.session_state["native_search_results"] = results
                    st.session_state["native_search_source_label"] = "FreeHire API"
                    if not results:
                        st.info("No matching FreeHire postings found. Try broadening your filters or keywords.")
                except Exception as e:
                    st.error(f"FreeHire search failed: {e}")

    # Render interactive results preview table if search results exist
    discovered_jobs = st.session_state.get("native_search_results", [])
    if discovered_jobs:
        seen_urls = db.load_job_urls()
        new_jobs = [j for j in discovered_jobs if j.get("url") not in seen_urls]
        already_seen_count = len(discovered_jobs) - len(new_jobs)

        st.markdown("#### 📋 Discovered Job Postings")
        m1, m2, m3 = st.columns(3)
        m1.metric("Results Found", len(discovered_jobs))
        m2.metric("New (Unevaluated)", len(new_jobs))
        m3.metric("Already in History", already_seen_count)

        table_rows = []
        for idx, j in enumerate(discovered_jobs):
            is_seen = j.get("url") in seen_urls
            table_rows.append({
                "Status": "✅ Evaluated" if is_seen else "🆕 New",
                "Title": j.get("title", ""),
                "Company": j.get("company", ""),
                "Location": j.get("location", ""),
                "Posted": j.get("date", "—"),
                "URL": j.get("url", ""),
                "_idx": idx,
            })

        preview_df = pd.DataFrame(table_rows)
        selection_event = st.dataframe(
            preview_df[["Status", "Title", "Company", "Location", "Posted", "URL"]],
            width="stretch",
            on_select="rerun",
            selection_mode="multi-row",
            column_config={"URL": st.column_config.LinkColumn("Posting Link")},
            key="native_search_preview_table"
        )

        selected_indices = selection_event.selection.rows if selection_event and selection_event.selection else []
        col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 1])

        with col_btn1:
            batch_count = min(len(new_jobs), max_jobs)
            if st.button(
                f"🚀 Evaluate Top {batch_count} New Posting{'s' if batch_count != 1 else ''}",
                type="primary",
                disabled=(batch_count == 0),
                use_container_width=True,
                key="btn_eval_top_native"
            ):
                process_evaluations(new_jobs[:max_jobs])

        with col_btn2:
            sel_count = len(selected_indices)
            if st.button(
                f"🎯 Evaluate Selected ({sel_count})",
                disabled=(sel_count == 0),
                use_container_width=True,
                key="btn_eval_selected_native"
            ):
                chosen_items = [discovered_jobs[i] for i in selected_indices if 0 <= i < len(discovered_jobs)]
                process_evaluations(chosen_items[:max_jobs])

        with col_btn3:
            if st.button("🗑️ Clear Results", use_container_width=True, key="btn_clear_native_results"):
                del st.session_state["native_search_results"]
                st.rerun()

elif selected_mode == "Paste a Job Description":
    st.subheader("📝 Paste a Job Description")
    st.caption("🛡️ Protected by **Posting Guard**: invisible Unicode tampering and prompt-injection lines are automatically stripped and flagged.")
    with st.form("manual_paste_form"):
        job_description = st.text_area("Paste Job Description Here:", height=250)
        submitted = st.form_submit_button("Evaluate Posting", type="primary")

    if submitted:
        if not job_description.strip() or not st.session_state.resume_text.strip():
            st.warning("Please provide both the master resume and job description.")
        else:
            with st.spinner("Running Posting Guard & analyzing alignment with AI..."):
                try:
                    cleaned_job_text, guard_findings = run_posting_guard(job_description, mode="auto")
                    sec_flags = list(guard_findings.get("security_flags") or [])
                    if sec_flags:
                        for sf in sec_flags:
                            st.warning(sf)

                    result = evaluate_job(
                        st.session_state.resume_text,
                        cleaned_job_text,
                        st.session_state.system_instructions,
                        st.session_state.get("model_choice"),
                        st.session_state.get("user_api_key"),
                        st.session_state.get("local_base_url"),
                        st.session_state.get("local_model_name"),
                        pre_security_flags=sec_flags,
                    )
                    resolved_company = result.company_name if result.company_name != "Unknown Company" else ""
                    match_data = {
                        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "Position": result.position_name,
                        "Company": resolved_company,
                        "Deadline": result.application_deadline or "",
                        "URL": f"Manual_Paste_{int(time.time())}",
                        "Eligible": result.is_eligible,
                        "Disqualification Reason": result.disqualification_reason,
                        "Score": result.match_score,
                        "Technical Score": result.technical_score,
                        "Experience Score": result.experience_score,
                        "Behavioral Score": result.behavioral_score,
                        "Career Score": result.career_alignment_score,
                        "Location Gate": result.location_gate,
                        "Eligibility Gate": result.eligibility_gate,
                        "Summary": result.summary,
                        "Matching Skills": ", ".join(result.matching_skills),
                        "Missing Skills": ", ".join(result.missing_skills),
                        "Red Flags": " | ".join(result.red_flags_or_caveats),
                        "Job Text": cleaned_job_text,
                        "Application Status": "Not Applied",
                        "Matched Resumes": ", ".join(st.session_state.get("selected_resumes", ["Master Resume"])),
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
    st.caption("Paste individual job URLs (one per line). Supports **Built In**, **LinkedIn (`linkedin.com/jobs/view/...`)**, and public company career pages.")
    
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
    st.subheader("🧭 Universal Search")
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
