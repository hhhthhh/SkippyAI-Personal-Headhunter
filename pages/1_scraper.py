import sys
import os
import time
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import streamlit as st

from utils import (
    render_resume_selector,
    combine_selected_resumes,
    render_active_prompt_indicator,
    initialize_core_state,
    start_scraper_evaluations as process_evaluations,
)
import database as db
from scraper import (
    scrape_universal_search_results,
    is_safe_url,
    search_linkedin_guest,
    search_freehire_jobs,
    fetch_ats_board_jobs,
)
from posting_guard import guard as run_posting_guard
from evaluator import evaluate_job

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


# Quick-Start Guide for first-time or new users
show_quick_start = st.session_state.get("show_quick_start", False)
dismissed = db.get_setting("dismissed_quick_start", "") == "true"
eval_urls, eval_li_ids = db.load_evaluated_job_identifiers()
has_evaluated_jobs = bool(eval_urls or eval_li_ids)

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

    st.markdown("---")

mode_options = [
    "🔎 Job Board Search",
    "📝 Paste Job Text",
    "🌐 Paste Multiple Links",
    "🧭 Search by Category",
]
if "selected_scraper_mode_idx" in st.session_state:
    idx = st.session_state.pop("selected_scraper_mode_idx")
    if isinstance(idx, int) and 0 <= idx < len(mode_options):
        st.session_state["scraper_mode_radio"] = mode_options[idx]

selected_mode = st.radio(
    "Choose How to Add Jobs:",
    mode_options,
    horizontal=True,
    key="scraper_mode_radio",
)


