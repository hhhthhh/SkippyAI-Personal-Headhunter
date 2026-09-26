import os
import time
import json
import pandas as pd
import streamlit as st
from datetime import datetime
from playwright.sync_api import sync_playwright

from scraper import scrape_job_text, scrape_universal_search_results
from evaluator import evaluate_job, tailor_resume, tailor_cover_letter, generate_interview_prep, generate_docx_from_markdown

# --- Boilerplate Constants & Helpers ---
BOILERPLATE_PROMPT = """You are an advanced automated job-matching engine and career risk analyst evaluating a candidate's master resume against a job description.

EVALUATION INSTRUCTIONS:
1. **Hard Stop Check:** Identify if the job demands an absolute legal or compliance requirement (such as an active government security clearance, specific citizenship, or mandatory active-duty status) that is completely absent from the resume. If so, set `is_eligible` to False and `match_score` to 0.
2. **Skill Matching:** Do not penalize the candidate for missing verbatim keywords if their technical projects or SOC experience imply competence (e.g., Linux, Wireshark, malware analysis, network configuration).
3. **Red Flag & Caveat Analysis:** Actively scan the job description for potential drawbacks, ambiguous expectations, unrealistic requirements, heavy on-call demands, or red flags, and detail them in the red_flags_or_caveats field."""

