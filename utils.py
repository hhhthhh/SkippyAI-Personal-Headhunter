import os
import streamlit as st
from dotenv import load_dotenv, set_key
import streamlit.components.v1 as components
from pipeline import pipeline_manager

ENV_FILE = ".env"

def secure_file_permissions(filepath: str):
    """Restricts file permissions to user-read/write only (0600)."""
    if os.path.exists(filepath):
        try:
            os.chmod(filepath, 0o600)
        except OSError:
            pass

if not os.path.exists(ENV_FILE):
    try:
        with open(ENV_FILE, 'a', encoding="utf-8") as f:
            pass
    except OSError:
        pass
secure_file_permissions(ENV_FILE)

load_dotenv(ENV_FILE)

def load_local_config():
    return os.environ.get("USER_API_KEY", "")

def save_local_config(api_key):
    try:
        set_key(ENV_FILE, "USER_API_KEY", api_key)
    except OSError:
        # Fallback for Docker single-file bind mounts where os.replace raises EBUSY (Errno 16)
        lines = []
        if os.path.exists(ENV_FILE):
            try:
                with open(ENV_FILE, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except OSError:
                lines = []
        escaped_val = api_key.replace("\\", "\\\\").replace("'", "\\'")
        new_line = f"USER_API_KEY='{escaped_val}'\n"
        updated = False
        for i, line in enumerate(lines):
            if line.lstrip().startswith("USER_API_KEY="):
                lines[i] = new_line
                updated = True
                break
        if not updated:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(new_line)
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines)
    os.environ["USER_API_KEY"] = api_key
    secure_file_permissions(ENV_FILE)

def render_help_content():
    st.markdown("**🔑 Acquiring API Keys**")
    st.markdown("NOTE: We recommend using Google Gemini as it has been extensively tested, works the best, and is free to use!")
    st.markdown(
        "- **Google Gemini:** [Google AI Studio](https://aistudio.google.com/app/apikey)\n"
        "- **OpenAI ChatGPT:** [OpenAI Platform](https://platform.openai.com/api-keys)\n"
        "- **Anthropic Claude:** [Anthropic Console](https://console.anthropic.com/settings/keys)\n"
        "- **xAI Grok:** [xAI Console](https://console.x.ai/)"
    )
    st.markdown("---")
    st.markdown("**📊 Using the Pipeline**")
    st.markdown(
        "- **Focus Mode:** Click any checkbox in the Overview Table to instantly jump to that job's details.\n"
        "- **Status Tracking:** Changing a job's status automatically color-codes your pipeline table."
    )
    st.markdown("---")
    st.markdown("**⚠️ Formatting Notice**")
    st.markdown("When downloading a tailored resume, paste the newly generated bullet points into your stylized Word template using **'Keep Text Only'**.")
    st.markdown("---")
    st.markdown("**🌐 Supported Job Sites & Scraping Guide**")
    st.markdown(
        "- **Supported Job Site:** **Built In** (`builtin.com`) is officially verified for automated searching and scraping.\n"
        "- **LinkedIn:** Use Skippy's official browser extension (see the LinkedIn Evaluator tab) to send postings directly to Skippy with 1 click!\n"
        "- **Other Job Sites (Indeed, Glassdoor, Workday, etc.):** Use **Paste a Job Description** for instant AI evaluation on any posting."
    )

def render_help_section(in_sidebar=True):
    if in_sidebar:
        with st.sidebar.expander("❓ Help & Setup Guide"):
            render_help_content()
    else:
        with st.expander("❓ Help & Setup Guide"):
            render_help_content()

