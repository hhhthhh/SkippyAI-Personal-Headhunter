import os
import io
import json
import re
import streamlit as st
from dotenv import load_dotenv, set_key
from pipeline import pipeline_manager
from auth import enforce_authentication, render_sidebar_auth_controls, logout_user

from database import (
    secure_file_permissions,
    atomic_write_text,
    atomic_write_json,
    set_env_var_safe,
    save_user_profile,
    load_user_profile,
    get_setting,
    set_setting,
    is_onboarding_completed,
    mark_onboarding_completed,
    reset_onboarding_status,
)
import career_compass
from sample_data import SAMPLE_RESUMES, SAMPLE_JOBS, test_ai_connection

ENV_FILE = ".env"
RESUMES_FILE = "resumes.json"
CUSTOM_PROMPT_FILE = "custom_prompt.txt"
CUSTOM_USER_PROMPT_FILE = "custom_user_prompt.txt"
CUSTOM_PROMPT_TEMPLATE_FILE = "custom_prompt.template.txt"
PROMPT_MODE_SETTING = "prompt_mode"
PROMPT_MODE_COMPASS = "compass"
PROMPT_MODE_CUSTOM = "custom"

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
    set_env_var_safe("USER_API_KEY", api_key, env_file=ENV_FILE)

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
        "- **🔎 Native Job Board Search (Free, No Key Required):** Search **LinkedIn** (via public guest endpoints) and **FreeHire** (global tech job aggregator) directly inside Skippy by role, location, workplace mode, and recency.\n"
        "- **🏢 Built In & Direct URLs:** **Built In** (`builtin.com`) and direct **LinkedIn** job URLs (`linkedin.com/jobs/view/...`) are supported for automated scraping in Multi-URL and Universal Search.\n"
        "- **🧩 LinkedIn Evaluator (Fallback):** Tucked under **Scraper** in the sidebar. Use Skippy's browser extension as a fallback if LinkedIn rate-limits guest requests or when you want to send postings with 1 click while browsing logged-in.\n"
        "- **🛡️ Posting Guard Security:** All scraped and pasted postings are deterministically sanitized to remove hidden HTML prompt-injection blocks and invisible Unicode tampering before reaching your AI provider."
    )

def render_help_section(in_sidebar=True):
    if in_sidebar:
        with st.sidebar.expander("❓ Help & Setup Guide"):
            render_help_content()
    else:
        with st.expander("❓ Help & Setup Guide"):
            render_help_content()

