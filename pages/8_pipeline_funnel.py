import os
import sys
import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import database as db
from sankey_utils import (
    generate_safe_job_key,
    parse_date_safely,
    compute_sankey_data,
    build_sankey_figure,
    render_sankey_section,
)

# Re-export for backwards compatibility
__all__ = [
    "generate_safe_job_key",
    "parse_date_safely",
    "compute_sankey_data",
    "build_sankey_figure",
    "render_sankey_section",
]


def render_pipeline_funnel_page():
    st.subheader("🌊 Application Tracker")
    st.caption(
        "Visual chart tracking your jobs from first review to applications, interviews, and job offers. "
        "Drag boxes to rearrange; hover over lines to see job counts."
    )

    history_data = db.load_all_jobs(summary_only=True)

    if not history_data:
        with st.container(border=True):
            st.subheader("🌊 Application Tracker Pipeline")
            st.write(
                "This visual pipeline tracks your applications across every stage (Qualified ➔ Applied ➔ Screening ➔ Interviews & Offers) "
                "and measures employer response times. Start by reviewing jobs to populate your pipeline!"
            )
            c1, _ = st.columns([2.5, 4.5])
            with c1:
                if st.button("🔍 Find & Review Jobs to Start ➔", type="primary", width="stretch", key="btn_pipeline_empty_goto_search"):
                    st.switch_page("pages/1_scraper.py")
    else:
        render_sankey_section(history_data)


if __name__ == "__main__":
    render_pipeline_funnel_page()
