import os
import streamlit as st
from dotenv import load_dotenv, set_key
import streamlit.components.v1 as components

ENV_FILE = ".env"

if not os.path.exists(ENV_FILE):
    open(ENV_FILE, 'a').close()

load_dotenv(ENV_FILE)

def load_local_config():
    return os.environ.get("USER_API_KEY", "")

def save_local_config(api_key):
    set_key(ENV_FILE, "USER_API_KEY", api_key)
    os.environ["USER_API_KEY"] = api_key

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
            try:
                with open("resume.md", "r", encoding="utf-8") as f:
                    default_resume = f.read()
            except Exception:
                pass
        st.session_state.resume_text = default_resume
        
    if "model_choice" not in st.session_state:
        st.session_state["model_choice"] = "Google Gemini"

    # 2. Load API Key from disk BEFORE the gatekeeper checks it
    if "user_api_key" not in st.session_state or not st.session_state.user_api_key:
        st.session_state.user_api_key = load_local_config()

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
            st.session_state["user_api_key"] = updated_key
            st.session_state["show_key_success"] = True
            save_local_config(updated_key)
            st.rerun()

        if st.session_state.get("show_key_success"):
            st.sidebar.success("Key Accepted! ✅")
            components.html(
                """
                <script>
                setTimeout(function() {
                    const alerts = window.parent.document.querySelectorAll('[data-testid="stAlert"]');
                    alerts.forEach(alert => {
                        if (alert.innerText.includes("Key Accepted!")) {
                            alert.style.display = "none";
                        }
                    });
                }, 10000);
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
                    st.session_state["user_api_key"] = api_key.strip()
                    st.session_state["show_key_success"] = True
                    save_local_config(api_key.strip())
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
                    st.success("Master resume saved! Initializing dashboard...")
                    st.rerun()
                    
        st.markdown("---")
        render_help_section(in_sidebar=False)
        st.stop()