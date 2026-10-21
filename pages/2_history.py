import streamlit as st
import pandas as pd
import os
import re
import time
import sys
from datetime import date, datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils import setup_sidebar, enforce_onboarding, load_resumes, combine_selected_resumes
import database as db
from evaluator import (
    tailor_resume,
    tailor_cover_letter,
    generate_interview_prep,
    generate_application_qa,
    generate_followup_note,
    generate_docx_from_markdown,
    generate_ats_resume_docx,
    generate_ats_resume_pdf,
    render_ats_resume_html,
    review_and_refine_document,
    format_audit_report_markdown,
    get_fit_band,
)

st.title("🗂️ Evaluation History")

if "latest_batch_info" in st.session_state:
    b_info = st.session_state["latest_batch_info"]
    src = b_info.get("source", "Scraper")
    count = len(b_info.get("urls", []))
    col_msg, col_dism = st.columns([5.5, 1])
    with col_msg:
        st.info(f"✨ **Latest Run Results:** Viewing {count} newly evaluated posting{'s' if count != 1 else ''} from **{src}**. Review summary in the Overview Table and detailed cards below.", icon="🎯")
    with col_dism:
        if st.button("Dismiss", key="dismiss_latest_batch_info"):
            del st.session_state["latest_batch_info"]
            st.rerun()

# Data Management tools tucked neatly at the top
col_act1, col_act2, _ = st.columns([1.5, 1.5, 7.0])
with col_act1:
    if st.button("🔄 Refresh Data", type="secondary", use_container_width=True):
        st.rerun()
with col_act2:
    if st.button("🗑️ Clear History", type="secondary", use_container_width=True):
        db.clear_all_history()
        st.rerun()

all_saved_jobs = db.load_all_jobs()
if not all_saved_jobs:
    st.info("Your database is empty. Process jobs using the Scraper or LinkedIn tools to see them here!")
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


# --- TOP-LEVEL DATAFRAME & FILTERS ---
filter_col, metric_col, _ = st.columns([3, 2, 5])
with filter_col:
    filter_selection = st.selectbox(
        "Filter by Assessment:",
        ["All", "Strong Fit (75+)", "Good Fit (60-74)", "Moderate / Weak Fit (<60)", "Disqualified"]
    )
with metric_col:
    st.metric("Total Postings Saved", len(all_saved_jobs))

df = pd.DataFrame(all_saved_jobs)
# Store the original list index so we can tie dataframe clicks back to the right card
df["Original_Index"] = df.index
if "Company" not in df.columns:
    df["Company"] = ""
if "Deadline" not in df.columns:
    df["Deadline"] = ""

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


def highlight_status(row):
    status = row.get("Application Status", "Not Applied")
    colors = {
        "Applied": "rgba(30,136,229,0.2)",
        "Interviewing": "rgba(253,216,53,0.2)",
        "Waitlisted": "rgba(245,124,0,0.2)",
        "Rejected": "rgba(229,57,53,0.2)",
        "Offer": "rgba(67,160,71,0.2)",
    }
    return [f"background-color: {colors.get(status, '')}"] * len(row)


display_cols = ["Timestamp", "Position", "Company_Display", "Assessment", "Score", "Deadline_Display", "Application Status", "URL", "Red Flags"]
styled_df = df[display_cols].rename(
    columns={"Company_Display": "Company", "Deadline_Display": "Deadline"}
).style.apply(highlight_status, axis=1)

selection_event = st.dataframe(
    styled_df,
    width="stretch",
    on_select="rerun",
    selection_mode="single-row",
    column_config={"URL": st.column_config.LinkColumn("Source URL")}
)

# Identify which job the user clicked in the dataframe
active_job_id = int(df.iloc[selection_event.selection.rows[0]]["Original_Index"]) if selection_event.selection.rows else None

st.markdown("---")
st.subheader("🔍 Detailed Postings", anchor="details")

# Auto-scroll down to the cards if a user clicks a row in the dataframe
if active_job_id is not None:
    import streamlit.components.v1 as components
    components.html(
        f"<script>try {{ window.parent.document.getElementById('details').scrollIntoView({{behavior: 'smooth'}}); }} catch(e) {{}} /* {time.time()} */</script>",
        height=0
    )


