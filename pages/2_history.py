import streamlit as st
import pandas as pd
import os
import re
import sys
import hashlib
from datetime import date, datetime, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils import load_resumes, combine_selected_resumes, render_ats_resume_downloads, navigate_to_page
import database as db
from evaluator import (
    tailor_resume,
    tailor_cover_letter,
    generate_interview_prep,
    generate_application_qa,
    generate_followup_note,
    generate_outreach_messages,
    generate_deep_company_brief,
    generate_docx_from_markdown,
    is_pdf_conversion_available,
    render_ats_resume_html,
    review_and_refine_document,
    format_audit_report_markdown,
    get_fit_band,
)

st.title("📁 Evaluations")

def safe_fragment_rerun():
    """Reruns only the local fragment if inside a fragment interaction; falls back to app rerun."""
    try:
        st.rerun(scope="fragment")
    except Exception:
        st.rerun()

if "latest_batch_info" in st.session_state:
    b_info = st.session_state["latest_batch_info"]
    src = b_info.get("source", "Scraper")
    urls = b_info.get("urls", [])
    count = len(urls)
    if "active_job_url" not in st.session_state and urls:
        st.session_state["active_job_url"] = urls[0]
    col_msg, col_dism = st.columns([5.5, 1], vertical_alignment="center")
    with col_msg:
        st.info(f"✨ **Latest Run Results:** Viewing {count} newly evaluated posting{'s' if count != 1 else ''} from **{src}**.", icon="🎯")
    with col_dism:
        if st.button("Dismiss", key="dismiss_latest_batch_info"):
            del st.session_state["latest_batch_info"]
            st.rerun()

def _clear_deleted_job_state(urls: list[str]) -> None:
    """Cleans up session_state references for deleted job URLs."""
    url_set = set(urls or [])
    if st.session_state.get("active_job_url") in url_set:
        st.session_state.pop("active_job_url", None)
    for u in url_set:
        for col in db.DOC_COLUMNS:
            st.session_state.pop(f"{col}_{u}", None)


all_saved_jobs = db.load_all_jobs(summary_only=True)
if "resumes_vault" not in st.session_state:
    st.session_state["resumes_vault"] = load_resumes()

# Header Toolbar with Summary Metrics & Quick Action Tools
col_act1, col_act2, col_act3, _ = st.columns([1.5, 2.2, 1.8, 4.5])
with col_act1:
    if st.button("🔄 Refresh Data", type="secondary", width="stretch"):
        st.rerun()
with col_act2:
    with st.popover("🧹 Clean Up Postings", width="stretch"):
        st.markdown("**Bulk Prune Unwanted Postings**")
        st.caption("Remove low-scoring or unwanted listings while keeping them marked as **Seen** so future searches skip them.")
        cleanup_mode_label = st.radio(
            "Cleanup Rule:",
            [
                "📉 Low Score & Disqualified",
                "❌ Disqualified Postings Only",
                "🗂️ By Application Status",
            ],
            key="history_bulk_cleanup_mode",
        )
        max_score_cutoff = 60
        include_disq = True
        chosen_statuses = []

        if cleanup_mode_label == "📉 Low Score & Disqualified":
            max_score_cutoff = st.slider(
                "Delete postings with Score below:",
                min_value=10,
                max_value=90,
                value=60,
                step=5,
                key="history_bulk_max_score",
            )
            include_disq = st.checkbox(
                "Also include Disqualified postings",
                value=True,
                key="history_bulk_include_disq",
            )
            mode_key = "low_score"
        elif cleanup_mode_label == "❌ Disqualified Postings Only":
            mode_key = "disqualified"
        else:
            mode_key = "status"
            chosen_statuses = st.multiselect(
                "Select Application Statuses to Remove:",
                options=[
                    "Not Applied",
                    "Archived",
                    "Ghosted / Stale",
                    "Rejected (Application)",
                    "Rejected (Interview)",
                ],
                default=["Archived", "Rejected (Application)", "Rejected (Interview)"],
                key="history_bulk_statuses",
            )

        protect_saved = st.checkbox(
            "🛡️ Protect active applications (Applied, Interviewing, Offer) & postings with saved documents",
            value=True,
            key="history_bulk_protect_saved",
        )

        to_del, protected_list = db.preview_bulk_delete(
            all_saved_jobs,
            mode=mode_key,
            max_score=max_score_cutoff,
            include_disqualified=include_disq,
            statuses=chosen_statuses,
            protect_active_and_docs=protect_saved,
        )
        del_count = len(to_del)
        prot_count = len(protected_list)

        if del_count > 0:
            prot_note = f" ({prot_count} protected)" if prot_count > 0 else ""
            st.info(f"Matches **{del_count}** posting(s) to remove{prot_note}.")
        elif prot_count > 0:
            st.caption(f"0 postings to delete ({prot_count} matching posting(s) are protected by the safety guardrail).")
        else:
            st.caption("No postings currently match this rule.")

        if st.button(
            f"🗑️ Delete {del_count} Matching Posting{'s' if del_count != 1 else ''}",
            type="primary",
            disabled=(del_count == 0),
            key="btn_confirm_bulk_cleanup",
            width="stretch",
        ):
            target_urls = [j["URL"] for j in to_del if j.get("URL")]
            removed = db.delete_jobs_by_urls(target_urls, keep_seen=True)
            _clear_deleted_job_state(target_urls)
            st.toast(f"🧹 Removed {removed} posting(s) (kept marked as Seen).")
            st.rerun()

with col_act3:
    with st.popover("🗑️ Clear History", width="stretch"):
        st.warning("⚠️ **Warning:** This will permanently delete all evaluated postings, generated documents, and audit reports.")
        if st.button("Confirm Delete All History", type="primary", key="btn_confirm_clear_all_history", width="stretch"):
            db.clear_all_history()
            st.session_state.pop("active_job_url", None)
            st.rerun()

if not all_saved_jobs:
    with st.container(border=True):
        st.subheader("🗂️ No Jobs Reviewed Yet")
        st.write(
            "Your evaluated jobs, 4-pillar match scores, dealbreaker checks, and tailored application "
            "materials (ATS resumes, custom cover letters, STAR interview prep) will appear here once you review them."
        )
        col_goto_search, _ = st.columns([2.5, 4.5])
        with col_goto_search:
            if st.button("🔍 Go to Job Search & Review a Role ➔", type="primary", width="stretch", key="btn_empty_history_goto_search"):
                navigate_to_page("pages/1_scraper.py")
    st.stop()


