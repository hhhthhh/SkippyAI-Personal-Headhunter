import streamlit as st
import pandas as pd
import os
import re
import time
import sys
import hashlib
from datetime import date, datetime, timedelta
from collections import defaultdict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils import setup_sidebar, enforce_onboarding, load_resumes, combine_selected_resumes
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
    generate_ats_resume_docx,
    generate_ats_resume_pdf,
    is_pdf_conversion_available,
    render_ats_resume_html,
    review_and_refine_document,
    format_audit_report_markdown,
    get_fit_band,
)

st.title("🗂️ Job History")

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
    col_msg, col_dism = st.columns([5.5, 1])
    with col_msg:
        st.info(f"✨ **Latest Run Results:** Viewing {count} newly evaluated posting{'s' if count != 1 else ''} from **{src}**. Review summary in the Overview Table and detailed cards below.", icon="🎯")
    with col_dism:
        if st.button("Dismiss", key="dismiss_latest_batch_info"):
            del st.session_state["latest_batch_info"]
            st.rerun()

# Data Management tools tucked neatly at the top
col_act1, col_act2, _ = st.columns([1.5, 1.8, 6.7])
with col_act1:
    if st.button("🔄 Refresh Data", type="secondary", width="stretch"):
        st.rerun()
with col_act2:
    with st.popover("🗑️ Clear History", width="stretch"):
        st.warning("⚠️ **Warning:** This will permanently delete all evaluated postings, generated documents, and audit reports.")
        if st.button("Confirm Delete All History", type="primary", key="btn_confirm_clear_all_history", width="stretch"):
            db.clear_all_history()
            st.session_state.pop("active_job_url", None)
            st.rerun()

all_saved_jobs = db.load_all_jobs()
if "resumes_vault" not in st.session_state:
    st.session_state["resumes_vault"] = load_resumes()
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
                st.switch_page("pages/1_scraper.py")
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
    if not timestamp_str or not isinstance(timestamp_str, str):
        return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", timestamp_str.strip())
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def format_day_group_label(job_date: date | None, today: date) -> str:
    """Formats an expandable group header label with relative and absolute calendar information."""
    if job_date is None:
        return "📅 Earlier / Undated Evaluations"
    date_short = f"{job_date.month}/{job_date.day}/{str(job_date.year)[-2:]}"
    date_long = job_date.strftime("%A, %b ") + str(job_date.day) + job_date.strftime(", %Y")
    delta = (today - job_date).days
    if delta == 0:
        return f"📅 Today ({date_short}) — {date_long}"
    elif delta == 1:
        return f"📅 Yesterday ({date_short}) — {date_long}"
    elif 1 < delta <= 7:
        return f"📅 {date_long} ({date_short} · {delta} days ago)"
    else:
        return f"📅 {date_long} ({date_short})"


# --- TOP-LEVEL DATAFRAME & FILTERS ---
today = date.today()
fcol1, fcol2, metric_col, _ = st.columns([2.5, 2.5, 2, 3])
with fcol1:
    filter_selection = st.selectbox(
        "Filter by Assessment:",
        ["All", "Strong Fit (75+)", "Good Fit (60-74)", "Moderate / Weak Fit (<60)", "Disqualified"]
    )
with fcol2:
    date_filter_selection = st.selectbox(
        "Filter by Evaluation Date:",
        ["All Dates", "Today", "Yesterday", "Past 7 Days", "Past 30 Days"]
    )

df = pd.DataFrame(all_saved_jobs)
# Store the original list index so we can tie dataframe clicks back to the right card
df["Original_Index"] = df.index
if "Company" not in df.columns:
    df["Company"] = ""
if "Deadline" not in df.columns:
    df["Deadline"] = ""
if "Timestamp" not in df.columns:
    df["Timestamp"] = ""