# --- UI Helper Functions ---
def application_status_tracker(item: dict):
    url = item.get("URL")
    statuses = ["Not Applied", "Applied", "Interviewing", "Waitlisted", "Rejected", "Offer"]
    current = item.get("Application Status", "Not Applied")
    
    def on_status_change():
        new_status = st.session_state[f"status_tracker_{url}"]
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
    vault = load_resumes()
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
                "📄 Resume Profile(s) to Harvest From:",
                options=vault_names,
                default=default_doc_resumes,
                key=f"doc_res_sel_{cache_key}",
                help="Select 1 or more saved resumes. If you select multiple, Skippy harvests and merges the best-matching roles, projects, skills, and bullet points across them into a single cohesive document.",
            ) or default_doc_resumes
        active_resume_for_gen = combine_selected_resumes(chosen_doc_resumes, vault) if chosen_doc_resumes else st.session_state.resume_text

        if supports_reviewer:
            use_reviewer = st.checkbox(
                "🛡️ Run Drafter–Reviewer Pass & ATS Fact Audit (Zero-Hallucination & Keyword Check)",
                value=True,
                key=f"chk_rev_{cache_key}",
                help="Runs a second Reviewer & Factual Grounding Audit pass comparing the draft against your selected Resume(s) and the Job Description to eliminate hallucinations, strip AI clichés, normalize ASCII dates, and verify ATS keyword coverage."
            )
        elif doc_type == "Interview Prep":
            interview_stage = st.selectbox(
                "🎯 Target Interview Stage:",
                [
                    "Full Loop (All Stages)",
                    "Phone / Recruiter Screen (30 min — Motivation, Pitch & High-Level Fit)",
                    "Technical / Hiring Manager (45-60 min — Deep Architecture, Hands-On & Gap Defense)",
                    "Behavioral / Final Round (Leadership, Conflict Resolution & Executive Alignment)",
                ],
                key=f"stage_sel_{cache_key}",
                help="Customizes STAR stories, Honest Gap Bridges, and Questions to Ask for your specific interview round."
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
                f"Step 1/2: Drafting {doc_type} → Step 2/2: Running Reviewer & ATS Fact Audit..."
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
                db.update_job_field(url, doc_type, content)
                st.rerun()
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
                pdf_bytes = generate_ats_resume_pdf(edited_doc, template_style=ats_style_key)
                if pdf_bytes:
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
                        use_container_width=True,
                        key=f"dl_{cache_key}",
                    )
                if col_pdf is not None and pdf_bytes:
                    with col_pdf:
                        st.download_button(
                            "📕 Download ATS (.pdf)",
                            data=pdf_bytes,
                            file_name=f"ATS_Resume_{safe_title}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
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
                        use_container_width=True,
                        key=f"dl_{cache_key}"
                    )
            with col2:
                if st.button("🔍 Run Reviewer & ATS Fact Audit", use_container_width=True, key=f"audit_btn_{cache_key}"):
                    with st.spinner(f"Auditing {doc_type} against selected Resume(s) & ATS keywords..."):
                        try:
                            audit_resume_pool = combine_selected_resumes(default_doc_resumes, vault) if default_doc_resumes else st.session_state.resume_text
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
                            db.update_job_field(url, "Reviewer Audit", audit_md)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Reviewer Audit failed: {e}")
            with col3:
                if st.button("🔄 Regenerate", use_container_width=True, key=f"regen_{cache_key}"):
                    st.session_state[cache_key] = ""
                    db.update_job_field(url, doc_type, "")
                    st.rerun()

            if st.session_state.get(audit_cache_key):
                with st.expander("🛡️ View Drafter–Reviewer & ATS Grounding Audit Report", expanded=True):
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
                    db.update_job_field(url, doc_type, "")
                    st.rerun()


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
    
    with st.expander(f"{fit_band} ({score}/100) — {item.get('Position', 'Role')}{company_suffix}{deadline_header} ({item.get('URL', 'Link')})", expanded=is_expanded):
        tabs = st.tabs([
            "Overview",
            "⚡ Tailor Resume",
            "✉️ Cover Letter",
            "📋 Application Q&A",
            "🎤 Interview Prep",
            "📬 Follow-Up Note",
        ])
        with tabs[0]:
            c1, c2, _ = st.columns([1.2, 2.0, 6.8])
            if item["URL"].startswith("http"):
                c1.link_button("🚀 Apply to this Job", item["URL"], type="primary")
            with c2:
                application_status_tracker(item)
                
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
                f"**Eligibility Gate:** `{elig_gate}`",
                f"**Location Gate:** `{loc_gate}`",
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
                    st.caption("📊 **Multi-Dimensional Weighted Score Breakdown** *(30% Technical · 25% Experience · 15% Behavioral · 30% Career Alignment)*")
                    sc1, sc2, sc3, sc4 = st.columns(4)
                    with sc1:
                        st.metric("💻 Technical (30%)", f"{tech_s}/100")
                        st.progress(min(max(tech_s / 100.0, 0.0), 1.0))
                    with sc2:
                        st.metric("📈 Experience (25%)", f"{exp_s}/100")
                        st.progress(min(max(exp_s / 100.0, 0.0), 1.0))
                    with sc3:
                        st.metric("🤝 Behavioral (15%)", f"{beh_s}/100")
                        st.progress(min(max(beh_s / 100.0, 0.0), 1.0))
                    with sc4:
                        st.metric("🎯 Career Fit (30%)", f"{car_s}/100")
                        st.progress(min(max(car_s / 100.0, 0.0), 1.0))
                
            st.write(f"**Summary:** {item.get('Summary', '')}")
            
            if item.get("Red Flags"):
                st.warning("🚨 **Red Flags & Security Notices:**")
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
            st.caption("Generates character/word-counted short pitches (`<=140 chars` & `<=280 chars`), self-introductions (`<=1000 chars` & `<=150 words`), *'Why This Company'* responses, structured project entries, and internal `NOTE TO SELF` reminders.")
            document_generator(item, "Application QA", generate_application_qa)
        with tabs[4]:
            st.caption("Generates stage-specific STAR stories, **Honest Gap Bridges** for missing skills, and tailored questions to ask.")
            document_generator(item, "Interview Prep", generate_interview_prep)
        with tabs[5]:
            st.caption("Drafts concise 60–120 word follow-up & post-interview thank-you notes (Email + LinkedIn/Portal versions).")
            document_generator(item, "Followup Note", generate_followup_note)


