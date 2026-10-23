import sys
import os
import time
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import streamlit as st

from utils import (
    render_completion_card,
    check_and_handle_pipeline_completion,
    render_resume_selector,
    combine_selected_resumes,
)
import database as db
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
max_jobs = st.sidebar.slider("Max Postings to Evaluate", min_value=1, max_value=50, value=5, step=1, key="scraper_results_max_jobs")


def process_evaluations(items: list):
    """Starts the background evaluation pipeline for a list of job dicts or URLs."""
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
def render_active_results_pipeline():
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
            st.info("💡 **Page persistence active:** Evaluation continues running in the background while you review postings or navigate Skippy.")
            if st.button("🛑 Stop Pipeline", key="stop_results_pipeline_main"):
                pipeline_manager.cancel()
                st.rerun()


render_active_results_pipeline()

# Accessible Completion Card displayed if a run just completed
if "completion_batch" in st.session_state:
    render_completion_card(
        st.session_state["completion_batch"]["jobs"],
        source_label=st.session_state["completion_batch"]["source"]
    )
    st.markdown("---")

col_title, col_back = st.columns([3.5, 1.8])
with col_title:
    st.title("📋 Scraper Results")
    source_label = st.session_state.get("native_search_source_label", "Job Board Search")
    st.caption(f"Discovered postings from **{source_label}**. Filter, curate, and submit jobs for AI evaluation.")
with col_back:
    if st.button("🔍 Back to Scraper", width="stretch"):
        st.switch_page("pages/1_scraper.py")
    if st.button("🔗 LinkedIn Evaluator (Fallback)", width="stretch", key="btn_goto_li_fallback_results"):
        st.switch_page("pages/5_linkedin.py")

render_resume_selector(key_suffix="scraper_results_page", in_sidebar=False)
st.markdown("---")

# Restore persisted scraper results if session state was cleared by page refresh
if not st.session_state.get("scraper_results_cleared"):
    if "native_search_results" not in st.session_state or not st.session_state["native_search_results"]:
        cached_scraper_results = db.load_scraper_results()
        if cached_scraper_results:
            st.session_state["native_search_results"] = cached_scraper_results
            st.session_state["native_search_source_label"] = cached_scraper_results[0].get("source_board") or cached_scraper_results[0].get("source") or "Job Board Search"

discovered_jobs = st.session_state.get("native_search_results", [])

if not discovered_jobs:
    with st.container(border=True):
        st.subheader("📭 No Postings in Results Queue")
        st.write("You don't have any search results loaded right now. Head over to the Scraper page to search live postings from LinkedIn or FreeHire.")
        if st.button("🔍 Open Scraper Search", type="primary"):
            st.switch_page("pages/1_scraper.py")

    with st.expander("⚙️ Seen History Settings", expanded=False):
        total_seen = db.get_seen_postings_count()
        st.write(f"Skippy currently remembers **{total_seen}** previously seen posting(s).")
        if st.button("🔄 Reset Seen Postings History", key="btn_reset_seen_history_empty"):
            db.clear_seen_postings()
            db.clear_scraper_results()
            if "native_search_results" in st.session_state:
                del st.session_state["native_search_results"]
            st.success("Seen postings history has been cleared.")
            st.rerun()

