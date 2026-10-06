import os
import streamlit as st
from dotenv import load_dotenv, set_key

ENV_FILE = ".env"

# Ensure the .env file exists so we can safely write to it
if not os.path.exists(ENV_FILE):
    open(ENV_FILE, 'a').close()

# Load any existing keys into the environment
load_dotenv(ENV_FILE)

def load_local_config():
    """Loads the API key securely from the environment variables."""
    return os.environ.get("USER_API_KEY", "")

def save_local_config(api_key):
    """Saves the API key securely to the .env file."""
    set_key(ENV_FILE, "USER_API_KEY", api_key)
    os.environ["USER_API_KEY"] = api_key

def render_help_section():
    with st.sidebar.expander("❓ Help & Setup Guide"):
        st.markdown("**🔑 Acquiring API Keys**")
        st.markdown("NOTE: We recommend using Google Gemini as it has been extensively tested, works the best and also is free to use!")
        st.markdown(
            "- **Google Gemini:** [Google AI Studio](https://aistudio.google.com/app/apikey)\n"
            "- **OpenAI ChatGPT:** [OpenAI Platform](https://platform.openai.com/api-keys)\n"
            "- **Anthropic Claude:** [Anthropic Console](https://console.anthropic.com/settings/keys)\n"
            "- **xAI Grok:** [xAI Console](https://console.x.ai/)"
        )
        st.markdown("---")
        st.markdown("**📊 Using the Pipeline**")
        st.markdown("- **Focus Mode:** Click any checkbox in the Overview Table to instantly jump to that job's details.\n"
                    "- **Status Tracking:** Changing a job's status automatically color-codes your pipeline table.")
        st.markdown("---")
        st.markdown("**⚠️ Formatting Notice**")
        st.markdown("When downloading a tailored resume, paste the newly generated bullet points into your stylized Word template using **'Keep Text Only'**.")

def initialize_core_state():
    """Ensures all global state variables exist before any page loads."""
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

def setup_sidebar():
    # --- GUARANTEES INITIALIZATION RUNS FIRST ---
    initialize_core_state()

    # --- NEW: Inject CSS to increase sidebar font size ---
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
        "Select AI Provider / Model",
        model_options,
        index=model_options.index(st.session_state["model_choice"])
    )

    if "user_api_key" not in st.session_state or not st.session_state.user_api_key:
        st.session_state.user_api_key = load_local_config()

    def confirm_api_key():
        if st.session_state.get("temp_api_key_input"):
            st.toast("API Key successfully registered!", icon="🔑")

    if "Local" in st.session_state["model_choice"]:
        st.session_state["local_base_url"] = st.sidebar.text_input("Local API Base URL", value="http://localhost:11434/v1")
        st.session_state["local_model_name"] = st.sidebar.text_input("Local Model Name", value="llama3")
        st.session_state["user_api_key"] = ""
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
            save_local_config(updated_key)

    render_help_section()

def enforce_onboarding():
    """Acts as a gatekeeper across all pages if the API key is missing."""
    if not st.session_state.get("user_api_key") and "Local" not in st.session_state.get("model_choice", ""):
        st.title("Welcome to Skippy! 🦘")
        st.write("Before we start analyzing job postings, let's connect your local CRM to Google Gemini.")
        st.write("NOTE: We recommend using Google Gemini as it has been extensively tested, works the best and also is free to use!")
        
        st.info(
            "**Setup Instructions (Free & Takes 30 Seconds):**\n\n"
            "1. Click the link in the Help sidebar to get an API key.\n"
            "2. Paste it into the 'Enter API Key' box in the sidebar.\n"
            "3. Press Enter.",
            icon="ℹ️"
        )
        st.stop()