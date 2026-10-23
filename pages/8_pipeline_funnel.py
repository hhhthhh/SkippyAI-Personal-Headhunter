import os
import sys
import re
from datetime import datetime
import streamlit as st
import plotly.graph_objects as go

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import database as db
from utils import setup_sidebar, enforce_onboarding


def parse_date_safely(d_str: str) -> datetime | None:
    """Safely extracts a datetime object from standard string formats."""
    if not d_str:
        return None
    d_str = str(d_str).strip()
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", d_str)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except Exception:
            return None
    return None


def compute_sankey_data(jobs: list[dict], stale_days: int = 14) -> dict:
    """
    Calculates exact drop-off and conversion stages across evaluated jobs,
    accounting for user status updates and stale application thresholds.
    """
    now = datetime.now()
    total = len(jobs)
    if not total:
        return {}

    ineligible = [j for j in jobs if not j.get("Eligible", True)]
    eligible = [j for j in jobs if j.get("Eligible", True)]

    not_applied = []
    applied_all = []
    for j in eligible:
        st_val = str(j.get("Application Status") or "Not Applied").strip()
        if not st_val or st_val == "Not Applied":
            not_applied.append(j)
        else:
            applied_all.append(j)

    awaiting_response = []
    stale_ghosted = []
    rejected_app = []
    interviewing_all = []

    for j in applied_all:
        st_val = str(j.get("Application Status") or "").strip().lower()
        if "ghost" in st_val or "stale" in st_val or "archive" in st_val:
            stale_ghosted.append(j)
        elif st_val == "rejected (interview)":
            interviewing_all.append(j)
        elif "reject" in st_val:
            rejected_app.append(j)
        elif any(k in st_val for k in ("interview", "offer", "waitlist")):
            interviewing_all.append(j)
        else:
            # Standard 'Applied' - check staleness timer
            date_str = j.get("Status Updated") or j.get("Timestamp") or ""
            d = parse_date_safely(date_str)
            days = (now - d).days if d else 0
            if days >= stale_days:
                stale_ghosted.append(j)
            else:
                awaiting_response.append(j)

    active_interviews = []
    rejected_interview = []
    waitlisted = []
    offers = []

    for j in interviewing_all:
        st_val = str(j.get("Application Status") or "").strip().lower()
        if "offer" in st_val:
            offers.append(j)
        elif "waitlist" in st_val:
            waitlisted.append(j)
        elif "reject" in st_val:
            rejected_interview.append(j)
        else:
            active_interviews.append(j)

    apply_rate = (len(applied_all) / len(eligible) * 100.0) if eligible else 0.0
    screen_rate = (len(interviewing_all) / len(applied_all) * 100.0) if applied_all else 0.0
    offer_rate = (len(offers) / len(applied_all) * 100.0) if applied_all else 0.0
    stale_rate = (len(stale_ghosted) / len(applied_all) * 100.0) if applied_all else 0.0

    return {
        "total": total,
        "ineligible": ineligible,
        "eligible": eligible,
        "not_applied": not_applied,
        "applied_all": applied_all,
        "awaiting_response": awaiting_response,
        "stale_ghosted": stale_ghosted,
        "rejected_app": rejected_app,
        "interviewing_all": interviewing_all,
        "active_interviews": active_interviews,
        "waitlisted": waitlisted,
        "rejected_interview": rejected_interview,
        "offers": offers,
        "apply_rate": apply_rate,
        "screen_rate": screen_rate,
        "offer_rate": offer_rate,
        "stale_rate": stale_rate,
    }


