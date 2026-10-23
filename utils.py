import os
import io
import json
import re
import streamlit as st
from dotenv import load_dotenv, set_key
import streamlit.components.v1 as components
from pipeline import pipeline_manager
from auth import enforce_authentication, render_sidebar_auth_controls, logout_user

from database import secure_file_permissions, atomic_write_text, atomic_write_json, set_env_var_safe

ENV_FILE = ".env"
RESUMES_FILE = "resumes.json"

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
        "📄 Active Resume(s) for Evaluation & Harvesting:",
        options=all_names,
        key=widget_key,
        on_change=_on_resume_sel_change,
        help="Select 1 or more resumes to evaluate against. Selecting only the relevant resume(s) keeps evaluation fast; selecting multiple lets Skippy combine and harvest the best matching skills & projects across them in a single pass.",
    )
    if not chosen_names:
        chosen_names = [all_names[0]]
        st.session_state["selected_resumes"] = chosen_names

    combined_text = combine_selected_resumes(chosen_names, vault)
    st.session_state["resume_text"] = combined_text
    if len(chosen_names) > 1:
        container.caption(
            f"✨ **Multi-Resume Harvesting Active ({len(chosen_names)} selected):** Skippy will evaluate against the combined skill pool and harvest the best-fitting roles, projects, and bullets across {', '.join(f'`{n}`' for n in chosen_names)}."
        )
    return chosen_names, combined_text


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
            if st.button("🛑 Cancel Pipeline", key="btn_cancel_global_pipeline", width="stretch"):
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
                if st.button("📂 History", key="sb_view_hist", width="stretch"):
                    st.session_state["active_history_source"] = src
                    st.switch_page("pages/2_history.py")
            with col2:
                if st.button("Dismiss", key="sb_dismiss_batch", width="stretch"):
                    del st.session_state["completion_batch"]
                    pipeline_manager.dismiss_latest_run()
                    st.rerun()


