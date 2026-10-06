import streamlit as st
from utils import setup_sidebar, enforce_onboarding

# 1. Global Page Configuration (Must be the very first Streamlit command)
st.set_page_config(page_title="Skippy - AI Job CRM", layout="wide")

# 2. Global Sidebar & Security
setup_sidebar()
enforce_onboarding()

# 3. Router Navigation
pages = [
    st.Page("pages/0_about.py", title="About", icon="👋"),
    st.Page("pages/1_scraper.py", title="Scraper", icon="🔍"),
    st.Page("pages/2_history.py", title="History", icon="📁"),
    st.Page("pages/3_metrics.py", title="Metrics", icon="📊"),
    st.Page("pages/4_editors.py", title="Editors", icon="⚙️")
]

pg = st.navigation(pages)
pg.run()