def build_sankey_figure(data: dict) -> go.Figure | None:
    """Builds a vibrant, interactive Plotly Sankey diagram with non-zero link pruning."""
    if not data or data.get("total", 0) == 0:
        return None

    node_defs = [
        ("Evaluated", f"Evaluated ({data['total']})", "#6366f1"),
        ("Ineligible", f"Ineligible ({len(data['ineligible'])})", "#ef4444"),
        ("Eligible", f"Eligible ({len(data['eligible'])})", "#3b82f6"),
        ("Saved", f"Saved / Reviewing ({len(data['not_applied'])})", "#94a3b8"),
        ("Applied", f"Applied Pipeline ({len(data['applied_all'])})", "#f59e0b"),
        ("Awaiting", f"Awaiting Response ({len(data['awaiting_response'])})", "#fbbf24"),
        ("Stale", f"Ghosted / Stale ({len(data['stale_ghosted'])})", "#78716c"),
        ("RejectedApp", f"Rejected: App ({len(data['rejected_app'])})", "#f87171"),
        ("Interviewing", f"Interviewing ({len(data['interviewing_all'])})", "#8b5cf6"),
        ("ActiveInterviews", f"Active Interviews ({len(data['active_interviews'])})", "#a855f7"),
        ("Waitlisted", f"Waitlisted ({len(data['waitlisted'])})", "#ec4899"),
        ("RejectedInt", f"Rejected: Interview ({len(data['rejected_interview'])})", "#b91c1c"),
        ("Offers", f"Offers Received ({len(data['offers'])})", "#10b981"),
    ]

    name_to_idx = {d[0]: i for i, d in enumerate(node_defs)}
    labels = [d[1] for d in node_defs]
    colors = [d[2] for d in node_defs]

    links = []
    def add(src, tgt, val, link_color="rgba(148, 163, 184, 0.3)"):
        if val > 0:
            links.append({"source": name_to_idx[src], "target": name_to_idx[tgt], "value": val, "color": link_color})

    add("Evaluated", "Ineligible", len(data["ineligible"]), "rgba(239, 68, 68, 0.35)")
    add("Evaluated", "Eligible", len(data["eligible"]), "rgba(59, 130, 246, 0.35)")
    add("Eligible", "Saved", len(data["not_applied"]), "rgba(148, 163, 184, 0.35)")
    add("Eligible", "Applied", len(data["applied_all"]), "rgba(245, 158, 11, 0.4)")
    add("Applied", "Awaiting", len(data["awaiting_response"]), "rgba(251, 191, 36, 0.4)")
    add("Applied", "Stale", len(data["stale_ghosted"]), "rgba(120, 113, 108, 0.4)")
    add("Applied", "RejectedApp", len(data["rejected_app"]), "rgba(248, 113, 113, 0.4)")
    add("Applied", "Interviewing", len(data["interviewing_all"]), "rgba(139, 92, 246, 0.45)")
    add("Interviewing", "ActiveInterviews", len(data["active_interviews"]), "rgba(168, 85, 247, 0.45)")
    add("Interviewing", "Waitlisted", len(data["waitlisted"]), "rgba(236, 72, 153, 0.45)")
    add("Interviewing", "RejectedInt", len(data["rejected_interview"]), "rgba(185, 28, 28, 0.45)")
    add("Interviewing", "Offers", len(data["offers"]), "rgba(16, 185, 129, 0.5)")

    fig = go.Figure(data=[go.Sankey(
        arrangement="snap",
        node=dict(
            pad=18,
            thickness=20,
            line=dict(color="#0f172a", width=1),
            label=labels,
            color=colors
        ),
        link=dict(
            source=[l["source"] for l in links],
            target=[l["target"] for l in links],
            value=[l["value"] for l in links],
            color=[l["color"] for l in links]
        )
    )])
    fig.update_layout(
        margin=dict(l=15, r=15, t=25, b=25),
        height=480,
    )
    return fig