def inject_interactive_hover_halo_effects():
    """
    Injects smooth interactive hover and halo (luminous glow) effects on buttons
    and menus while preserving 100% of the default Streamlit theme, textures, and colors.
    """
    st.markdown(
        """
        <style>
        /* Smooth transitions for interactive buttons */
        .stButton > button,
        button[data-testid="baseButton-primary"],
        button[data-testid="baseButton-secondary"],
        [data-testid="stLinkButton"] a,
        [data-testid="stDownloadButton"] button,
        button[data-testid="stBaseButton-primary"],
        button[data-testid="stBaseButton-secondary"] {
            transition: transform 0.15s cubic-bezier(0.16, 1, 0.3, 1),
                        box-shadow 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
        }

        /* Primary Button Hover Lift & Halo Glow */
        .stButton > button[kind="primary"]:hover,
        button[data-testid="baseButton-primary"]:hover,
        [data-testid="stLinkButton"] a[kind="primary"]:hover,
        [data-testid="stLinkButton"] a:hover,
        [data-testid="stDownloadButton"] button[kind="primary"]:hover,
        button[data-testid="stBaseButton-primary"]:hover {
            transform: translateY(-1.5px) !important;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15), 0 0 14px 2px rgba(255, 75, 75, 0.38) !important;
        }

        /* Primary Button Active Press */
        .stButton > button[kind="primary"]:active,
        button[data-testid="baseButton-primary"]:active,
        [data-testid="stLinkButton"] a:active,
        [data-testid="stDownloadButton"] button[kind="primary"]:active,
        button[data-testid="stBaseButton-primary"]:active {
            transform: translateY(0.5px) !important;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12), 0 0 8px 1px rgba(255, 75, 75, 0.25) !important;
        }

        /* Secondary Button Hover Lift & Soft Halo Glow */
        .stButton > button[kind="secondary"]:hover,
        button[data-testid="baseButton-secondary"]:hover,
        .stButton > button:not([kind="primary"]):hover,
        [data-testid="stDownloadButton"] button:not([kind="primary"]):hover,
        button[data-testid="stBaseButton-secondary"]:hover {
            transform: translateY(-1.5px) !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08), 0 0 10px 1px rgba(130, 150, 175, 0.32) !important;
        }

        /* Secondary Button Active Press */
        .stButton > button[kind="secondary"]:active,
        button[data-testid="baseButton-secondary"]:active,
        .stButton > button:not([kind="primary"]):active,
        [data-testid="stDownloadButton"] button:not([kind="primary"]):active,
        button[data-testid="stBaseButton-secondary"]:active {
            transform: translateY(0.5px) !important;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08) !important;
        }

        /* Sidebar Navigation Menu Items - Hover Shift & Glowing Halo */
        [data-testid="stSidebarNav"] ul > li a {
            transition: transform 0.18s cubic-bezier(0.16, 1, 0.3, 1),
                        box-shadow 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
            border-radius: 8px !important;
        }

        [data-testid="stSidebarNav"] ul > li a:hover {
            transform: translateX(3px) !important;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06), 0 0 12px 2px rgba(255, 75, 75, 0.22) !important;
        }

        /* Expander Accordion Menu Headers - Subtle Lift & Halo */
        [data-testid="stExpander"] > details > summary,
        [data-testid="stExpander"] summary {
            transition: transform 0.18s cubic-bezier(0.16, 1, 0.3, 1),
                box-shadow 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
            border-radius: 8px !important;
        }

        [data-testid="stExpander"] > details > summary:hover,
        [data-testid="stExpander"] summary:hover {
            transform: translateY(-1px) !important;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.06), 0 0 10px 1px rgba(255, 75, 75, 0.20) !important;
        }

        /* Navigation Tabs Menu - Subtle Lift & Glowing Halo on Hover */
        [data-testid="stTabs"] [data-baseweb="tab"] {
            transition: transform 0.15s cubic-bezier(0.16, 1, 0.3, 1),
                        box-shadow 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
            border-radius: 6px !important;
        }

        [data-testid="stTabs"] [data-baseweb="tab"]:hover {
            transform: translateY(-1px) !important;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05), 0 0 8px 1px rgba(255, 75, 75, 0.22) !important;
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

    render_help_section(in_sidebar=True)
    render_sidebar_auth_controls()

def enforce_onboarding():
    enforce_authentication()
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
        _, top_right_col = st.columns([6, 1])
        with top_right_col:
            if st.button("🔒 Log Out", key="btn_onboarding_logout", width="stretch"):
                logout_user()
                st.rerun()
    
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
                    save_resumes({"Master Resume": initial_resume})
                    st.session_state["resumes_vault"] = {"Master Resume": initial_resume}
                    st.session_state["selected_resumes"] = ["Master Resume"]
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
                sub_parts.append(f"Tech: {job['Technical Score']}")
            if job.get("Experience Score"):
                sub_parts.append(f"Exp: {job['Experience Score']}")
            if job.get("Behavioral Score"):
                sub_parts.append(f"Behav: {job['Behavioral Score']}")
            if job.get("Career Score"):
                sub_parts.append(f"Career: {job['Career Score']}")
            sub_str = f" · *({' | '.join(sub_parts)})*" if sub_parts else ""
            st.markdown(f"- {pos_display} — `{badge}` ({detail}){sub_str}")
            if job.get("Summary"):
                st.caption(f"> {job['Summary']}")

        st.markdown("")
        col_btn1, col_btn2 = st.columns([1.6, 1])
        with col_btn1:
            if st.button("👉 View in History & Tailor Documents 🚀", type="primary", width="stretch", key=f"view_hist_{source_label}"):
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
            if st.button("➕ Evaluate More Postings", width="stretch", key=f"eval_more_{source_label}"):
                if "completion_batch" in st.session_state:
                    del st.session_state["completion_batch"]
                st.rerun()