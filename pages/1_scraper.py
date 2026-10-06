import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

from utils import setup_sidebar, enforce_onboarding
import database as db
from scraper import scrape_job_text, scrape_universal_search_results
from evaluator import evaluate_job, tailor_resume, tailor_cover_letter, generate_interview_prep, generate_docx_from_markdown

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
min_score = st.sidebar.slider("Minimum Target Score", min_value=0, max_value=100, value=75, step=5)
max_jobs = st.sidebar.slider("Max Postings to Evaluate", min_value=1, max_value=50, value=5, step=1)

@st.fragment
def document_generator(item: dict, doc_type: str, generator_func):
    """Handles on-the-fly document generation directly inside the scraper cards."""
    url, job_text = item.get("URL"), item.get("Job Text", "")
    cache_key = f"{doc_type}_{url}"
    
    if cache_key not in st.session_state and item.get(doc_type):
        st.session_state[cache_key] = item[doc_type]
        
    if not st.session_state.get(cache_key):
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
        edited_doc = st.text_area(f"{doc_type} (Markdown)", value=st.session_state[cache_key], height=400, key=f"editor_{cache_key}")
        if edited_doc != st.session_state[cache_key]:
            st.session_state[cache_key] = edited_doc
            db.update_job_field(url, doc_type, edited_doc)
            
        col1, _, col2 = st.columns([3.2, 5.8, 1.5])
        with col1:
            st.download_button("📥 Download (.docx)", data=generate_docx_from_markdown(edited_doc), file_name=f"{doc_type.replace(' ', '_')}.docx", type="primary", key=f"dl_{cache_key}")
        with col2:
            if st.button("🔄 Regenerate", key=f"regen_{cache_key}"):
                del st.session_state[cache_key]
                db.update_job_field(url, doc_type, "")
                st.rerun()

def render_evaluation_card(match_data: dict):
    """Renders the evaluation inside an expander exactly like the History page."""
    score = match_data.get("Score", 0)
    eligible = match_data.get("Eligible", True)
    status_icon = "❌" if not eligible else ("✅" if score >= min_score else "⚠️️")
    
    with st.expander(f"{status_icon} Score: {score}/100 — {match_data.get('Position', 'Job Posting')}", expanded=True):
        tabs = st.tabs(["Overview", "⚡ Tailor Resume", "✉ Cover Letter", "🎤 Interview Prep"])
        
        with tabs[0]:
            if not eligible:
                st.error(f"❌ **DISQUALIFIED (Hard Blocker):** {match_data.get('Disqualification Reason', 'Requirement missing')}")
            elif score >= min_score:
                st.success(f"✅ **STRONG MATCH:** {score} / 100")
            else:
                st.warning(f"⚠️ **REACH MATCH:** {score} / 100 (Below target threshold of {min_score})")

            st.write(f"**Summary:** {match_data.get('Summary', '')}")

            if match_data.get("Red Flags"):
                st.warning("🚨 **Red Flags & Caveats:**")
                for flag in match_data["Red Flags"].split(" | "):
                    if flag.strip():
                        st.markdown(f"- ⚠️ {flag.strip()}")

            if eligible:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Matching Skills:**")
                    for skill in match_data.get("Matching Skills", "").split(", "):
                        if skill.strip():
                            st.markdown(f"- ✅ {skill.strip()}")
                with col2:
                    st.markdown("**Missing Skills / Gaps:**")
                    for gap in match_data.get("Missing Skills", "").split(", "):
                        if gap.strip():
                            st.markdown(f"- ⚠ {gap.strip()}")
                            
        with tabs[1]:
            document_generator(match_data, "Tailored Resume", tailor_resume)
        with tabs[2]:
            document_generator(match_data, "Cover Letter", tailor_cover_letter)
        with tabs[3]:
            document_generator(match_data, "Interview Prep", generate_interview_prep)

def process_evaluations(urls: list[str]):
    progress_bar = st.progress(0, text="Initializing evaluation pipeline...")
    total = len(urls)
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        shared_page = browser.new_page()
        
        for i, url in enumerate(urls):
            progress_bar.progress(i / total, text=f"Evaluating ({i+1}/{total}): {url}")
            job_text = scrape_job_text(url, page=shared_page)
            
            if not job_text.startswith("Error"):
                try:
                    result = evaluate_job(
                        st.session_state.resume_text, job_text, st.session_state.system_instructions, 
                        st.session_state.get("model_choice"), st.session_state.get("user_api_key"), 
                        st.session_state.get("local_base_url"), st.session_state.get("local_model_name")
                    )
                    match_data = {
                        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "Position": result.position_name,
                        "URL": url,
                        "Eligible": result.is_eligible,
                        "Disqualification Reason": result.disqualification_reason,
                        "Score": result.match_score,
                        "Summary": result.summary,
                        "Matching Skills": ", ".join(result.matching_skills),
                        "Missing Skills": ", ".join(result.missing_skills),
                        "Red Flags": " | ".join(result.red_flags_or_caveats),
                        "Job Text": job_text,
                        "Application Status": "Not Applied"
                    }
                    db.save_job_result(match_data)
                    results.append(match_data)
                    st.toast(f"Evaluated {result.position_name} ({result.match_score}/100)", icon="✅")
                except Exception as e:
                    st.toast(f"Issue on {url}: {e}", icon="⚠️")
                    print(f"[Skippy Warning] {url} failed with: {e}")
                        
            progress_bar.progress((i + 1) / total)
            if i < total - 1:
                time.sleep(3)
                
        browser.close()
        
    progress_bar.progress(1.0, text="Processing complete!")
    st.session_state.latest_batch_results = results

