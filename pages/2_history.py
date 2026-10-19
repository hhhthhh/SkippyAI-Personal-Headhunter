import streamlit as st
import pandas as pd
import os
import re
import time
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils import setup_sidebar, enforce_onboarding
import database as db
from evaluator import tailor_resume, tailor_cover_letter, generate_interview_prep, generate_docx_from_markdown

st.title("🗂️ History & Document Gallery")

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

# --- TOP-LEVEL DATAFRAME & FILTERS ---
filter_col, metric_col, _ = st.columns([3, 2, 5])
with filter_col:
    filter_selection = st.selectbox("Filter by Assessment:", ["All", "Strong Match", "Reach / Low Match", "Disqualified"])
with metric_col:
    st.metric("Total Postings Saved", len(all_saved_jobs))

df = pd.DataFrame(all_saved_jobs)
# Store the original list index so we can tie dataframe clicks back to the right card
df["Original_Index"] = df.index 

def get_assessment(row):
    if not row.get("Eligible", True): return "❌ Disqualified"
    if row.get("Score", 0) >= 75: return "✅ Strong Match" 
    return "⚠️ Reach"
    
df["Assessment"] = df.apply(get_assessment, axis=1)

if filter_selection == "Strong Match": df = df[df["Assessment"] == "✅ Strong Match"]
elif filter_selection == "Reach / Low Match": df = df[df["Assessment"] == "⚠️ Reach"]
elif filter_selection == "Disqualified": df = df[df["Assessment"] == "❌ Disqualified"]

def highlight_status(row):
    status = row.get("Application Status", "Not Applied")
    colors = {"Applied": "rgba(30,136,229,0.2)", "Interviewing": "rgba(253,216,53,0.2)", 
              "Waitlisted": "rgba(245,124,0,0.2)", "Rejected": "rgba(229,57,53,0.2)", "Offer": "rgba(67,160,71,0.2)"}
    return [f"background-color: {colors.get(status, '')}"] * len(row)

styled_df = df[["Timestamp", "Position", "Assessment", "Score", "Application Status", "URL", "Red Flags"]].style.apply(highlight_status, axis=1)

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
    
    db_content = item.get(doc_type)
    if pd.isna(db_content) or not db_content or str(db_content).lower() == "nan":
        db_content = ""
        
    if cache_key not in st.session_state:
        st.session_state[cache_key] = db_content
        
    current_content = st.session_state[cache_key]
    
    if not current_content:
        if st.button(f"⚡ Generate {doc_type}", key=f"btn_{cache_key}"):
            with st.spinner(f"Generating {doc_type}..."):
                content = generator_func(
                    st.session_state.resume_text, job_text, st.session_state.get("model_choice"), 
                    st.session_state.get("user_api_key"), st.session_state.get("local_base_url"), st.session_state.get("local_model_name")
                )
                st.session_state[cache_key] = content
                db.update_job_field(url, doc_type, content)
                st.rerun()
    else:
        edited_doc = st.text_area(f"{doc_type} (Markdown)", value=current_content, height=400, key=f"editor_{cache_key}")
        
        if edited_doc != current_content:
            st.session_state[cache_key] = edited_doc
            db.update_job_field(url, doc_type, edited_doc)
            
        col1, _, col2 = st.columns([3.2, 5.8, 1.5])
        with col1:
            raw_title = str(item.get("Company", item.get("Position", "Job")))
            safe_title = re.sub(r'[^\w\-_\.]', '_', raw_title.replace(" ", "_"))
            safe_doc_type = re.sub(r'[^\w\-_\.]', '_', doc_type.replace(" ", "_"))
            st.download_button("📥 Download (.docx)", data=generate_docx_from_markdown(edited_doc), file_name=f"{safe_doc_type}_{safe_title}.docx", type="primary", key=f"dl_{cache_key}")
        with col2:
            if st.button("🔄 Regenerate", key=f"regen_{cache_key}"):
                st.session_state[cache_key] = ""
                db.update_job_field(url, doc_type, "")
                st.rerun()

