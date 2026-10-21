import os
os.environ.setdefault("LITELLM_DISABLE_REDACT_SECRETS", "true")
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import streamlit as st
from utils import setup_sidebar, enforce_onboarding
from webhook import start_background_listener

# 1. Global Page Configuration (Must be the very first Streamlit command)
st.set_page_config(page_title="Skippy - AI Job CRM", layout="wide")

# 2. Spin up the background webhook listener for the browser extension
@st.cache_resource
def init_webhook():
    start_background_listener()
    return True

init_webhook()

# 3. Global Sidebar & Security
setup_sidebar()
enforce_onboarding()

# 4. Router Navigation
pages = [
    st.Page("pages/1_scraper.py", title="Scraper", icon="🔍"),
    st.Page("pages/5_linkedin.py", title="LinkedIn Evaluator (Fallback)", icon="🔗"),
    st.Page("pages/2_history.py", title="History", icon="📁"),
    st.Page("pages/6_gallery.py", title="Document Gallery", icon="🖼️"),
    st.Page("pages/3_metrics.py", title="Metrics", icon="📊"),
    st.Page("pages/4_editors.py", title="Editors", icon="⚙️"),
    st.Page("pages/0_about.py", title="About", icon="👋")
]

pg = st.navigation(pages)
pg.run()