def format_deadline_badge(deadline_str: str) -> str:
    """Formats a YYYY-MM-DD deadline with 🔥 urgency (<=7 days) or ⚠️ expired indicators."""
    raw = str(deadline_str or "").strip()
    if not raw or raw.lower() == "nan":
        return "—"
    try:
        dl_date = datetime.strptime(raw[:10], "%Y-%m-%d").date()
        today = date.today()
        delta = (dl_date - today).days
        if delta < 0:
            return f"⚠️ {raw[:10]} (Passed)"
        if delta <= 7:
            return f"🔥 {raw[:10]} ({delta}d left)"
        return raw[:10]
    except ValueError:
        return raw


def parse_job_date(timestamp_str: str) -> date | None:
    """Parses a date object from a job timestamp string (e.g. 'YYYY-MM-DD HH:MM' or ISO)."""
    dt = db.parse_date_safely(timestamp_str)
    return dt.date() if dt else None


def get_source(item: dict) -> str:
    """Safely extracts the job acquisition channel (Scraper, LinkedIn, or Manual)."""
    src = item.get("Source")
    if pd.isna(src) or not src:
        return "Manual"
    return str(src).strip()


# Build search dataframe
today = date.today()
df = pd.DataFrame(all_saved_jobs)
df["Original_Index"] = df.index
if "Company" not in df.columns:
    df["Company"] = ""
if "Deadline" not in df.columns:
    df["Deadline"] = ""
if "Timestamp" not in df.columns:
    df["Timestamp"] = ""
if "Position" not in df.columns:
    df["Position"] = "Role"
if "Source" not in df.columns:
    df["Source"] = "Manual"
if "Technical Score" not in df.columns:
    df["Technical Score"] = 0
if "Experience Score" not in df.columns:
    df["Experience Score"] = 0
if "Behavioral Score" not in df.columns:
    df["Behavioral Score"] = 0
if "Career Score" not in df.columns:
    df["Career Score"] = 0
if "Matching Skills" not in df.columns:
    df["Matching Skills"] = ""
if "Missing Skills" not in df.columns:
    df["Missing Skills"] = ""
if "Red Flags" not in df.columns:
    df["Red Flags"] = ""

df["Job_Date"] = df["Timestamp"].apply(parse_job_date)
df["Company_Display"] = df["Company"].apply(lambda c: c if str(c).strip() and str(c).strip() != "Unknown Company" else "—")
df["Deadline_Display"] = df["Deadline"].apply(format_deadline_badge)
df["Assessment"] = df.apply(lambda row: get_fit_band(row.get("Score", 0), bool(row.get("Eligible", True))), axis=1)
df["Clean_Source"] = df.apply(get_source, axis=1)
df["Score"] = pd.to_numeric(df["Score"], errors="coerce").fillna(0).astype(int)
df["Technical Score"] = pd.to_numeric(df["Technical Score"], errors="coerce").fillna(0).astype(int)
df["Experience Score"] = pd.to_numeric(df["Experience Score"], errors="coerce").fillna(0).astype(int)
df["Behavioral Score"] = pd.to_numeric(df["Behavioral Score"], errors="coerce").fillna(0).astype(int)
df["Career Score"] = pd.to_numeric(df["Career Score"], errors="coerce").fillna(0).astype(int)

def get_signals_badge(row):
    risk = db.check_repost_risk(row.get("Company", ""), row.get("Position", ""), row.get("URL", ""))
    if risk and risk.get("is_ghost_risk"):
        return risk.get("badge_text", "👻 Relisted")
    if risk:
        return risk.get("badge_text", "🔄 Relisted")
    return "✨ Fresh"

df["Signals"] = df.apply(get_signals_badge, axis=1)
df["_is_archived"] = df["Application Status"].fillna("").astype(str).str.strip().str.lower().str.contains("archive")
active_total_count = int((~df["_is_archived"]).sum())
archived_total_count = int(df["_is_archived"].sum())

# If jumping to a specific posting from another page, switch to the view containing that posting
if st.session_state.get("jump_to_card") and st.session_state.get("active_job_url"):
    _jump_target = next((j for j in all_saved_jobs if j.get("URL") == st.session_state.get("active_job_url")), None)
    if _jump_target is not None:
        _jump_is_archived = "archive" in str(_jump_target.get("Application Status") or "").strip().lower()
        st.session_state["history_archive_view"] = "archived" if _jump_is_archived else "active"

history_view_mode = st.radio(
    "Posting View:",
    options=["active", "archived"],
    format_func=lambda k: (
        f"📋 Active Postings ({active_total_count})"
        if k == "active"
        else f"🗄️ Archived ({archived_total_count})"
    ),
    horizontal=True,
    key="history_archive_view",
    label_visibility="collapsed",
)

# --- UNIFIED SEARCH & FILTER BAR ---
with st.container(border=True):
    col_search, col_source, col_fit, col_date = st.columns([3.2, 1.8, 2.5, 2.0], vertical_alignment="bottom")
    with col_search:
        search_query = st.text_input(
            "🔍 Search Evaluated Postings:",
            placeholder="Type role, company, skills...",
            key="history_search_query",
        ).strip().lower()
    with col_source:
        source_filter = st.selectbox(
            "Source Board:",
            ["All Sources", "🕸️ Scraper", "🔗 LinkedIn", "📝 Manual"],
            key="history_source_filter",
        )
    with col_fit:
        filter_selection = st.selectbox(
            "Fit Assessment:",
            ["All Fit Levels", "Strong Fit (75+)", "Good Fit (60-74)", "Moderate / Weak Fit (<60)", "Disqualified"],
            key="history_fit_filter",
        )
    with col_date:
        date_filter_selection = st.selectbox(
            "Evaluation Date:",
            ["All Dates", "Today", "Yesterday", "Past 7 Days", "Past 30 Days"],
            key="history_date_filter",
        )

# Apply filters
filtered_df = df[df["_is_archived"]].copy() if history_view_mode == "archived" else df[~df["_is_archived"]].copy()

