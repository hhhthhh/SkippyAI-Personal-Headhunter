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
    render_active_prompt_indicator,
    initialize_core_state,
)
import database as db
from scraper import (
    scrape_job_text,
    scrape_universal_search_results,
    is_safe_url,
    search_linkedin_guest,
    search_freehire_jobs,
    fetch_ats_board_jobs,
)
from posting_guard import guard as run_posting_guard
from evaluator import evaluate_job
from pipeline import pipeline_manager
from sample_data import SAMPLE_JOBS

if "system_instructions" not in st.session_state:
    initialize_core_state()

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Settings & Filters")
max_jobs = st.sidebar.slider("Max Jobs to Review", min_value=1, max_value=50, value=5, step=1)

# Restore persisted scraper results if session state was cleared by page refresh
if "native_search_results" not in st.session_state or not st.session_state["native_search_results"]:
    cached_scraper_results = db.load_scraper_results()
    if cached_scraper_results:
        st.session_state["native_search_results"] = cached_scraper_results
        st.session_state["native_search_source_label"] = cached_scraper_results[0].get("source_board") or cached_scraper_results[0].get("source") or "Job Board Search"


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
            st.subheader("⚙️ Reviewing Jobs in the Background...")
            total = max(status.get("total", 1), 1)
            completed = status.get("completed", 0)
            prog = min(completed / total, 1.0)
            cur = status.get("current_job", "Initializing...")
            if len(cur) > 60:
                cur = cur[:57] + "..."
            st.progress(prog, text=f"Reviewing ({completed}/{total}): {cur}")
            st.info("💡 **You can freely explore other pages:** Reviewing continues in the background, and you'll be notified as soon as it's finished!")
            if st.button("🛑 Stop Review", key="stop_scraper_pipeline_main"):
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

# Quick-Start Guide for first-time or new users
show_quick_start = st.session_state.get("show_quick_start", False)
dismissed = db.get_setting("dismissed_quick_start", "") == "true"
has_evaluated_jobs = bool(db.load_job_urls())

if (show_quick_start or not has_evaluated_jobs) and not dismissed:
    with st.container(border=True):
        col_qs_title, col_qs_dism = st.columns([5.5, 1])
        with col_qs_title:
            st.subheader("🎉 Welcome to Skippy! Quick-Start Guide")
            st.write("Get your first tailored application in 3 simple steps:")
        with col_qs_dism:
            if st.button("✕ Dismiss", key="btn_dismiss_quick_start", help="Hide this guide"):
                db.set_setting("dismissed_quick_start", "true")
                st.session_state["show_quick_start"] = False
                st.rerun()

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("##### 1. Find a Role")
            st.caption("Search live postings on LinkedIn, company hiring pages (Greenhouse/Ashby), or paste any job link or text.")
        with c2:
            st.markdown("##### 2. Review with AI")
            st.caption("Skippy checks your qualifications across 4 dimensions and spots red flags or dealbreakers upfront.")
        with c3:
            st.markdown("##### 3. Get Your Pack")
            st.caption("In **Job History**, download your fact-checked ATS resume, custom cover letter, and STAR interview prep.")

        st.markdown("")
        col_demo, _ = st.columns([2.5, 4])
        with col_demo:
            if st.button("🧪 Try a Sample Job Listing", type="secondary", width="stretch", help="Pre-populates a sample job description so you can test the review engine immediately."):
                sample_job = SAMPLE_JOBS[0]
                st.session_state["manual_job_text_buffer"] = sample_job["text"]
                st.session_state["selected_scraper_mode_idx"] = 1  # "📝 Paste Job Text"
                st.toast(f"Loaded '{sample_job['title']}' sample job posting!", icon="📋")
                st.rerun()

    st.markdown("---")

mode_options = [
    "🔎 Job Board Search",
    "📝 Paste Job Text",
    "🌐 Paste Multiple Links",
    "🧭 Search by Category",
]
default_mode_idx = st.session_state.pop("selected_scraper_mode_idx", 0)
if default_mode_idx >= len(mode_options):
    default_mode_idx = 0