df["Job_Date"] = df["Timestamp"].apply(parse_job_date)
df["Company_Display"] = df["Company"].apply(lambda c: c if str(c).strip() and str(c).strip() != "Unknown Company" else "—")
df["Deadline_Display"] = df["Deadline"].apply(format_deadline_badge)


def get_assessment(row):
    return get_fit_band(row.get("Score", 0), bool(row.get("Eligible", True)))


df["Assessment"] = df.apply(get_assessment, axis=1)

if filter_selection == "Strong Fit (75+)":
    df = df[df["Assessment"] == "✅ Strong Fit"]
elif filter_selection == "Good Fit (60-74)":
    df = df[df["Assessment"] == "🟢 Good Fit"]
elif filter_selection == "Moderate / Weak Fit (<60)":
    df = df[df["Assessment"].isin(["⚖️ Moderate Fit", "⚠️ Weak Fit", "🚫 Poor Fit"])]
elif filter_selection == "Disqualified":
    df = df[df["Assessment"] == "❌ Disqualified"]

if date_filter_selection == "Today":
    df = df[df["Job_Date"] == today]
elif date_filter_selection == "Yesterday":
    df = df[df["Job_Date"] == (today - timedelta(days=1))]
elif date_filter_selection == "Past 7 Days":
    df = df[df["Job_Date"].apply(lambda d: d is not None and 0 <= (today - d).days <= 7)]
elif date_filter_selection == "Past 30 Days":
    df = df[df["Job_Date"].apply(lambda d: d is not None and 0 <= (today - d).days <= 30)]

with metric_col:
    if len(df) != len(all_saved_jobs):
        st.metric("Postings Shown", len(df), delta=f"{len(df) - len(all_saved_jobs)} filtered")
    else:
        st.metric("Total Postings Saved", len(all_saved_jobs))


def highlight_status(row):
    status = row.get("Application Status", "Not Applied")
    colors = {
        "Applied": "rgba(30,136,229,0.2)",
        "Interviewing": "rgba(142,68,173,0.2)",
        "Waitlisted": "rgba(245,124,0,0.2)",
        "Rejected": "rgba(229,57,53,0.2)",
        "Rejected (Application)": "rgba(229,57,53,0.2)",
        "Rejected (Interview)": "rgba(183,28,28,0.25)",
        "Ghosted / Stale": "rgba(158,158,158,0.2)",
        "Archived": "rgba(117,117,117,0.2)",
        "Offer": "rgba(67,160,71,0.25)",
    }
    return [f"background-color: {colors.get(status, '')}"] * len(row)


display_cols = ["Timestamp", "Position", "Company_Display", "Assessment", "Score", "Deadline_Display", "Application Status", "URL", "Red Flags"]
valid_cols = [c for c in display_cols if c in df.columns]
styled_df = df[valid_cols].rename(
    columns={"Company_Display": "Company", "Deadline_Display": "Deadline"}
).style.apply(highlight_status, axis=1)

selection_event = st.dataframe(
    styled_df,
    width="stretch",
    on_select="rerun",
    selection_mode="single-row",
    column_config={"URL": st.column_config.LinkColumn("Source URL")},
    key="history_overview_table"
)

# Identify which job the user clicked in the dataframe
active_job_id = int(df.iloc[selection_event.selection.rows[0]]["Original_Index"]) if (selection_event.selection.rows and selection_event.selection.rows[0] < len(df)) else None
if active_job_id is not None and 0 <= active_job_id < len(all_saved_jobs):
    st.session_state["active_job_url"] = all_saved_jobs[active_job_id].get("URL")

st.markdown("---")
st.subheader("🔍 Detailed Postings", anchor="details")


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
        "Status",
        options=statuses,
        index=statuses.index(current) if current in statuses else 0,
        key=f"status_tracker_{url}",
        on_change=on_status_change,
        label_visibility="collapsed"
    )