def render_verified_sites_guide():
    with st.expander("ℹ️ Supported Search Boards & Built-in Safety Shield", expanded=False):
        st.markdown(
            "- **Live Search Boards:** LinkedIn Public Search (no account needed), Direct Career Boards (Greenhouse, Ashby, Lever), and FreeHire API.\n"
            "- **Direct Links:** Paste direct URLs from Built In, LinkedIn (`/jobs/view/...`), or company career pages.\n"
            "- **Extension Inbox:** Capture postings directly from your browser with 1-click via the Skippy extension.\n"
            "- **Job Text Safety Shield:** Automatically sanitizes job descriptions, stripping invisible prompt injection and tracking artifacts."
        )


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
    st.subheader("🔎 LinkedIn Search")
    st.caption("Search live job postings across LinkedIn public job boards—zero account or API keys required.")

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
                    saved_ok = db.save_scraper_results(results, "LinkedIn Guest Search")
                    st.session_state["native_search_results"] = db.load_scraper_results() if saved_ok else results
                    st.session_state["native_search_source_label"] = "LinkedIn Guest Search"
                    st.session_state.pop("scraper_results_cleared", None)
                    if not saved_ok:
                        st.warning("⚠️ Search succeeded, but saving results to the database failed. Results are shown in memory for this session.")
                    if not results:
                        st.info("No matching LinkedIn postings found. Try broadening your keywords, location, or date filter.")
                    else:
                        st.toast(f"Found {len(results)} jobs! Review them below.", icon="📋")
                        st.rerun()
                except Exception as e:
                    st.error(f"LinkedIn search failed: {e}")

    # Collapsed Submenu for Advanced Users: Direct Company Hiring Pages & FreeHire
    adv_expanded = bool(
        st.session_state.get("expand_advanced_portals", False)
        or st.session_state.get("ats_board_input")
        or st.session_state.get("fh_search_query")
    )
    with st.expander("⚙️ Advanced Search Portals (Company Career Pages & FreeHire)", expanded=adv_expanded):
        st.caption("Specialized search tools for direct company career boards (Greenhouse, Ashby, Lever) and tech job databases.")
        adv_portal_choice = st.radio(
            "Select Advanced Search Portal:",
            [
                "🏢 Direct Company Hiring Pages (Greenhouse · Ashby · Lever — No Login)",
                "🌍 FreeHire (Tech Jobs)",
            ],
            horizontal=True,
            key="native_adv_portal_choice"
        )

        is_ats = adv_portal_choice.startswith("🏢")

        if is_ats:
            st.caption("⚡ **Popular Company Career Boards (Click to Quick-Fill):**")
            b1, b2, b3, b4 = st.columns(4)
            with b1:
                if st.button("🏢 Anthropic (GH)", key="ats_qf_anthropic", width="stretch"):
                    st.session_state["ats_board_input"] = "anthropic"
                    st.session_state["ats_platform_choice"] = "Greenhouse"
                    st.session_state["expand_advanced_portals"] = True
                    st.rerun()
            with b2:
                if st.button("🤖 OpenAI (Ashby)", key="ats_qf_openai", width="stretch"):
                    st.session_state["ats_board_input"] = "openai"
                    st.session_state["ats_platform_choice"] = "Ashby"
                    st.session_state["expand_advanced_portals"] = True
                    st.rerun()
            with b3:
                if st.button("🛡️ Palantir (Lever)", key="ats_qf_palantir", width="stretch"):
                    st.session_state["ats_board_input"] = "palantir"
                    st.session_state["ats_platform_choice"] = "Lever"
                    st.session_state["expand_advanced_portals"] = True
                    st.rerun()
            with b4:
                if st.button("💳 Stripe (GH)", key="ats_qf_stripe", width="stretch"):
                    st.session_state["ats_board_input"] = "stripe"
                    st.session_state["ats_platform_choice"] = "Greenhouse"
                    st.session_state["expand_advanced_portals"] = True
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
                st.session_state["expand_advanced_portals"] = True
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
                                source_lbl = results[0].get("source", f"ATS ({board_input.strip()})")
                                saved_ok = db.save_scraper_results(results, source_lbl)
                                st.session_state["native_search_results"] = db.load_scraper_results() if saved_ok else results
                                st.session_state["native_search_source_label"] = source_lbl
                                st.session_state.pop("scraper_results_cleared", None)
                                if not saved_ok:
                                    st.warning("⚠️ Board loaded, but saving results to the database failed. Results are shown in memory for this session.")
                                st.toast(f"Found {len(results)} jobs! Review them below.", icon="📋")
                                st.rerun()
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
                            st.session_state["expand_advanced_portals"] = True
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
                st.session_state["expand_advanced_portals"] = True
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
                        saved_ok = db.save_scraper_results(results, "FreeHire API")
                        st.session_state["native_search_results"] = db.load_scraper_results() if saved_ok else results
                        st.session_state["native_search_source_label"] = "FreeHire API"
                        st.session_state.pop("scraper_results_cleared", None)
                        if not saved_ok:
                            st.warning("⚠️ Search succeeded, but saving results to the database failed. Results are shown in memory for this session.")
                        if not results:
                            st.info("No matching FreeHire postings found. Try broadening your filters or keywords.")
                        else:
                            st.toast(f"Found {len(results)} jobs! Review them below.", icon="📋")
                            st.rerun()
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
    if discovered_jobs:
        eval_urls, eval_li_ids = db.load_evaluated_job_identifiers()
        seen_urls, seen_li_ids = db.load_seen_job_identifiers()
        total_eval_vault = len(eval_urls)

        st.subheader(f"📋 Discovered Postings")
        source_label = st.session_state.get("native_search_source_label", "Job Board Search")
        st.caption(
            f"Accumulated search queue (latest search: **{source_label}**; click **🗑️ Clear** below to reset). "
            f"Total evaluated jobs in vault across all intake sources: **{total_eval_vault}**."
        )

        for j in discovered_jobs:
            raw_url = j.get("url") or j.get("original_url") or ""
            lid = db.extract_linkedin_job_id(j.get("id") or raw_url)
            norm_url = db.normalize_job_url(raw_url)
            if (lid and lid in eval_li_ids) or (norm_url and norm_url in eval_urls):
                j["status"] = "evaluated"
            elif j.get("status") == "evaluated":
                j["status"] = "seen" if ((lid and lid in seen_li_ids) or (norm_url and norm_url in seen_urls)) else "new"
            elif j.get("status") not in ("new", "seen"):
                j["status"] = "seen" if ((lid and lid in seen_li_ids) or (norm_url and norm_url in seen_urls)) else "new"

        new_jobs = [j for j in discovered_jobs if j.get("status") == "new"]
        seen_jobs = [j for j in discovered_jobs if j.get("status") == "seen"]
        evaluated_jobs = [j for j in discovered_jobs if j.get("status") == "evaluated"]

        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Saved Search Queue", len(discovered_jobs), help="Accumulated postings across your searches until you click Clear")
        col_m2.metric("🆕 New", len(new_jobs))
        col_m3.metric("👁️ Seen", len(seen_jobs))
        col_m4.metric("✅ Evaluated in Queue", f"{len(evaluated_jobs)} of {len(discovered_jobs)}", help=f"{len(evaluated_jobs)} of {len(discovered_jobs)} postings in your search queue have already been evaluated. (Total in Evaluations vault across all sources: {total_eval_vault})")

        if len(evaluated_jobs) == len(discovered_jobs) and len(discovered_jobs) > 0:
            st.info(
                f"💡 **All {len(discovered_jobs)} postings in your saved search queue have already been evaluated.** "
                f"You have **{total_eval_vault} total evaluated jobs** saved in **📁 Evaluations** (including Extension Inbox, Paste Links/Text, and archived postings). "
                f"Run a new search above or click **🗑️ Clear** to reset the queue.",
                icon="ℹ️"
            )

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
            key="scraper_inpage_view_filter"
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

        TABLE_COLUMNS = ["Status", "Title", "Company", "Signals", "Location", "Posted", "URL"]
        table_rows = []
        for idx, j in enumerate(displayed_jobs):
            st_badge = status_badge_map.get(j.get("status"), "🆕 New")
            risk = db.check_repost_risk(j.get("company", ""), j.get("title", ""), j.get("url", ""))
            if risk and risk.get("is_ghost_risk"):
                signals = risk.get("badge_text", "👻 Relisted")
            elif risk:
                signals = risk.get("badge_text", "🔄 Relisted")
            else:
                signals = "✨ Fresh"

            table_rows.append({
                "Status": st_badge,
                "Title": j.get("title", ""),
                "Company": j.get("company", ""),
                "Signals": signals,
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
            key="scraper_inpage_preview_table"
        )

        selected_indices = selection_event.selection.rows if selection_event and selection_event.selection else []
        b_col1, b_col2, b_col3, b_col4 = st.columns([2, 2, 1.5, 1])

        with b_col1:
            unevaluated_in_view = [j for j in displayed_jobs if j.get("status") != "evaluated"]
            all_unevaluated = [j for j in discovered_jobs if j.get("status") != "evaluated"]

            if new_jobs:
                candidate_jobs = new_jobs
                btn_batch = min(len(candidate_jobs), max_jobs)
                top_btn_label = f"🚀 Review Top {btn_batch} New Job{'s' if btn_batch != 1 else ''}"
            elif unevaluated_in_view:
                candidate_jobs = unevaluated_in_view
                btn_batch = min(len(candidate_jobs), max_jobs)
                top_btn_label = f"🚀 Review Top {btn_batch} Postings"
            elif all_unevaluated:
                candidate_jobs = all_unevaluated
                btn_batch = min(len(candidate_jobs), max_jobs)
                top_btn_label = f"🚀 Review Top {btn_batch} Postings"
            else:
                candidate_jobs = []
                btn_batch = 0
                top_btn_label = f"✅ All {len(discovered_jobs)} Jobs Evaluated"

            if st.button(
                top_btn_label,
                type="primary",
                disabled=(btn_batch == 0),
                width="stretch",
                key="btn_inpage_eval_top"
            ):
                process_evaluations(candidate_jobs[:max_jobs])

        with b_col2:
            sel_count = len(selected_indices)
            if st.button(
                f"🎯 Review Selected ({sel_count})",
                disabled=(sel_count == 0),
                width="stretch",
                key="btn_inpage_eval_selected"
            ):
                chosen_raw = [displayed_jobs[i] for i in selected_indices if 0 <= i < len(displayed_jobs)]
                chosen_unevaluated = [j for j in chosen_raw if j.get("status") != "evaluated"]
                skipped_eval = len(chosen_raw) - len(chosen_unevaluated)
                if skipped_eval > 0:
                    st.info(f"⏭️ Skipped {skipped_eval} already evaluated posting(s).")
                if not chosen_unevaluated:
                    st.warning("All selected postings have already been evaluated.")
                else:
                    process_evaluations(chosen_unevaluated)

        with b_col3:
            mark_btn_label = f"👁️ Mark Seen ({len(selected_indices)})" if selected_indices else "👁️ Mark Seen"
            can_mark = len(selected_indices) > 0 or len(new_jobs) > 0
            if st.button(
                mark_btn_label,
                width="stretch",
                disabled=not can_mark,
                key="btn_inpage_mark_seen",
                help="Marks postings as seen so future scrapes skip them."
            ):
                target_to_mark = [displayed_jobs[i] for i in selected_indices if 0 <= i < len(displayed_jobs)] if selected_indices else new_jobs
                if db.record_seen_postings(target_to_mark):
                    for j in target_to_mark:
                        if j.get("status") != "evaluated":
                            j["status"] = "seen"
                    db.save_scraper_results(discovered_jobs, st.session_state.get("native_search_source_label", ""))
                    st.toast(f"✅ Marked {len(target_to_mark)} posting(s) as seen.")
                    st.rerun()
                else:
                    st.error("⚠️ Could not save seen postings right now (database busy). Please try again.")

        with b_col4:
            if st.button("🗑️ Clear", width="stretch", key="btn_inpage_clear_results"):
                db.clear_scraper_results()
                st.session_state["scraper_results_cleared"] = True
                st.session_state["native_search_results"] = []
                st.rerun()

    else:
        with st.container(border=True):
            col_info, col_btn = st.columns([3, 1.4])
            with col_info:
                st.subheader("⚡ Extension Inbox")
                st.write("Prefer browsing LinkedIn directly? Use the Skippy browser extension to capture jobs into your **Extension Inbox** with a single click.")
            with col_btn:
                if st.button("🔗 Open Extension Inbox", type="primary", width="stretch", key="btn_goto_linkedin_fallback"):
                    st.switch_page("pages/5_linkedin.py")

elif selected_mode == "📝 Paste Job Text":
    st.subheader("📝 Paste Job Text")
    st.caption("🛡️ Protected by **Job Text Safety Shield**: hidden text, invisible symbols, and malicious commands are automatically removed.")
    if "manual_job_text_buffer" in st.session_state:
        st.session_state["manual_job_text_input"] = st.session_state.pop("manual_job_text_buffer")
    with st.form("manual_paste_form"):
        job_description = st.text_area("Paste Job Description Here:", height=250, key="manual_job_text_input")
        submitted = st.form_submit_button("Review Job with AI", type="primary")

    if submitted:
        chosen_resumes = st.session_state.get("selected_resumes", ["Master Resume"])
        active_resume_text = combine_selected_resumes(chosen_resumes) or st.session_state.get("resume_text", "")
        st.session_state.resume_text = active_resume_text
        if not job_description.strip() or not active_resume_text.strip():
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
                        active_resume_text,
                        cleaned_job_text,
                        st.session_state.system_instructions,
                        st.session_state.get("model_choice"),
                        st.session_state.get("user_api_key"),
                        st.session_state.get("local_base_url"),
                        st.session_state.get("local_model_name"),
                        st.session_state.get("model_override", ""),
                        pre_security_flags=sec_flags,
                        skip_guard=True,
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
    
    with st.form("batch_url_form"):
        urls_input = st.text_area(
            "Job URLs (one per line):",
            value="",
            height=150,
            placeholder="https://builtin.com/job/...\nhttps://www.linkedin.com/jobs/view/...\nhttps://boards.greenhouse.io/..."
        )
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
                eval_urls, eval_li_ids = db.load_evaluated_job_identifiers()
                new_urls = [u for u in safe_urls if db.classify_posting(u, eval_urls, eval_li_ids, set(), set()) != "evaluated"]
                skipped = len(safe_urls) - len(new_urls)
                if skipped > 0:
                    st.info(f"⏭ Skipped {skipped} previously evaluated postings.")
                if not new_urls:
                    st.warning("All provided URLs have already been evaluated. Check your History tab!")
                else:
                    process_evaluations(new_urls)

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
                eval_urls, eval_li_ids = db.load_evaluated_job_identifiers()
                new_urls = [u for u in discovered_urls if db.classify_posting(u, eval_urls, eval_li_ids, set(), set()) != "evaluated"]
                skipped = len(discovered_urls) - len(new_urls)
                if skipped > 0:
                    st.info(f"⏭️ Skipped {skipped} previously evaluated postings.")
                if not new_urls:
                    st.warning("All discovered jobs on this page have already been evaluated.")
                else:
                    process_evaluations(new_urls[:max_jobs])
