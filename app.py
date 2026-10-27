import os
os.environ.setdefault("LITELLM_DISABLE_REDACT_SECRETS", "true")
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import streamlit as st
from auth import is_authenticated, render_login_page
from utils import setup_sidebar, enforce_onboarding, inject_interactive_hover_halo_effects
from webhook import start_background_listener

# 1. Global Page Configuration (Must be the very first Streamlit command)
st.set_page_config(page_title="Skippy - AI Job CRM", layout="wide")

# 2. Interactive Hover & Halo Effects (Preserving 100% native theme/colors)
inject_interactive_hover_halo_effects()

# 3. Router Navigation Definition
pages = [
    st.Page("pages/1_scraper.py", title="Job Search", icon="🔍"),
    st.Page("pages/7_scraper_results.py", title="Search Results", icon="📋"),
    st.Page("pages/5_linkedin.py", title="LinkedIn Inbox", icon="🔗"),
    st.Page("pages/2_history.py", title="Job History", icon="📁"),
    st.Page("pages/6_gallery.py", title="Saved Documents", icon="🖼️"),
    st.Page("pages/8_pipeline_funnel.py", title="Application Tracker", icon="🌊"),
    st.Page("pages/3_metrics.py", title="Skills & Insights", icon="📊"),
    st.Page("pages/4_editors.py", title="Resumes & AI Settings", icon="⚙️"),
    st.Page("pages/9_career_compass.py", title="Career Profile", icon="🧭"),
    st.Page("pages/0_about.py", title="About Skippy", icon="👋")
]

# 3. Authentication Gatekeeper & Router Initialization
authenticated = is_authenticated()
pg = st.navigation(pages, position="sidebar" if authenticated else "hidden")

if not authenticated:
    render_login_page()
    st.stop()

# 4. Spin up the background webhook listener for the browser extension
@st.cache_resource
def init_webhook():
    start_background_listener()
    return True

init_webhook()

# 5. Global Sidebar & Security
setup_sidebar()
enforce_onboarding()

pg.run()