@st.fragment
def document_generator(item: dict, doc_type: str, generator_func):
    url, job_text = item.get("URL"), item.get("Job Text", "")
    cache_key = f"{doc_type}_{url}"
    audit_cache_key = f"Reviewer_Audit_{url}"
    supports_reviewer = doc_type in ("Tailored Resume", "Cover Letter")
    
    db_content = item.get(doc_type)
    if pd.isna(db_content) or not db_content or str(db_content).lower() == "nan":
        db_content = ""
        
    if cache_key not in st.session_state:
        st.session_state[cache_key] = db_content

    db_audit = item.get("Reviewer Audit", "")
    if pd.isna(db_audit) or not db_audit or str(db_audit).lower() == "nan":
        db_audit = ""
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
        use_reviewer = True
        interview_stage = "Full Loop (All Stages)"
        followup_type = "Post-Application Follow-Up (10-14+ Days Quiet)"

        chosen_doc_resumes = default_doc_resumes
        if len(vault_names) > 1:
            chosen_doc_resumes = st.multiselect(
                "📄 Resume Profile(s) to Pull Details From:",
                options=vault_names,
                default=default_doc_resumes,
                key=f"doc_res_sel_{cache_key}",
                help="Select 1 or more saved resumes. If you select multiple, Skippy pulls the best-matching roles, projects, skills, and bullet points across them into a single cohesive document.",
            ) or default_doc_resumes
        active_resume_for_gen = combine_selected_resumes(chosen_doc_resumes, vault) if chosen_doc_resumes else st.session_state.get("resume_text", "")

        if supports_reviewer:
            use_reviewer = st.checkbox(
                "🛡️ Run Accuracy & Fact Check (Prevents Made-Up Info & Checks Keywords)",
                value=True,
                key=f"chk_rev_{cache_key}",
                help="Runs a second review pass comparing the draft against your real resume and the job description to eliminate made-up details, strip clichés, and verify key skill terms."
            )
        elif doc_type == "Interview Prep":
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
            spinner_msg = (
                f"Step 1/2: Drafting {doc_type} → Step 2/2: Running Accuracy & Fact Check..."
                if (supports_reviewer and use_reviewer)
                else f"Generating {doc_type}..."
            )
            with st.spinner(spinner_msg):
                try:
                    if doc_type == "Interview Prep":
                        content = generator_func(
                            active_resume_for_gen,
                            job_text,
                            st.session_state.get("model_choice"),
                            st.session_state.get("user_api_key"),
                            st.session_state.get("local_base_url"),
                            st.session_state.get("local_model_name"),
                            missing_skills=str(item.get("Missing Skills") or ""),
                            tailored_resume=str(item.get("Tailored Resume") or ""),
                            cover_letter=str(item.get("Cover Letter") or ""),
                            interview_stage=interview_stage,
                            model_override=st.session_state.get("model_override", ""),
                        )
                    elif doc_type == "Application QA":
                        content = generator_func(
                            active_resume_for_gen,
                            job_text,
                            st.session_state.get("model_choice"),
                            st.session_state.get("user_api_key"),
                            st.session_state.get("local_base_url"),
                            st.session_state.get("local_model_name"),
                            model_override=st.session_state.get("model_override", ""),
                        )
                    elif doc_type == "Followup Note":
                        content = generator_func(
                            active_resume_for_gen,
                            job_text,
                            company_name=str(item.get("Company") or ""),
                            position_name=str(item.get("Position") or ""),
                            note_type=followup_type,
                            tailored_resume=str(item.get("Tailored Resume") or ""),
                            cover_letter=str(item.get("Cover Letter") or ""),
                            model_choice=st.session_state.get("model_choice"),
                            api_key=st.session_state.get("user_api_key"),
                            local_base_url=st.session_state.get("local_base_url"),
                            local_model_name=st.session_state.get("local_model_name"),
                            model_override=st.session_state.get("model_override", ""),
                        )
                    elif doc_type == "Outreach Message":
                        content = generator_func(
                            master_resume=active_resume_for_gen,
                            job_description=job_text,
                            company_name=str(item.get("Company") or ""),
                            position_name=str(item.get("Position") or ""),
                            model_choice=st.session_state.get("model_choice"),
                            api_key=st.session_state.get("user_api_key"),
                            local_base_url=st.session_state.get("local_base_url"),
                            local_model_name=st.session_state.get("local_model_name"),
                            tailored_resume=str(item.get("Tailored Resume") or ""),
                            model_override=st.session_state.get("model_override", ""),
                        )
                    elif doc_type == "Company Intel":
                        content = generator_func(
                            company_name=str(item.get("Company") or ""),
                            position_name=str(item.get("Position") or ""),
                            job_description=job_text,
                            master_resume=active_resume_for_gen,
                            model_choice=st.session_state.get("model_choice"),
                            api_key=st.session_state.get("user_api_key"),
                            local_base_url=st.session_state.get("local_base_url"),
                            local_model_name=st.session_state.get("local_model_name"),
                            model_override=st.session_state.get("model_override", ""),
                        )
                    else:
                        content = generator_func(
                            active_resume_for_gen, job_text, st.session_state.get("model_choice"),
                            st.session_state.get("user_api_key"), st.session_state.get("local_base_url"), st.session_state.get("local_model_name"),
                            model_override=st.session_state.get("model_override", ""),
                        )
                except Exception as gen_err:
                    st.error(f"⚠️ Could not generate {doc_type}: {gen_err}")
                    return
                if supports_reviewer and use_reviewer:
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
                        )
                        if audit_res.revised_document and len(audit_res.revised_document.strip()) > 50:
                            content = audit_res.revised_document
                        audit_md = format_audit_report_markdown(audit_res, doc_label=doc_type)
                        st.session_state[audit_cache_key] = audit_md
                        db.update_job_field(url, "Reviewer Audit", audit_md)
                    except Exception as rev_err:
                        st.warning(f"Drafter pass succeeded, but Reviewer audit encountered an error: {rev_err}")

                st.session_state[cache_key] = content
                st.session_state["active_job_url"] = url
                db.update_job_field(url, doc_type, content)
                safe_fragment_rerun()
    else:
        raw_title = str(item.get("Company") or item.get("Position") or "Job")
        if raw_title == "Unknown Company":
            raw_title = str(item.get("Position") or "Job")
        safe_title = re.sub(r'[^\w\-_\.]', '_', raw_title.replace(" ", "_"))
        safe_doc_type = re.sub(r'[^\w\-_\.]', '_', doc_type.replace(" ", "_"))

        ats_style_key = "classic"
        editor_key = f"editor_{cache_key}"

        def _sync_editor_to_cache():
            if editor_key in st.session_state:
                updated_val = st.session_state[editor_key]
                if updated_val is not None and updated_val != st.session_state.get(cache_key):
                    st.session_state[cache_key] = updated_val
                    item[doc_type] = updated_val
                    db.update_job_field(url, doc_type, updated_val)

        # Ensure any pending edit in session_state is synced before rendering preview
        _sync_editor_to_cache()
        current_content = st.session_state[cache_key]

        if doc_type == "Tailored Resume":
            style_options = {
                "📄 Classic Clean ATS (Arial — Standard Single-Column, Right-Aligned Dates)": "classic",
                "✨ Modern Executive ATS (Calibri + Section Divider Rules)": "modern",
                "🏛️ Harvard / Traditional Serif ATS (Times New Roman + Section Rules)": "serif",
            }
            col_tpl, col_view = st.columns([2.8, 2.4])
            with col_tpl:
                chosen_label = st.selectbox(
                    "🎨 ATS Resume Template Style:",
                    list(style_options.keys()),
                    key=f"ats_tpl_{cache_key}",
                    help="Formats your tailored resume directly into a single-column, ATS-parseable Word (.docx) and PDF template with centered contact header and flush-right dates—no copy-pasting needed.",
                )
                ats_style_key = style_options[chosen_label]
            with col_view:
                view_mode = st.radio(
                    "View Mode:",
                    ["📄 ATS Template Preview", "✏️ Edit Markdown", "🔀 Live Split View"],
                    horizontal=True,
                    key=f"ats_view_{cache_key}",
                )

            if view_mode == "✏️ Edit Markdown":
                st.session_state[editor_key] = current_content
                edited_doc = st.text_area(
                    f"{doc_type} (Markdown — Press Ctrl+Enter or switch back to ATS Preview to see changes)",
                    height=420,
                    key=editor_key,
                    on_change=_sync_editor_to_cache,
                )
                if edited_doc != current_content:
                    st.session_state[cache_key] = edited_doc
                    item[doc_type] = edited_doc
                    db.update_job_field(url, doc_type, edited_doc)
                    current_content = edited_doc
            elif view_mode == "🔀 Live Split View":
                st.session_state[editor_key] = current_content
                sp_left, sp_right = st.columns([1, 1.15])
                with sp_left:
                    edited_doc = st.text_area(
                        "✏️ Edit Markdown (Press Ctrl+Enter to refresh preview):",
                        height=560,
                        key=editor_key,
                        on_change=_sync_editor_to_cache,
                    )
                    if edited_doc != current_content:
                        st.session_state[cache_key] = edited_doc
                        item[doc_type] = edited_doc
                        db.update_job_field(url, doc_type, edited_doc)
                        current_content = edited_doc
                with sp_right:
                    st.caption("📄 **Live ATS Template Preview**")
                    st.markdown(render_ats_resume_html(current_content, template_style=ats_style_key), unsafe_allow_html=True)
            else:
                edited_doc = current_content
                st.markdown(render_ats_resume_html(edited_doc, template_style=ats_style_key), unsafe_allow_html=True)
                st.caption("💡 Switch to **✏️ Edit Markdown** or **🔀 Live Split View** above to tweak bullet points and see your updates live.")
        else:
            st.session_state[editor_key] = current_content
            edited_doc = st.text_area(
                f"{doc_type} (Markdown)",
                height=400,
                key=editor_key,
                on_change=_sync_editor_to_cache,
            )
            if edited_doc != current_content:
                st.session_state[cache_key] = edited_doc
                item[doc_type] = edited_doc
                db.update_job_field(url, doc_type, edited_doc)

        if supports_reviewer:
            if doc_type == "Tailored Resume":
                has_pdf = is_pdf_conversion_available()
                if has_pdf:
                    col1, col_pdf, col2, col3 = st.columns([2.2, 2.2, 2.8, 1.3])
                else:
                    col1, col2, col3 = st.columns([2.5, 3.2, 1.5])
                    col_pdf = None
                with col1:
                    st.download_button(
                        "📥 Download ATS (.docx)",
                        data=generate_ats_resume_docx(edited_doc, template_style=ats_style_key),
                        file_name=f"ATS_Resume_{safe_title}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        type="primary",
                        width="stretch",
                        key=f"dl_{cache_key}",
                    )
                if col_pdf is not None and has_pdf:
                    with col_pdf:
                        st.download_button(
                            "📕 Download ATS (.pdf)",
                            data=lambda: generate_ats_resume_pdf(edited_doc, template_style=ats_style_key),
                            file_name=f"ATS_Resume_{safe_title}.pdf",
                            mime="application/pdf",
                            width="stretch",
                            key=f"dl_pdf_{cache_key}",
                        )
            else:
                col1, col2, col3 = st.columns([2.5, 3.2, 1.5])
                with col1:
                    st.download_button(
                        "📥 Download (.docx)",
                        data=generate_docx_from_markdown(edited_doc),
                        file_name=f"{safe_doc_type}_{safe_title}.docx",
                        type="primary",
                        width="stretch",
                        key=f"dl_{cache_key}"
                    )
            with col2:
                if st.button("🔍 Run Reviewer & ATS Fact Audit", width="stretch", key=f"audit_btn_{cache_key}"):
                    with st.spinner(f"Auditing {doc_type} against selected Resume(s) & ATS keywords..."):
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
                            )
                            if audit_res.revised_document and len(audit_res.revised_document.strip()) > 50:
                                st.session_state[cache_key] = audit_res.revised_document
                                db.update_job_field(url, doc_type, audit_res.revised_document)
                            audit_md = format_audit_report_markdown(audit_res, doc_label=doc_type)
                            st.session_state[audit_cache_key] = audit_md
                            st.session_state["active_job_url"] = url
                            db.update_job_field(url, "Reviewer Audit", audit_md)
                            safe_fragment_rerun()
                        except Exception as e:
                            st.error(f"Reviewer Audit failed: {e}")
            with col3:
                if st.button("🔄 Regenerate", width="stretch", key=f"regen_{cache_key}"):
                    st.session_state[cache_key] = ""
                    st.session_state.pop(editor_key, None)
                    st.session_state.pop(audit_cache_key, None)
                    st.session_state["active_job_url"] = url
                    db.update_job_field(url, doc_type, "")
                    db.update_job_field(url, "Reviewer Audit", "")
                    safe_fragment_rerun()

            if st.session_state.get(audit_cache_key):
                with st.expander("🛡️ View Accuracy & Fact-Check Review Report", expanded=True):
                    st.markdown(st.session_state[audit_cache_key])
        else:
            col1, _, col2 = st.columns([3.2, 5.8, 1.5])
            with col1:
                st.download_button(
                    "📥 Download (.docx)",
                    data=generate_docx_from_markdown(edited_doc),
                    file_name=f"{safe_doc_type}_{safe_title}.docx",
                    type="primary",
                    key=f"dl_{cache_key}"
                )
            with col2:
                if st.button("🔄 Regenerate", key=f"regen_{cache_key}"):
                    st.session_state[cache_key] = ""
                    st.session_state.pop(editor_key, None)
                    st.session_state["active_job_url"] = url
                    db.update_job_field(url, doc_type, "")
                    safe_fragment_rerun()