# Helper to safely determine the job source without crashing on old Pandas NaN data
def get_source(item):
    src = item.get("Source")
    if pd.isna(src) or not src:
        return "Manual"
    return str(src).strip()


# --- Build the Tabbed Layout (Intelligently order so active source or selected row's source is first) ---
if active_job_id is not None and 0 <= active_job_id < len(all_saved_jobs):
    active_source = get_source(all_saved_jobs[active_job_id])
else:
    active_source = st.session_state.get("active_history_source", "Scraper")

if active_source == "Scraper":
    tabs = st.tabs([
        "🕸️ Scraper Batch",
        "🔗 LinkedIn Inbox",
        "📝 Manual Entries",
    ])
    tab_scraper, tab_linkedin, tab_manual = tabs[0], tabs[1], tabs[2]
elif active_source == "Manual":
    tabs = st.tabs([
        "📝 Manual Entries",
        "🕸️ Scraper Batch",
        "🔗 LinkedIn Inbox",
    ])
    tab_manual, tab_scraper, tab_linkedin = tabs[0], tabs[1], tabs[2]
else:
    tabs = st.tabs([
        "🔗 LinkedIn Inbox",
        "🕸️ Scraper Batch",
        "📝 Manual Entries",
    ])
    tab_linkedin, tab_scraper, tab_manual = tabs[0], tabs[1], tabs[2]

with tab_linkedin:
    linkedin_jobs = [j for i, j in enumerate(all_saved_jobs) if get_source(j) == "LinkedIn" and (active_job_id is None or active_job_id == i)]
    if not linkedin_jobs and active_job_id is None:
        st.info("No LinkedIn extension jobs evaluated yet.")
    for j in linkedin_jobs:
        render_history_card(j, is_expanded=(active_job_id is not None))

with tab_scraper:
    scraper_jobs = [j for i, j in enumerate(all_saved_jobs) if get_source(j) == "Scraper" and (active_job_id is None or active_job_id == i)]
    if not scraper_jobs and active_job_id is None:
        st.info("No Scraper batch jobs evaluated yet.")
    for j in scraper_jobs:
        render_history_card(j, is_expanded=(active_job_id is not None))

with tab_manual:
    manual_jobs = [j for i, j in enumerate(all_saved_jobs) if get_source(j) == "Manual" and (active_job_id is None or active_job_id == i)]
    if not manual_jobs and active_job_id is None:
        st.info("No manual entries evaluated yet. (Note: Old jobs from before the update are also stored here).")
    for j in manual_jobs:
        render_history_card(j, is_expanded=(active_job_id is not None))
