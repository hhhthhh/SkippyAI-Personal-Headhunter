import os
import io
import html
import json
import streamlit as st
from dotenv import load_dotenv
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
)
import career_compass
from evaluator import test_ai_connection

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
    return (os.environ.get("USER_API_KEY", "") or "").strip().strip("'\"")

def save_local_config(api_key):
    clean_key = (api_key or "").strip().strip("'\"")
    set_env_var_safe("USER_API_KEY", clean_key, env_file=ENV_FILE)

def render_help_content():
    st.markdown("**🔑 AI Providers & API Keys**")
    st.markdown(
        "Skippy lets you bring your own AI provider (default models shown)—or run **100% offline** with Ollama:\n"
        "- **Google Gemini (Recommended):** `gemini-2.5-flash` — [Google AI Studio](https://aistudio.google.com/app/apikey) *(~$0.0004/evaluation on Tier 1; paste multiple keys separated by commas/newlines for automatic rotation)*\n"
        "- **OpenAI ChatGPT:** `gpt-4o-mini` — [OpenAI Platform](https://platform.openai.com/api-keys)\n"
        "- **Anthropic Claude:** `claude-3-5-sonnet` — [Anthropic Console](https://console.anthropic.com/settings/keys)\n"
        "- **xAI Grok:** `grok-2-latest` — [xAI Console](https://console.x.ai/)\n"
        "- **Local / Custom (Ollama):** 100% free and offline on your own hardware (no API key required)."
    )
    st.markdown("---")
    st.markdown("**🤖 What Uses AI vs. Offline Tools**")
    st.markdown(
        "- **Uses AI:** Job match evaluations, tailored resumes/cover letters (with automatic **Fact-Check Grounding**), interview prep, application answers, outreach/company briefs, **Deep Career Profile Analysis**, **AI Content Polish**, and **Learning Plans**.\n"
        "- **100% Offline (0 API calls):** Job board discovery, **Job Text Safety Shield**, repost/ghost-job checks, **Smart Auto-Fix** resume formatting, **Quick Regex** career profiling, **Application Tracker**, and `.docx`/`.pdf` exports.\n"
        "- **Privacy:** All data is stored locally in `skippy.db`. Cloud providers only receive the resume and job text needed for the active request; choose **Ollama** for fully offline runs."
    )
    st.markdown("---")
    st.markdown("**📄 Resume Editing, Templates & Fact-Checking**")
    st.markdown(
        "- **Live Split View & Apply Changes:** Edit generated resumes side-by-side with a live preview in **Evaluations** and **Saved Documents**, then click **💾 Apply Changes** to save edits to your database.\n"
        "- **ATS Templates:** Switch between **Standard ATS** (Arial), **Harvard Style** (Times New Roman with divider rules), and **Modern Slate** (Calibri) before downloading `.docx` (or `.pdf` when LibreOffice is installed).\n"
        "- **Automatic Fact-Check Report:** Every newly generated tailored resume and cover letter is automatically audited against your real resume, with a separate **Accuracy & Fact-Check Grounding Report** shown beneath each draft."
    )
    st.markdown("---")
    st.markdown("**📊 Evaluations, Archiving & Application Tracker**")
    st.markdown(
        "- **Active & Archived Views:** Setting a posting's status to **Archived** moves it to the dedicated **🗄️ Archived** view in **Evaluations** and its own **Archived** stage in **Application Tracker**.\n"
        "- **Jump to Posting:** Use **🔍 Jump to Posting ➔** from **Application Tracker** or **Saved Documents** to open any job's full workspace immediately."
    )
    st.markdown("---")
    st.markdown("**🌐 Supported Job Sites & Scraping Guide**")
    st.markdown(
        "- **🔎 Live Job Board Search (Free, No Login):** Search **LinkedIn** (public guest search), **Direct Company Hiring Pages** (**Greenhouse**, **Ashby**, **Lever**), and **FreeHire** by role, location, workplace mode, and recency.\n"
        "- **📝 Paste Job Text, Multiple Links & Categories:** Paste raw job descriptions, batch URLs (**Built In**, **LinkedIn**, company boards), or browse category presets directly in **Job Search**.\n"
        "- **🔗 Extension Inbox:** Right-click any LinkedIn listing with the Skippy browser extension to queue it into **Extension Inbox** and evaluate in the background.\n"
        "- **🛡️ Job Text Safety Shield:** All scraped and pasted postings are deterministically sanitized to strip hidden HTML, invisible Unicode characters, and prompt-injection lines before reaching your AI."
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
        pdftotext_bin = shutil.which("pdftotext")
        soffice_bin = shutil.which("soffice") or shutil.which("libreoffice")
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "upload.pdf")
            txt_path = os.path.join(tmpdir, "upload.txt")
            with open(pdf_path, "wb") as f:
                f.write(raw_bytes)
            if pdftotext_bin:
                subprocess.run([pdftotext_bin, pdf_path, txt_path], capture_output=True, timeout=10, check=False)
            if not os.path.exists(txt_path) and soffice_bin:
                subprocess.run(
                    [soffice_bin, "--headless", "--infilter=writer_pdf_import", "--convert-to", "txt:Text", "--outdir", tmpdir, pdf_path],
                    capture_output=True,
                    timeout=15,
                    check=False,
                )
            if os.path.exists(txt_path):
                with open(txt_path, "r", encoding="utf-8", errors="ignore") as tf:
                    return tf.read().strip()
        return ""

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
    vault = st.session_state.get("resumes_vault") or load_resumes()
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

    # Bump version counter so sidebar radio renders with updated index cleanly without widget conflicts
    st.session_state["prompt_mode_version"] = st.session_state.get("prompt_mode_version", 0) + 1

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
                safe_title = html.escape(str(details["title"]))
                st.markdown(
                    f":green-background[**Active: 🧭 Career Profile**]  \n"
                    f"<small style='opacity:0.85;'>Profile: <b>{safe_title}</b></small>",
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
            ver = st.session_state.get("prompt_mode_version", 0)
            radio_key = f"prompt_mode_toggle_sb_v{ver}_{key_suffix}".strip("_")

            def _on_prompt_mode_change():
                chosen_label = st.session_state.get(radio_key)
                new_mode = PROMPT_MODE_COMPASS if chosen_label == "🧭 Career Profile" else PROMPT_MODE_CUSTOM
                set_active_prompt_mode(new_mode)
                new_details = get_active_prompt_details()
                st.toast(f"🎯 AI instructions switched to: {new_details['title']}", icon="✅")

            st.radio(
                "Evaluation Prompt Strategy:",
                mode_options,
                index=current_idx,
                key=radio_key,
                on_change=_on_prompt_mode_change,
                label_visibility="collapsed",
            )
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

    if "model_override" not in st.session_state:
        st.session_state["model_override"] = get_setting("model_override", "")

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
            was_cancelled = batch.get("was_cancelled", False)
            if batch.get("jobs"):
                st.session_state["completion_batch"] = batch
                count = len(batch["jobs"])
                src = batch.get("source", "Pipeline")
                if was_cancelled:
                    st.toast(f"⏹️ {src} Review Stopped: {count} job{'s' if count != 1 else ''} evaluated and saved.", icon="⏹️")
                else:
                    st.toast(f"🎉 Evaluation Complete! {count} job{'s' if count != 1 else ''} evaluated from {src}.", icon="✅")
            elif was_cancelled:
                st.toast("⏹️ Review Stopped: Evaluation pipeline halted.", icon="⏹️")
            elif batch.get("failed", 0) > 0:
                err_msg = f": {batch['last_error']}" if batch.get("last_error") else ""
                st.toast(f"⚠️ Evaluation finished with {batch['failed']} failed job(s){err_msg}.", icon="⚠️")
            st.rerun()
            return True
    return False

def render_pipeline_spinner_html(
    title: str,
    subtitle: str = "",
    compact: bool = False,
    is_stopping: bool = False,
) -> None:
    """Renders a continuous 60fps CSS spinner graphic alongside status text."""
    ring_color = "#f59e0b" if is_stopping else "#3b82f6"
    size_px = 18 if compact else 24
    border_px = 2.5 if compact else 3
    font_size = "0.95rem" if compact else "1.15rem"
    safe_title = html.escape(str(title or ""))
    safe_subtitle = html.escape(str(subtitle or ""))
    sub_html = (
        f"<div style='font-size:0.82rem; opacity:0.85; margin-top:2px;'>{safe_subtitle}</div>"
        if safe_subtitle else ""
    )
    st.markdown(
        f"""
        <style>
        @keyframes skippy-spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        </style>
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:8px;">
            <div style="
                width:{size_px}px;
                height:{size_px}px;
                border:{border_px}px solid rgba(59, 130, 246, 0.2);
                border-top:{border_px}px solid {ring_color};
                border-radius:50%;
                animation: skippy-spin 0.8s linear infinite;
                flex-shrink:0;
            "></div>
            <div>
                <div style="font-weight:600; font-size:{font_size}; line-height:1.25;">{safe_title}</div>
                {sub_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def start_scraper_evaluations(items: list) -> None:
    """Starts the background evaluation pipeline for a list of job dicts or URLs."""
    if not items:
        st.warning("⚠️ No postings provided to review.")
        return

    if pipeline_manager.is_running:
        st.warning("⚠️ An evaluation pipeline is already running in the background. Please wait for it to complete or stop it from the sidebar.")
        return

    chosen_resumes = st.session_state.get("selected_resumes", ["Master Resume"])
    combined_resume = combine_selected_resumes(chosen_resumes)
    st.session_state["resume_text"] = combined_resume

    system_instructions = st.session_state.get("system_instructions", "")
    if not system_instructions:
        details = get_active_prompt_details()
        system_instructions = details.get("prompt_text", "")

    api_key = st.session_state.get("user_api_key", "")
    if not api_key:
        config = load_local_config()
        api_key = config.get("user_api_key") or os.environ.get("USER_API_KEY", "")

    started = pipeline_manager.start_url_pipeline(
        urls=items,
        resume_text=combined_resume,
        system_instructions=system_instructions,
        model_choice=st.session_state.get("model_choice", "Google Gemini"),
        api_key=api_key,
        local_base_url=st.session_state.get("local_base_url", ""),
        local_model_name=st.session_state.get("local_model_name", ""),
        model_override=st.session_state.get("model_override", ""),
        source="Scraper",
        matched_resumes=", ".join(chosen_resumes),
    )
    if started:
        if "completion_batch" in st.session_state:
            del st.session_state["completion_batch"]
        st.session_state["pipeline_scroll_to_banner_nonce"] = st.session_state.get("pipeline_scroll_to_banner_nonce", 0) + 1
        st.toast("🚀 Evaluation pipeline started! Scrolling to live progress...", icon="⚡")
        st.rerun()
    else:
        st.error("Failed to start evaluation pipeline. Please check if another pipeline is running or verify your API settings.")


def render_ats_resume_downloads(
    markdown_text: str,
    ats_style_key: str,
    file_stem: str,
    docx_key: str,
    pdf_state_key: str,
    prep_pdf_key: str,
    pdf_dl_key: str,
    docx_label: str = "📥 Download ATS (.docx)",
    col_docx=None,
    col_pdf=None,
) -> None:
    """Shared DOCX + on-demand PDF export buttons for ATS resumes across Evaluations and Saved Documents."""
    from evaluator import generate_ats_resume_docx, generate_ats_resume_pdf, is_pdf_conversion_available

    has_pdf = is_pdf_conversion_available()
    if col_docx is None:
        if has_pdf:
            col_docx, col_pdf = st.columns(2)
        else:
            col_docx = st.container()
            col_pdf = None

    with col_docx:
        st.download_button(
            docx_label,
            data=lambda: generate_ats_resume_docx(markdown_text, template_style=ats_style_key),
            file_name=f"{file_stem}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            width="stretch",
            type="primary",
            key=docx_key,
        )

    if has_pdf and col_pdf is not None:
        with col_pdf:
            pdf_src = (markdown_text, ats_style_key)
            cached_pdf = st.session_state.get(pdf_state_key)
            if not (cached_pdf and cached_pdf[0] == pdf_src) and st.button("📕 Prepare ATS PDF", width="stretch", key=prep_pdf_key):
                with st.spinner("Converting to PDF (first run can take ~20s)..."):
                    built = generate_ats_resume_pdf(*pdf_src)
                if built:
                    st.session_state[pdf_state_key] = (pdf_src, built)
                else:
                    st.warning("PDF conversion failed. Download the .docx instead, or try again.")
            cached_pdf = st.session_state.get(pdf_state_key)
            if cached_pdf and cached_pdf[0] == pdf_src:
                st.download_button(
                    "📕 Download ATS (.pdf)",
                    data=cached_pdf[1],
                    file_name=f"{file_stem}.pdf",
                    mime="application/pdf",
                    width="stretch",
                    key=pdf_dl_key,
                )


def navigate_to_page(page_path: str) -> None:
    """Defers page switching to the next full-app rerun in app.py.

    Calling st.switch_page while a @st.fragment(run_every=...) timer is active can
    race with a stale auto-rerun carrying the previous page_script_hash, causing
    Streamlit's frontend to wipe the destination page blank. A full-app rerun first
    clears browser auto-rerun intervals before app.py calls st.switch_page.
    """
    st.session_state["_pending_switch_page"] = page_path
    st.rerun()


@st.fragment(run_every="2s")
def _render_running_top_pipeline_banner():
    """Polls active background evaluation progress every 2 seconds."""
    if check_and_handle_pipeline_completion():
        return
    status = pipeline_manager.get_status()
    if not status.get("is_running"):
        st.rerun()
        return

    st.html("<div id='global_pipeline_top_banner' style='scroll-margin-top: 100px;'></div>")
    is_stopping = status.get("is_stopping", False)
    total = max(status.get("total", 1), 1)
    completed = status.get("completed", 0)
    remaining = max(total - completed, 0)
    prog = min(completed / total, 1.0)
    cur = status.get("current_job", "Initializing...")
    source = status.get("source", "Job Evaluation")

    with st.container(border=True):
        st.markdown(
            f"""
            <style>
            @keyframes skippy-spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
            @keyframes skippy-pulse-ring {{
                0% {{ box-shadow: 0 0 0 0 rgba(147, 51, 234, 0.6); }}
                70% {{ box-shadow: 0 0 0 10px rgba(147, 51, 234, 0); }}
                100% {{ box-shadow: 0 0 0 0 rgba(147, 51, 234, 0); }}
            }}
            .skippy-pipeline-banner {{
                background: linear-gradient(135deg, rgba(147, 51, 234, 0.12) 0%, rgba(59, 130, 246, 0.12) 100%);
                border-radius: 8px;
                padding: 14px 18px;
                border: 1px solid rgba(147, 51, 234, 0.35);
                margin-bottom: 12px;
            }}
            .skippy-banner-spinner {{
                width: 34px;
                height: 34px;
                border: 3.5px solid rgba(147, 51, 234, 0.2);
                border-top: 3.5px solid #9333ea;
                border-radius: 50%;
                animation: skippy-spin 0.8s linear infinite;
                flex-shrink: 0;
            }}
            .skippy-inline-spinner {{
                width: 15px;
                height: 15px;
                border: 2px solid rgba(147, 51, 234, 0.2);
                border-top: 2px solid #9333ea;
                border-radius: 50%;
                animation: skippy-spin 0.8s linear infinite;
                flex-shrink: 0;
                display: inline-block;
            }}
            .skippy-live-pill {{
                display: inline-flex;
                align-items: center;
                gap: 6px;
                background: {'rgba(239, 68, 68, 0.2)' if is_stopping else 'rgba(16, 185, 129, 0.2)'};
                color: {'#ef4444' if is_stopping else '#10b981'};
                border: 1px solid {'rgba(239, 68, 68, 0.4)' if is_stopping else 'rgba(16, 185, 129, 0.4)'};
                padding: 3px 10px;
                border-radius: 9999px;
                font-size: 0.75rem;
                font-weight: 700;
                letter-spacing: 0.05em;
            }}
            .skippy-live-dot {{
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: {'#ef4444' if is_stopping else '#10b981'};
                animation: skippy-pulse-ring 1.5s infinite;
            }}
            </style>
            <div class="skippy-pipeline-banner">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                    <div style="display:flex; align-items:center; gap:14px;">
                        {f'''<span style="font-size:1.8rem; line-height:1;">🛑</span>''' if is_stopping else f'''<div style="position:relative; width:34px; height:34px; display:flex; align-items:center; justify-content:center; flex-shrink:0;"><div class="skippy-banner-spinner" style="position:absolute; width:100%; height:100%; box-sizing:border-box;"></div><span style="font-size:1.1rem; line-height:1;">⚡</span></div>'''}
                        <div>
                            <h3 style="margin:0; font-size:1.2rem; font-weight:700; letter-spacing:-0.01em;">
                                {'Halting Evaluation Pipeline...' if is_stopping else 'AI Job Evaluation Pipeline In Progress'}
                            </h3>
                            <p style="margin:2px 0 0 0; font-size:0.86rem; opacity:0.85;">
                                {'Wrapping up active analysis and safely committing progress...' if is_stopping else 'Skippy is scoring postings in the background with 4-pillar rubrics, eligibility compliance, and gap analysis.'}
                            </p>
                        </div>
                    </div>
                    <div class="skippy-live-pill">
                        <span class="skippy-live-dot"></span>
                        <span>{'STOPPING' if is_stopping else 'LIVE PIPELINE'}</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Key live metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Evaluated", f"{completed} / {total}")
        c2.metric("Progress", f"{int(prog * 100)}%")
        c3.metric("Remaining", f"{remaining}")
        c4.metric("Source", source)

        st.progress(prog, text=f"Evaluating role {min(completed + 1, total)} of {total} ({int(prog * 100)}% complete)...")

        escaped_cur = html.escape(cur)
        st.markdown(
            f"""
            <div style="
                padding: 8px 12px;
                background: rgba(128, 128, 128, 0.08);
                border-left: 3px solid rgba(147, 51, 234, 0.8);
                border-radius: 4px;
                margin: 8px 0 12px 0;
                font-size: 0.88rem;
                display: flex;
                align-items: center;
                gap: 8px;
                flex-wrap: wrap;
            ">
                {f'<span style="font-size:1rem;">🛑</span>' if is_stopping else '<div class="skippy-inline-spinner"></div>'}
                <span style="font-weight:600; color:rgba(147, 51, 234, 1.0);">Currently Evaluating:</span>
                <span style="font-family: monospace; font-size: 0.85rem;">{escaped_cur}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        btn_col1, btn_col2, _ = st.columns([2.5, 3.5, 4.0], vertical_alignment="center")
        with btn_col1:
            if is_stopping:
                st.button("🛑 Stopping...", key="btn_stop_top_banner_disabled", disabled=True, width="stretch")
            else:
                if st.button("🛑 Stop Review", key="btn_stop_top_banner", type="secondary", width="stretch"):
                    pipeline_manager.cancel()
                    st.rerun()
        with btn_col2:
            if st.button("📁 View Completed in Evaluations ➔", key="btn_view_running_banner_hist", type="primary", width="stretch"):
                st.session_state["active_history_source"] = source
                navigate_to_page("pages/2_history.py")

    st.markdown("---")

    # Smooth auto-scroll to the top banner when a review is started
    current_scroll_nonce = st.session_state.get("pipeline_scroll_to_banner_nonce", 0)
    last_scrolled_nonce = st.session_state.get("_last_pipeline_scroll_nonce", -1)

    if current_scroll_nonce > 0 and current_scroll_nonce != last_scrolled_nonce:
        st.session_state["_last_pipeline_scroll_nonce"] = current_scroll_nonce
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
                        const target = doc.getElementById('global_pipeline_top_banner');
                        if (target) {{
                            clearInterval(interval);
                            target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                        }} else {{
                            const main = doc.querySelector('.stMain') || doc.querySelector('[data-testid=\"stMain\"]') || (window.parent || window);
                            if (main && typeof main.scrollTo === 'function') {{
                                main.scrollTo({{ top: 0, behavior: 'smooth' }});
                            }}
                            if (attempts >= maxAttempts) clearInterval(interval);
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


def render_global_top_pipeline_banner():
    """
    Renders a prominent, full-width screen-wide banner notification
    across all app pages whenever background job evaluations are underway,
    or upon completion with a one-click navigation jump to Evaluations.

    Only mounts a 2-second polling fragment while a pipeline is actively running.
    """
    if check_and_handle_pipeline_completion():
        return
    status = pipeline_manager.get_status()
    is_running = bool(status.get("is_running"))
    was_running = bool(st.session_state.get("_last_observed_pipeline_running", False))
    st.session_state["_last_observed_pipeline_running"] = is_running

    if is_running and not was_running:
        st.session_state["pipeline_scroll_to_banner_nonce"] = st.session_state.get("pipeline_scroll_to_banner_nonce", 0) + 1

    if is_running:
        _render_running_top_pipeline_banner()
    elif "completion_batch" in st.session_state and st.session_state["completion_batch"].get("jobs"):
        batch = st.session_state["completion_batch"]
        jobs = batch.get("jobs", [])
        count = len(jobs)
        src = batch.get("source", "Pipeline")
        was_cancelled = batch.get("was_cancelled", False)

        strong = sum(1 for j in jobs if j.get("Score", 0) >= 75 and j.get("Eligible", True))
        reach = sum(1 for j in jobs if j.get("Score", 0) < 75 and j.get("Eligible", True))
        disqualified = sum(1 for j in jobs if not j.get("Eligible", True))

        with st.container(border=True):
            st.markdown(
                f"""
                <div style="display:flex; align-items:center; gap:12px; margin-bottom:8px;">
                    <span style="font-size:2rem; line-height:1;">{'⏹️' if was_cancelled else '🎉'}</span>
                    <div>
                        <h3 style="margin:0; font-size:1.25rem; font-weight:700;">
                            {'Evaluation Stopped' if was_cancelled else 'Evaluation Pipeline Finished!'}
                        </h3>
                        <p style="margin:2px 0 0 0; font-size:0.88rem; opacity:0.85;">
                            {'Review halted gracefully. All evaluated jobs were saved to your database.' if was_cancelled else f'Successfully evaluated {count} posting(s) from <strong>{html.escape(src)}</strong>. Tailored materials are ready to generate.'}
                        </p>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Jobs Evaluated", count)
            m2.metric("Strong Matches (75+)", strong)
            m3.metric("Moderate Matches", reach)
            m4.metric("Dealbreakers", disqualified)

            col_view, col_dismiss, _ = st.columns([3.5, 2.0, 4.5], vertical_alignment="center")
            with col_view:
                if st.button("📁 View in Evaluations ➔", key="btn_view_done_banner_hist", type="primary", width="stretch"):
                    st.session_state["active_history_source"] = src
                    st.session_state.pop("completion_batch", None)
                    pipeline_manager.dismiss_latest_run()
                    navigate_to_page("pages/2_history.py")
            with col_dismiss:
                if st.button("Dismiss", key="btn_dismiss_top_banner", width="stretch"):
                    st.session_state.pop("completion_batch", None)
                    pipeline_manager.dismiss_latest_run()
                    st.rerun()

        st.markdown("---")


@st.fragment(run_every="2s")
def _render_running_pipeline_sidebar_status():
    """Polls active background pipeline status in the sidebar every 2 seconds."""
    if check_and_handle_pipeline_completion():
        return
    status = pipeline_manager.get_status()
    if not status.get("is_running"):
        st.rerun()
        return

    with st.container(border=True):
        if status.get("is_stopping"):
            st.caption("🛑 **Halting Pipeline...**")
            st.button("Stopping...", key="btn_cancel_global_pipeline_disabled", width="stretch", disabled=True)
        else:
            total = max(status.get("total", 1), 1)
            completed = status.get("completed", 0)
            prog = min(completed / total, 1.0)
            st.markdown(f"⚡ **Pipeline:** {completed}/{total} Jobs")
            st.progress(prog)
            if st.button("🛑 Stop Review", key="btn_cancel_global_pipeline", width="stretch"):
                pipeline_manager.cancel()
                st.rerun()


def render_global_pipeline_status():
    if check_and_handle_pipeline_completion():
        return
    status = pipeline_manager.get_status()

    # If pipeline is running, mount a 2-second polling card in the sidebar
    if status.get("is_running"):
        _render_running_pipeline_sidebar_status()

    # If a completion batch exists, show a static quick action card in the sidebar (no polling)
    elif "completion_batch" in st.session_state and st.session_state["completion_batch"].get("jobs"):
        batch = st.session_state["completion_batch"]
        count = len(batch.get("jobs", []))
        src = batch.get("source", "Pipeline")
        with st.container(border=True):
            st.success(f"🎉 **{count}** jobs ready ({src})!")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📁 Evaluations", key="sb_view_hist", width="stretch"):
                    st.session_state["active_history_source"] = src
                    st.session_state.pop("completion_batch", None)
                    pipeline_manager.dismiss_latest_run()
                    navigate_to_page("pages/2_history.py")
            with col2:
                if st.button("Dismiss", key="sb_dismiss_batch", width="stretch"):
                    st.session_state.pop("completion_batch", None)
                    pipeline_manager.dismiss_latest_run()
                    st.rerun()


def inject_interactive_hover_halo_effects():
    """
    Injects smooth interactive hover and luminous halo effects on buttons
    and navigation elements styled in blue and white.
    """
    st.markdown(
        """<style>
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
            font-size: 1.05rem !important;
            font-weight: 500 !important;
        }
        /* Submenu indicator on Job Search */
        [data-testid="stSidebarNav"] ul > li:has(a[href*="1_scraper"]) a::after {
            content: "▾";
            margin-left: auto;
            font-size: 0.85rem;
            opacity: 0.6;
        }
        /* Nested sub-button styling for Extension Inbox directly under Job Search */
        [data-testid="stSidebarNav"] ul > li:has(a[href*="5_linkedin"]),
        [data-testid="stSidebarNav"] ul > li:has(a[href*="linkedin"]) {
            position: relative;
            padding-left: 1.65rem !important;
            margin-top: -3px !important;
        }
        /* L-shaped tree branch connector (└──) */
        [data-testid="stSidebarNav"] ul > li:has(a[href*="5_linkedin"])::before,
        [data-testid="stSidebarNav"] ul > li:has(a[href*="linkedin"])::before {
            content: "";
            position: absolute;
            left: 1.15rem;
            top: 0;
            height: 50%;
            width: 0.65rem;
            border-left: 2px solid rgba(150, 150, 150, 0.45);
            border-bottom: 2px solid rgba(150, 150, 150, 0.45);
            border-bottom-left-radius: 4px;
            pointer-events: none;
        }
        [data-testid="stSidebarNav"] ul > li:has(a[href*="5_linkedin"]) span,
        [data-testid="stSidebarNav"] ul > li:has(a[href*="linkedin"]) span {
            font-size: 0.95rem !important;
            font-weight: 400 !important;
            opacity: 0.95;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    with st.sidebar:
        render_global_pipeline_status()

    st.sidebar.header("🔌 LLM Configuration")
    
    model_options = ["Google Gemini", "OpenAI ChatGPT", "xAI Grok", "Anthropic Claude", "Local / Custom (Ollama)"]
    current_provider = st.session_state.get("model_choice", "Google Gemini")
    if current_provider not in model_options:
        current_provider = "Google Gemini"
        st.session_state["model_choice"] = current_provider

    if st.session_state.get("sb_model_choice_select") not in model_options:
        st.session_state["sb_model_choice_select"] = current_provider

    def _on_sidebar_model_change():
        chosen = st.session_state.get("sb_model_choice_select", "Google Gemini")
        st.session_state["model_choice"] = chosen
        set_setting("model_choice", chosen)

    st.sidebar.selectbox(
        "Select AI Provider",
        model_options,
        key="sb_model_choice_select",
        on_change=_on_sidebar_model_change,
    )
    st.session_state["model_choice"] = st.session_state["sb_model_choice_select"]

    sb_test_clicked = False
    sb_test_status = None
    if "Local" in st.session_state["model_choice"]:
        if "sb_local_base_url" not in st.session_state:
            st.session_state["sb_local_base_url"] = st.session_state.get("local_base_url", "http://localhost:11434/v1")
        if "sb_local_model_name" not in st.session_state:
            st.session_state["sb_local_model_name"] = st.session_state.get("local_model_name", "llama3")

        def _on_local_llm_change():
            base_url = (st.session_state.get("sb_local_base_url") or "http://localhost:11434/v1").strip()
            model_name = (st.session_state.get("sb_local_model_name") or "llama3").strip()
            st.session_state["local_base_url"] = base_url
            st.session_state["local_model_name"] = model_name
            set_setting("local_base_url", base_url)
            set_setting("local_model_name", model_name)

        st.sidebar.text_input(
            "Local API Base URL",
            key="sb_local_base_url",
            on_change=_on_local_llm_change,
        )
        st.sidebar.text_input(
            "Local Model Name",
            key="sb_local_model_name",
            on_change=_on_local_llm_change,
        )
        st.session_state["local_base_url"] = st.session_state["sb_local_base_url"]
        st.session_state["local_model_name"] = st.session_state["sb_local_model_name"]
    else:
        current_key = st.session_state.get("user_api_key", "")
        if "temp_api_key_input" not in st.session_state:
            st.session_state["temp_api_key_input"] = current_key

        updated_key = (st.sidebar.text_input(
            "Enter API Key", 
            type="password", 
            key="temp_api_key_input",
            on_change="ignore",
            help="Works seamlessly with the selected provider."
        ) or "").strip().strip("'\"")
        
        if updated_key and updated_key != current_key:
            save_local_config(updated_key)
            st.session_state["user_api_key"] = updated_key
            st.toast("Key Accepted! ✅", icon="🔑")

        sb_test_clicked = st.sidebar.button("🧪 Test Connection", key="btn_sb_test_key", width="stretch")
        sb_test_status = st.sidebar.empty()

        with st.sidebar.expander("⚙️ Advanced Settings"):
            if "sb_model_override" not in st.session_state:
                st.session_state["sb_model_override"] = st.session_state.get("model_override", "")

            def _on_model_override_change():
                override_val = (st.session_state.get("sb_model_override") or "").strip()
                st.session_state["model_override"] = override_val
                set_setting("model_override", override_val)

            st.text_input(
                "Model Version Override (Optional)",
                key="sb_model_override",
                on_change=_on_model_override_change,
                help="Leave blank to use recommended defaults (e.g., 'gemini-flash-latest' or 'gpt-4o-mini'). Examples: 'gemini-2.5-pro', 'gpt-4o', 'claude-3-7-sonnet-latest'.",
            )
            st.session_state["model_override"] = st.session_state["sb_model_override"]

    render_prompt_mode_toggle(in_sidebar=True)
    render_help_section(in_sidebar=True)
    render_sidebar_auth_controls()

    if sb_test_clicked and sb_test_status is not None:
        val = (st.session_state.get("temp_api_key_input") or "").strip().strip("'\"")
        if val:
            save_local_config(val)
            st.session_state["user_api_key"] = val
        sb_test_status.info("⏳ Testing connection...")
        ok, msg = test_ai_connection(st.session_state["model_choice"], val)
        if ok:
            sb_test_status.success("Connected! ✅")
        else:
            sb_test_status.error(f"❌ {msg[:120]}")

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
        if current_choice not in model_options:
            current_choice = "Google Gemini"
            st.session_state["model_choice"] = current_choice

        if st.session_state.get("onboarding_model_choice_select") not in model_options:
            st.session_state["onboarding_model_choice_select"] = current_choice

        selected_model = st.selectbox(
            "Select AI Provider",
            model_options,
            key="onboarding_model_choice_select",
        )
        if "Local" not in selected_model:
            st.session_state["model_choice"] = selected_model
            st.session_state["sb_model_choice_select"] = selected_model

        api_key_val = st.session_state.get("user_api_key", "")
        local_base = st.session_state.get("local_base_url", "http://localhost:11434/v1")
        local_model = st.session_state.get("local_model_name", "llama3")

        with st.container():
            if selected_model == "Google Gemini":
                st.info(
                    "💡 **Google Gemini is recommended**. "
                    "[Click here to get your Gemini API key from Google AI Studio ↗](https://aistudio.google.com/app/apikey)",
                    icon="✨"
                )
                api_key_input = st.text_input(
                    "Enter Google Gemini API Key",
                    value=api_key_val,
                    type="password",
                    key="onboarding_gemini_api_key_input",
                    on_change="ignore",
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
                    local_base = st.text_input(
                        "Local API Base URL",
                        value=local_base,
                        key="onboarding_local_base_url_input",
                        on_change="ignore",
                    )
                with c_mod:
                    local_model = st.text_input(
                        "Local Model Name",
                        value=local_model,
                        key="onboarding_local_model_name_input",
                        on_change="ignore",
                    )
                api_key_input = ""
            else:
                provider_slug = selected_model.replace(" ", "_").lower()
                api_key_input = st.text_input(
                    f"Enter {selected_model} API Key",
                    value=api_key_val,
                    type="password",
                    key=f"onboarding_{provider_slug}_api_key_input",
                    on_change="ignore",
                    help=f"Enter your API key for {selected_model}."
                )

        clean_input_key = (api_key_input or "").strip().strip("'\"")

        col_test, col_save = st.columns([1, 1.4])
        with col_test:
            test_clicked = st.button(
                "🧪 Test Connection",
                key="btn_onboarding_test_connection",
                type="secondary",
                width="stretch",
            )
        with col_save:
            save_clicked = st.button(
                "Save & Continue ➔",
                key="btn_onboarding_save_continue",
                type="primary",
                width="stretch",
            )

        status_slot = st.empty()

        st.markdown("---")
        render_help_section(in_sidebar=False)

        if test_clicked:
            status_slot.info("⏳ Testing AI connection...")
            test_key = clean_input_key if selected_model != "Local / Custom (Ollama)" else ""
            ok, msg = test_ai_connection(
                selected_model,
                test_key,
                local_base_url=local_base,
                local_model_name=local_model,
            )
            if ok:
                status_slot.success(f"✅ {msg}")
            else:
                status_slot.error(f"❌ {msg}")

        if save_clicked:
            st.session_state["model_choice"] = selected_model
            st.session_state["sb_model_choice_select"] = selected_model
            set_setting("model_choice", selected_model)
            if selected_model == "Local / Custom (Ollama)":
                set_setting("local_base_url", local_base)
                set_setting("local_model_name", local_model)
                st.session_state["local_base_url"] = local_base
                st.session_state["local_model_name"] = local_model
                st.session_state["sb_local_base_url"] = local_base
                st.session_state["sb_local_model_name"] = local_model
                st.session_state["show_key_success"] = True
                st.rerun()
            else:
                if clean_input_key:
                    save_local_config(clean_input_key)
                    st.session_state["user_api_key"] = clean_input_key
                    st.session_state["show_key_success"] = True
                    st.rerun()
                else:
                    status_slot.warning("Please enter a valid API key to continue.")

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

        # 2. Text Area (Review, Edit, or Paste Directly)
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
                    st.warning("Please upload a file or paste your resume before proceeding.")
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

        # Primary Hero Action: Auto-Detect
        with st.container(border=True):
            st.markdown("### ⚡ Auto-Detect Career Profile from Resume (Recommended)")
            st.caption("AI analyzes your uploaded master resume to automatically identify your career field, licenses, specialized tools, and core competencies.")
            if st.button("⚡ Generate Career Profile with AI", type="primary", width="stretch", key="btn_onboard_hero_autodetect"):
                with st.spinner("Setting up your career profile..."):
                    detected_profile = career_compass.auto_detect_alignment_from_resume(
                        st.session_state.get("resume_text", ""),
                        use_ai=True,
                        industry_hint="",
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

def render_completion_card(batch_jobs: list[dict], source_label: str = "Scraper"):
    """
    Renders an accessible completion card summarizing the recent evaluation run.
    Gives the user full agency to review highlights before transitioning to History.
    """
    if not batch_jobs:
        return

    from datetime import datetime
    was_cancelled = bool(st.session_state.get("completion_batch", {}).get("was_cancelled", False))

    with st.container(border=True):
        if was_cancelled:
            st.subheader("⏹️ Job Review Stopped")
        else:
            st.subheader("🎉 Job Reviews Finished!")
        total = len(batch_jobs)
        strong = sum(1 for j in batch_jobs if j.get("Score", 0) >= 75 and j.get("Eligible", True))
        reach = sum(1 for j in batch_jobs if j.get("Score", 0) < 75 and j.get("Eligible", True))
        disqualified = sum(1 for j in batch_jobs if not j.get("Eligible", True))

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Jobs Evaluated Before Stop" if was_cancelled else "Jobs Reviewed", total)
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
                st.session_state.pop("completion_batch", None)
                pipeline_manager.dismiss_latest_run()
                navigate_to_page("pages/2_history.py")
        with col_btn2:
            if st.button("➕ Review More Jobs", width="stretch", key=f"eval_more_{source_label}"):
                st.session_state.pop("completion_batch", None)
                pipeline_manager.dismiss_latest_run()
                st.rerun()