def _format_gate_pill(gate_val: str) -> str:
    g = str(gate_val or "PASS").strip().upper()
    if g == "FAIL":
        return "❌ FAIL"
    if g == "FLAG":
        return "⚠️ FLAG"
    return "✅ PASS"


def render_history_card(item: dict, is_expanded: bool = False):
    score = int(item.get("Score", 0) or 0)
    eligible = bool(item.get("Eligible", True))
    fit_band = get_fit_band(score, eligible)
    company = str(item.get("Company") or "").strip()
    if company == "Unknown Company":
        company = ""
    company_suffix = f" at {company}" if company else ""
    deadline_badge = format_deadline_badge(item.get("Deadline", ""))
    deadline_header = f" · 🗓️ {deadline_badge}" if deadline_badge != "—" else ""
    
    card_hash = hashlib.sha256((item.get("URL") or item.get("Position", "")).encode("utf-8", errors="ignore")).hexdigest()[:12]
    if is_expanded:
        st.html("<div id='active_job_card' style='scroll-margin-top: 80px;'></div>")
    with st.expander(f"{fit_band} ({score}/100) — {item.get('Position', 'Role')}{company_suffix}{deadline_header} ({item.get('URL', 'Link')})", expanded=is_expanded):
        tabs = st.tabs([
            "Overview",
            "⚡ Tailored Resume",
            "✉️ Cover Letter",
            "📋 Application Answers",
            "🎤 Interview Prep",
            "📬 Follow-Up Notes",
            "🎯 Networking Messages",
            "🏢 Company Research Guide",
        ], key=f"hist_tabs_{card_hash}")
        with tabs[0]:
            c1, c2, _ = st.columns([1.2, 2.0, 6.8])
            raw_url = str(item.get("URL") or "")
            if raw_url.startswith(("http://", "https://")):
                c1.link_button("🚀 Apply to this Job", raw_url, type="primary")
            with c2:
                application_status_tracker(item)

            risk = db.check_repost_risk(item.get("Company", ""), item.get("Position", ""), item.get("URL", ""))
            if risk:
                if risk.get("is_ghost_risk"):
                    st.warning(
                        f"👻 **Repeated Listing Warning:** {risk['badge_text']}. "
                        f"This job was first spotted on `{risk['first_seen']}` across {risk['count']} distinct postings over {risk['days_span']} days. "
                        "Employers frequently relist stale or churned roles—verify with a recruiter or hiring manager before over-investing time."
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

            # Pre-scoring Gates & Metadata Row
            elig_gate = _format_gate_pill(item.get("Eligibility Gate", "PASS" if eligible else "FAIL"))
            loc_gate = _format_gate_pill(item.get("Location Gate", "PASS"))
            meta_parts = [
                f"**Requirements Check:** `{elig_gate}`",
                f"**Location Check:** `{loc_gate}`",
            ]
            if company:
                meta_parts.insert(0, f"**Company:** {company}")
            if deadline_badge != "—":
                meta_parts.append(f"**Deadline:** `{deadline_badge}`")
            matched_res_str = str(item.get("Matched Resumes") or "").strip()
            if matched_res_str and matched_res_str.lower() != "nan":
                meta_parts.append(f"**Resume(s):** `{matched_res_str}`")
            st.markdown(" &nbsp;|&nbsp; ".join(meta_parts))

            # Multi-Dimensional Sub-Score Breakdown
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
                        st.metric("🤝 Work Style & Team Fit (15%)", f"{beh_s}/100")
                        st.progress(min(max(beh_s / 100.0, 0.0), 1.0))
                    with sc4:
                        st.metric("🎯 Career Goals Match (30%)", f"{car_s}/100")
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
            st.caption("Generates quick, character-counted answers for online job applications (short pitches, introductions, and 'Why this company' answers).")
            document_generator(item, "Application QA", generate_application_qa)
        with tabs[4]:
            st.caption("Generates interview practice questions, realistic story examples (STAR method), ways to address missing skills, and smart questions to ask the interviewer.")
            document_generator(item, "Interview Prep", generate_interview_prep)
        with tabs[5]:
            st.caption("Drafts concise follow-up and thank-you notes for email and LinkedIn (60–120 words).")
            document_generator(item, "Followup Note", generate_followup_note)
        with tabs[6]:
            st.caption("Generates personalized LinkedIn connection notes (under 300 characters) for hiring managers, recruiters, and peers, plus a direct email draft.")
            document_generator(item, "Outreach Message", generate_outreach_messages)
        with tabs[7]:
            st.caption("Creates a complete company overview covering what they do, tools they use, recent news, key challenges, team culture, and winning interview talking points.")
            document_generator(item, "Company Intel", generate_deep_company_brief)


# Helper to safely determine the job source without crashing on old Pandas NaN data
def get_source(item):
    src = item.get("Source")
    if pd.isna(src) or not src:
        return "Manual"
    return str(src).strip()


# --- Build the Tabbed Layout (Intelligently order so active source or selected row's source is first) ---
active_job = None
if active_job_id is not None and 0 <= active_job_id < len(all_saved_jobs):
    active_job = all_saved_jobs[active_job_id]
    st.session_state["active_job_url"] = active_job.get("URL")
elif st.session_state.get("active_job_url"):
    target_url = st.session_state.get("active_job_url")
    active_job = next((j for j in all_saved_jobs if j.get("URL") == target_url), None)

if active_job is not None:
    active_source = get_source(active_job)
    st.session_state["active_history_source"] = active_source
else:
    active_source = st.session_state.get("active_history_source", "Scraper")

source_tabs_config = [
    ("Scraper", "🕸️ Scraper Batch", "No Scraper batch jobs evaluated yet."),
    ("LinkedIn", "🔗 LinkedIn Inbox", "No LinkedIn extension jobs evaluated yet."),
    ("Manual", "📝 Manual Entries", "No manual entries evaluated yet. (Note: Old jobs from before the update are also stored here)."),
]
# Move active source to the front
source_tabs_config.sort(key=lambda x: 0 if x[0] == active_source else 1)

allowed_indices = set(df["Original_Index"].tolist())
if active_job is not None:
    # Ensure active_job is always included in allowed_indices even if filters would have excluded it
    for i, j in enumerate(all_saved_jobs):
        if j.get("URL") == active_job.get("URL"):
            allowed_indices.add(i)
            break

tab_elements = st.tabs([cfg[1] for cfg in source_tabs_config])
for tab, (src_name, _, empty_msg) in zip(tab_elements, source_tabs_config):
    with tab:
        src_jobs = [j for i, j in enumerate(all_saved_jobs) if get_source(j) == src_name and i in allowed_indices]
        if not src_jobs:
            if filter_selection != "All" or date_filter_selection != "All Dates":
                st.info(f"No {src_name} postings match the selected filter(s).")
            else:
                st.info(empty_msg)
            continue

        # Group postings by evaluation date
        groups = defaultdict(list)
        for j in src_jobs:
            d = parse_job_date(j.get("Timestamp", ""))
            groups[d].append(j)

        sorted_dates = sorted(groups.keys(), key=lambda d: d if d is not None else date.min, reverse=True)

        for job_date in sorted_dates:
            day_jobs = groups[job_date]
            # Order newest evaluation first within each day
            day_jobs.sort(key=lambda x: str(x.get("Timestamp", "")), reverse=True)

            day_label = format_day_group_label(job_date, today)
            contains_active = (active_job is not None and any(j.get("URL") == active_job.get("URL") for j in day_jobs))

            # Smart expand: if a table row is clicked, expand the day container holding that job.
            # Otherwise, expand today's evaluations by default, or expand if there is only 1 day group.
            if active_job is not None:
                is_day_expanded = contains_active
            else:
                is_day_expanded = (job_date == today) or (len(sorted_dates) == 1)

            day_count_text = f"**{len(day_jobs)}** posting{'s' if len(day_jobs) != 1 else ''}"
            with st.expander(f"{day_label} · {day_count_text}", expanded=is_day_expanded):
                for j in day_jobs:
                    is_active_card = (active_job is not None and j.get("URL") == active_job.get("URL"))
                    render_history_card(j, is_expanded=is_active_card)

# Auto-scroll directly to the expanded card when jumping from Gallery or clicking table row
should_scroll = (active_job_id is not None) or st.session_state.get("jump_to_card")
if should_scroll:
    st.html(
        f"""
        <script>
        (function() {{
            let attempts = 0;
            const maxAttempts = 60;
            const interval = setInterval(function() {{
                attempts++;
                const doc = window.parent ? window.parent.document : document;
                const target = doc.getElementById('active_job_card');
                if (target) {{
                    clearInterval(interval);
                    target.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                    const expander = target.closest('[data-testid="stExpander"]') || target.nextElementSibling;
                    if (expander) {{
                        expander.style.transition = 'box-shadow 0.4s ease';
                        expander.style.boxShadow = '0 0 0 3px rgba(33, 150, 243, 0.6)';
                        setTimeout(function() {{
                            expander.style.boxShadow = '';
                        }}, 2500);
                    }}
                }} else if (attempts >= maxAttempts) {{
                    clearInterval(interval);
                    const fallback = doc.getElementById('details');
                    if (fallback) {{
                        fallback.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                    }}
                }}
            }}, 50);
        }})();
        </script>
        <!-- {time.time()} -->
        """,
        unsafe_allow_javascript=True
    )
    st.session_state.pop("jump_to_card", None)
