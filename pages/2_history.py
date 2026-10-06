import streamlit as st
import pandas as pd
import os
import time

from utils import setup_sidebar, enforce_onboarding
import database as db
from evaluator import tailor_resume, tailor_cover_letter, generate_interview_prep, generate_docx_from_markdown

st.subheader("📁 Review Past Matches")

# Data Management tools tucked neatly at the top
if st.button("🗑️ Clear Entire History", type="secondary"):
    db.clear_all_history()
    st.rerun()

batch_results = db.load_all_jobs()
if not batch_results:
    st.info("Your history database is currently empty. Run the Scraper to get started!")
    st.stop()

filter_col, metric_col, _ = st.columns([3, 2, 5])
with filter_col:
    filter_selection = st.selectbox("Filter by Assessment:", ["All", "Strong Match", "Reach / Low Match", "Disqualified"])
with metric_col:
    st.metric("Total Postings Crawled", len(batch_results))

df = pd.DataFrame(batch_results)
df["Original_Index"] = df.index 

def get_assessment(row):
    if not row["Eligible"]: return "❌ Disqualified"
    if row["Score"] >= 75: return "✅ Strong Match" # Assuming 75 is a default target threshold
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

selection_event = st.dataframe(styled_df, width="stretch", on_select="rerun", selection_mode="single-row", column_config={"URL": st.column_config.LinkColumn("Source URL")})

active_job_id = int(df.iloc[selection_event.selection.rows[0]]["Original_Index"]) if selection_event.selection.rows else None

st.markdown("---")
# 1. Add the anchor ID to the subheader so the browser knows where to scroll
st.subheader("🔍 Detailed Postings", anchor="details")

# 2. Inject the smooth-scroll JavaScript if a job is actively selected
if active_job_id is not None:
    import streamlit.components.v1 as components
    import time
    
    # The hidden timestamp forces Streamlit to treat this as a brand new script every click
    components.html(
        f"<script>window.parent.document.getElementById('details').scrollIntoView({{behavior: 'smooth'}}); /* {time.time()} */</script>",
        height=0
    )

def application_status_tracker(item: dict):
    url = item.get("URL")
    statuses = ["Not Applied", "Applied", "Interviewing", "Waitlisted", "Rejected", "Offer"]
    current = item.get("Application Status", "Not Applied")
    
    def on_status_change():
        new_status = st.session_state[f"status_tracker_{url}"]
        db.update_job_field(url, "Application Status", new_status)
        st.rerun()
        
    st.selectbox("Status", options=statuses, index=statuses.index(current) if current in statuses else 0, key=f"status_tracker_{url}", on_change=on_status_change, label_visibility="collapsed")

@st.fragment
def document_generator(item: dict, doc_type: str, generator_func):
    url, job_text = item.get("URL"), item.get("Job Text", "")
    cache_key = f"{doc_type}_{url}"
    
    # 1. Safely pull existing content from DB, forcing None/NaN to an empty string
    db_content = item.get(doc_type)
    if not db_content or str(db_content).lower() == "nan":
        db_content = ""
        
    # 2. Sync to session state to ensure Streamlit always has a valid string
    if cache_key not in st.session_state:
        st.session_state[cache_key] = db_content
        
    current_content = st.session_state[cache_key]
    
    # 3. If there is no content, show the Generate button
    if not current_content:
        if st.button(f"⚡ Generate {doc_type}", key=f"btn_{cache_key}"):
            with st.spinner(f"Generating {doc_type}..."):
                content = generator_func(
                    st.session_state.resume_text, job_text, st.session_state.get("model_choice"), 
                    st.session_state.get("user_api_key"), st.session_state.get("local_base_url"), st.session_state.get("local_model_name")
                )
                st.session_state[cache_key] = content
                import database as db
                db.update_job_field(url, doc_type, content)
                
                # Because we are in a fragment, this st.rerun() safely reloads JUST the tab!
                st.rerun()
                
    # 4. If content exists, show the Markdown editor and download options
    else:
        edited_doc = st.text_area(f"{doc_type} (Markdown)", value=current_content, height=400, key=f"editor_{cache_key}")
        
        if edited_doc != current_content:
            st.session_state[cache_key] = edited_doc
            import database as db
            db.update_job_field(url, doc_type, edited_doc)
            
        col1, _, col2 = st.columns([3.2, 5.8, 1.5])
        with col1:
            st.download_button("📥 Download (.docx)", data=generate_docx_from_markdown(edited_doc), file_name=f"{doc_type.replace(' ', '_')}.docx", type="primary", key=f"dl_{cache_key}")
        with col2:
            if st.button("🔄 Regenerate", key=f"regen_{cache_key}"):
                st.session_state[cache_key] = ""
                import database as db
                db.update_job_field(url, doc_type, "")
                st.rerun()

for idx, item in enumerate(batch_results):
    if active_job_id is not None and active_job_id != idx: continue
    
    # If a filter is applied, skip drawing any job that was removed from the dataframe
    if filter_selection != "All" and idx not in df["Original_Index"].values: 
        continue
        
    status_icon = "❌" if not item["Eligible"] else ("✅" if item["Score"] >= 75 else "⚠️")
    with st.expander(f"{status_icon} Score: {item['Score']}/100 — {item['URL']}", expanded=(active_job_id == idx)):
        tabs = st.tabs(["Overview", "⚡ Tailor Resume", "✉️️ Cover Letter", "🎤 Interview Prep"])
        with tabs[0]:
                    c1, c2, _ = st.columns([1.2, 2.0, 6.8])
                    if item["URL"].startswith("http"): c1.link_button("🚀 Apply to this Job", item["URL"], type="primary")
                    with c2: application_status_tracker(item)
                    st.write(f"**Summary:** {item['Summary']}")
                    
                    if item["Red Flags"]:
                        st.warning("🚨 **Red Flags:**")
                        for f in item["Red Flags"].split(" | "): 
                            if f.strip():
                                # Added the proper color emoji here
                                st.markdown(f"- ⚠️ {f.strip()}")
                    
                    if item.get("Eligible"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("**Matching Skills:**")
                            for skill in item.get("Matching Skills", "").split(", "):
                                if skill.strip():
                                    st.markdown(f"- ✅ {skill.strip()}")
                        with col2:
                            st.markdown("**Missing Skills / Gaps:**")
                            for gap in item.get("Missing Skills", "").split(", "):
                                if gap.strip():
                                    # Swapped the text-symbol for the color emoji here
                                    st.markdown(f"- ⚠️️ {gap.strip()}")
        with tabs[1]:
            document_generator(item, "Tailored Resume", tailor_resume)
        with tabs[2]:
            document_generator(item, "Cover Letter", tailor_cover_letter)
        with tabs[3]:
            document_generator(item, "Interview Prep", generate_interview_prep)
                    