selected_mode = st.radio(
    "Choose How to Add Jobs:",
    mode_options,
    index=default_mode_idx,
    horizontal=True
)


def render_verified_sites_guide():
    with st.expander("ℹ️ Supported Websites & Built-in Safety Shield", expanded=False):
        st.markdown("""
        - **🔎 Live Job Board Search (100% Free, No Login Needed):**
          - **LinkedIn Public Search:** Search live postings by role, location, workplace mode (`Remote`/`Hybrid`/`On-site`), and recency without logging in.
          - **Direct Company Career Pages:** Browse openings directly from company hiring boards (Greenhouse, Ashby, Lever).
          - **FreeHire Tech Search:** Search tech & engineering postings worldwide with full job descriptions.
        - **🌐 Multi-Link & Category Search:** Supports **Built In** (`builtin.com`), direct **LinkedIn** job links, and public company career pages.
        - **🧩 LinkedIn Extension Inbox:** If you prefer browsing LinkedIn logged in, use the **🔗 LinkedIn Inbox** in the sidebar to capture jobs with a single right-click.
        - **🛡️ Job Text Safety Shield:** Every job description is automatically cleaned to remove hidden text, invisible symbols, and malicious commands before sending to the AI.
        """)


render_verified_sites_guide()
render_resume_selector(key_suffix="scraper_page", in_sidebar=False)
render_active_prompt_indicator()
st.markdown("---")

DATE_POSTED_MAP = {
    "Any Time": 0,
    "Past 24 Hours": 1,
    "Past 7 Days": 7,
    "Past 14 Days": 14,
    "Past 30 Days": 30,
}