def initialize_core_state():
    # 1. Load Resume from disk
    if "resume_text" not in st.session_state:
        default_resume = ""
        if os.path.exists("resume.md"):
            secure_file_permissions("resume.md")
            try:
                with open("resume.md", "r", encoding="utf-8") as f:
                    default_resume = f.read()
            except Exception:
                pass
        st.session_state.resume_text = default_resume

    # 2. Load System Instructions from disk so all pages (Scraper, LinkedIn, etc.) have it
    if "system_instructions" not in st.session_state:
        default_instructions = "You are an advanced automated job-matching engine..."
        if os.path.exists("custom_prompt.txt"):
            try:
                with open("custom_prompt.txt", "r", encoding="utf-8") as f:
                    default_instructions = f.read()
            except Exception:
                pass
        st.session_state.system_instructions = default_instructions
        
    if "model_choice" not in st.session_state:
        st.session_state["model_choice"] = "Google Gemini"

    # 3. Load API Key from disk BEFORE the gatekeeper checks it
    if "user_api_key" not in st.session_state or not st.session_state.user_api_key:
        st.session_state.user_api_key = load_local_config()

def check_and_handle_pipeline_completion() -> bool:
    """
    Checks if a background evaluation pipeline has finished.
    If so, consumes the batch, updates session state, displays a toast,
    and triggers an immediate full-app rerun so completion cards render without user action.
    Returns True if a completion was handled.
    """
    status = pipeline_manager.get_status()
    if status.get("has_unnotified_completion"):
        batch = pipeline_manager.consume_completed_batch()
        if batch:
            if batch.get("jobs"):
                st.session_state["completion_batch"] = batch
                count = len(batch["jobs"])
                src = batch.get("source", "Pipeline")
                st.toast(f"🎉 Evaluation Complete! {count} job{'s' if count != 1 else ''} evaluated from {src}.", icon="✅")
            elif batch.get("failed", 0) > 0:
                err_msg = f": {batch['last_error']}" if batch.get("last_error") else ""
                st.toast(f"⚠️ Evaluation finished with {batch['failed']} failed job(s){err_msg}.", icon="⚠️")
            st.rerun()
            return True
    return False

@st.fragment(run_every="2s")
def render_global_pipeline_status():
    check_and_handle_pipeline_completion()
    status = pipeline_manager.get_status()

    # 1. If pipeline is running, render a live card in the sidebar
    if status.get("is_running"):
        with st.sidebar.container(border=True):
            st.markdown("⚡ **Evaluation In Progress**")
            total = max(status.get("total", 1), 1)
            completed = status.get("completed", 0)
            prog = min(completed / total, 1.0)

            cur = status.get("current_job", "Working...")
            if len(cur) > 35:
                cur = cur[:32] + "..."
            st.progress(prog, text=f"{completed}/{status.get('total', 1)} evaluated")
            st.caption(f"📍 `{cur}`")
            st.caption("💡 *You can navigate to any other page while this runs.*")
            if st.button("🛑 Cancel Pipeline", key="btn_cancel_global_pipeline", use_container_width=True):
                pipeline_manager.cancel()
                st.rerun()

    # 3. If a completion batch exists, show a quick action card in the sidebar
    elif "completion_batch" in st.session_state and st.session_state["completion_batch"].get("jobs"):
        batch = st.session_state["completion_batch"]
        count = len(batch.get("jobs", []))
        src = batch.get("source", "Pipeline")
        with st.sidebar.container(border=True):
            st.success(f"🎉 **{count}** jobs ready ({src})!")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📂 History", key="sb_view_hist", use_container_width=True):
                    st.session_state["active_history_source"] = src
                    st.switch_page("pages/2_history.py")
            with col2:
                if st.button("Dismiss", key="sb_dismiss_batch", use_container_width=True):
                    del st.session_state["completion_batch"]
                    pipeline_manager.dismiss_latest_run()
                    st.rerun()