def load_prompt_presets() -> dict:
    if os.path.exists("prompt_presets.json"):
        try:
            with open("prompt_presets.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"Default Boilerplate": BOILERPLATE_PROMPT}

def save_prompt_presets(presets: dict):
    with open("prompt_presets.json", "w", encoding="utf-8") as f:
        json.dump(presets, f, indent=4)

def load_system_prompt() -> str:
    if os.path.exists("custom_prompt.txt"):
        with open("custom_prompt.txt", "r", encoding="utf-8") as f:
            return f.read()
    return BOILERPLATE_PROMPT

def save_system_prompt(prompt_text: str):
    with open("custom_prompt.txt", "w", encoding="utf-8") as f:
        f.write(prompt_text)

def clear_results():
    st.session_state.batch_results = []
    st.session_state.manual_result = None
    st.session_state.manual_job_text = ""

def load_history() -> set:
    if os.path.exists("job_history.txt"):
        with open("job_history.txt", "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_to_history(result_dict: dict):
    with open("job_history.txt", "a", encoding="utf-8") as f:
        f.write(f"{result_dict['URL']}\n")
    
    results = []
    if os.path.exists("job_results.json"):
        try:
            with open("job_results.json", "r", encoding="utf-8") as f:
                results = json.load(f)
        except Exception:
            pass
            
    results.append(result_dict)
    with open("job_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)

def update_job_history_field(url: str, field_name: str, content: str):
    """Updates job_results.json and writes a physical .md file for persistence."""
    # 1. Database Persistence
    if url != "Manual_Role" and os.path.exists("job_results.json"):
        try:
            with open("job_results.json", "r", encoding="utf-8") as f:
                results = json.load(f)
            for r in results:
                if r.get("URL") == url:
                    r[field_name] = content
                    break
            with open("job_results.json", "w", encoding="utf-8") as f:
                json.dump(results, f, indent=4)
        except Exception as e:
            st.error(f"Failed to update database: {e}")

    # 2. File System Persistence (.md files)
    if not os.path.exists("generated_docs"):
        os.makedirs("generated_docs")
    
    safe_name = "".join([c if c.isalnum() else "_" for c in url])[-40:]
    if url == "Manual_Role":
        safe_name = f"Manual_{int(time.time())}"
        
    prefix_map = {"Tailored Resume": "Resume", "Cover Letter": "CoverLetter", "Interview Prep": "Prep"}
    file_prefix = prefix_map.get(field_name, "Doc")
    
    if content:  # Don't save empty files on regeneration clears
        filepath = os.path.join("generated_docs", f"{file_prefix}_{safe_name}.md")
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            pass

# --- Session State Initialization ---
if "resume_text" not in st.session_state:
    default_resume = ""
    if os.path.exists("resume.md"):
        with open("resume.md", "r", encoding="utf-8") as f:
            default_resume = f.read()
    st.session_state.resume_text = default_resume

if "system_instructions" not in st.session_state:
    st.session_state.system_instructions = load_system_prompt()

if "batch_results" not in st.session_state:
    st.session_state.batch_results = []

if "manual_result" not in st.session_state:
    st.session_state.manual_result = None

if "manual_job_text" not in st.session_state:
    st.session_state.manual_job_text = ""

if "view_mode" not in st.session_state:
    st.session_state.view_mode = "scraper"

if "active_preset_name" not in st.session_state:
    active_text = st.session_state.system_instructions
    presets = load_prompt_presets()
    matched_name = "Custom / Modified"
    for name, text in presets.items():
        if text.strip() == active_text.strip():
            matched_name = name
            break
    st.session_state.active_preset_name = matched_name

# --- Prompt Callbacks ---
def do_set_active():
    current_preset = st.session_state.preset_selector
    prompt_text = st.session_state.get(f"editor_{current_preset}", BOILERPLATE_PROMPT)
    st.session_state.system_instructions = prompt_text
    save_system_prompt(prompt_text)
    st.session_state.active_preset_name = current_preset 
    st.session_state.prompt_msg = "Prompt activated!"

def do_update():
    current_preset = st.session_state.preset_selector
    prompt_text = st.session_state.get(f"editor_{current_preset}", "")
    presets = load_prompt_presets()
    presets[current_preset] = prompt_text
    save_prompt_presets(presets)
    st.session_state.prompt_msg = f"Updated '{current_preset}'!"

def do_delete():
    current_preset = st.session_state.preset_selector
    if current_preset == "Default Boilerplate":
        st.session_state.prompt_err = "Cannot delete the default template."
        return
    presets = load_prompt_presets()
    if current_preset in presets:
        del presets[current_preset]
        save_prompt_presets(presets)
    st.session_state.preset_selector = "Default Boilerplate"
    st.session_state.prompt_msg = f"Deleted '{current_preset}'!"

def do_save_new():
    new_name = st.session_state.get("new_preset_input", "").strip()
    if not new_name:
        st.session_state.prompt_err = "Please provide a valid name."
        return
    current_preset = st.session_state.preset_selector
    prompt_text = st.session_state.get(f"editor_{current_preset}", "")
    presets = load_prompt_presets()
    presets[new_name] = prompt_text
    save_prompt_presets(presets)
    st.session_state.preset_selector = new_name
    st.session_state.prompt_msg = f"Saved '{new_name}'!"

# --- Inline Document Generators (Persistent) ---
def inline_tailored_resume(item: dict):
    url = item.get("URL", "Manual_Role")
    job_text = item.get("Job Text", item.get("Summary", ""))
    cache_key = f"tailored_{url}"
    
    model_choice = st.session_state.get("model_choice", "Google Gemini (gemini-3.6-flash)")
    api_key = st.session_state.get("user_api_key", "")
    base_url = st.session_state.get("local_base_url", "")
    local_model = st.session_state.get("local_model_name", "")
    
    # Load from persistent memory if missing in active session
    if cache_key not in st.session_state and item.get("Tailored Resume"):
        st.session_state[cache_key] = item["Tailored Resume"]
        
    if cache_key not in st.session_state:
        st.write("Extract role keywords and dynamically adjust your verified background for this position.")
        if st.button("⚡ Generate Tailored Resume", key=f"btn_{cache_key}"):
            with st.spinner(f"Tailoring resume with {model_choice}..."):
                try:
                    content = tailor_resume(st.session_state.resume_text, job_text, model_choice, api_key, base_url, local_model)
                    st.session_state[cache_key] = content
                    item["Tailored Resume"] = content
                    update_job_history_field(url, "Tailored Resume", content)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to generate: {str(e)}")
    else:
        st.caption("Perform a final check, make manual adjustments if desired, and download. Changes auto-save.")
        edited_resume = st.text_area("Tailored Resume (Markdown)", value=st.session_state[cache_key], height=400, key=f"editor_{cache_key}")
        
        if edited_resume != st.session_state[cache_key]:
            st.session_state[cache_key] = edited_resume
            item["Tailored Resume"] = edited_resume
            update_job_history_field(url, "Tailored Resume", edited_resume)
            
        st.info("⚠️ **Formatting Notice:** Copy the updated bullet points from the downloaded file and paste them into your original formatted template using 'Keep Text Only'.")
        
        col1, _, col2 = st.columns([3.2, 5.8, 1.5])
        with col1:
            docx_data = generate_docx_from_markdown(edited_resume)
            safe_id = "".join([c if c.isalnum() else "_" for c in url])[-15:]
            st.download_button("📥 Download Tailored Resume (.docx)", data=docx_data, file_name=f"tailored_resume_{safe_id}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"dl_{cache_key}", type="primary")
        with col2:
            if st.button("🔄 Regenerate", key=f"regen_{cache_key}"):
                del st.session_state[cache_key]
                if "Tailored Resume" in item:
                    item["Tailored Resume"] = ""
                    update_job_history_field(url, "Tailored Resume", "")
                st.rerun()

def inline_cover_letter(item: dict):
    url = item.get("URL", "Manual_Role")
    job_text = item.get("Job Text", item.get("Summary", ""))
    cache_key = f"cover_{url}"
    
    model_choice = st.session_state.get("model_choice", "Google Gemini (gemini-3.6-flash)")
    api_key = st.session_state.get("user_api_key", "")
    base_url = st.session_state.get("local_base_url", "")
    local_model = st.session_state.get("local_model_name", "")
    
    if cache_key not in st.session_state and item.get("Cover Letter"):
        st.session_state[cache_key] = item["Cover Letter"]
        
    if cache_key not in st.session_state:
        st.write("Draft a grounded, conversational cover letter tailored specifically to this posting.")
        if st.button("✉️ Generate Cover Letter", key=f"btn_{cache_key}"):
            with st.spinner(f"Drafting cover letter with {model_choice}..."):
                try:
                    content = tailor_cover_letter(st.session_state.resume_text, job_text, model_choice, api_key, base_url, local_model)
                    st.session_state[cache_key] = content
                    item["Cover Letter"] = content
                    update_job_history_field(url, "Cover Letter", content)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to generate: {str(e)}")
    else:
        edited_cover = st.text_area("Cover Letter Content (Markdown)", value=st.session_state[cache_key], height=400, key=f"editor_{cache_key}")
        
        if edited_cover != st.session_state[cache_key]:
            st.session_state[cache_key] = edited_cover
            item["Cover Letter"] = edited_cover
            update_job_history_field(url, "Cover Letter", edited_cover)
            
        col1, _, col2 = st.columns([3.2, 5.8, 1.5])
        with col1:
            docx_data = generate_docx_from_markdown(edited_cover)
            safe_id = "".join([c if c.isalnum() else "_" for c in url])[-15:]
            st.download_button("📥 Download Cover Letter (.docx)", data=docx_data, file_name=f"cover_letter_{safe_id}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"dl_{cache_key}", type="primary")
        with col2:
            if st.button("🔄 Regenerate", key=f"regen_{cache_key}"):
                del st.session_state[cache_key]
                if "Cover Letter" in item:
                    item["Cover Letter"] = ""
                    update_job_history_field(url, "Cover Letter", "")
                st.rerun()

def inline_interview_prep(item: dict):
    url = item.get("URL", "Manual_Role")
    job_text = item.get("Job Text", item.get("Summary", ""))
    cache_key = f"prep_{url}"
    
    model_choice = st.session_state.get("model_choice", "Google Gemini (gemini-3.6-flash)")
    api_key = st.session_state.get("user_api_key", "")
    base_url = st.session_state.get("local_base_url", "")
    local_model = st.session_state.get("local_model_name", "")
    
    if cache_key not in st.session_state and item.get("Interview Prep"):
        st.session_state[cache_key] = item["Interview Prep"]
        
    if cache_key not in st.session_state:
        st.write("Build a custom interview strategy, complete with tailored questions and STAR method outlines.")
        if st.button("🎤 Generate Interview Prep", key=f"btn_{cache_key}"):
            with st.spinner(f"Building strategy with {model_choice}..."):
                try:
                    content = generate_interview_prep(st.session_state.resume_text, job_text, model_choice, api_key, base_url, local_model)
                    st.session_state[cache_key] = content
                    item["Interview Prep"] = content
                    update_job_history_field(url, "Interview Prep", content)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to generate: {str(e)}")
    else:
        edited_prep = st.text_area("Interview Prep Notes (Markdown)", value=st.session_state[cache_key], height=400, key=f"editor_{cache_key}")
        
        if edited_prep != st.session_state[cache_key]:
            st.session_state[cache_key] = edited_prep
            item["Interview Prep"] = edited_prep
            update_job_history_field(url, "Interview Prep", edited_prep)
            
        col1, _, col2 = st.columns([3.2, 5.8, 1.5])
        with col1:
            docx_data = generate_docx_from_markdown(edited_prep)
            safe_id = "".join([c if c.isalnum() else "_" for c in url])[-15:]
            st.download_button("📥 Download Prep Notes (.docx)", data=docx_data, file_name=f"interview_prep_{safe_id}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"dl_{cache_key}", type="primary")
        with col2:
            if st.button("🔄 Regenerate", key=f"regen_{cache_key}"):
                del st.session_state[cache_key]
                if "Interview Prep" in item:
                    item["Interview Prep"] = ""
                    update_job_history_field(url, "Interview Prep", "")
                st.rerun()

# --- Shared Logic Helpers ---
def process_evaluations(urls: list[str]):
    progress_bar = st.progress(0, text="Initializing evaluation pipeline...")
    total = len(urls)
    model_choice = st.session_state.get("model_choice")
    api_key = st.session_state.get("user_api_key")
    base_url = st.session_state.get("local_base_url")
    local_model = st.session_state.get("local_model_name")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        shared_page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        for i, url in enumerate(urls):
            current_status = f"Processing ({i+1}/{total}): {url}"
            progress_bar.progress(i / total, text=current_status)
            
            job_text = scrape_job_text(url, page=shared_page)
            
            if job_text.startswith("Error"):
                st.session_state.batch_results.append({
                    "URL": url,
                    "Eligible": False,
                    "Disqualification Reason": job_text,
                    "Score": 0,
                    "Summary": "Failed to scrape URL.",
                    "Matching Skills": "",
                    "Missing Skills": "",
                    "Red Flags": "",
                    "Job Text": ""
                })
            else:
                try:
                    result = evaluate_job(
                        st.session_state.resume_text, 
                        job_text, 
                        st.session_state.system_instructions, 
                        model_choice, 
                        api_key, 
                        base_url, 
                        local_model
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
                        "Job Text": job_text
                    }
                    st.session_state.batch_results.append(match_data)
                    save_to_history(match_data)
                except Exception as e:
                    st.error(f"Error evaluating {url}: {str(e)}")
                        
            progress_bar.progress((i + 1) / total, text=current_status)
            if i < total - 1:
                time.sleep(4)
                
        browser.close()
    progress_bar.progress(1.0, text="Batch processing complete!")

def render_batch_results(batch_results, min_score):
    if not batch_results: return
        
    st.markdown("---")
    st.subheader("📊 Batch Overview Table")
    
    # Fallbacks for older history entries that lack the new fields
    for item in batch_results:
        if "Timestamp" not in item:
            item["Timestamp"] = "Legacy Data"
        if "Position" not in item:
            item["Position"] = "Unknown Role"
            
    df = pd.DataFrame(batch_results)
    
    def get_assessment(row):
        if not row["Eligible"]: return "❌ Disqualified"
        if row["Score"] >= min_score: return "✅ Strong Match"
        return "⚠️ Reach"
        
    df["Assessment"] = df.apply(get_assessment, axis=1)
    
    # Display the updated columns
    st.dataframe(
        df[["Timestamp", "Position", "Assessment", "Score", "URL", "Red Flags"]], 
        use_container_width=True,
        column_config={"URL": st.column_config.LinkColumn("Source URL")}
    )
    
    export_df = df.drop(columns=["Job Text"], errors="ignore")
    st.download_button("📥 Download Full Results as CSV", data=export_df.to_csv(index=False).encode('utf-8'), file_name="job_match_results.csv", mime="text/csv")
    st.markdown("---")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("🔍 Detailed Postings")
        st.caption(f"Target Score Threshold: {min_score}+")
    with col2:
        filter_selection = st.selectbox("Filter Postings", ["All", "Strong Match", "Reach / Low Match", "Disqualified"], label_visibility="collapsed")
    
    for idx, item in enumerate(batch_results):
        if not item["Eligible"]:
            status_icon, match_label, category = "❌", "HARD BLOCKER", "Disqualified"
        elif item["Score"] >= min_score:
            status_icon, match_label, category = "✅", "STRONG MATCH", "Strong Match"
        else:
            status_icon, match_label, category = "⚠️", "REACH / LOW MATCH", "Reach / Low Match"
            
        if filter_selection != "All" and filter_selection != category:
            continue
            
        card_title = f"{status_icon} [{match_label}] Score: {item['Score']}/100 — {item['URL']}"
        
        with st.expander(card_title):
            # Unlocked: Always display all 4 tabs
            tabs = st.tabs(["Overview", "⚡ Tailor Resume", "✉️ Cover Letter", "🎤 Interview Prep"])
                
            with tabs[0]:
                if not item["Eligible"]:
                    st.error(f"**Disqualified:** {item['Disqualification Reason']}")
                elif item["Score"] < min_score:
                    st.warning(f"**Note:** This job's score ({item['Score']}) is below your target threshold of {min_score}.")
                    
                st.write(f"**Summary:** {item['Summary']}")
                
                if item["Red Flags"]:
                    st.warning("🚨 **Red Flags & Caveats:**")
                    for flag in item["Red Flags"].split(" | "):
                        st.markdown(f"- ⚠️ {flag}")
                
                if item["Eligible"]:
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**Matching Skills:**")
                        for s in item["Matching Skills"].split(", "):
                            if s: st.markdown(f"- ✅ {s}")
                    with c2:
                        st.markdown("**Missing / Gaps:**")
                        for g in item["Missing Skills"].split(", "):
                            if g: st.markdown(f"- ⚠️ {g}")

            # Unlocked: Always render the generative tools
            with tabs[1]:
                inline_tailored_resume(item)
            with tabs[2]:
                inline_cover_letter(item)
            with tabs[3]:
                inline_interview_prep(item)

# --- Streamlit UI Layout ---
st.set_page_config(page_title="Job Matcher AI", layout="wide")

st.title("🛡️ AI Job Matcher & Scraper")
st.write("Evaluate job descriptions against your master resume using AI.")

# --- Sidebar Configuration ---
st.sidebar.header("🔌 LLM Configuration")
st.session_state["model_choice"] = st.sidebar.selectbox(
    "Select AI Provider / Model",
    [
        "Google Gemini (gemini-3.6-flash)",
        "OpenAI ChatGPT (gpt-4o-mini)",
        "xAI Grok (grok-2-latest)",
        "Anthropic Claude (claude-3-5-sonnet-20241022)",
        "Local / Custom (Ollama)"
    ]
)

def confirm_api_key():
    if st.session_state.get("temp_api_key_input"):
        st.toast("API Key successfully registered!", icon="🔑")

if "Local" in st.session_state["model_choice"]:
    st.session_state["local_base_url"] = st.sidebar.text_input("Local API Base URL", value="http://localhost:11434/v1")
    st.session_state["local_model_name"] = st.sidebar.text_input("Local Model Name", value="llama3")
    st.session_state["user_api_key"] = ""
else:
    st.session_state["user_api_key"] = st.sidebar.text_input(
        "Enter API Key", 
        type="password", 
        key="temp_api_key_input",
        on_change=confirm_api_key,
        help="Works seamlessly with the selected provider."
    )

st.sidebar.markdown("---")
st.sidebar.header("🎯 Job Operations")
selected_mode = st.sidebar.radio("Select Scraper Mode", ["Manual Paste", "Multi-URL Batch Scraper", "Universal Search Auto-Scraper"], on_change=clear_results, label_visibility="collapsed")

if st.sidebar.button("▶️ Run Active Scraper Mode", type="primary", use_container_width=True):
    st.session_state.view_mode = "scraper"
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("📁 History & Analytics")
if st.sidebar.button("📂 Review Past Matches", use_container_width=True):
    st.session_state.view_mode = "history"
    st.rerun()

if st.sidebar.button("📊 Metrics & Insights", use_container_width=True):
    st.session_state.view_mode = "metrics"
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("📄 Customization")
if st.sidebar.button("Open Resume Editor", use_container_width=True):
    st.session_state.view_mode = "resume_editor"
    st.rerun()

if st.sidebar.button("Prompt Presets & History", use_container_width=True):
    st.session_state.view_mode = "prompt_editor"
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Settings & Filters")
min_score = st.sidebar.slider("Minimum Target Score", min_value=0, max_value=100, value=75, step=5)
max_jobs = st.sidebar.slider("Max Postings to Evaluate", min_value=1, max_value=100, value=1, step=1)

st.sidebar.markdown("---")
st.sidebar.subheader("💾 Data Management")
if st.sidebar.button("🗑️ Clear History", type="secondary", use_container_width=True):
    if os.path.exists("job_history.txt"): os.remove("job_history.txt")
    if os.path.exists("job_results.json"): os.remove("job_results.json")
    import shutil
    if os.path.exists("generated_docs"): shutil.rmtree("generated_docs")
    st.session_state.batch_results = []
    st.sidebar.success("History cleared!")
    time.sleep(1)
    st.rerun()

# --- Main App Routing Logic ---

if st.session_state.view_mode == "resume_editor":
    st.subheader("📄 Edit Master Resume")
    st.write("Modify and save your master resume text natively in this view:")
    updated_resume = st.text_area("Master Resume Content", value=st.session_state.resume_text, height=600)
    if st.button("Save Changes", type="primary"):
        st.session_state.resume_text = updated_resume
        with open("resume.md", "w", encoding="utf-8") as f:
            f.write(updated_resume)
        st.success("Master resume saved successfully!")

elif st.session_state.view_mode == "prompt_editor":
    st.subheader("⚙️ Prompt Presets & History")
    if "prompt_msg" in st.session_state:
        st.success(st.session_state.prompt_msg)
        del st.session_state.prompt_msg
    if "prompt_err" in st.session_state:
        st.error(st.session_state.prompt_err)
        del st.session_state.prompt_err
        
    st.info(f"**Currently Active:** {st.session_state.get('active_preset_name', 'Custom')}")
    st.write("Manage prompt presets or write custom evaluation instructions.")
    
    presets = load_prompt_presets()
    preset_names = list(presets.keys())
    
    # Streamlit natively handles the index state via the key parameter
    selected_preset = st.selectbox("Load Preset", preset_names, key="preset_selector")
    
    editor_key = f"editor_{selected_preset}"
    st.text_area("Instructions Editor", value=presets.get(selected_preset, BOILERPLATE_PROMPT), height=400, key=editor_key)
    
    col1, col2, col3, col4 = st.columns([1.3, 1, 1, 1.5])
    with col1:
        st.button("Set as Active Prompt", type="primary", use_container_width=True, on_click=do_set_active)
    with col2:
        st.button("💾 Update", use_container_width=True, on_click=do_update)
    with col3:
        st.button("🗑️ Delete", type="secondary", use_container_width=True, on_click=do_delete)
    with col4:
        st.text_input("New Preset Name", key="new_preset_input", label_visibility="collapsed", placeholder="New preset name...")
        st.button("Save as New", use_container_width=True, on_click=do_save_new)

elif st.session_state.view_mode == "history":
    st.subheader("📁 Review Past Matches")
    st.write("Browse, review, and apply to jobs you've previously scraped and evaluated.")
    
    if os.path.exists("job_results.json"):
        try:
            with open("job_results.json", "r", encoding="utf-8") as f:
                past_results = json.load(f)
            
            if past_results:
                render_batch_results(past_results[::-1], min_score)
            else:
                st.info("Your history database is currently empty.")
        except Exception as e:
            st.error(f"Error loading history data: {str(e)}")
    else:
        st.info("No past results found. Run a scraper to start building your history database!")

elif st.session_state.view_mode == "metrics":
    st.subheader("📊 Market Intelligence & Skill Analytics")
    st.write("Aggregated insights harvested from your evaluated job history to track your strongest assets and market skill gaps.")
    
    if not os.path.exists("job_results.json"):
        st.info("No job history found yet. Run a batch or search scraper to start collecting market data!")
    else:
        try:
            with open("job_results.json", "r", encoding="utf-8") as f:
                history_data = json.load(f)
                
            if not history_data:
                st.info("Your history database is currently empty.")
            else:
                from collections import Counter
                
                total_jobs = len(history_data)
                eligible_jobs = sum(1 for item in history_data if item.get("Eligible", True))
                avg_score = sum(item.get("Score", 0) for item in history_data) / total_jobs if total_jobs > 0 else 0
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Postings Analyzed", total_jobs)
                col2.metric("Eligible Matches", eligible_jobs)
                col3.metric("Average Alignment Score", f"{avg_score:.1f} / 100")
                
                st.markdown("---")
                matching_skills_list, missing_skills_list, red_flags_list = [], [], []
                
                for item in history_data:
                    if m_skills := item.get("Matching Skills", ""):
                        matching_skills_list.extend([s.strip().title() for s in m_skills.split(",") if s.strip()])
                    if mis_skills := item.get("Missing Skills", ""):
                        missing_skills_list.extend([g.strip().title() for g in mis_skills.split(",") if g.strip()])
                    if r_flags := item.get("Red Flags", ""):
                        red_flags_list.extend([rf.strip() for rf in r_flags.split("|") if rf.strip()])
                
                top_matching = Counter(matching_skills_list).most_common(10)
                top_missing = Counter(missing_skills_list).most_common(10)
                top_flags = Counter(red_flags_list).most_common(5)
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown("### ✨ Skills That Shine (Top Matches)")
                    if top_matching:
                        st.bar_chart(pd.DataFrame(top_matching, columns=["Skill", "Frequency"]).set_index("Skill"), color="#2baf2b")
                    else:
                        st.info("Not enough data recorded yet.")
                with col_b:
                    st.markdown("### ⚠️ In-Demand Gaps (Skills Needing Work)")
                    if top_missing:
                        st.bar_chart(pd.DataFrame(top_missing, columns=["Skill", "Frequency"]).set_index("Skill"), color="#ff4b4b")
                    else:
                        st.info("Not enough data recorded yet.")
                        
                st.markdown("---")
                st.subheader("🚨 Common Market Red Flags & Caveats")
                if top_flags:
                    for flag, count in top_flags:
                        st.markdown(f"- ⚠️ **({count}x occurrences)** {flag}")
                else:
                    st.info("No recurring red flags detected in current dataset.")
        except Exception as e:
            st.error(f"Error compiling metrics dashboard: {str(e)}")

else:
    # --- The Scraper View ---
    if selected_mode == "Manual Paste":
        st.subheader("📝 Manual Job Description Input")
        job_description = st.text_area("Paste Job Description Here:", height=250)
        
        if st.button("Evaluate Posting", type="primary"):
            if not job_description or not st.session_state.resume_text:
                st.warning("Please make sure both the resume and job description are provided.")
            else:
                st.session_state.manual_job_text = job_description
                with st.spinner("Analyzing alignment..."):
                    try:
                        result = evaluate_job(
                            st.session_state.resume_text, job_description, st.session_state.system_instructions,
                            st.session_state.get("model_choice"), st.session_state.get("user_api_key"),
                            st.session_state.get("local_base_url"), st.session_state.get("local_model_name")
                        )
                        st.session_state.manual_result = result
                        
                        # Fix: Save manual results to the persistent database with a unique ID
                        manual_url = f"Manual_Paste_{int(time.time())}"
                        match_data = {
                            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "Position": result.position_name,
                            "URL": manual_url,
                            "Eligible": result.is_eligible,
                            "Disqualification Reason": result.disqualification_reason,
                            "Score": result.match_score,
                            "Summary": result.summary,
                            "Matching Skills": ", ".join(result.matching_skills),
                            "Missing Skills": ", ".join(result.missing_skills),
                            "Red Flags": " | ".join(result.red_flags_or_caveats),
                            "Job Text": job_description
                        }
                        save_to_history(match_data)
                        st.session_state.manual_match_data = match_data
                        
                    except Exception as e:
                        st.error(f"Error evaluating posting: {str(e)}")
                        
        if st.session_state.get("manual_match_data"):
            match_data = st.session_state.manual_match_data
            if not match_data["Eligible"]:
                st.error(f"❌ DISQUALIFIED (Hard Stop): {match_data['Disqualification Reason']}")
            elif match_data["Score"] >= min_score:
                st.success(f"✅ STRONG MATCH: {match_data['Score']} / 100")
            else:
                st.warning(f"⚠️ REACH MATCH: {match_data['Score']} / 100 (Below {min_score} threshold)")
            
            st.subheader("Summary")
            st.write(match_data["Summary"])
            
            if match_data["Red Flags"]:
                st.warning("🚨 **Red Flags & Caveats Detected:**")
                for flag in match_data["Red Flags"].split(" | "): 
                    if flag: st.markdown(f"- ⚠️ {flag}")

            if match_data["Eligible"]:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Matching Skills:**")
                    for skill in match_data["Matching Skills"].split(", "): 
                        if skill: st.markdown(f"- ✅ {skill}")
                with col2:
                    st.markdown("**Missing / Gaps:**")
                    for gap in match_data["Missing Skills"].split(", "): 
                        if gap: st.markdown(f"- ⚠️ {gap}")
                        
            st.markdown("---")
            tabs = st.tabs(["⚡ Tailor Resume", "✉️ Cover Letter", "🎤 Interview Prep"])
            with tabs[0]: inline_tailored_resume(match_data)
            with tabs[1]: inline_cover_letter(match_data)
            with tabs[2]: inline_interview_prep(match_data)

    elif selected_mode == "Multi-URL Batch Scraper":
        st.subheader("🌐 Multi-URL Batch Scraper & Matcher")
        urls_input = st.text_area("Job URLs (one per line):", placeholder="https://example.com/job-post-1", height=150)
        
        if st.button("Scrape & Evaluate All URLs", type="primary"):
            all_urls = [u.strip() for u in urls_input.splitlines() if u.strip()]
            if not all_urls:
                st.warning("Please enter at least one valid URL.")
            elif not st.session_state.resume_text:
                st.warning("Master resume is missing.")
            else:
                st.session_state.batch_results = []
                seen_urls = load_history()
                new_urls = [u for u in all_urls if u not in seen_urls]
                skipped_count = len(all_urls) - len(new_urls)
                
                if skipped_count > 0: st.info(f"⏭️ Skipped {skipped_count} previously evaluated postings.")
                if not new_urls:
                    st.warning("All provided URLs have already been evaluated. Nothing new to scrape!")
                else:
                    if len(new_urls) > max_jobs:
                        st.info(f"Limiting evaluation to the first {max_jobs} new postings.")
                        new_urls = new_urls[:max_jobs]
                    process_evaluations(new_urls)
                    
        if st.session_state.batch_results:
            render_batch_results(st.session_state.batch_results, min_score)

    elif selected_mode == "Universal Search Auto-Scraper":
        st.subheader("🔍 Universal Search Page Auto-Scraper")
        search_url = st.text_input("Search URL:", placeholder="https://builtin.com/jobs/cyber-security/entry-level")
        
        if st.button("Auto-Discover & Evaluate Jobs", type="primary"):
            if not search_url or not st.session_state.resume_text:
                st.warning("Please ensure both a valid search URL and Master Resume are provided.")
            else:
                with st.spinner("Harvesting job posting links..."):
                    discovered_urls = scrape_universal_search_results(search_url)
                    
                if not discovered_urls:
                    st.warning("No job posting links could be automatically extracted from this search page.")
                else:
                    st.session_state.batch_results = []
                    seen_urls = load_history()
                    new_urls = [u for u in discovered_urls if u not in seen_urls]
                    skipped_count = len(discovered_urls) - len(new_urls)
                    
                    if skipped_count > 0: st.info(f"⏭️ Skipped {skipped_count} that were previously evaluated.")
                    if not new_urls:
                        st.warning("All discovered jobs on this page have already been evaluated.")
                    else:
                        if len(new_urls) > max_jobs: new_urls = new_urls[:max_jobs]
                        process_evaluations(new_urls)
                    
        if st.session_state.batch_results:
            render_batch_results(st.session_state.batch_results, min_score)