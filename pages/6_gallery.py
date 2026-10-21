import streamlit as st
import pandas as pd
import os
import re
import sys
from datetime import datetime, date, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import database as db
from evaluator import (
    generate_docx_from_markdown,
    generate_ats_resume_docx,
    generate_ats_resume_pdf,
    render_ats_resume_html,
    get_fit_band,
)

st.title("🖼️ Document Gallery")
st.caption("Browse, preview, filter, and download all tailored resumes, cover letters, portal Q&A packs, interview guides, and follow-up notes.")

all_saved_jobs = db.load_all_jobs()


def _has_generated_docs(job: dict) -> bool:
    for key in ("Tailored Resume", "Cover Letter", "Application QA", "Interview Prep", "Followup Note", "Reviewer Audit"):
        val = job.get(key)
        if val and not pd.isna(val) and str(val).strip() and str(val).strip().lower() != "nan":
            return True
    return False


def _parse_job_timestamp(ts_str: str) -> datetime:
    raw = str(ts_str or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw[:19], fmt)
        except ValueError:
            continue
    return datetime.min


gallery_jobs = [j for j in all_saved_jobs if _has_generated_docs(j)]

if not gallery_jobs:
    st.info("No documents generated yet. Generate resumes, cover letters, or interview prep in the **History** page to see them here!")
    st.stop()


# --- Document Viewer Modal (Supports Live ATS Resume Editing, Preview & Downloads) ---
@st.dialog("📄 Document Viewer", width="large")
def open_document_modal(doc_label: str, doc_content: str, file_prefix: str, doc_key: str, job: dict):
    url = str(job.get("URL") or "")
    pos = str(job.get("Position") or "Role")
    comp = str(job.get("Company") or "").strip()
    if comp == "Unknown Company":
        comp = ""
    ts = str(job.get("Timestamp") or "").strip()

    comp_part = f" - {comp}" if comp else ""
    ts_part = f" - {ts}" if ts else ""
    st.markdown(f"### {doc_label}")
    st.caption(f"**{pos}{comp_part}{ts_part}**")

    raw_title = comp or pos or "Job"
    safe_title = re.sub(r"[^\w\-_\.]", "_", raw_title.replace(" ", "_"))
    safe_prefix = re.sub(r"[^\w\-_\.]", "_", str(file_prefix))
    safe_suffix = re.sub(r"[^\w\-]", "_", url[-8:]) if url else "doc"

    cache_key = f"{doc_key}_{url}"
    editor_key = f"modal_txt_{file_prefix}_{url}"

    if cache_key not in st.session_state or not st.session_state[cache_key]:
        st.session_state[cache_key] = doc_content

    def _sync_modal_editor():
        if editor_key in st.session_state:
            updated_val = st.session_state[editor_key]
            if updated_val is not None and updated_val != st.session_state.get(cache_key):
                st.session_state[cache_key] = updated_val
                job[doc_key] = updated_val
                if url:
                    db.update_job_field(url, doc_key, updated_val)

    _sync_modal_editor()
    active_content = st.session_state[cache_key]

    if file_prefix == "Resume":
        style_options = {
            "📄 Classic Clean ATS (Arial — Standard Single-Column, Right-Aligned Dates)": "classic",
            "✨ Modern Executive ATS (Calibri + Section Divider Rules)": "modern",
            "🏛️ Harvard / Traditional Serif ATS (Times New Roman + Section Rules)": "serif",
        }
        c_tpl, c_view = st.columns([2.8, 2.4])
        with c_tpl:
            chosen_label = st.selectbox(
                "🎨 ATS Resume Template Style:",
                list(style_options.keys()),
                key=f"gal_ats_tpl_{safe_suffix}",
            )
            ats_style_key = style_options[chosen_label]
        with c_view:
            view_mode = st.radio(
                "View Mode:",
                ["📄 ATS Template Preview", "✏️ Edit Markdown", "🔀 Live Split View"],
                horizontal=True,
                key=f"gal_ats_view_{safe_suffix}",
            )

        if view_mode == "✏️ Edit Markdown":
            st.session_state[editor_key] = active_content
            edited_val = st.text_area(
                "Edit Resume Markdown (Press Ctrl+Enter or switch back to ATS Preview to see changes):",
                height=450,
                key=editor_key,
                on_change=_sync_modal_editor,
            )
            if edited_val != active_content:
                st.session_state[cache_key] = edited_val
                job[doc_key] = edited_val
                if url:
                    db.update_job_field(url, doc_key, edited_val)
                active_content = edited_val
        elif view_mode == "🔀 Live Split View":
            st.session_state[editor_key] = active_content
            sp_left, sp_right = st.columns([1, 1.15])
            with sp_left:
                edited_val = st.text_area(
                    "✏️ Edit Markdown (Press Ctrl+Enter to refresh preview):",
                    height=520,
                    key=editor_key,
                    on_change=_sync_modal_editor,
                )
                if edited_val != active_content:
                    st.session_state[cache_key] = edited_val
                    job[doc_key] = edited_val
                    if url:
                        db.update_job_field(url, doc_key, edited_val)
                    active_content = edited_val
            with sp_right:
                st.caption("📄 **Live ATS Template Preview**")
                st.markdown(render_ats_resume_html(active_content, template_style=ats_style_key), unsafe_allow_html=True)
        else:
            st.markdown(render_ats_resume_html(active_content, template_style=ats_style_key), unsafe_allow_html=True)

        pdf_bytes = generate_ats_resume_pdf(active_content, template_style=ats_style_key)
        if pdf_bytes:
            dl_c1, dl_c2 = st.columns(2)
            with dl_c1:
                st.download_button(
                    "📥 Download ATS Resume (.docx)",
                    data=generate_ats_resume_docx(active_content, template_style=ats_style_key),
                    file_name=f"ATS_Resume_{safe_title}_{safe_suffix}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    type="primary",
                    key=f"modal_dl_docx_{file_prefix}_{url}",
                )
            with dl_c2:
                st.download_button(
                    "📕 Download ATS Resume (.pdf)",
                    data=pdf_bytes,
                    file_name=f"ATS_Resume_{safe_title}_{safe_suffix}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"modal_dl_pdf_{file_prefix}_{url}",
                )
        else:
            st.download_button(
                "📥 Download ATS Resume (.docx)",
                data=generate_ats_resume_docx(active_content, template_style=ats_style_key),
                file_name=f"ATS_Resume_{safe_title}_{safe_suffix}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                type="primary",
                key=f"modal_dl_{file_prefix}_{url}",
            )
    else:
        st.session_state[editor_key] = active_content
        edited_val = st.text_area(
            "Edit / Copy Markdown:",
            height=480,
            key=editor_key,
            on_change=_sync_modal_editor,
        )
        if edited_val != active_content:
            st.session_state[cache_key] = edited_val
            job[doc_key] = edited_val
            if url:
                db.update_job_field(url, doc_key, edited_val)
            active_content = edited_val
        st.download_button(
            f"📥 Download {doc_label} (.docx)",
            data=generate_docx_from_markdown(active_content),
            file_name=f"{safe_prefix}_{safe_title}_{safe_suffix}.docx",
            use_container_width=True,
            type="primary",
            key=f"modal_dl_{file_prefix}_{url}",
        )


