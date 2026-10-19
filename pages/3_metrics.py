import streamlit as st
import pandas as pd
from collections import Counter
import database as db
from utils import setup_sidebar, enforce_onboarding

st.subheader("📊 Market Intelligence & Skill Analytics")
st.write("Aggregated insights harvested from your evaluated job history.")

history_data = db.load_all_jobs()

if not history_data:
    st.info("No job history found yet. Run the scraper to start collecting market data!")
else:
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
        st.markdown("### ✨ Skills That Shine")
        if top_matching: st.bar_chart(pd.DataFrame(top_matching, columns=["Skill", "Frequency"]).set_index("Skill"), color="#2baf2b")
    with col_b:
        st.markdown("### ⚠️ In-Demand Gaps")
        if top_missing: st.bar_chart(pd.DataFrame(top_missing, columns=["Skill", "Frequency"]).set_index("Skill"), color="#ff4b4b")
            
    st.markdown("---")
    st.subheader("🚨 Common Market Red Flags")
    if top_flags:
        for flag, count in top_flags: st.markdown(f"- ⚠️ **({count}x)** {flag}")