if search_query:
    filtered_df = filtered_df[
        filtered_df["Position"].astype(str).str.lower().str.contains(search_query, regex=False) |
        filtered_df["Company"].astype(str).str.lower().str.contains(search_query, regex=False) |
        filtered_df["Summary"].astype(str).str.lower().str.contains(search_query, regex=False) |
        filtered_df["Matching Skills"].astype(str).str.lower().str.contains(search_query, regex=False)
    ]

if source_filter == "🕸️ Scraper":
    filtered_df = filtered_df[filtered_df["Clean_Source"] == "Scraper"]
elif source_filter == "🔗 LinkedIn":
    filtered_df = filtered_df[filtered_df["Clean_Source"] == "LinkedIn"]
elif source_filter == "📝 Manual":
    filtered_df = filtered_df[filtered_df["Clean_Source"] == "Manual"]

if filter_selection == "Strong Fit (75+)":
    filtered_df = filtered_df[filtered_df["Assessment"] == "✅ Strong Fit"]
elif filter_selection == "Good Fit (60-74)":
    filtered_df = filtered_df[filtered_df["Assessment"] == "🟢 Good Fit"]
elif filter_selection == "Moderate / Weak Fit (<60)":
    filtered_df = filtered_df[filtered_df["Assessment"].isin(["⚖️ Moderate Fit", "⚠️ Weak Fit", "🚫 Poor Fit"])]
elif filter_selection == "Disqualified":
    filtered_df = filtered_df[filtered_df["Assessment"] == "❌ Disqualified"]

if date_filter_selection == "Today":
    filtered_df = filtered_df[filtered_df["Job_Date"] == today]
elif date_filter_selection == "Yesterday":
    filtered_df = filtered_df[filtered_df["Job_Date"] == (today - timedelta(days=1))]
elif date_filter_selection == "Past 7 Days":
    filtered_df = filtered_df[filtered_df["Job_Date"].apply(lambda d: d is not None and 0 <= (today - d).days <= 7)]
elif date_filter_selection == "Past 30 Days":
    filtered_df = filtered_df[filtered_df["Job_Date"].apply(lambda d: d is not None and 0 <= (today - d).days <= 30)]


# Determine Active / Selected Job within the current view
target_url = st.session_state.get("active_job_url")
active_job = None
if target_url:
    candidate_job = next((j for j in all_saved_jobs if j.get("URL") == target_url), None)
    if candidate_job is not None:
        cand_archived = "archive" in str(candidate_job.get("Application Status") or "").strip().lower()
        if (history_view_mode == "archived") == cand_archived:
            active_job = candidate_job

# If no active job yet or target_url belongs to the other view, default to the top filtered job
if active_job is None and not filtered_df.empty:
    first_idx = int(filtered_df.iloc[0]["Original_Index"])
    active_job = all_saved_jobs[first_idx]
    st.session_state["active_job_url"] = active_job.get("URL")


# --- UI Helper Functions ---
def application_status_tracker(item: dict):
    url = item.get("URL")
    statuses = [
        "Not Applied",
        "Applied",
        "Interviewing",
        "Waitlisted",
        "Offer",
        "Rejected (Application)",
        "Rejected (Interview)",
        "Ghosted / Stale",
        "Archived",
    ]
    current = item.get("Application Status", "Not Applied")
    if current and current not in statuses:
        statuses.append(current)
    
    def on_status_change():
        new_status = st.session_state[f"status_tracker_{url}"]
        st.session_state["active_job_url"] = url
        db.update_job_field(url, "Application Status", new_status)
        
    st.selectbox(
        "Application Status",
        options=statuses,
        index=statuses.index(current) if current in statuses else 0,
        key=f"status_tracker_{url}",
        on_change=on_status_change,
        label_visibility="collapsed"
    )