# --- FILTER & SORT BAR (By Timestamp or Score) ---
with st.container(border=True):
    f_col1, f_col2, f_col3, f_col4 = st.columns([2.4, 2.2, 2.6, 1.8])
    with f_col1:
        sort_by = st.selectbox(
            "🔃 Sort Cards By:",
            [
                "🕒 Timestamp (Newest First)",
                "🕒 Timestamp (Oldest First)",
                "🎯 Score (Highest First)",
                "🎯 Score (Lowest First)",
            ],
            key="gallery_sort_by",
        )
    with f_col2:
        time_filter = st.selectbox(
            "📅 Filter by Timestamp:",
            [
                "All Time",
                "Today",
                "Past 7 Days",
                "Past 30 Days",
                "Specific Date Range",
            ],
            key="gallery_time_filter",
        )
    with f_col3:
        score_range = st.slider(
            "🎯 Filter by Score Range:",
            min_value=0,
            max_value=100,
            value=(0, 100),
            step=1,
            key="gallery_score_range",
        )
    with f_col4:
        search_query = st.text_input(
            "🔎 Search Role / Company:",
            value="",
            placeholder="e.g. SOC Analyst...",
            key="gallery_search_query",
        )

    custom_start_date = None
    custom_end_date = None
    if time_filter == "Specific Date Range":
        d_col1, d_col2, _ = st.columns([2, 2, 6])
        with d_col1:
            custom_start_date = st.date_input("Start Date", value=date.today() - timedelta(days=30), key="gal_start_dt")
        with d_col2:
            custom_end_date = st.date_input("End Date", value=date.today(), key="gal_end_dt")

# Apply Score Filter
min_score, max_score = score_range
filtered_jobs = [
    j for j in gallery_jobs
    if min_score <= int(j.get("Score", 0) or 0) <= max_score
]