else:
    eval_urls, eval_li_ids = db.load_evaluated_job_identifiers()

    # Update status: if evaluated in database, it upgrades to 'evaluated'
    for j in discovered_jobs:
        raw_url = j.get("url") or j.get("original_url") or ""
        lid = db.extract_linkedin_job_id(j.get("id") or raw_url)
        norm_url = db.normalize_job_url(raw_url)
        if (lid and lid in eval_li_ids) or (norm_url and norm_url in eval_urls):
            j["status"] = "evaluated"
        elif j.get("status") not in ("new", "seen", "evaluated"):
            j["status"] = "new"

    new_jobs = [j for j in discovered_jobs if j.get("status") == "new"]
    seen_jobs = [j for j in discovered_jobs if j.get("status") == "seen"]
    evaluated_jobs = [j for j in discovered_jobs if j.get("status") == "evaluated"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Results Found", len(discovered_jobs))
    m2.metric("🆕 New", len(new_jobs))
    m3.metric("👁️ Seen", len(seen_jobs))
    m4.metric("✅ Evaluated", len(evaluated_jobs))

    default_filter_idx = 0 if len(new_jobs) > 0 else 1
    filter_mode = st.radio(
        "Filter View:",
        ["🆕 New Only", "All Postings", "👁️ Seen", "✅ Evaluated"],
        index=default_filter_idx,
        format_func=lambda opt: {
            "🆕 New Only": f"🆕 New Only ({len(new_jobs)})",
            "All Postings": f"All Postings ({len(discovered_jobs)})",
            "👁️ Seen": f"👁️ Seen ({len(seen_jobs)})",
            "✅ Evaluated": f"✅ Evaluated ({len(evaluated_jobs)})",
        }.get(opt, opt),
        horizontal=True,
        key="results_page_view_filter"
    )

    if filter_mode == "🆕 New Only":
        displayed_jobs = new_jobs
    elif filter_mode == "👁️ Seen":
        displayed_jobs = seen_jobs
    elif filter_mode == "✅ Evaluated":
        displayed_jobs = evaluated_jobs
    else:
        displayed_jobs = discovered_jobs

    status_badge_map = {
        "new": "🆕 New",
        "seen": "👁️ Seen",
        "evaluated": "✅ Evaluated"
    }

    TABLE_COLUMNS = ["Status", "Title", "Company", "Location", "Posted", "URL"]
    table_rows = []
    for idx, j in enumerate(displayed_jobs):
        st_badge = status_badge_map.get(j.get("status"), "🆕 New")
        table_rows.append({
            "Status": st_badge,
            "Title": j.get("title", ""),
            "Company": j.get("company", ""),
            "Location": j.get("location", ""),
            "Posted": j.get("date", "—"),
            "URL": j.get("url", ""),
            "_orig_idx": idx,
        })

    preview_df = pd.DataFrame(table_rows, columns=TABLE_COLUMNS)

    if preview_df.empty:
        st.info("ℹ️ No job postings found matching this filter view.")

    selection_event = st.dataframe(
        preview_df[TABLE_COLUMNS],
        width="stretch",
        on_select="rerun",
        selection_mode="multi-row",
        column_config={"URL": st.column_config.LinkColumn("Posting Link")},
        key="results_page_preview_table"
    )

    selected_indices = selection_event.selection.rows if selection_event and selection_event.selection else []
    col_btn1, col_btn2, col_btn3, col_btn4 = st.columns([2, 2, 1.5, 1])

    with col_btn1:
        batch_count = min(len(new_jobs), max_jobs)
        if st.button(
            f"🚀 Evaluate Top {batch_count} New Posting{'s' if batch_count != 1 else ''}",
            type="primary",
            disabled=(batch_count == 0),
            width="stretch",
            key="btn_eval_top_results"
        ):
            process_evaluations(new_jobs[:max_jobs])

    with col_btn2:
        sel_count = len(selected_indices)
        if st.button(
            f"🎯 Evaluate Selected ({sel_count})",
            disabled=(sel_count == 0),
            width="stretch",
            key="btn_eval_selected_results"
        ):
            chosen_raw = [displayed_jobs[i] for i in selected_indices if 0 <= i < len(displayed_jobs)]
            chosen_unevaluated = [j for j in chosen_raw if j.get("status") != "evaluated"]
            skipped_eval = len(chosen_raw) - len(chosen_unevaluated)
            if skipped_eval > 0:
                st.info(f"⏭️ Skipped {skipped_eval} already evaluated posting(s).")
            if not chosen_unevaluated:
                st.warning("All selected postings have already been evaluated.")
            else:
                process_evaluations(chosen_unevaluated[:max_jobs])

    with col_btn3:
        mark_btn_label = f"👁️ Mark Selected as Seen ({len(selected_indices)})" if selected_indices else "👁️ Mark as Seen"
        can_mark = len(selected_indices) > 0 or len(new_jobs) > 0
        if st.button(
            mark_btn_label,
            width="stretch",
            disabled=not can_mark,
            key="btn_mark_seen_results",
            help="Marks postings as seen so future scrapes skip them."
        ):
            if selected_indices:
                target_to_mark = [displayed_jobs[i] for i in selected_indices if 0 <= i < len(displayed_jobs)]
            else:
                target_to_mark = new_jobs

            db.record_seen_postings(target_to_mark)
            for j in target_to_mark:
                if j.get("status") != "evaluated":
                    j["status"] = "seen"
            # Persist updated status so it survives page refreshes
            db.save_scraper_results(discovered_jobs, st.session_state.get("native_search_source_label", ""))
            st.toast(f"✅ Marked {len(target_to_mark)} posting(s) as seen.")
            st.rerun()

    with col_btn4:
        if st.button("🗑️ Clear Results", width="stretch", key="btn_clear_results_page"):
            db.clear_scraper_results()
            st.session_state["scraper_results_cleared"] = True
            st.session_state["native_search_results"] = []
            st.rerun()

    with st.expander("⚙️ Seen History Settings", expanded=False):
        total_seen = db.get_seen_postings_count()
        st.caption(f"Skippy remembers scraped postings you've seen ({total_seen} currently tracked) so they don't crowd out future searches. You can clear this history anytime.")
        if st.button("🔄 Reset Seen Postings History", key="btn_reset_seen_history_results"):
            db.clear_seen_postings()
            db.clear_scraper_results()
            if "native_search_results" in st.session_state:
                del st.session_state["native_search_results"]
            st.success("Seen postings history cleared and table results reset.")
            st.rerun()