def _render_document_generation_panel(
    item: dict,
    doc_type: str,
    generator_func,
    url: str,
    job_text: str,
    cache_key: str,
    audit_cache_key: str,
    audit_warn_key: str,
    vault: dict,
    vault_names: list[str],
    default_doc_resumes: list[str],
):
    """Renders generation options and triggers AI creation + automatic fact-check audit."""
    interview_stage = "Full Loop (All Stages)"
    followup_type = "Post-Application Follow-Up (10-14+ Days Quiet)"

    chosen_doc_resumes = default_doc_resumes
    if len(vault_names) > 1:
        with st.expander("📄 Resume Profile(s) to Pull Details From", expanded=False):
            chosen_doc_resumes = st.multiselect(
                "Select Resumes to Pull Achievements & Context From:",
                options=vault_names,
                default=default_doc_resumes,
                key=f"doc_res_sel_{cache_key}",
                help="Select 1 or more saved resumes. If you select multiple, Skippy pulls the best-matching roles, projects, skills, and bullet points across them into a single cohesive document.",
            ) or default_doc_resumes
    active_resume_for_gen = combine_selected_resumes(chosen_doc_resumes, vault) if chosen_doc_resumes else st.session_state.get("resume_text", "")

    if doc_type == "Interview Prep":
        interview_stage = st.selectbox(
            "🎯 Target Interview Stage:",
            [
                "Full Loop (All Stages)",
                "Phone / Recruiter Screen (30 min — Motivation, Pitch & High-Level Fit)",
                "Technical / Subject Matter Expert (45-60 min — Deep Domain, Systems & Case Defense)",
                "Behavioral / Final Round (Leadership, Conflict Resolution & Executive Alignment)",
            ],
            key=f"stage_sel_{cache_key}",
            help="Customizes STAR stories, ways to address missing skills, and smart questions to ask for your specific interview round."
        )
    elif doc_type == "Followup Note":
        followup_type = st.selectbox(
            "📬 Follow-Up / Thank-You Scenario:",
            [
                "Post-Application Follow-Up (10-14+ Days Quiet)",
                "Post-Interview Thank-You Note (Within 24 Hours)",
                "Status Update / Value-Add Check-In",
            ],
            key=f"followup_sel_{cache_key}",
            help="Generates concise 60–120 word Email + LinkedIn/Portal messages with zero banned AI clichés."
        )

    if st.button(f"⚡ Generate {doc_type}", key=f"btn_{cache_key}", type="primary"):
        with st.spinner(f"Generating {doc_type}..."):
            try:
                common_args = (
                    active_resume_for_gen,
                    job_text,
                    st.session_state.get("model_choice"),
                    st.session_state.get("user_api_key"),
                    st.session_state.get("local_base_url"),
                    st.session_state.get("local_model_name"),
                )
                extra_kwargs = {
                    "model_override": st.session_state.get("model_override", ""),
                    "skip_guard": True,
                }
                if doc_type == "Interview Prep":
                    extra_kwargs.update(
                        missing_skills=str(item.get("Missing Skills") or ""),
                        tailored_resume=str(item.get("Tailored Resume") or ""),
                        cover_letter=str(item.get("Cover Letter") or ""),
                        interview_stage=interview_stage,
                    )
                elif doc_type == "Followup Note":
                    extra_kwargs["scenario"] = followup_type

                content = generator_func(*common_args, **extra_kwargs)

                audit_md = ""
                if doc_type in ("Tailored Resume", "Cover Letter"):
                    try:
                        audit_res = review_and_refine_document(
                            draft_text=content,
                            master_resume=active_resume_for_gen,
                            job_description=job_text,
                            doc_type=doc_type,
                            model_choice=st.session_state.get("model_choice"),
                            api_key=st.session_state.get("user_api_key"),
                            local_base_url=st.session_state.get("local_base_url", ""),
                            local_model_name=st.session_state.get("local_model_name", ""),
                            model_override=st.session_state.get("model_override", ""),
                            skip_guard=True,
                        )
                        if audit_res.revised_document and len(audit_res.revised_document.strip()) > 50:
                            content = audit_res.revised_document
                        audit_md = format_audit_report_markdown(audit_res, doc_label=doc_type)
                        st.session_state.pop(audit_warn_key, None)
                    except Exception as a_err:
                        audit_md = ""
                        st.session_state[audit_warn_key] = (
                            f"Automatic fact-check could not run ({a_err}). "
                            "Review your draft carefully or click **Generate Fact-Check Report** below to retry."
                        )

                st.session_state[cache_key] = content
                item[doc_type] = content
                db.update_job_field(url, doc_type, content)

                if audit_md:
                    merged_audit = db.set_doc_audit(item.get("Reviewer Audit", ""), doc_type, audit_md)
                    st.session_state[audit_cache_key] = audit_md
                    item["Reviewer Audit"] = merged_audit
                    db.update_job_field(url, "Reviewer Audit", merged_audit)

                st.session_state["active_job_url"] = url
                safe_fragment_rerun()
            except Exception as e:
                st.error(f"Error generating {doc_type}: {e}")


def _render_document_audit_section(
    item: dict,
    doc_type: str,
    url: str,
    job_text: str,
    edited_doc: str,
    cache_key: str,
    audit_cache_key: str,
    audit_warn_key: str,
    vault: dict,
    default_doc_resumes: list[str],
):
    """Displays or runs the Accuracy & Fact-Check Grounding Report for resumes and cover letters."""
    audit_warn = st.session_state.get(audit_warn_key)
    if audit_warn:
        st.warning(f"⚠️ {audit_warn}")
    audit_report = st.session_state.get(audit_cache_key) or db.get_doc_audit(item.get("Reviewer Audit", ""), doc_type)
    if audit_report and str(audit_report).strip():
        with st.expander("🛡️ Accuracy & Fact-Check Grounding Report", expanded=True):
            st.markdown(audit_report)
    else:
        with st.expander("🛡️ Accuracy & Fact-Check Grounding Report", expanded=bool(audit_warn)):
            st.caption("No fact-check grounding report is on file for this draft yet.")
            if st.button("🔍 Generate Fact-Check Report", key=f"btn_audit_{cache_key}"):
                with st.spinner(f"Auditing {doc_type} against selected resume profile(s)..."):
                    try:
                        audit_resume_pool = combine_selected_resumes(default_doc_resumes, vault) if default_doc_resumes else st.session_state.get("resume_text", "")
                        audit_res = review_and_refine_document(
                            draft_text=edited_doc,
                            master_resume=audit_resume_pool,
                            job_description=job_text,
                            doc_type=doc_type,
                            model_choice=st.session_state.get("model_choice"),
                            api_key=st.session_state.get("user_api_key"),
                            local_base_url=st.session_state.get("local_base_url", ""),
                            local_model_name=st.session_state.get("local_model_name", ""),
                            model_override=st.session_state.get("model_override", ""),
                            skip_guard=True,
                        )
                        audit_md = format_audit_report_markdown(audit_res, doc_label=doc_type)
                        merged_audit = db.set_doc_audit(item.get("Reviewer Audit", ""), doc_type, audit_md)
                        st.session_state[audit_cache_key] = audit_md
                        st.session_state.pop(audit_warn_key, None)
                        item["Reviewer Audit"] = merged_audit
                        db.update_job_field(url, "Reviewer Audit", merged_audit)
                        safe_fragment_rerun()
                    except Exception as a_err:
                        st.error(f"Audit failed: {a_err}")