def load_resumes() -> dict[str, str]:
    """Loads all named resumes from `resumes.json`, migrating `resume.md` automatically if needed."""
    resumes: dict[str, str] = {}
    if os.path.exists(RESUMES_FILE):
        secure_file_permissions(RESUMES_FILE)
        try:
            with open(RESUMES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    resumes = {str(k): str(v) for k, v in data.items() if str(v).strip()}
        except Exception:
            resumes = {}

    if not resumes and os.path.exists("resume.md"):
        secure_file_permissions("resume.md")
        try:
            with open("resume.md", "r", encoding="utf-8") as f:
                default_md = f.read().strip()
                if default_md:
                    resumes["Master Resume"] = default_md
                    save_resumes(resumes)
        except Exception:
            pass

    return resumes


def save_resumes(resumes_dict: dict[str, str]):
    """Persists the multi-resume dictionary to `resumes.json` (0600) and syncs the primary resume to `resume.md`."""
    clean_dict = {str(k).strip(): str(v) for k, v in resumes_dict.items() if str(k).strip()}
    atomic_write_json(RESUMES_FILE, clean_dict, indent=2)

    # Keep resume.md synced with the first resume for backward compatibility
    if clean_dict:
        first_val = next(iter(clean_dict.values()))
        try:
            atomic_write_text("resume.md", first_val)
        except OSError:
            pass


def extract_text_from_uploaded_resume(uploaded_file) -> str:
    """Extracts clean plain text / Markdown from an uploaded .md, .txt, .docx, or .pdf resume file."""
    filename = (getattr(uploaded_file, "name", "") or "").lower()
    raw_bytes = uploaded_file.getvalue()

    if filename.endswith(".docx"):
        from docx import Document
        doc = Document(io.BytesIO(raw_bytes))
        lines = []
        for p in doc.paragraphs:
            if p.text and p.text.strip():
                lines.append(p.text.strip())
        for table in doc.tables:
            for row in table.rows:
                row_txt = " | ".join(c.text.strip() for c in row.cells if c.text and c.text.strip())
                if row_txt:
                    lines.append(row_txt)
        return "\n".join(lines).strip()

    if filename.endswith(".pdf"):
        import shutil
        import subprocess
        import tempfile
        soffice_bin = shutil.which("soffice") or shutil.which("libreoffice")
        if soffice_bin:
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    pdf_path = os.path.join(tmpdir, "upload.pdf")
                    txt_path = os.path.join(tmpdir, "upload.txt")
                    with open(pdf_path, "wb") as f:
                        f.write(raw_bytes)
                    subprocess.run(
                        [soffice_bin, "--headless", "--convert-to", "txt:Text", "--outdir", tmpdir, pdf_path],
                        capture_output=True,
                        timeout=15,
                        check=False,
                    )
                    if os.path.exists(txt_path):
                        with open(txt_path, "r", encoding="utf-8", errors="ignore") as tf:
                            extracted = tf.read().strip()
                            if extracted:
                                return extracted
            except Exception:
                pass
        # Fallback pdftotext if installed
        pdftotext_bin = shutil.which("pdftotext")
        if pdftotext_bin:
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    pdf_path = os.path.join(tmpdir, "upload.pdf")
                    txt_path = os.path.join(tmpdir, "upload.txt")
                    with open(pdf_path, "wb") as f:
                        f.write(raw_bytes)
                    subprocess.run([pdftotext_bin, pdf_path, txt_path], capture_output=True, timeout=10, check=False)
                    if os.path.exists(txt_path):
                        with open(txt_path, "r", encoding="utf-8", errors="ignore") as tf:
                            return tf.read().strip()
            except Exception:
                pass

    return raw_bytes.decode("utf-8", errors="ignore").strip()


parse_resume_file = extract_text_from_uploaded_resume


def combine_selected_resumes(selected_names: list[str], resumes_dict: dict[str, str] | None = None) -> str:
    """
    Combines the selected resume(s) into a single reference string.
    - If 1 resume is selected, returns its text directly (zero extra tokens).
    - If multiple resumes are selected, wraps each in a labeled `=== RESUME PROFILE ===` block
      so the AI can evaluate against the combined skill/experience pool and harvest the best pieces
      in a single pass without multiplying API calls.
    """
    vault = resumes_dict if resumes_dict is not None else st.session_state.get("resumes_vault") or load_resumes()
    if not vault:
        return st.session_state.get("resume_text", "")

    valid_names = [n for n in (selected_names or []) if n in vault and vault[n].strip()]
    if not valid_names:
        valid_names = [next(iter(vault.keys()))]

    if len(valid_names) == 1:
        return vault[valid_names[0]].strip()

    blocks = []
    for idx, name in enumerate(valid_names, 1):
        blocks.append(f"=== RESUME PROFILE {idx}: [{name}] ===\n{vault[name].strip()}")
    return "\n\n".join(blocks)


def render_resume_selector(key_suffix: str = "main", in_sidebar: bool = False) -> tuple[list[str], str]:
    """
    Renders a multi-resume selector allowing users to pick which specific resume(s)
    to use for evaluation or document generation to prevent long wait times.
    Returns `(selected_resume_names, combined_resume_text)`.
    """
    vault = load_resumes()
    st.session_state["resumes_vault"] = vault
    all_names = list(vault.keys())
    if not all_names:
        return [], st.session_state.get("resume_text", "")

    current_selected = [
        n for n in st.session_state.get("selected_resumes", [all_names[0]]) if n in all_names
    ]
    if not current_selected:
        current_selected = [all_names[0]]
    st.session_state["selected_resumes"] = current_selected

    widget_key = f"resume_multiselect_{key_suffix}"
    st.session_state[widget_key] = current_selected

    def _on_resume_sel_change():
        chosen = st.session_state.get(widget_key) or [all_names[0]]
        st.session_state["selected_resumes"] = chosen
        st.session_state["resume_text"] = combine_selected_resumes(chosen, vault)

    container = st.sidebar if in_sidebar else st
    chosen_names = container.multiselect(
        "📄 Active Resume(s) for Review & Tailoring:",
        options=all_names,
        key=widget_key,
        on_change=_on_resume_sel_change,
        help="Select 1 or more resumes to compare against jobs. If you select multiple, Skippy will draw the best matching skills, experiences, and projects across all of them.",
    )
    if not chosen_names:
        chosen_names = [all_names[0]]
        st.session_state["selected_resumes"] = chosen_names

    combined_text = combine_selected_resumes(chosen_names, vault)
    st.session_state["resume_text"] = combined_text
    if len(chosen_names) > 1:
        container.caption(
            f"✨ **Using {len(chosen_names)} Selected Resumes:** Skippy will draw the best matching roles, projects, and skills across {', '.join(f'`{n}`' for n in chosen_names)}."
        )
    return chosen_names, combined_text


def load_custom_user_prompt() -> str:
    """Loads the user's custom prompt from custom_user_prompt.txt, seeding it intelligently if missing."""
    if os.path.exists(CUSTOM_USER_PROMPT_FILE):
        try:
            with open(CUSTOM_USER_PROMPT_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return content
        except Exception:
            pass

    # If custom_user_prompt.txt is missing, seed it
    default_text = ""
    compass_prompt = ""
    profile = load_user_profile()
    if profile:
        compass_prompt = (profile.get("adapted_prompt") or "").strip()

    # If custom_prompt.txt exists and is distinct from the compass prompt, preserve it
    if os.path.exists(CUSTOM_PROMPT_FILE):
        try:
            with open(CUSTOM_PROMPT_FILE, "r", encoding="utf-8") as f:
                disk_prompt = f.read().strip()
                if disk_prompt and (not compass_prompt or disk_prompt != compass_prompt):
                    default_text = disk_prompt
        except Exception:
            pass

    if not default_text and os.path.exists(CUSTOM_PROMPT_TEMPLATE_FILE):
        try:
            with open(CUSTOM_PROMPT_TEMPLATE_FILE, "r", encoding="utf-8") as f:
                default_text = f.read().strip()
        except Exception:
            pass

    if not default_text:
        default_text = "You are an advanced automated job-matching engine and career evaluator configured to assess candidate qualifications against job descriptions."

    try:
        atomic_write_text(CUSTOM_USER_PROMPT_FILE, default_text)
    except Exception:
        pass

    return default_text


def save_custom_user_prompt(prompt_text: str) -> None:
    """Persists the user's custom prompt to custom_user_prompt.txt."""
    clean_text = str(prompt_text or "").strip()
    if clean_text:
        atomic_write_text(CUSTOM_USER_PROMPT_FILE, clean_text)


def load_compass_prompt() -> str:
    """Loads the adapted prompt from the user's career compass profile."""
    profile = st.session_state.get("user_profile")
    if not profile:
        profile = load_user_profile()

    if profile:
        prompt = (profile.get("adapted_prompt") or "").strip()
        if prompt:
            return prompt
        # Generate prompt if profile has industry profile or domains
        if profile.get("industry_title") or profile.get("archetype_title") or profile.get("primary_domain"):
            try:
                prompt = career_compass.generate_adapted_custom_prompt(profile)
                if prompt:
                    profile["adapted_prompt"] = prompt
                    save_user_profile(profile)
                    st.session_state["user_profile"] = profile
                    return prompt
            except Exception:
                pass

    return load_custom_user_prompt()


def get_prompt_mode() -> str:
    """Returns the currently active prompt mode ('compass' or 'custom')."""
    if "prompt_mode" in st.session_state and st.session_state["prompt_mode"] in (PROMPT_MODE_COMPASS, PROMPT_MODE_CUSTOM):
        return st.session_state["prompt_mode"]

    saved_mode = get_setting(PROMPT_MODE_SETTING, "").strip().lower()
    if saved_mode in (PROMPT_MODE_COMPASS, PROMPT_MODE_CUSTOM):
        st.session_state["prompt_mode"] = saved_mode
        return saved_mode

    profile = st.session_state.get("user_profile")
    if not profile:
        profile = load_user_profile()
    if profile and (profile.get("industry_title") or profile.get("archetype_title")):
        default_mode = PROMPT_MODE_COMPASS
    else:
        default_mode = PROMPT_MODE_CUSTOM

    st.session_state["prompt_mode"] = default_mode
    return default_mode


def get_active_prompt_details() -> dict:
    """
    Returns metadata about the active evaluation prompt:
    {
        "mode": "compass" | "custom",
        "prompt_text": str,
        "title": str,
        "badge_label": str,
        "is_compass": bool,
    }
    """
    mode = get_prompt_mode()
    profile = st.session_state.get("user_profile")
    if not profile:
        profile = load_user_profile()

    if mode == PROMPT_MODE_COMPASS:
        prompt_text = load_compass_prompt()
        arch_title = (profile.get("industry_title") or profile.get("archetype_title")) if profile else ""
        if not arch_title:
            arch_title = "Universal Industry Profile"
        return {
            "mode": PROMPT_MODE_COMPASS,
            "prompt_text": prompt_text,
            "title": arch_title,
            "badge_label": f"🧭 Career Profile ({arch_title})",
            "is_compass": True,
        }
    else:
        prompt_text = load_custom_user_prompt()
        return {
            "mode": PROMPT_MODE_CUSTOM,
            "prompt_text": prompt_text,
            "title": "Custom Instructions",
            "badge_label": "⚙️ Custom Instructions",
            "is_compass": False,
        }


def set_active_prompt_mode(mode: str) -> None:
    """Switches the active evaluation prompt mode ('compass' or 'custom') and syncs state."""
    clean_mode = PROMPT_MODE_COMPASS if mode == PROMPT_MODE_COMPASS else PROMPT_MODE_CUSTOM
    st.session_state["prompt_mode"] = clean_mode
    set_setting(PROMPT_MODE_SETTING, clean_mode)

    details = get_active_prompt_details()
    active_text = details["prompt_text"]
    st.session_state.system_instructions = active_text
    try:
        atomic_write_text(CUSTOM_PROMPT_FILE, active_text)
    except Exception:
        pass


def render_prompt_mode_toggle(in_sidebar: bool = True, key_suffix: str = ""):
    """Renders the prompt priority/source toggle and active status indicator."""
    details = get_active_prompt_details()
    current_mode = details["mode"]
    
    container = st.sidebar if in_sidebar else st
    
    with container:
        if in_sidebar:
            st.markdown("---")
            st.subheader("🎯 AI Instructions")
            
            if details["is_compass"]:
                st.markdown(
                    f":green-background[**Active: 🧭 Career Profile**]  \n"
                    f"<small style='opacity:0.85;'>Profile: <b>{details['title']}</b></small>",
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    ":blue-background[**Active: ⚙️ Custom Instructions**]  \n"
                    "<small style='opacity:0.85;'>Instructions: <b>Custom Guidelines</b></small>",
                    unsafe_allow_html=True
                )
            
            mode_options = ["🧭 Career Profile", "⚙️ Custom Instructions"]
            current_idx = 0 if current_mode == PROMPT_MODE_COMPASS else 1
            
            radio_key = f"prompt_mode_toggle_sb_{key_suffix}".strip("_")
            chosen = st.radio(
                "Evaluation Prompt Strategy:",
                mode_options,
                index=current_idx,
                key=radio_key,
                label_visibility="collapsed",
            )
            chosen_mode = PROMPT_MODE_COMPASS if chosen == "🧭 Career Profile" else PROMPT_MODE_CUSTOM
            if chosen_mode != current_mode:
                set_active_prompt_mode(chosen_mode)
                new_details = get_active_prompt_details()
                st.toast(f"🎯 AI instructions switched to: {new_details['title']}", icon="✅")
                st.rerun()
        else:
            st.caption("🎯 **Active AI Instructions**")
            if details["is_compass"]:
                st.info(
                    f"🧭 **Active Instructions:** Career Profile (**{details['title']}**). "
                    "Evaluations are tuned to your field.",
                    icon="🟢"
                )
            else:
                st.info(
                    "⚙️ **Active Instructions:** Custom Instructions. "
                    "Evaluations use your personalized guidelines.",
                    icon="🟢"
                )


def render_active_prompt_indicator(compact: bool = True):
    """Renders a compact, non-intrusive badge showing the currently active rubric."""
    details = get_active_prompt_details()
    if details["is_compass"]:
        st.caption(f"🎯 **Active Instructions:** :green-background[🧭 Career Profile: **{details['title']}**] *(switch in sidebar)*")
    else:
        st.caption("🎯 **Active Instructions:** :blue-background[⚙️ **Custom Instructions**] *(switch in sidebar)*")


def initialize_core_state():
    # 1. Load Multi-Resume Vault from disk if not yet loaded in session
    if "resumes_vault" not in st.session_state:
        vault = load_resumes()
        st.session_state["resumes_vault"] = vault
    else:
        vault = st.session_state["resumes_vault"]
    all_names = list(vault.keys())

    if "selected_resumes" not in st.session_state or not st.session_state["selected_resumes"]:
        st.session_state["selected_resumes"] = [all_names[0]] if all_names else []
    else:
        valid = [n for n in st.session_state["selected_resumes"] if n in vault]
        st.session_state["selected_resumes"] = valid or ([all_names[0]] if all_names else [])

    if all_names:
        st.session_state.resume_text = combine_selected_resumes(st.session_state["selected_resumes"], vault)
    elif "resume_text" not in st.session_state:
        st.session_state.resume_text = ""

    # 2. Load User Career Compass Profile from disk/database first
    if "user_profile" not in st.session_state:
        st.session_state["user_profile"] = load_user_profile()

    # 3. Load Prompt Mode & System Instructions from disk/database
    if "prompt_mode" not in st.session_state:
        st.session_state["prompt_mode"] = get_prompt_mode()

    if "system_instructions" not in st.session_state or not st.session_state.system_instructions:
        details = get_active_prompt_details()
        st.session_state.system_instructions = details["prompt_text"]
        try:
            atomic_write_text(CUSTOM_PROMPT_FILE, details["prompt_text"])
        except Exception:
            pass

    if "model_choice" not in st.session_state:
        st.session_state["model_choice"] = get_setting("model_choice", "Google Gemini")

    if "local_base_url" not in st.session_state:
        st.session_state["local_base_url"] = get_setting("local_base_url", "http://localhost:11434/v1")

    if "local_model_name" not in st.session_state:
        st.session_state["local_model_name"] = get_setting("local_model_name", "llama3")

    # 4. Load API Key from disk BEFORE the gatekeeper checks it
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
            st.markdown("⚡ **Reviewing Jobs...**")
            total = max(status.get("total", 1), 1)
            completed = status.get("completed", 0)
            prog = min(completed / total, 1.0)

            cur = status.get("current_job", "Working...")
            if len(cur) > 35:
                cur = cur[:32] + "..."
            st.progress(prog, text=f"{completed}/{status.get('total', 1)} reviewed")
            st.caption(f"📍 `{cur}`")
            st.caption("💡 *You can freely browse other pages while this runs.*")
            if st.button("🛑 Stop Review", key="btn_cancel_global_pipeline", width="stretch"):
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
                if st.button("📂 Job History", key="sb_view_hist", width="stretch"):
                    st.session_state["active_history_source"] = src
                    st.switch_page("pages/2_history.py")
            with col2:
                if st.button("Dismiss", key="sb_dismiss_batch", width="stretch"):
                    del st.session_state["completion_batch"]
                    pipeline_manager.dismiss_latest_run()
                    st.rerun()


def inject_interactive_hover_halo_effects():
    """
    Injects smooth interactive hover and luminous halo effects on buttons
    and navigation elements styled in blue and white.
    """
    st.markdown(
        """
        <style>
        /* Smooth transitions for interactive buttons */
        .stButton > button,
        .stFormSubmitButton > button,
        button[data-testid="baseButton-primary"],
        button[data-testid="baseButton-secondary"],
        [data-testid="stLinkButton"] a,
        [data-testid="stDownloadButton"] button,
        button[data-testid="stBaseButton-primary"],
        button[data-testid="stBaseButton-secondary"] {
            transition: transform 0.15s cubic-bezier(0.16, 1, 0.3, 1),
                        box-shadow 0.2s cubic-bezier(0.16, 1, 0.3, 1),
                        background-color 0.15s ease,
                        border-color 0.15s ease,
                        color 0.15s ease !important;
        }

        /* Primary Button Base (Blue & White) */
        .stButton > button[kind="primary"],
        .stFormSubmitButton > button[kind="primary"],
        button[data-testid="baseButton-primary"],
        [data-testid="stLinkButton"] a[kind="primary"],
        [data-testid="stDownloadButton"] button[kind="primary"],
        button[data-testid="stBaseButton-primary"] {
            background-color: #2563eb !important;
            color: #ffffff !important;
            border: 1px solid #1d4ed8 !important;
            font-weight: 500 !important;
        }

        /* Primary Button Hover Lift & Blue/White Halo Glow */
        .stButton > button[kind="primary"]:hover,
        .stFormSubmitButton > button[kind="primary"]:hover,
        button[data-testid="baseButton-primary"]:hover,
        [data-testid="stLinkButton"] a[kind="primary"]:hover,
        [data-testid="stLinkButton"] a:hover,
        [data-testid="stDownloadButton"] button[kind="primary"]:hover,
        button[data-testid="stBaseButton-primary"]:hover {
            transform: translateY(-1.5px) !important;
            background-color: #1d4ed8 !important;
            color: #ffffff !important;
            border-color: #1e40af !important;
            box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35), 0 0 16px 3px rgba(59, 130, 246, 0.55), 0 0 4px 1px rgba(255, 255, 255, 0.75) !important;
        }

        /* Primary Button Active Press */
        .stButton > button[kind="primary"]:active,
        .stFormSubmitButton > button[kind="primary"]:active,
        button[data-testid="baseButton-primary"]:active,
        [data-testid="stLinkButton"] a:active,
        [data-testid="stDownloadButton"] button[kind="primary"]:active,
        button[data-testid="stBaseButton-primary"]:active {
            transform: translateY(0.5px) !important;
            background-color: #1e40af !important;
            color: #ffffff !important;
            box-shadow: 0 2px 6px rgba(30, 64, 175, 0.3), 0 0 10px 2px rgba(59, 130, 246, 0.4) !important;
        }

        /* Secondary Button Hover Lift & Soft Blue/White Halo Glow */
        .stButton > button[kind="secondary"]:hover,
        .stFormSubmitButton > button[kind="secondary"]:hover,
        button[data-testid="baseButton-secondary"]:hover,
        .stButton > button:not([kind="primary"]):hover,
        .stFormSubmitButton > button:not([kind="primary"]):hover,
        [data-testid="stDownloadButton"] button:not([kind="primary"]):hover,
        button[data-testid="stBaseButton-secondary"]:hover {
            transform: translateY(-1.5px) !important;
            border-color: #3b82f6 !important;
            color: #ffffff !important;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2), 0 0 12px 2px rgba(59, 130, 246, 0.42), 0 0 4px 1px rgba(255, 255, 255, 0.6) !important;
        }

        /* Secondary Button Active Press */
        .stButton > button[kind="secondary"]:active,
        .stFormSubmitButton > button[kind="secondary"]:active,
        button[data-testid="baseButton-secondary"]:active,
        .stButton > button:not([kind="primary"]):active,
        .stFormSubmitButton > button:not([kind="primary"]):active,
        [data-testid="stDownloadButton"] button:not([kind="primary"]):active,
        button[data-testid="stBaseButton-secondary"]:active {
            transform: translateY(0.5px) !important;
            border-color: #60a5fa !important;
            color: #ffffff !important;
            box-shadow: 0 1px 4px rgba(37, 99, 235, 0.2) !important;
        }

        /* Focus Rings (Accessible Blue & White Halo) */
        .stButton > button:focus-visible,
        .stFormSubmitButton > button:focus-visible,
        button[data-testid="baseButton-primary"]:focus-visible,
        button[data-testid="baseButton-secondary"]:focus-visible,
        button[data-testid="stBaseButton-primary"]:focus-visible,
        button[data-testid="stBaseButton-secondary"]:focus-visible {
            outline: none !important;
            box-shadow: 0 0 0 2px #ffffff, 0 0 0 4px rgba(59, 130, 246, 0.7) !important;
        }

        /* Sidebar Navigation Menu Items - Hover Shift & Glowing Blue/White Halo */
        [data-testid="stSidebarNav"] ul > li a {
            transition: transform 0.18s cubic-bezier(0.16, 1, 0.3, 1),
                        box-shadow 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
            border-radius: 8px !important;
        }

        [data-testid="stSidebarNav"] ul > li a:hover {
            transform: translateX(3px) !important;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06), 0 0 14px 2px rgba(59, 130, 246, 0.32), 0 0 4px 1px rgba(255, 255, 255, 0.5) !important;
        }

        /* Expander Accordion Menu Headers - Subtle Lift & Blue/White Halo */
        [data-testid="stExpander"] > details > summary,
        [data-testid="stExpander"] summary {
            transition: transform 0.18s cubic-bezier(0.16, 1, 0.3, 1),
                        box-shadow 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
            border-radius: 8px !important;
        }

        [data-testid="stExpander"] > details > summary:hover,
        [data-testid="stExpander"] summary:hover {
            transform: translateY(-1px) !important;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.06), 0 0 12px 2px rgba(59, 130, 246, 0.28), 0 0 4px 1px rgba(255, 255, 255, 0.45) !important;
        }

        /* Navigation Tabs Menu - Subtle Lift & Glowing Blue/White Halo on Hover */
        [data-testid="stTabs"] [data-baseweb="tab"] {
            transition: transform 0.15s cubic-bezier(0.16, 1, 0.3, 1),
                        box-shadow 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
            border-radius: 6px !important;
        }

        [data-testid="stTabs"] [data-baseweb="tab"]:hover {
            transform: translateY(-1px) !important;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05), 0 0 10px 2px rgba(59, 130, 246, 0.32), 0 0 4px 1px rgba(255, 255, 255, 0.5) !important;
        }

        /* Selected Tab Highlight in Blue */
        [data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
            color: #60a5fa !important;
        }
        [data-testid="stTabs"] [data-baseweb="tab-highlight"] {
            background-color: #3b82f6 !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )


def setup_sidebar():
    inject_interactive_hover_halo_effects()
    enforce_authentication()
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
        /* Chevron indicator on Scraper showing it has a hover submenu */
        [data-testid="stSidebarNav"] ul > li:nth-child(1) a::after,
        [data-testid="stSidebarNav"] ul > li:has(a[href*="1_scraper"]) a::after {
            content: "▸";
            margin-left: auto;
            font-size: 0.85rem;
            opacity: 0.55;
            transition: transform 0.2s ease, opacity 0.2s ease;
        }
        [data-testid="stSidebarNav"] ul:has(> li:nth-child(2) [aria-current="page"]) > li:nth-child(1) a::after,
        [data-testid="stSidebarNav"] ul > li:nth-child(1):hover a::after,
        [data-testid="stSidebarNav"] ul:has(> li:nth-child(2):hover) > li:nth-child(1) a::after,
        [data-testid="stSidebarNav"] ul:has(> li a[href*="5_linkedin"][aria-current="page"]) > li:has(a[href*="1_scraper"]) a::after,
        [data-testid="stSidebarNav"] ul > li:has(a[href*="1_scraper"]):hover a::after,
        [data-testid="stSidebarNav"] ul:has(> li:has(a[href*="5_linkedin"]):hover) > li:has(a[href*="1_scraper"]) a::after,
        [data-testid="stSidebarNav"] ul:has(> li:has(a[href*="linkedin"]):hover) > li:nth-child(1) a::after {
            content: "▾";
            opacity: 0.9;
        }
        /* Nested tree submenu styling for LinkedIn Evaluator (Fallback) under Scraper */
        [data-testid="stSidebarNav"] ul > li:has(a[href*="5_linkedin"]),
        [data-testid="stSidebarNav"] ul > li:has(a[href*="linkedin"]),
        [data-testid="stSidebarNav"] ul > li:nth-child(2) {
            position: relative;
            margin: 0 !important;
            padding-left: 1.85rem !important;
            padding-top: 0 !important;
            padding-bottom: 0 !important;
            max-height: 0;
            opacity: 0;
            overflow: hidden;
            /* 0.35s closing grace delay so moving the cursor from Scraper to the submenu never drops hover */
            transition:
                max-height 0.22s ease 0.35s,
                opacity 0.18s ease 0.35s,
                padding-top 0.22s ease 0.35s,
                padding-bottom 0.22s ease 0.35s;
        }
        /* L-shaped tree branch connector (|__) drawn inside the left padding area */
        [data-testid="stSidebarNav"] ul > li:has(a[href*="5_linkedin"])::before,
        [data-testid="stSidebarNav"] ul > li:has(a[href*="linkedin"])::before,
        [data-testid="stSidebarNav"] ul > li:nth-child(2)::before {
            content: "";
            position: absolute;
            left: 1.15rem;
            top: 0;
            height: 55%;
            width: 0.5rem;
            border-left: 1.5px solid rgba(150, 150, 150, 0.5);
            border-bottom: 1.5px solid rgba(150, 150, 150, 0.5);
            border-bottom-left-radius: 3px;
            pointer-events: none;
        }
        [data-testid="stSidebarNav"] ul > li:has(a[href*="5_linkedin"]) span,
        [data-testid="stSidebarNav"] ul > li:has(a[href*="linkedin"]) span,
        [data-testid="stSidebarNav"] ul > li:nth-child(2) span {
            font-size: 0.92rem !important;
            font-weight: 400 !important;
        }
        /* Instant expand on hover of Scraper or when inside submenu */
        [data-testid="stSidebarNav"] ul > li:has(a[href*="1_scraper"]):hover + li:has(a[href*="5_linkedin"]),
        [data-testid="stSidebarNav"] ul > li:has(a[href*="5_linkedin"]):hover,
        [data-testid="stSidebarNav"] ul > li:has(a[href*="5_linkedin"]):active,
        [data-testid="stSidebarNav"] ul > li:has(a[href*="5_linkedin"]):focus-within,
        [data-testid="stSidebarNav"] ul > li:has(a[href*="5_linkedin"] [aria-current="page"]),
        [data-testid="stSidebarNav"] ul > li:has(a[href*="linkedin"]):hover,
        [data-testid="stSidebarNav"] ul > li:has(a[href*="linkedin"]):active,
        [data-testid="stSidebarNav"] ul > li:has(a[href*="linkedin"]):focus-within,
        [data-testid="stSidebarNav"] ul > li:has(a[href*="linkedin"] [aria-current="page"]),
        [data-testid="stSidebarNav"] ul > li:nth-child(1):hover + li:nth-child(2),
        [data-testid="stSidebarNav"] ul > li:nth-child(2):hover,
        [data-testid="stSidebarNav"] ul > li:nth-child(2):active,
        [data-testid="stSidebarNav"] ul > li:nth-child(2):focus-within,
        [data-testid="stSidebarNav"] ul > li:nth-child(2):has([aria-current="page"]) {
            max-height: 3.5rem;
            opacity: 0.95;
            padding-top: 0.2rem !important;
            padding-bottom: 0.25rem !important;
            transition:
                max-height 0.18s ease 0s,
                opacity 0.14s ease 0s,
                padding-top 0.18s ease 0s,
                padding-bottom 0.18s ease 0s;
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
            st.toast("Key Accepted! ✅", icon="🔑")
            st.rerun()

    render_prompt_mode_toggle(in_sidebar=True)
    render_help_section(in_sidebar=True)
    render_sidebar_auth_controls()

def enforce_onboarding():
    enforce_authentication()

    # CRITICAL: Onboarding runs strictly once on the first launch.
    # Subsequent launches immediately bypass onboarding!
    if is_onboarding_completed():
        return

    has_key = bool(st.session_state.get("user_api_key")) or ("Local" in st.session_state.get("model_choice", ""))
    has_resume = bool(st.session_state.get("resume_text", "").strip())
    has_profile = bool(st.session_state.get("user_profile")) or bool(st.session_state.get("quiz_onboarding_skipped"))

    if not (has_key and has_resume and has_profile):
        st.markdown(
            """
            <style>
                [data-testid="stSidebar"] { display: none; }
                [data-testid="collapsedControl"] { display: none; }
            </style>
            """,
            unsafe_allow_html=True
        )
        _, top_right_col = st.columns([6, 1])
        with top_right_col:
            if st.button("🔒 Log Out", key="btn_onboarding_logout", width="stretch"):
                logout_user()
                st.rerun()

    # =========================================================================
    # STEP 1: Connect AI Provider
    # =========================================================================
    if not has_key:
        st.title("Welcome to Skippy! 🦘")
        st.progress(0.33, text="Step 1 of 3: Connect Your AI Provider")
        st.write("Before reviewing job postings and tailoring resumes, connect Skippy to an AI provider.")

        model_options = ["Google Gemini", "OpenAI ChatGPT", "xAI Grok", "Anthropic Claude", "Local / Custom (Ollama)"]
        current_choice = st.session_state.get("model_choice", "Google Gemini")
        chosen_idx = model_options.index(current_choice) if current_choice in model_options else 0
        selected_model = st.selectbox("Select AI Provider", model_options, index=chosen_idx)
        st.session_state["model_choice"] = selected_model

        api_key_val = st.session_state.get("user_api_key", "")
        local_base = st.session_state.get("local_base_url", "http://localhost:11434/v1")
        local_model = st.session_state.get("local_model_name", "llama3")

        if selected_model == "Google Gemini":
            st.info(
                "💡 **Google Gemini is free to use** with no credit card required. "
                "[Click here to get your free Gemini API key from Google AI Studio ↗](https://aistudio.google.com/app/apikey)",
                icon="✨"
            )
            api_key_input = st.text_input(
                "Enter Google Gemini API Key",
                value=api_key_val,
                type="password",
                help="Get a free key from Google AI Studio (takes 30 seconds, no credit card required)."
            )
        elif selected_model == "Local / Custom (Ollama)":
            st.info(
                "💻 **100% Private & Offline**: Requires [Ollama](https://ollama.com) running on your computer. "
                "In your terminal, start your model with: `ollama run llama3`",
                icon="🖥️"
            )
            c_url, c_mod = st.columns(2)
            with c_url:
                local_base = st.text_input("Local API Base URL", value=local_base)
            with c_mod:
                local_model = st.text_input("Local Model Name", value=local_model)
            api_key_input = ""
        else:
            api_key_input = st.text_input(
                f"Enter {selected_model} API Key",
                value=api_key_val,
                type="password",
                help=f"Enter your API key for {selected_model}."
            )

        col_test, col_save = st.columns([1, 1.4])
        with col_test:
            if st.button("🧪 Test Connection", type="secondary", width="stretch"):
                with st.spinner("Testing AI connection..."):
                    test_key = api_key_input.strip() if selected_model != "Local / Custom (Ollama)" else ""
                    ok, msg = test_ai_connection(
                        selected_model,
                        test_key,
                        local_base_url=local_base,
                        local_model_name=local_model
                    )
                    if ok:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")

        with col_save:
            if st.button("Save & Continue ➔", type="primary", width="stretch"):
                set_setting("model_choice", selected_model)
                if selected_model == "Local / Custom (Ollama)":
                    set_setting("local_base_url", local_base)
                    set_setting("local_model_name", local_model)
                    st.session_state["local_base_url"] = local_base
                    st.session_state["local_model_name"] = local_model
                    st.session_state["show_key_success"] = True
                    st.rerun()
                else:
                    if api_key_input.strip():
                        save_local_config(api_key_input.strip())
                        st.session_state["user_api_key"] = api_key_input.strip()
                        st.session_state["show_key_success"] = True
                        st.rerun()
                    else:
                        st.warning("Please enter a valid API key to continue.")

        st.markdown("---")
        render_help_section(in_sidebar=False)
        st.stop()

    # =========================================================================
    # STEP 2: Add Master Resume
    # =========================================================================
    if not has_resume:
        st.title("Welcome to Skippy! 🦘")
        st.progress(0.66, text="Step 2 of 3: Add Your Master Resume")
        st.write(
            "Your **Master Resume** is your complete work history containing all your jobs, skills, certifications, and projects. "
            "Don't worry about keeping it under one page! Skippy will pick and choose the best parts whenever it creates a custom resume for a specific job."
        )
        st.info("🔒 **100% Local Privacy:** Your resume is stored safely in your local SQLite database on your hard drive and is never shared.", icon="🛡️")

        # 1. File Uploader
        uploaded_resume_file = st.file_uploader(
            "📁 Drag and drop your resume file (.docx, .pdf, .md, .txt):",
            type=["docx", "pdf", "md", "txt"],
            key="onboarding_resume_file_uploader",
            help="Upload your existing resume in Word, PDF, Markdown, or text format."
        )

        if uploaded_resume_file is not None:
            extracted_resume_text = parse_resume_file(uploaded_resume_file)
            if extracted_resume_text and extracted_resume_text.strip():
                st.session_state["onboarding_resume_text_buffer"] = extracted_resume_text
                st.toast(f"Extracted resume from {uploaded_resume_file.name}!", icon="📄")

        # 2. 1-Click Sample Resumes
        st.markdown("##### 🧪 Or Test-Drive Skippy with a Sample Resume:")
        st.caption("Don't have a resume file on this computer? Choose a realistic sample profile to test drive Skippy right away:")
        sample_cols = st.columns(4)
        sample_keys = list(SAMPLE_RESUMES.keys())
        for idx, s_name in enumerate(sample_keys):
            with sample_cols[idx]:
                if st.button(f"📄 {s_name}", key=f"btn_sample_resume_{idx}", width="stretch"):
                    st.session_state["onboarding_resume_text_buffer"] = SAMPLE_RESUMES[s_name]
                    st.toast(f"Loaded '{s_name}' sample resume!", icon="✅")

        # 3. Text Area
        current_buffer = st.session_state.get("onboarding_resume_text_buffer", "")
        with st.form("onboarding_resume_form"):
            initial_resume = st.text_area(
                "Master Resume Content (Editable):",
                value=current_buffer,
                height=320,
                placeholder="# Your Name\n\n## Experience\n- Lead Role at Company (2020-Present)...",
                help="Review, edit, or paste your work history here."
            )
            saved = st.form_submit_button("Save Resume & Continue ➔", type="primary", width="stretch")

            if saved:
                if not initial_resume.strip():
                    st.warning("Please upload a file, pick a sample, or paste your resume before proceeding.")
                else:
                    st.session_state.resume_text = initial_resume
                    save_resumes({"Master Resume": initial_resume})
                    st.session_state["resumes_vault"] = {"Master Resume": initial_resume}
                    st.session_state["selected_resumes"] = ["Master Resume"]
                    st.success("Master resume saved! Setting up your career profile...")
                    st.rerun()

        st.markdown("---")
        render_help_section(in_sidebar=False)
        st.stop()

    # =========================================================================
    # STEP 3: Career Direction & Profile
    # =========================================================================
    if not has_profile:
        st.title("Welcome to Skippy! 🦘")
        st.progress(1.0, text="Step 3 of 3: Choose Your Career Field & Direction")
        st.markdown(
            "Skippy adapts to candidates across all walks of work—from skilled trades, first responders, "
            "and military veterans to healthcare clinicians, engineers, and business professionals. "
            "Let AI discover your profile from your resume in 1 click, choose a career field, or answer 7 quick questions."
        )

        onboarding_hint = st.text_input(
            "🎯 Industry, Trade, or Field Focus (Optional Guidance)",
            placeholder="e.g. Subsea Robotics, Watchmaking, Ammonia Refrigeration, Fire Protection (or leave blank to infer from resume)",
            key="onboarding_industry_hint",
            help="Provide your specific trade or industry if you work in a specialized field."
        )

        # Primary Hero Action: Auto-Detect
        with st.container(border=True):
            st.markdown("### ⚡ Auto-Detect Career Profile from Resume (Recommended)")
            st.caption("AI reads the resume you just added to identify your career field, licenses, specialized tools, and core competencies automatically.")
            if st.button("⚡ 1-Click Auto-Detect Career Profile", type="primary", width="stretch", key="btn_onboard_hero_autodetect"):
                with st.spinner("Setting up your career profile..."):
                    detected_profile = career_compass.auto_detect_alignment_from_resume(
                        st.session_state.get("resume_text", ""),
                        use_ai=True,
                        industry_hint=onboarding_hint,
                        model_choice=st.session_state.get("model_choice"),
                        api_key=st.session_state.get("user_api_key")
                    )
                    adapted_prompt = career_compass.generate_adapted_custom_prompt(detected_profile)
                    detected_profile["adapted_prompt"] = adapted_prompt
                    save_user_profile(detected_profile)
                    st.session_state["user_profile"] = detected_profile
                    set_active_prompt_mode(PROMPT_MODE_COMPASS)
                    mark_onboarding_completed()
                    st.session_state["show_quick_start"] = True
                    st.toast(f"🎯 Career Profile Detected: {detected_profile.get('industry_title') or detected_profile.get('archetype_title', 'Specialist')}", icon="✅")
                    st.rerun()

        # Quick Career Track Selector
        with st.expander("🎯 Or Choose a Popular Career Track"):
            popular_tracks = [
                "Technology & Software Engineering",
                "Clinical Healthcare & Nursing",
                "Operations, Logistics & Supply Chain",
                "Skilled Trades, HVAC & Manufacturing",
                "First Responders & Public Safety",
                "Military Transition & Defense Operations",
                "Corporate, Finance & Human Resources",
                "General Professional / Business Operations"
            ]
            chosen_track = st.selectbox("Select Your Career Track", popular_tracks, key="onboarding_popular_track_select")
            if st.button("Save Career Track & Continue ➔", width="stretch", key="btn_save_popular_track"):
                profile = career_compass.auto_detect_alignment_from_resume(
                    st.session_state.get("resume_text", ""),
                    use_ai=False,
                    industry_hint=chosen_track
                )
                profile["industry_title"] = chosen_track
                adapted_prompt = career_compass.generate_adapted_custom_prompt(profile)
                profile["adapted_prompt"] = adapted_prompt
                save_user_profile(profile)
                st.session_state["user_profile"] = profile
                set_active_prompt_mode(PROMPT_MODE_COMPASS)
                mark_onboarding_completed()
                st.session_state["show_quick_start"] = True
                st.toast(f"🎯 Career Track Set: {chosen_track}!", icon="✅")
                st.rerun()

        # Optional Detailed Quiz
        with st.expander("📝 Or Take the Detailed 7-Question Career Direction Quiz"):
            with st.form("onboarding_career_compass_quiz_form"):
                user_answers = {}
                for q in career_compass.UNIVERSAL_QUIZ_QUESTIONS:
                    st.markdown(f"**{q['title']}**")
                    st.caption(q["question"])
                    labels = [opt["label"] for opt in q["options"]]
                    chosen_label = st.radio(
                        label=q["title"],
                        options=labels,
                        index=0,
                        key=f"onboarding_q_{q['id']}",
                        label_visibility="collapsed"
                    )
                    user_answers[q["id"]] = labels.index(chosen_label)
                    st.markdown("<br>", unsafe_allow_html=True)

                quiz_submitted = st.form_submit_button("Complete Setup & Launch Skippy 🚀", type="primary", width="stretch")
                if quiz_submitted:
                    profile = career_compass.score_quiz_responses(user_answers)
                    adapted_prompt = career_compass.generate_adapted_custom_prompt(profile)
                    profile["adapted_prompt"] = adapted_prompt
                    save_user_profile(profile)
                    st.session_state["user_profile"] = profile
                    set_active_prompt_mode(PROMPT_MODE_COMPASS)
                    mark_onboarding_completed()
                    st.session_state["show_quick_start"] = True
                    st.success(f"🎯 Career Profile Set: {profile.get('industry_title') or profile.get('archetype_title', 'Specialist')}! Initializing dashboard...")
                    st.rerun()

        # Skip for now
        st.markdown("")
        if st.button("⏭️ Skip for Now & Launch Skippy", type="secondary", width="stretch", help="Proceed with standard settings. You can set up your career profile anytime from the Career Profile tab."):
            st.session_state["quiz_onboarding_skipped"] = True
            set_active_prompt_mode(PROMPT_MODE_CUSTOM)
            mark_onboarding_completed()
            st.session_state["show_quick_start"] = True
            st.rerun()

        st.markdown("---")
        render_help_section(in_sidebar=False)
        st.stop()

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
        st.subheader("🎉 Job Reviews Finished!")
        total = len(batch_jobs)
        strong = sum(1 for j in batch_jobs if j.get("Score", 0) >= 75 and j.get("Eligible", True))
        reach = sum(1 for j in batch_jobs if j.get("Score", 0) < 75 and j.get("Eligible", True))
        disqualified = sum(1 for j in batch_jobs if not j.get("Eligible", True))

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Jobs Reviewed", total)
        m2.metric("Strong Matches", strong)
        m3.metric("Moderate Matches", reach)
        m4.metric("Dealbreakers", disqualified)

        st.markdown("#### 📋 Findings Summary")
        for job in batch_jobs:
            score = int(job.get("Score", 0) or 0)
            eligible = job.get("Eligible", True)
            if not eligible:
                badge = "❌ Disqualified"
                detail = f"Hard blocker: {job.get('Disqualification Reason', 'Requirement not met')}"
            elif score >= 75:
                badge = "✅ Strong Fit"
                detail = f"Score: {score}/100"
            elif score >= 60:
                badge = "🟢 Good Fit"
                detail = f"Score: {score}/100"
            elif score >= 45:
                badge = "⚖️ Moderate Fit"
                detail = f"Score: {score}/100"
            else:
                badge = "⚠️ Weak / Reach"
                detail = f"Score: {score}/100"

            pos = job.get("Position", "Unknown Position")
            comp = job.get("Company", "")
            pos_display = f"{pos} at **{comp}**" if comp and comp != "Unknown Company" else f"**{pos}**"
            sub_parts = []
            if job.get("Technical Score"):
                sub_parts.append(f"Skills: {job['Technical Score']}")
            if job.get("Experience Score"):
                sub_parts.append(f"Experience: {job['Experience Score']}")
            if job.get("Behavioral Score"):
                sub_parts.append(f"Work Style: {job['Behavioral Score']}")
            if job.get("Career Score"):
                sub_parts.append(f"Career Goals: {job['Career Score']}")
            sub_str = f" · *({' | '.join(sub_parts)})*" if sub_parts else ""
            st.markdown(f"- {pos_display} — `{badge}` ({detail}){sub_str}")
            if job.get("Summary"):
                st.caption(f"> {job['Summary']}")

        st.markdown("")
        col_btn1, col_btn2 = st.columns([1.6, 1])
        with col_btn1:
            if st.button("View in Job History & Create Tailored Resumes 🚀", type="primary", width="stretch", key=f"view_hist_{source_label}"):
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
            if st.button("➕ Review More Jobs", width="stretch", key=f"eval_more_{source_label}"):
                if "completion_batch" in st.session_state:
                    del st.session_state["completion_batch"]
                st.rerun()