if selected_mode == "🔎 Job Board Search":
    st.subheader("🔎 Live Job Board Search")
    st.caption("Search live postings across LinkedIn, Company Career Pages (Greenhouse, Ashby, Lever), and FreeHire—zero account or API keys required.")

    portal_choice = st.radio(
        "Job Portal Source:",
        [
            "🔗 LinkedIn (Global Search — No Login Needed)",
            "🏢 Direct Company Hiring Pages (Greenhouse · Ashby · Lever — No Login)",
            "🌍 FreeHire (Tech Jobs)",
        ],
        horizontal=True,
        key="native_portal_choice"
    )

    is_linkedin = portal_choice.startswith("🔗")
    is_ats = portal_choice.startswith("🏢")

    if is_linkedin:
        user_prof = st.session_state.get("user_profile")
        if user_prof and user_prof.get("search_queries"):
            st.caption(f"🎯 **Recommended Roles for Your Profile ({user_prof.get('industry_title') or user_prof.get('archetype_title', 'Industry')}):**")
            rec_roles = user_prof.get("search_queries", [])[:4]
            r_cols = st.columns(len(rec_roles))
            for idx, r in enumerate(rec_roles):
                with r_cols[idx]:
                    if st.button(f"{r}", key=f"qf_compass_li_{idx}", width="stretch"):
                        st.session_state["li_search_query"] = r
                        st.rerun()

        with st.form("linkedin_guest_search_form"):
            col_q, col_loc = st.columns(2)
            with col_q:
                li_query = st.text_input(
                    "Keywords / Role Title:",
                    value=st.session_state.get("li_search_query", ""),
                    placeholder="e.g., Registered Nurse, Corporate Counsel, Operations Manager, SOC Analyst"
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

            search_submitted = st.form_submit_button("🔍 Search LinkedIn Jobs", type="primary", width="stretch")

        if search_submitted:
            st.session_state["li_search_query"] = li_query
            st.session_state["li_search_location"] = li_location
            if not li_location.strip() and not li_query.strip():
                st.warning("Please provide at least a keyword or location to search.")
            else:
                with st.spinner("Searching LinkedIn public job board..."):
                    try:
                        eval_urls, eval_li_ids = db.load_evaluated_job_identifiers()
                        seen_urls, seen_li_ids = db.load_seen_job_identifiers()
                        remote_param = "" if li_work_mode == "Any" else li_work_mode.lower()
                        results = search_linkedin_guest(
                            query=li_query.strip(),
                            location=li_location.strip() or "United States",
                            remote=remote_param,
                            jobage_days=DATE_POSTED_MAP.get(li_age_label, 0),
                            limit=int(li_limit),
                            evaluated_ids=eval_li_ids,
                            seen_ids=seen_li_ids,
                        )
                        db.record_seen_postings(results)
                        db.save_scraper_results(results, "LinkedIn Guest Search")
                        st.session_state["native_search_results"] = db.load_scraper_results()
                        st.session_state["native_search_source_label"] = "LinkedIn Guest Search"
                        st.session_state.pop("scraper_results_cleared", None)
                        if not results:
                            st.info("No matching LinkedIn postings found. Try broadening your keywords, location, or date filter.")
                        else:
                            st.switch_page("pages/7_scraper_results.py")
                    except Exception as e:
                        st.error(f"LinkedIn search failed: {e}")

    elif is_ats:
        st.caption("⚡ **Popular Company Career Boards (Click to Quick-Fill):**")
        b1, b2, b3, b4 = st.columns(4)
        with b1:
            if st.button("🏢 Anthropic (GH)", key="ats_qf_anthropic", width="stretch"):
                st.session_state["ats_board_input"] = "anthropic"
                st.session_state["ats_platform_choice"] = "Greenhouse"
                st.rerun()
        with b2:
            if st.button("🤖 OpenAI (Ashby)", key="ats_qf_openai", width="stretch"):
                st.session_state["ats_board_input"] = "openai"
                st.session_state["ats_platform_choice"] = "Ashby"
                st.rerun()
        with b3:
            if st.button("🛡️ Palantir (Lever)", key="ats_qf_palantir", width="stretch"):
                st.session_state["ats_board_input"] = "palantir"
                st.session_state["ats_platform_choice"] = "Lever"
                st.rerun()
        with b4:
            if st.button("💳 Stripe (GH)", key="ats_qf_stripe", width="stretch"):
                st.session_state["ats_board_input"] = "stripe"
                st.session_state["ats_platform_choice"] = "Greenhouse"
                st.rerun()

        with st.form("ats_board_search_form"):
            col_b, col_p, col_lim = st.columns([2, 1, 1])
            with col_b:
                board_input = st.text_input(
                    "Company Board Slug or URL:",
                    value=st.session_state.get("ats_board_input", ""),
                    placeholder="e.g. anthropic, jobs.ashbyhq.com/openai, or boards.greenhouse.io/gitlab",
                    help="Enter the company name slug or paste the direct career board link."
                )
            with col_p:
                plat_options = ["Auto-Detect", "Greenhouse", "Ashby", "Lever"]
                curr_plat = st.session_state.get("ats_platform_choice", "Auto-Detect")
                p_idx = plat_options.index(curr_plat) if curr_plat in plat_options else 0
                ats_platform = st.selectbox("ATS Platform:", plat_options, index=p_idx)
            with col_lim:
                ats_limit = st.selectbox("Max Roles:", [15, 30, 50, 100], index=1)

            ats_submitted = st.form_submit_button("🔍 Load Company Job Openings", type="primary", width="stretch")

        if ats_submitted:
            st.session_state["ats_board_input"] = board_input
            st.session_state["ats_platform_choice"] = ats_platform
            if not board_input.strip():
                st.warning("Please provide a company board name slug or career board URL.")
            else:
                with st.spinner(f"Loading public openings for '{board_input.strip()}'..."):
                    try:
                        eval_urls, eval_li_ids = db.load_evaluated_job_identifiers()
                        seen_urls, seen_li_ids = db.load_seen_job_identifiers()
                        results = fetch_ats_board_jobs(
                            platform=ats_platform.lower(),
                            token_or_url=board_input.strip(),
                            limit=int(ats_limit),
                            evaluated_urls=eval_urls,
                            seen_urls=seen_urls,
                        )
                        if not results:
                            st.info(f"No active postings found for board '{board_input.strip()}'. Verify the slug or try a direct board URL.")
                        else:
                            db.record_seen_postings(results)
                            source_lbl = results[0].get("source", f"ATS ({board_input.strip()})")
                            db.save_scraper_results(results, source_lbl)
                            st.session_state["native_search_results"] = db.load_scraper_results()
                            st.session_state["native_search_source_label"] = source_lbl
                            st.session_state.pop("scraper_results_cleared", None)
                            st.switch_page("pages/7_scraper_results.py")
                    except Exception as e:
                        st.error(f"Failed to load career board: {e}")

    else:
        user_prof = st.session_state.get("user_profile")
        if user_prof and user_prof.get("search_queries"):
            st.caption(f"🎯 **Recommended Roles for Your Profile ({user_prof.get('industry_title') or user_prof.get('archetype_title', 'Industry')}):**")
            rec_roles = user_prof.get("search_queries", [])[:4]
            r_cols = st.columns(len(rec_roles))
            for idx, r in enumerate(rec_roles):
                with r_cols[idx]:
                    if st.button(f"{r}", key=f"qf_compass_fh_{idx}", width="stretch"):
                        st.session_state["fh_search_query"] = r
                        st.rerun()

        with st.form("freehire_search_form"):
            col_q, col_reg, col_sen = st.columns([2, 1, 1])
            with col_q:
                fh_query = st.text_input(
                    "Keywords / Domain Stack / Role:",
                    value=st.session_state.get("fh_search_query", ""),
                    placeholder="e.g., Operations, Healthcare, Legal, Python, Security, Supply Chain"
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

            search_submitted = st.form_submit_button("🔍 Search FreeHire Jobs", type="primary", width="stretch")

        if search_submitted:
            st.session_state["fh_search_query"] = fh_query
            with st.spinner("Searching FreeHire jobs (with full descriptions)..."):
                try:
                    eval_urls, eval_li_ids = db.load_evaluated_job_identifiers()
                    seen_urls, seen_li_ids = db.load_seen_job_identifiers()
                    results = search_freehire_jobs(
                        query=fh_query.strip(),
                        work_mode="" if fh_work_mode == "Any" else fh_work_mode.lower(),
                        region="" if fh_region == "Any" else fh_region,
                        seniority="" if fh_seniority == "Any" else fh_seniority,
                        jobage_days=DATE_POSTED_MAP.get(fh_age_label, 0),
                        limit=int(fh_limit),
                        evaluated_ids=eval_urls | eval_li_ids,
                        seen_ids=seen_urls | seen_li_ids,
                    )
                    db.record_seen_postings(results)
                    db.save_scraper_results(results, "FreeHire API")
                    st.session_state["native_search_results"] = db.load_scraper_results()
                    st.session_state["native_search_source_label"] = "FreeHire API"
                    st.session_state.pop("scraper_results_cleared", None)
                    if not results:
                        st.info("No matching FreeHire postings found. Try broadening your filters or keywords.")
                    else:
                        st.switch_page("pages/7_scraper_results.py")
                except Exception as e:
                    st.error(f"FreeHire search failed: {e}")

    # Navigation & quick links
    if not st.session_state.get("scraper_results_cleared"):
        if "native_search_results" not in st.session_state or not st.session_state["native_search_results"]:
            cached = db.load_scraper_results()
            if cached:
                st.session_state["native_search_results"] = cached
                st.session_state["native_search_source_label"] = cached[0].get("source_board") or cached[0].get("source") or "Job Board Search"

    discovered_jobs = st.session_state.get("native_search_results", [])
    st.markdown("---")
    with st.container(border=True):
        col_info, col_btn = st.columns([3, 1.4])
        with col_info:
            if discovered_jobs:
                st.subheader("📋 Search Results Available")
                st.write(f"You have **{len(discovered_jobs)}** jobs loaded in your search results. Review, filter, and choose which ones to score on the **Search Results** page.")
            else:
                st.subheader("⚡ Quick Navigation & Extension Fallback")
                st.write("Browse results from previous searches, or use the **LinkedIn Inbox** if you prefer sending jobs directly from LinkedIn.")
        with col_btn:
            if st.button("Open Search Results", type="primary" if discovered_jobs else "secondary", width="stretch", key="btn_goto_results_banner"):
                st.switch_page("pages/7_scraper_results.py")
            if st.button("🔗 LinkedIn Inbox", width="stretch", key="btn_goto_linkedin_fallback"):
                st.switch_page("pages/5_linkedin.py")

elif selected_mode == "📝 Paste Job Text":
    st.subheader("📝 Paste Job Text")
    st.caption("🛡️ Protected by **Job Text Safety Shield**: hidden text, invisible symbols, and malicious commands are automatically removed.")
    prefill_job_text = st.session_state.pop("manual_job_text_buffer", "")
    with st.form("manual_paste_form"):
        job_description = st.text_area("Paste Job Description Here:", value=prefill_job_text, height=250)
        submitted = st.form_submit_button("Review Job with AI", type="primary")

    if submitted:
        if not job_description.strip() or not st.session_state.resume_text.strip():
            st.warning("Please provide both the master resume and job description.")
        else:
            with st.spinner("Checking safety & analyzing alignment with AI..."):
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
                        "URL": f"Manual_Paste_{int(time.time() * 1000)}",
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

elif selected_mode == "🌐 Paste Multiple Links":
    st.subheader("🌐 Paste Multiple Links")
    st.caption("Paste individual job web links (one per line). Supports **Built In**, **LinkedIn (`linkedin.com/jobs/view/...`)**, and company career pages.")
    
    col_samp, _ = st.columns([3, 7])
    with col_samp:
        if st.button("📋 Load Sample BuiltIn URLs", key="btn_sample_urls"):
            st.session_state["batch_urls_input"] = (
                "https://builtin.com/job/operations/operations-manager/224560\n"
                "https://builtin.com/job/healthtech/clinical-specialist/224561\n"
                "https://builtin.com/job/developer/software-engineer/224562\n"
                "https://builtin.com/job/cyber-security/information-security-analyst/224563"
            )
            st.rerun()

    sample_val = st.session_state.get("batch_urls_input", "")
    with st.form("batch_url_form"):
        urls_input = st.text_area("Job URLs (one per line):", value=sample_val, height=150)
        submitted = st.form_submit_button("Review All Job Links", type="primary")
        
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

elif selected_mode == "🧭 Search by Category":
    st.subheader("🧭 Search by Category")
    st.caption("⚡ **Browse Popular Career Categories:**")
    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
        if st.button("🏥 Healthcare / Biotech", key="preset_builtin_health", width="stretch"):
            st.session_state["search_url_preset"] = "https://builtin.com/jobs/healthtech/entry-level"
            st.rerun()
    with col_p2:
        if st.button("💼 Operations & HR", key="preset_builtin_ops", width="stretch"):
            st.session_state["search_url_preset"] = "https://builtin.com/jobs/operations/entry-level"
            st.rerun()
    with col_p3:
        if st.button("📊 Data & Analytics", key="preset_builtin_data", width="stretch"):
            st.session_state["search_url_preset"] = "https://builtin.com/jobs/data-analytics/entry-level"
            st.rerun()

    col_p4, col_p5, col_p6 = st.columns(3)
    with col_p4:
        if st.button("🛡️ Cybersecurity", key="preset_builtin_cyber", width="stretch"):
            st.session_state["search_url_preset"] = "https://builtin.com/jobs/cyber-security/entry-level"
            st.rerun()
    with col_p5:
        if st.button("💻 Software Engineering", key="preset_builtin_dev", width="stretch"):
            st.session_state["search_url_preset"] = "https://builtin.com/jobs/dev-engineering/entry-level"
            st.rerun()
    with col_p6:
        if st.button("☁️ Cloud & DevOps", key="preset_builtin_cloud", width="stretch"):
            st.session_state["search_url_preset"] = "https://builtin.com/jobs/devops-cloud/entry-level"
            st.rerun()

    preset_search = st.session_state.get("search_url_preset", "https://builtin.com/jobs/operations/entry-level")
    with st.form("search_form"):
        search_url = st.text_input("Search URL:", value=preset_search, placeholder="https://builtin.com/jobs/... or any job board search URL")
        submitted = st.form_submit_button("Find & Review Jobs", type="primary")
        
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