def render_history_card(item: dict, is_expanded: bool = False):
    score = item.get("Score", 0)
    eligible = item.get("Eligible", True)
    status_icon = "❌" if not eligible else ("✅" if score >= 75 else "⚠️")
    
    with st.expander(f"{status_icon} Score: {score}/100 — {item.get('Position', 'Role')} ({item.get('URL', 'Link')})", expanded=is_expanded):
        tabs = st.tabs(["Overview", "⚡ Tailor Resume", "✉️ Cover Letter", "🎤 Interview Prep"])
        with tabs[0]:
            c1, c2, _ = st.columns([1.2, 2.0, 6.8])
            if item["URL"].startswith("http"): 
                c1.link_button("🚀 Apply to this Job", item["URL"], type="primary")
            with c2: 
                application_status_tracker(item)
                
            if not eligible:
                st.error(f"❌ **DISQUALIFIED:** {item.get('Disqualification Reason', '')}")
            elif score >= 75:
                st.success(f"✅ **STRONG MATCH:** {score} / 100")
                
            st.write(f"**Summary:** {item.get('Summary', '')}")
            
            if item.get("Red Flags"):
                st.warning("🚨 **Red Flags:**")
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
            document_generator(item, "Interview Prep", generate_interview_prep)


# Helper to safely determine the job source without crashing on old Pandas NaN data
def get_source(item):
    src = item.get("Source")
    if pd.isna(src) or not src:
        return "Manual"
    return str(src).strip()

# --- Build the Tabbed Layout (Intelligently order so active source is first) ---
active_source = st.session_state.get("active_history_source", "Scraper")

if active_source == "Scraper":
    tabs = st.tabs([
        "🕸️ Scraper Batch", 
        "🔗 LinkedIn Inbox", 
        "📝 Manual Entries", 
        "🖼️ Document Gallery"
    ])
    tab_scraper, tab_linkedin, tab_manual, tab_gallery = tabs[0], tabs[1], tabs[2], tabs[3]
elif active_source == "Manual":
    tabs = st.tabs([
        "📝 Manual Entries", 
        "🕸️ Scraper Batch", 
        "🔗 LinkedIn Inbox", 
        "🖼️ Document Gallery"
    ])
    tab_manual, tab_scraper, tab_linkedin, tab_gallery = tabs[0], tabs[1], tabs[2], tabs[3]
else:
    tabs = st.tabs([
        "🔗 LinkedIn Inbox", 
        "🕸️ Scraper Batch", 
        "📝 Manual Entries", 
        "🖼️ Document Gallery"
    ])
    tab_linkedin, tab_scraper, tab_manual, tab_gallery = tabs[0], tabs[1], tabs[2], tabs[3]

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

# --- Define the large modal window outside the tabs ---
@st.dialog("📄 Document Viewer", width="large")
def open_document_modal(doc_label, doc_content, file_prefix, url):
    st.markdown(f"### {doc_label}")
    
    # Larger text area since we have a bigger window now
    st.text_area(
        "Copy/Paste Markdown:", 
        value=doc_content, 
        height=500, 
        key=f"modal_txt_{file_prefix}_{url}"
    )
    
    safe_prefix = re.sub(r'[^\w\-_\.]', '_', str(file_prefix))
    safe_suffix = re.sub(r'[^\w\-]', '_', str(url)[-8:])
    st.download_button(
        f"📥 Download {doc_label} (.docx)", 
        data=generate_docx_from_markdown(doc_content), 
        file_name=f"{safe_prefix}_{safe_suffix}.docx", 
        use_container_width=True,
        type="primary",
        key=f"modal_dl_{file_prefix}_{url}"
    )

with tab_gallery:
    gallery_jobs = [j for i, j in enumerate(all_saved_jobs) if (j.get("Tailored Resume") or j.get("Cover Letter") or j.get("Interview Prep")) and (active_job_id is None or active_job_id == i)]
    
    if not gallery_jobs and active_job_id is None:
        st.info("No documents generated yet. Generate materials in the other tabs to see them here!")
    else:
        cols = st.columns(3)
        for index, job in enumerate(gallery_jobs):
            with cols[index % 3]:
                with st.container(border=True):
                    # Mimic the UI from the screenshot
                    st.subheader(f"{job.get('Score', 0)}/100")
                    st.markdown(f"**{job.get('Position', 'Role')}**")
                    st.write("") # Quick spacer
                    
                    # Helper function to render standard buttons that open the modal
                    def render_gallery_button(doc_label, doc_key, file_prefix, icon):
                        doc_content = job.get(doc_key)
                        if doc_content and str(doc_content).lower() != "nan":
                            # Use a standard button instead of a popover
                            if st.button(f"{icon} View {doc_label}", use_container_width=True, key=f"gal_btn_{file_prefix}_{job.get('URL')}"):
                                # Trigger the large modal window
                                open_document_modal(doc_label, doc_content, file_prefix, job.get('URL'))

                    # Render the buttons dynamically based on what exists in the database
                    render_gallery_button("Resume", "Tailored Resume", "Resume", "📄")
                    render_gallery_button("Cover Letter", "Cover Letter", "CoverLetter", "✉️")
                    render_gallery_button("Interview Prep", "Interview Prep", "InterviewPrep", "🎤")