selected_mode = st.radio(
    "Select Scraper Mode", 
    ["Manual Paste", "Multi-URL Batch Scraper", "Universal Search Auto-Scraper"], 
    horizontal=True
)
st.markdown("---")

if selected_mode == "Manual Paste":
    st.subheader("📝 Manual Job Description Input")
    with st.form("manual_paste_form"):
        job_description = st.text_area(
            "Paste Job Description Here:", 
            height=250, 
            help="Press Ctrl+Enter to evaluate"
        )
        submitted = st.form_submit_button("Evaluate Posting", type="primary")

    if submitted:
        if not job_description.strip() or not st.session_state.resume_text.strip():
            st.warning("Please provide both the master resume and job description.")
        else:
            with st.spinner("Analyzing alignment with AI..."):
                try:
                    result = evaluate_job(
                        st.session_state.resume_text, job_description, st.session_state.system_instructions,
                        st.session_state.get("model_choice"), st.session_state.get("user_api_key"),
                        st.session_state.get("local_base_url"), st.session_state.get("local_model_name")
                    )
                    match_data = {
                        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "Position": result.position_name,
                        "URL": f"Manual_Paste_{int(time.time())}",
                        "Eligible": result.is_eligible,
                        "Disqualification Reason": result.disqualification_reason,
                        "Score": result.match_score,
                        "Summary": result.summary,
                        "Matching Skills": ", ".join(result.matching_skills),
                        "Missing Skills": ", ".join(result.missing_skills),
                        "Red Flags": " | ".join(result.red_flags_or_caveats),
                        "Job Text": job_description,
                        "Application Status": "Not Applied"
                    }
                    db.save_job_result(match_data)
                    st.session_state.latest_manual_result = match_data
                except Exception as e:
                    st.error(f"Error evaluating posting: {e}")

    if st.session_state.get("latest_manual_result"):
        render_evaluation_card(st.session_state.latest_manual_result)

elif selected_mode == "Multi-URL Batch Scraper":
    st.subheader("🌐 Multi-URL Batch Scraper")
    with st.form("batch_url_form"):
        urls_input = st.text_area(
            "Job URLs (one per line):", 
            height=150, 
            help="Press Ctrl+Enter to evaluate"
        )
        submitted = st.form_submit_button("Scrape & Evaluate All URLs", type="primary")
        
    if submitted:
        all_urls = [u.strip() for u in urls_input.splitlines() if u.strip()]
        if not all_urls:
            st.warning("Please enter at least one valid URL.")
        else:
            seen_urls = db.load_job_urls()
            new_urls = [u for u in all_urls if u not in seen_urls]
            skipped = len(all_urls) - len(new_urls)
            if skipped > 0:
                st.info(f"⏭ Skipped {skipped} previously evaluated postings.")
            if not new_urls:
                st.warning("All provided URLs have already been evaluated. Check your History tab!")
            else:
                process_evaluations(new_urls[:max_jobs])

    if st.session_state.get("latest_batch_results"):
        st.markdown("---")
        st.subheader("📊 Recent Evaluations")
        for item in st.session_state.latest_batch_results:
            render_evaluation_card(item)

elif selected_mode == "Universal Search Auto-Scraper":
    st.subheader("🔍 Universal Search Page Auto-Scraper")
    with st.form("search_form"):
        search_url = st.text_input(
            "Search URL:", 
            value="https://builtin.com/jobs/cyber-security/entry-level"
        )
        submitted = st.form_submit_button("Auto-Discover & Evaluate Jobs", type="primary")
        
    if submitted:
        if not search_url.strip():
            st.warning("Please provide a search URL.")
        else:
            with st.spinner("Harvesting job posting links..."):
                discovered_urls = scrape_universal_search_results(search_url)
            if not discovered_urls:
                st.warning("No job posting links could be extracted from this page.")
            else:
                seen_urls = db.load_job_urls()
                new_urls = [u for u in discovered_urls if u not in seen_urls]
                skipped = len(discovered_urls) - len(new_urls)
                if skipped > 0:
                    st.info(f"⏭️ Skipped {skipped} previously evaluated postings.")
                if not new_urls:
                    st.warning("All discovered jobs on this page have already been evaluated. Check your History tab!")
                else:
                    process_evaluations(new_urls[:max_jobs])

    if st.session_state.get("latest_batch_results"):
        st.markdown("---")
        st.subheader("📊 Recent Evaluations")
        for item in st.session_state.latest_batch_results:
            render_evaluation_card(item)