# Apply Timestamp Filter
today_dt = date.today()
if time_filter == "Today":
    filtered_jobs = [
        j for j in filtered_jobs
        if _parse_job_timestamp(j.get("Timestamp", "")).date() == today_dt
    ]
elif time_filter == "Past 7 Days":
    cutoff = today_dt - timedelta(days=7)
    filtered_jobs = [
        j for j in filtered_jobs
        if _parse_job_timestamp(j.get("Timestamp", "")).date() >= cutoff
    ]
elif time_filter == "Past 30 Days":
    cutoff = today_dt - timedelta(days=30)
    filtered_jobs = [
        j for j in filtered_jobs
        if _parse_job_timestamp(j.get("Timestamp", "")).date() >= cutoff
    ]
elif time_filter == "Specific Date Range" and custom_start_date and custom_end_date:
    filtered_jobs = [
        j for j in filtered_jobs
        if custom_start_date <= _parse_job_timestamp(j.get("Timestamp", "")).date() <= custom_end_date
    ]

# Apply Text Search Filter
if search_query.strip():
    q = search_query.strip().lower()
    filtered_jobs = [
        j for j in filtered_jobs
        if q in str(j.get("Position", "")).lower()
        or q in str(j.get("Company", "")).lower()
        or q in str(j.get("Timestamp", "")).lower()
    ]

# Apply Sorting
if sort_by == "🕒 Timestamp (Newest First)":
    filtered_jobs.sort(key=lambda j: _parse_job_timestamp(j.get("Timestamp", "")), reverse=True)
elif sort_by == "🕒 Timestamp (Oldest First)":
    filtered_jobs.sort(key=lambda j: _parse_job_timestamp(j.get("Timestamp", "")), reverse=False)
elif sort_by == "🎯 Score (Highest First)":
    filtered_jobs.sort(key=lambda j: (int(j.get("Score", 0) or 0), _parse_job_timestamp(j.get("Timestamp", ""))), reverse=True)
elif sort_by == "🎯 Score (Lowest First)":
    filtered_jobs.sort(key=lambda j: (int(j.get("Score", 0) or 0), _parse_job_timestamp(j.get("Timestamp", ""))), reverse=False)

st.caption(f"Showing **{len(filtered_jobs)}** of **{len(gallery_jobs)}** job card(s) with generated documents.")

if not filtered_jobs:
    st.warning("No generated document cards match your current timestamp or score filters.")
else:
    cols = st.columns(3)
    for index, job in enumerate(filtered_jobs):
        with cols[index % 3]:
            with st.container(border=True):
                score_val = int(job.get("Score", 0) or 0)
                fit_band = get_fit_band(score_val, bool(job.get("Eligible", True)))
                st.subheader(f"{score_val}/100 · {fit_band}")

                pos_name = str(job.get("Position") or "Role").strip()
                comp_name = str(job.get("Company") or "").strip()
                if comp_name == "Unknown Company":
                    comp_name = ""
                ts_val = str(job.get("Timestamp") or "").strip()

                comp_str = f" - {comp_name}" if comp_name else ""
                ts_str = f" - 🕒 {ts_val}" if ts_val else ""
                st.markdown(f"**{pos_name}{comp_str}{ts_str}**")
                st.write("")

                def render_gallery_button(doc_label: str, doc_key: str, file_prefix: str, icon: str, current_job: dict = job):
                    url_val = str(current_job.get("URL") or "")
                    cache_k = f"{doc_key}_{url_val}"
                    doc_content = st.session_state.get(cache_k) or current_job.get(doc_key)
                    if doc_content and not pd.isna(doc_content) and str(doc_content).strip().lower() != "nan":
                        if st.button(
                            f"{icon} View {doc_label}",
                            use_container_width=True,
                            key=f"gal_btn_{file_prefix}_{url_val}",
                        ):
                            open_document_modal(doc_label, str(doc_content), file_prefix, doc_key, current_job)

                render_gallery_button("Resume", "Tailored Resume", "Resume", "📄")
                render_gallery_button("Cover Letter", "Cover Letter", "CoverLetter", "✉️")
                render_gallery_button("Application Q&A", "Application QA", "ApplicationQA", "📋")
                render_gallery_button("Interview Prep", "Interview Prep", "InterviewPrep", "🎤")
                render_gallery_button("Follow-Up Note", "Followup Note", "FollowupNote", "📬")
                if job.get("Reviewer Audit") and str(job.get("Reviewer Audit")).lower() != "nan":
                    render_gallery_button("ATS & Fact Audit", "Reviewer Audit", "AuditReport", "🛡️")