def render_sankey_section(history_data: list[dict]):
    """Renders the Sankey Conversion Funnel, KPI badges, and Stage Explorer."""
    col_kpi_title, col_s = st.columns([2.7, 1.3])
    with col_kpi_title:
        st.markdown("#### 📊 Funnel Flow & Metrics")
    with col_s:
        stale_days = st.slider(
            "⏳ Stale Threshold (Days)",
            min_value=7,
            max_value=30,
            value=14,
            step=1,
            help="Applications in 'Applied' status with no activity for longer than this flow into 'Ghosted / Stale'. Updating a status resets the clock."
        )

    sankey_data = compute_sankey_data(history_data, stale_days=stale_days)
    if not sankey_data:
        st.info("No applications recorded yet.")
        return

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Active in Pipeline", len(sankey_data["applied_all"]))
    m2.metric("Application Rate", f"{sankey_data['apply_rate']:.1f}%", help="Applied / Eligible target postings")
    m3.metric("Screen / Interview Rate", f"{sankey_data['screen_rate']:.1f}%", help="Interviews / Total applied")
    m4.metric("Offer Conversion", f"{sankey_data['offer_rate']:.1f}%", help="Offers / Total applied")

    fig = build_sankey_figure(sankey_data)
    if fig:
        st.plotly_chart(fig, width="stretch")

    st.markdown("---")
    st.markdown("#### 🔍 Stage Explorer & Quick Status Manager")
    st.caption("Inspect roles in any funnel stage. If a stale application hears back, advance its status to move it forward in your pipeline.")

    stage_map = {
        f"All Active Applications ({len(sankey_data['applied_all'])})": sankey_data["applied_all"],
        f"Awaiting Response ({len(sankey_data['awaiting_response'])})": sankey_data["awaiting_response"],
        f"Ghosted / Stale ({len(sankey_data['stale_ghosted'])})": sankey_data["stale_ghosted"],
        f"Interviewing / Screening ({len(sankey_data['interviewing_all'])})": sankey_data["interviewing_all"],
        f"Offers Received ({len(sankey_data['offers'])})": sankey_data["offers"],
        f"Waitlisted ({len(sankey_data['waitlisted'])})": sankey_data["waitlisted"],
        f"Rejected: Application ({len(sankey_data['rejected_app'])})": sankey_data["rejected_app"],
        f"Rejected: Interview ({len(sankey_data['rejected_interview'])})": sankey_data["rejected_interview"],
        f"Saved / Reviewing ({len(sankey_data['not_applied'])})": sankey_data["not_applied"],
        f"Ineligible / Disqualified ({len(sankey_data['ineligible'])})": sankey_data["ineligible"],
    }

    selected_stage_key = st.selectbox("Select Funnel Stage to View:", list(stage_map.keys()), index=0)
    selected_jobs = stage_map[selected_stage_key]

    if not selected_jobs:
        st.info("No postings currently in this stage.")
    else:
        for idx, job in enumerate(selected_jobs):
            pos = job.get("Position") or "Untitled Role"
            comp = job.get("Company") or "Unknown Company"
            score = job.get("Score", 0)
            curr_status = job.get("Application Status", "Not Applied")
            url = job.get("URL") or f"job_{idx}"
            ts = job.get("Status Updated") or job.get("Timestamp") or ""
            d = parse_date_safely(ts)
            days_ago = (datetime.now() - d).days if d else None
            age_str = f"{days_ago}d ago" if days_ago is not None else "Recently"

            with st.container(border=True):
                r1, r2, r3, r4 = st.columns([3.5, 1.4, 2.3, 2.8])
                with r1:
                    st.markdown(f"**{pos}**")
                    st.caption(f"🏢 {comp} • Updated: {age_str}")
                with r2:
                    if score >= 75:
                        st.success(f"🎯 Score: {score}")
                    elif score >= 50:
                        st.info(f"⚖️ Score: {score}")
                    else:
                        st.warning(f"⚠️ Score: {score}")
                with r3:
                    # If stale or pending, provide a 1-click advance button
                    if curr_status in ("Applied", "Ghosted / Stale") or "stale" in selected_stage_key.lower():
                        if st.button("👉 Heard back: Interview ➔", key=f"quick_adv_{url}_{idx}", width="stretch"):
                            db.update_job_field(url, "Application Status", "Interviewing")
                            st.toast(f"🎉 Moved {pos} to Interviewing!")
                            st.rerun()
                with r4:
                    statuses = [
                        "Not Applied",
                        "Applied",
                        "Interviewing",
                        "Waitlisted",
                        "Offer",
                        "Rejected (Application)",
                        "Rejected (Interview)",
                        "Ghosted / Stale",
                        "Archived",
                    ]
                    if curr_status not in statuses:
                        statuses.append(curr_status)

                    def make_status_updater(target_url, widget_key, role_name):
                        def _handler():
                            chosen = st.session_state[widget_key]
                            db.update_job_field(target_url, "Application Status", chosen)
                            st.toast(f"Updated {role_name} to {chosen}")
                        return _handler

                    select_key = f"sankey_stage_status_{url}_{idx}"
                    st.selectbox(
                        "Status",
                        options=statuses,
                        index=statuses.index(curr_status) if curr_status in statuses else 0,
                        key=select_key,
                        on_change=make_status_updater(url, select_key, pos),
                        label_visibility="collapsed"
                    )


# --- MAIN PAGE ENTRY POINT ---
st.subheader("🌊 Application Conversion Funnel")
st.caption(
    "Interactive Sankey visualization tracking your job search lifecycle from initial discovery and screening to interviews and offers. "
    "Nodes can be dragged to customize layout; hover over flows to inspect exact job counts."
)

history_data = db.load_all_jobs()

if not history_data:
    st.info("No job history found yet. Run the scraper or evaluate postings to start tracking your application pipeline!")
else:
    render_sankey_section(history_data)