def setup_sidebar():
    initialize_core_state()

    has_key = bool(st.session_state.get("user_api_key")) or ("Local" in st.session_state.get("model_choice", ""))
    has_resume = bool(st.session_state.get("resume_text", "").strip())
    
    if not (has_key and has_resume):
        return

    st.markdown(
        """
        <style>
        [data-testid="stSidebarNav"] span {
            font-size: 1.15rem !important;
            font-weight: 500 !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    render_global_pipeline_status()

    st.sidebar.header("🔌 LLM Configuration")
    
    model_options = ["Google Gemini", "OpenAI ChatGPT", "xAI Grok", "Anthropic Claude", "Local / Custom (Ollama)"]
    st.session_state["model_choice"] = st.sidebar.selectbox(
        "Select AI Provider",
        model_options,
        index=model_options.index(st.session_state.get("model_choice", "Google Gemini"))
    )

    st.session_state["model_override"] = st.sidebar.text_input(
        "Model Version Override (Optional)", 
        value=st.session_state.get("model_override", ""),
        help="Leave blank for defaults. Example: 'gemini-4.5-pro' or 'gpt-5'."
    )

    def confirm_api_key():
        if st.session_state.get("temp_api_key_input"):
            st.toast("API Key successfully registered!", icon="🔑")

    if "Local" in st.session_state["model_choice"]:
        st.session_state["local_base_url"] = st.sidebar.text_input("Local API Base URL", value="http://localhost:11434/v1")
        st.session_state["local_model_name"] = st.sidebar.text_input("Local Model Name", value="llama3")
    else:
        current_key = st.session_state.get("user_api_key", "")
        updated_key = st.sidebar.text_input(
            "Enter API Key", 
            value=current_key,
            type="password", 
            key="temp_api_key_input",
            on_change=confirm_api_key,
            help="Works seamlessly with the selected provider."
        )
        
        if updated_key and updated_key != current_key:
            save_local_config(updated_key)
            st.session_state["user_api_key"] = updated_key
            st.session_state["show_key_success"] = True
            st.rerun()

        if st.session_state.get("show_key_success"):
            st.sidebar.success("Key Accepted! ✅")
            components.html(
                """
                <script>
                try {
                    setTimeout(function() {
                        const alerts = window.parent.document.querySelectorAll('[data-testid="stAlert"]');
                        alerts.forEach(alert => {
                            if (alert.innerText.includes("Key Accepted!")) {
                                alert.style.display = "none";
                            }
                        });
                    }, 10000);
                } catch (e) {
                    // Browser iframe restrictions gracefully handled
                }
                </script>
                """,
                height=0
            )
            st.session_state["show_key_success"] = False

    render_help_section(in_sidebar=True)

def enforce_onboarding():
    has_key = bool(st.session_state.get("user_api_key")) or ("Local" in st.session_state.get("model_choice", ""))
    has_resume = bool(st.session_state.get("resume_text", "").strip())
    
    if not (has_key and has_resume):
        st.markdown(
            """
            <style>
                [data-testid="stSidebar"] { display: none; }
                [data-testid="collapsedControl"] { display: none; }
            </style>
            """,
            unsafe_allow_html=True
        )
    
    if not has_key:
        st.title("Welcome to Skippy! 🦘")
        st.subheader("Step 1 of 2: Connect Your AI Provider")
        st.write("Before analyzing job postings, let's connect your local CRM to an AI provider.")
        st.info("NOTE: We recommend using Google Gemini as it has been extensively tested, works best, and is free to use!", icon="ℹ️")
        
        model_options = ["Google Gemini", "OpenAI ChatGPT", "xAI Grok", "Anthropic Claude", "Local / Custom (Ollama)"]
        selected_model = st.selectbox("Select AI Provider", model_options, index=0)
        st.session_state["model_choice"] = selected_model
        
        if "Local" in selected_model:
            local_base = st.text_input("Local API Base URL", value="http://localhost:11434/v1")
            local_model = st.text_input("Local Model Name", value="llama3")
            if st.button("Save & Continue 🚀", type="primary"):
                st.session_state["local_base_url"] = local_base
                st.session_state["local_model_name"] = local_model
                st.session_state["show_key_success"] = True
                st.rerun()
        else:
            api_key = st.text_input("Enter API Key", type="password", help="Get a free key from Google AI Studio")
            if st.button("Save & Continue 🚀", type="primary"):
                if api_key.strip():
                    save_local_config(api_key.strip())
                    st.session_state["user_api_key"] = api_key.strip()
                    st.session_state["show_key_success"] = True
                    st.rerun()
                else:
                    st.warning("Please enter a valid API key.")
        
        st.markdown("---")
        render_help_section(in_sidebar=False)
        st.stop()

    if not has_resume:
        st.title("Welcome to Skippy! 🦘")
        st.subheader("Step 2 of 2: Add Your Master Resume")
        st.write(
            "Skippy matches job postings against your real background and generates tailored materials. "
            "Paste your complete master resume below in plain text or Markdown to finish onboarding."
        )

        with st.form("onboarding_resume_form"):
            initial_resume = st.text_area(
                "Master Resume (Markdown or Plain Text):",
                height=400,
                placeholder="# Hayden Tanaka\n\n## Experience\n- Security Operations Center Analyst...",
                help="Include your full work history, projects, and skills."
            )
            saved = st.form_submit_button("Complete Setup & Start Matching 🚀", type="primary")
            
            if saved:
                if not initial_resume.strip():
                    st.warning("Please paste your resume before proceeding.")
                else:
                    st.session_state.resume_text = initial_resume
                    with open("resume.md", "w", encoding="utf-8") as f:
                        f.write(initial_resume)
                    secure_file_permissions("resume.md")
                    st.success("Master resume saved! Initializing dashboard...")
                    st.rerun()
                    
        st.markdown("---")
        render_help_section(in_sidebar=False)
        st.stop()

def render_completion_card(batch_jobs: list[dict], source_label: str = "Scraper"):
    """
    Renders an accessible completion card summarizing the recent evaluation run.
    Gives the user full agency to review highlights before transitioning to History.
    """
    if not batch_jobs:
        return

    from datetime import datetime

    with st.container(border=True):
        st.subheader("🎉 Evaluation Complete!")
        total = len(batch_jobs)
        strong = sum(1 for j in batch_jobs if j.get("Score", 0) >= 75 and j.get("Eligible", True))
        reach = sum(1 for j in batch_jobs if j.get("Score", 0) < 75 and j.get("Eligible", True))
        disqualified = sum(1 for j in batch_jobs if not j.get("Eligible", True))

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Postings Evaluated", total)
        m2.metric("Strong Matches", strong)
        m3.metric("Reach Roles", reach)
        m4.metric("Disqualified", disqualified)

        st.markdown("#### 📋 Findings Summary")
        for job in batch_jobs:
            score = job.get("Score", 0)
            eligible = job.get("Eligible", True)
            if not eligible:
                badge = "❌ Disqualified"
                detail = f"Hard blocker: {job.get('Disqualification Reason', 'Requirement not met')}"
            elif score >= 75:
                badge = "✅ Strong Match"
                detail = f"Score: {score}/100"
            else:
                badge = "⚠️ Reach"
                detail = f"Score: {score}/100"

            pos = job.get("Position", "Unknown Position")
            st.markdown(f"- **{pos}** — `{badge}` ({detail})")
            if job.get("Summary"):
                st.caption(f"> {job['Summary']}")

        st.markdown("")
        col_btn1, col_btn2 = st.columns([1.6, 1])
        with col_btn1:
            if st.button("👉 View in History & Tailor Documents 🚀", type="primary", use_container_width=True, key=f"view_hist_{source_label}"):
                st.session_state["latest_batch_info"] = {
                    "source": source_label,
                    "urls": [j.get("URL") for j in batch_jobs],
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                st.session_state["active_history_source"] = source_label
                if "completion_batch" in st.session_state:
                    del st.session_state["completion_batch"]
                st.switch_page("pages/2_history.py")
        with col_btn2:
            if st.button("➕ Evaluate More Postings", use_container_width=True, key=f"eval_more_{source_label}"):
                if "completion_batch" in st.session_state:
                    del st.session_state["completion_batch"]
                st.rerun()