def _render_document_editor_and_exports(
    item: dict,
    doc_type: str,
    url: str,
    current_content: str,
    cache_key: str,
    audit_cache_key: str,
    audit_warn_key: str,
) -> str:
    """Renders the live preview/editor, persistence actions, download buttons, and Regenerate button."""
    ats_style_key = "clean"
    if doc_type == "Tailored Resume":
        style_options = {
            "clean": "Standard ATS (Clean Arial, Bold Roles)",
            "harvard": "Harvard Style (Times New Roman, Divider Rules)",
            "modern": "Modern Slate (Calibri, Compact Margins)",
        }
        c_style, _ = st.columns([3.8, 3.2])
        with c_style:
            chosen_label = st.selectbox(
                "🎨 Template Style:",
                options=list(style_options.values()),
                index=0,
                key=f"ats_style_sel_{cache_key}",
                help="Applies clean, human-designed margins, professional typography, and ATS-friendly headers to your Word and PDF exports.",
            )
            ats_style_key = next((k for k, v in style_options.items() if v == chosen_label), "clean")

    editor_key = f"edit_{cache_key}"
    if editor_key not in st.session_state:
        st.session_state[editor_key] = current_content

    safe_doc_type = re.sub(r'[^a-zA-Z0-9_-]', '_', doc_type)
    pos = item.get("Position", "Job")
    company = item.get("Company", "")
    safe_company = re.sub(r'[^a-zA-Z0-9_-]', '_', company) if company and company != "Unknown Company" else ""
    safe_pos = re.sub(r'[^a-zA-Z0-9_-]', '_', pos)
    safe_title = f"{safe_company}_{safe_pos}".strip('_') if safe_company else safe_pos

    view_mode = "✏️ Edit Markdown"
    if doc_type == "Tailored Resume":
        col_toggle, _ = st.columns([4.2, 2.8])
        with col_toggle:
            view_mode = st.radio(
                "Display Format:",
                ["🔀 Live Split View", "📄 Formatted ATS Preview", "✏️ Edit Markdown"],
                index=0,
                horizontal=True,
                key=f"view_mode_{cache_key}",
                label_visibility="collapsed",
            )

    def _save_edited(text_val: str, notify: bool = False):
        st.session_state[cache_key] = text_val
        item[doc_type] = text_val
        db.update_job_field(url, doc_type, text_val)
        if notify:
            st.session_state.pop(f"pdf_bytes_{cache_key}", None)
            st.toast("✅ Changes applied and saved to database!", icon="💾")
            safe_fragment_rerun()

    def _render_ats_preview_box(padding: str, max_height: str):
        preview_html = render_ats_resume_html(st.session_state[editor_key], template_style=ats_style_key)
        st.markdown(
            f"""
            <div style="
                border: 1px solid rgba(128,128,128,0.25);
                border-radius: 6px;
                padding: {padding};
                max-height: {max_height};
                overflow-y: auto;
                background: #ffffff;
                color: #111827;
                box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
                margin-bottom: 12px;
            ">
                {preview_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

    if doc_type == "Tailored Resume" and view_mode == "🔀 Live Split View":
        sp1, sp2 = st.columns([1, 1], gap="medium")
        with sp1:
            st.caption("✏️ **Markdown Source (Editable)**")
            edited_doc = st.text_area(
                "Edit Resume Markdown:",
                height=580,
                key=editor_key,
                label_visibility="collapsed",
            )
            col_btn, _ = st.columns([3.2, 2.8])
            with col_btn:
                if st.button("💾 Apply Changes", key=f"apply_{cache_key}", type="secondary", width="stretch"):
                    _save_edited(edited_doc, notify=True)
            if edited_doc != current_content:
                _save_edited(edited_doc, notify=False)
        with sp2:
            st.caption("📄 **Live ATS Template Preview**")
            _render_ats_preview_box("24px 28px", "580px")
    elif doc_type == "Tailored Resume" and view_mode == "📄 Formatted ATS Preview":
        _render_ats_preview_box("32px 40px", "600px")
        edited_doc = st.session_state[editor_key]
    else:
        edited_doc = st.text_area(
            f"{doc_type} (Editable):",
            height=420,
            key=editor_key,
        )
        col_btn, _ = st.columns([2.5, 5.5])
        with col_btn:
            if st.button("💾 Apply Changes", key=f"apply_{cache_key}", type="secondary", width="stretch"):
                _save_edited(edited_doc, notify=True)
        if edited_doc != current_content:
            _save_edited(edited_doc, notify=False)

    def _handle_regenerate():
        st.session_state[cache_key] = ""
        st.session_state.pop(editor_key, None)
        st.session_state.pop(f"pdf_bytes_{cache_key}", None)
        st.session_state.pop(audit_cache_key, None)
        st.session_state.pop(audit_warn_key, None)
        st.session_state["active_job_url"] = url
        db.update_job_field(url, doc_type, "")
        if doc_type in ("Tailored Resume", "Cover Letter"):
            updated_audit = db.set_doc_audit(item.get("Reviewer Audit", ""), doc_type, "")
            item["Reviewer Audit"] = updated_audit
            db.update_job_field(url, "Reviewer Audit", updated_audit)
        safe_fragment_rerun()

    if doc_type == "Tailored Resume":
        has_pdf = is_pdf_conversion_available()
        if has_pdf:
            col1, col_pdf, col_reg = st.columns([2.5, 2.5, 1.5])
        else:
            col1, col_reg = st.columns([3.5, 1.5])
            col_pdf = None
        render_ats_resume_downloads(
            markdown_text=edited_doc,
            ats_style_key=ats_style_key,
            file_stem=f"ATS_Resume_{safe_title}",
            docx_key=f"dl_{cache_key}",
            pdf_state_key=f"pdf_bytes_{cache_key}",
            prep_pdf_key=f"prep_pdf_{cache_key}",
            pdf_dl_key=f"dl_pdf_{cache_key}",
            docx_label="📥 Download ATS (.docx)",
            col_docx=col1,
            col_pdf=col_pdf,
        )
        with col_reg:
            if st.button("🔄 Regenerate", width="stretch", key=f"regen_{cache_key}"):
                _handle_regenerate()
    else:
        col1, col_reg = st.columns([3.5, 1.5])
        with col1:
            st.download_button(
                "📥 Download (.docx)",
                data=lambda: generate_docx_from_markdown(edited_doc),
                file_name=f"{safe_doc_type}_{safe_title}.docx",
                type="primary",
                width="stretch",
                key=f"dl_{cache_key}"
            )
        with col_reg:
            if st.button("🔄 Regenerate", width="stretch", key=f"regen_{cache_key}"):
                _handle_regenerate()

    return edited_doc


@st.fragment
def document_generator(item: dict, doc_type: str, generator_func):
    url, job_text = item.get("URL"), item.get("Job Text", "")
    cache_key = f"{doc_type}_{url}"
    audit_cache_key = f"Reviewer_Audit_{doc_type}_{url}"
    audit_warn_key = f"Reviewer_Audit_Warn_{doc_type}_{url}"

    db_content = item.get(doc_type)
    if pd.isna(db_content) or not db_content or str(db_content).lower() == "nan":
        db_content = ""
    if cache_key not in st.session_state:
        st.session_state[cache_key] = db_content

    db_audit_raw = item.get("Reviewer Audit", "")
    if pd.isna(db_audit_raw) or not db_audit_raw or str(db_audit_raw).lower() == "nan":
        db_audit_raw = ""
    db_audit = db.get_doc_audit(db_audit_raw, doc_type)
    if audit_cache_key not in st.session_state:
        st.session_state[audit_cache_key] = db_audit

    current_content = st.session_state[cache_key]
    vault = st.session_state.get("resumes_vault") or load_resumes()
    vault_names = list(vault.keys())
    raw_matched = [r.strip() for r in str(item.get("Matched Resumes") or "").split(",") if r.strip() in vault]
    default_doc_resumes = raw_matched or [
        r for r in st.session_state.get("selected_resumes", []) if r in vault
    ] or (vault_names[:1] if vault_names else [])

    if not current_content:
        _render_document_generation_panel(
            item, doc_type, generator_func, url, job_text,
            cache_key, audit_cache_key, audit_warn_key,
            vault, vault_names, default_doc_resumes,
        )
        return

    edited_doc = _render_document_editor_and_exports(
        item, doc_type, url, current_content,
        cache_key, audit_cache_key, audit_warn_key,
    )
    if doc_type in ("Tailored Resume", "Cover Letter"):
        _render_document_audit_section(
            item, doc_type, url, job_text, edited_doc,
            cache_key, audit_cache_key, audit_warn_key,
            vault, default_doc_resumes,
        )


def _format_gate_pill(gate_val: str) -> str:
    g = str(gate_val or "PASS").strip().upper()
    if g == "FAIL":
        return "❌ FAIL"
    if g == "FLAG":
        return "⚠️ FLAG"
    return "✅ PASS"


def render_active_job_dossier(item: dict):
    """Renders the complete evaluation dossier and tailoring tabs for the selected job."""
    score = int(item.get("Score", 0) or 0)
    eligible = bool(item.get("Eligible", True))
    fit_band = get_fit_band(score, eligible)
    company = str(item.get("Company") or "").strip()
    if company == "Unknown Company":
        company = ""
    company_suffix = f" at {company}" if company else ""
    deadline_badge = format_deadline_badge(item.get("Deadline", ""))
    deadline_header = f" · 🗓️ {deadline_badge}" if deadline_badge != "—" else ""
    raw_url = str(item.get("URL") or "")
    card_hash = hashlib.sha256((raw_url or item.get("Position", "")).encode("utf-8", errors="ignore")).hexdigest()[:12]

    # Full details lazy-load
    item = {**item, **db.load_job_detail(raw_url)}

    st.markdown(f"### {fit_band} ({score}/100) — {item.get('Position', 'Role')}{company_suffix}")
    
    # Top Action Row
    c_apply, c_status, _, c_del = st.columns([1.6, 2.2, 4.2, 1.2], vertical_alignment="center")
    with c_apply:
        if raw_url.startswith(("http://", "https://")):
            st.link_button("🚀 View/Apply to Job", raw_url, type="primary", width="stretch")
    with c_status:
        application_status_tracker(item)
    with c_del:
        pos_title = item.get("Position") or "Role"
        if db.job_has_saved_work(item):
            with st.popover("🗑️ Delete", width="stretch"):
                st.warning("This posting has saved documents or an active status.")
                if st.button("Confirm", type="primary", key=f"confirm_del_active_{card_hash}", width="stretch"):
                    db.delete_job_by_url(raw_url, keep_seen=True)
                    _clear_deleted_job_state([raw_url])
                    st.toast(f"🗑️ Removed '{pos_title}'")
                    st.rerun()
        else:
            if st.button("🗑️ Delete", key=f"del_active_{card_hash}", width="stretch", help="Delete posting from History"):
                db.delete_job_by_url(raw_url, keep_seen=True)
                _clear_deleted_job_state([raw_url])
                st.toast(f"🗑️ Removed '{pos_title}'")
                st.rerun()

    # Workspace Tabs
    tabs = st.tabs([
        "Overview & Fit",
        "⚡ Tailored Resume",
        "✉️ Cover Letter",
        "📋 Application Answers",
        "🎤 Interview Prep",
        "📬 Follow-Up Notes",
        "🎯 Outreach Messages",
        "🏢 Company Research Guide",
    ], key=f"dossier_tabs_{card_hash}")

    with tabs[0]:
        risk = db.check_repost_risk(item.get("Company", ""), item.get("Position", ""), item.get("URL", ""))
        if risk:
            if risk.get("is_ghost_risk"):
                st.warning(
                    f"👻 **Repeated Listing Warning:** {risk['badge_text']}. "
                    f"Spotted on `{risk['first_seen']}` across {risk['count']} distinct postings over {risk['days_span']} days."
                )
            else:
                st.info(f"🔄 **Listing Activity:** {risk['badge_text']} (First seen: `{risk['first_seen']}`).")

        applied_date = item.get("Applied Date", "")
        status_up = item.get("Status Updated", "")
        if applied_date:
            st.caption(f"📅 **Application Timeline:** Submitted on `{applied_date}`" + (f" · Status updated on `{status_up}`" if status_up else ""))

        if not eligible:
            st.error(f"❌ **DISQUALIFIED:** {item.get('Disqualification Reason', '')}")
        elif score >= 75:
            st.success(f"✅ **STRONG FIT:** {score} / 100")
        elif score >= 60:
            st.info(f"🟢 **GOOD FIT:** {score} / 100")
        elif score >= 45:
            st.warning(f"⚖️ **MODERATE FIT:** {score} / 100")
        else:
            st.warning(f"⚠️ **WEAK / POOR FIT:** {score} / 100")

        # Metadata Row
        elig_gate = _format_gate_pill(item.get("Eligibility Gate", "PASS" if eligible else "FAIL"))
        loc_gate = _format_gate_pill(item.get("Location Gate", "PASS"))
        meta_parts = [
            f"**Requirements:** `{elig_gate}`",
            f"**Location:** `{loc_gate}`",
        ]
        if company:
            meta_parts.insert(0, f"**Company:** {company}")
        if deadline_badge != "—":
            meta_parts.append(f"**Deadline:** `{deadline_badge}`")
        matched_res_str = str(item.get("Matched Resumes") or "").strip()
        if matched_res_str and matched_res_str.lower() != "nan":
            meta_parts.append(f"**Resume(s):** `{matched_res_str}`")
        st.markdown(" &nbsp;|&nbsp; ".join(meta_parts))

        # 4-Pillar Score Breakdown
        tech_s = int(item.get("Technical Score", 0) or 0)
        exp_s = int(item.get("Experience Score", 0) or 0)
        beh_s = int(item.get("Behavioral Score", 0) or 0)
        car_s = int(item.get("Career Score", 0) or 0)
        if any(v > 0 for v in (tech_s, exp_s, beh_s, car_s)):
            with st.container(border=True):
                st.caption("📊 **Match Score Breakdown** *(30% Skills · 25% Experience · 15% Work Style · 30% Career Goals)*")
                sc1, sc2, sc3, sc4 = st.columns(4)
                with sc1:
                    st.metric("🛠️ Skills & Tools (30%)", f"{tech_s}/100")
                    st.progress(min(max(tech_s / 100.0, 0.0), 1.0))
                with sc2:
                    st.metric("📈 Experience Match (25%)", f"{exp_s}/100")
                    st.progress(min(max(exp_s / 100.0, 0.0), 1.0))
                with sc3:
                    st.metric("🤝 Work Style & Team (15%)", f"{beh_s}/100")
                    st.progress(min(max(beh_s / 100.0, 0.0), 1.0))
                with sc4:
                    st.metric("🎯 Career Goals (30%)", f"{car_s}/100")
                    st.progress(min(max(car_s / 100.0, 0.0), 1.0))

        st.write(f"**Summary:** {item.get('Summary', '')}")

        if item.get("Red Flags"):
            st.warning("🚨 **Red Flags & Dealbreakers:**")
            for f in str(item["Red Flags"]).split(" | "):
                if f.strip():
                    st.markdown(f"- ⚠️ {f.strip()}")

        if eligible:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Matching Skills:**")
                for skill in str(item.get("Matching Skills", "")).split(", "):
                    if skill.strip():
                        st.markdown(f"- ✅ {skill.strip()}")
            with col2:
                st.markdown("**Missing Skills / Gaps:**")
                for gap in str(item.get("Missing Skills", "")).split(", "):
                    if gap.strip():
                        st.markdown(f"- ⚠️ {gap.strip()}")

    with tabs[1]:
        document_generator(item, "Tailored Resume", tailor_resume)
    with tabs[2]:
        document_generator(item, "Cover Letter", tailor_cover_letter)
    with tabs[3]:
        st.caption("⚡ Quick, character-counted answers for online applications and screening questions.")
        document_generator(item, "Application QA", generate_application_qa)
    with tabs[4]:
        st.caption("🎯 Realistic interview practice questions, STAR story frameworks, and smart questions to ask.")
        document_generator(item, "Interview Prep", generate_interview_prep)
    with tabs[5]:
        st.caption("📬 Concise 60–120 word follow-up and thank-you notes for email and LinkedIn.")
        document_generator(item, "Followup Note", generate_followup_note)
    with tabs[6]:
        st.caption("💬 Under-300-character LinkedIn notes for hiring managers, recruiters, and peers.")
        document_generator(item, "Outreach Message", generate_outreach_messages)
    with tabs[7]:
        st.caption("🏢 Strategic company briefing: business model, tech stack, news, and talking points.")
        document_generator(item, "Company Intel", generate_deep_company_brief)


# --- MAIN EVALUATIONS TABLE & DETAIL WORKSPACE ---
if filtered_df.empty:
    if history_view_mode == "archived" and archived_total_count == 0:
        st.info("No archived postings yet. Change any posting's status to **Archived** to move it into this view.")
    else:
        st.info("No postings match your search filters. Try clearing or relaxing the search criteria above.")
else:
    # Precomputed styling lookup to avoid runtime list/string allocation in hot loops
    current_active_url = st.session_state.get("active_job_url")
    _status_colors = {
        "Applied": "rgba(30,136,229,0.18)",
        "Interviewing": "rgba(142,68,173,0.18)",
        "Waitlisted": "rgba(245,124,0,0.18)",
        "Rejected": "rgba(229,57,53,0.18)",
        "Rejected (Application)": "rgba(229,57,53,0.18)",
        "Rejected (Interview)": "rgba(183,28,28,0.22)",
        "Ghosted / Stale": "rgba(158,158,158,0.18)",
        "Archived": "rgba(117,117,117,0.18)",
        "Offer": "rgba(67,160,71,0.22)",
    }
    _active_row_style = "background-color: rgba(147, 51, 234, 0.45); font-weight: 600; color: #ffffff;"

    def highlight_status(row):
        if current_active_url and row.get("URL") == current_active_url:
            return [_active_row_style] * len(row)
        bg = _status_colors.get(row.get("Application Status", "Not Applied"), "")
        return [f"background-color: {bg}"] * len(row)

    col_tbl_hdr, col_tbl_meta = st.columns([6.2, 3.8], vertical_alignment="bottom")
    with col_tbl_hdr:
        st.markdown(f"#### 📊 Evaluated Postings & Match Breakdown ({len(filtered_df)})")
        st.caption("Click any row in the table below to inspect its detailed evaluation and tailored application workspace:")
    with col_tbl_meta:
        show_all_cols = st.checkbox(
            "Show 4-Pillar Breakdown in Table",
            value=False,
            key="chk_eval_table_all_cols",
            help="Show granular Skills, Experience, Style, Goals scores and raw skill lists directly in the table."
        )
        if len(filtered_df) != len(all_saved_jobs):
            st.caption(f"Showing **{len(filtered_df)}** of {len(all_saved_jobs)} total saved jobs")
        else:
            st.caption(f"Showing all **{len(all_saved_jobs)}** saved jobs")

    # Table columns definition
    if show_all_cols:
        eval_table_cols = [
            "Position",
            "Company_Display",
            "Assessment",
            "Score",
            "Technical Score",
            "Experience Score",
            "Behavioral Score",
            "Career Score",
            "Matching Skills",
            "Missing Skills",
            "Red Flags",
            "Signals",
            "Deadline_Display",
            "Application Status",
            "Clean_Source",
            "URL",
        ]
    else:
        eval_table_cols = [
            "Position",
            "Company_Display",
            "Assessment",
            "Score",
            "Signals",
            "Application Status",
            "Deadline_Display",
            "Clean_Source",
            "URL",
        ]
    valid_cols = [c for c in eval_table_cols if c in filtered_df.columns]
    styled_df = filtered_df[valid_cols].rename(
        columns={
            "Company_Display": "Company",
            "Deadline_Display": "Deadline",
            "Clean_Source": "Source",
        }
    ).style.apply(highlight_status, axis=1)

    column_configurations = {
        "Score": st.column_config.ProgressColumn(
            "Overall Fit",
            help="Weighted 4-pillar match score (0-100)",
            min_value=0,
            max_value=100,
            format="%d",
        ),
        "Technical Score": st.column_config.NumberColumn(
            "Skills (30%)",
            help="Technical skills & tool compatibility",
            format="%d",
        ),
        "Experience Score": st.column_config.NumberColumn(
            "Exp (25%)",
            help="Seniority and domain depth match",
            format="%d",
        ),
        "Behavioral Score": st.column_config.NumberColumn(
            "Style (15%)",
            help="Work style & culture fit",
            format="%d",
        ),
        "Career Score": st.column_config.NumberColumn(
            "Goals (30%)",
            help="Long-term trajectory & role alignment",
            format="%d",
        ),
        "URL": st.column_config.LinkColumn(
            "Listing URL",
            display_text="View Listing ➔",
        ),
        "Matching Skills": st.column_config.TextColumn(
            "Matching Skills",
            width="medium",
        ),
        "Missing Skills": st.column_config.TextColumn(
            "Gaps / Missing",
            width="medium",
        ),
        "Red Flags": st.column_config.TextColumn(
            "Red Flags",
            width="medium",
        ),
    }

    selection_event = st.dataframe(
        styled_df,
        width="stretch",
        on_select="rerun",
        selection_mode=["single-row", "single-cell"],
        column_config=column_configurations,
        key="history_evaluations_main_table",
    )

    # Synchronize table selection with active job (supports both row selection and clicking any cell in a row)
    selected_row_idx = None
    if selection_event.selection.rows:
        selected_row_idx = selection_event.selection.rows[0]
    elif getattr(selection_event.selection, "cells", None) and selection_event.selection.cells:
        # Cell selection tuple: (row_int_index, column_name)
        cell_item = selection_event.selection.cells[0]
        if isinstance(cell_item, (tuple, list)) and len(cell_item) > 0:
            selected_row_idx = cell_item[0]
        elif isinstance(cell_item, dict) and "row" in cell_item:
            selected_row_idx = cell_item["row"]

    # Extract selection signature to detect fresh user click interactions
    current_sel_sig = (
        tuple(selection_event.selection.rows),
        tuple(
            (c[0], c[1]) if isinstance(c, (tuple, list))
            else (c.get("row"), c.get("column")) if isinstance(c, dict)
            else str(c)
            for c in getattr(selection_event.selection, "cells", [])
        ),
    )
    last_handled_sig = st.session_state.get("_last_handled_table_sig")

    if selected_row_idx is not None and 0 <= selected_row_idx < len(filtered_df):
        selected_row = filtered_df.iloc[selected_row_idx]
        selected_url = selected_row["URL"]
        # If user clicked a row or cell, register interaction and trigger auto-scroll
        if current_sel_sig != last_handled_sig:
            st.session_state["_last_handled_table_sig"] = current_sel_sig
            st.session_state["active_job_url"] = selected_url
            orig_idx = int(selected_row["Original_Index"])
            active_job = all_saved_jobs[orig_idx]
            st.session_state["_hist_jump_nonce"] = st.session_state.get("_hist_jump_nonce", 0) + 1
            st.session_state["scroll_trigger_nonce"] = st.session_state.get("scroll_trigger_nonce", 0) + 1
            st.rerun()
    elif not selection_event.selection.rows and not getattr(selection_event.selection, "cells", None):
        st.session_state["_last_handled_table_sig"] = None

    # Handle external redirection jumps (e.g. from Saved Documents Gallery)
    if st.session_state.get("jump_to_card"):
        st.session_state["scroll_trigger_nonce"] = st.session_state.get("scroll_trigger_nonce", 0) + 1
        st.session_state.pop("jump_to_card", None)

    # If active_job is set, update its dictionary data
    current_active_url = st.session_state.get("active_job_url")
    if current_active_url:
        matching_rows = filtered_df[filtered_df["URL"] == current_active_url]
        if not matching_rows.empty:
            orig_idx = int(matching_rows.iloc[0]["Original_Index"])
            active_job = all_saved_jobs[orig_idx]

    st.markdown("---")

    # Render Active Job Dossier & Workspace
    if active_job:
        st.html("<div id='active_job_workspace' style='scroll-margin-top: 75px;'></div>")
        with st.container(border=True):
            render_active_job_dossier(active_job)

        # Smooth auto-scroll when a row is clicked (reliably triggers on every single interaction)
        current_scroll_nonce = st.session_state.get("scroll_trigger_nonce", 0)
        last_scrolled_nonce = st.session_state.get("_last_executed_scroll_nonce", -1)

        if current_scroll_nonce > 0 and current_scroll_nonce != last_scrolled_nonce:
            st.session_state["_last_executed_scroll_nonce"] = current_scroll_nonce

            st.iframe(
                f"""<!DOCTYPE html>
                <html>
                <head>
                <style>html, body {{ margin: 0; padding: 0; border: none; overflow: hidden; background: transparent; }}</style>
                </head>
                <body>
                <script>
                (function() {{
                    let attempts = 0;
                    const maxAttempts = 60;
                    const interval = setInterval(function() {{
                        attempts++;
                        try {{
                            const doc = window.parent ? window.parent.document : document;
                            const target = doc.getElementById('active_job_workspace');
                            if (target) {{
                                clearInterval(interval);
                                target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                            }} else if (attempts >= maxAttempts) {{
                                clearInterval(interval);
                            }}
                        }} catch (e) {{
                            if (attempts >= maxAttempts) clearInterval(interval);
                        }}
                    }}, 30);
                }})();
                </script>
                <!-- nonce: {current_scroll_nonce} -->
                </body>
                </html>""",
                height=1,
            )
    else:
        st.info("Select a row in the table above to view its detailed evaluation dossier and generate tailored materials.")

# Clean up jump flags
st.session_state.pop("jump_to_card", None)
