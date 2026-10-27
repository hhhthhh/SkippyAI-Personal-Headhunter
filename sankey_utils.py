import os
import sys
import re
import hashlib
from datetime import datetime
import streamlit as st
import plotly.graph_objects as go

import database as db


def generate_safe_job_key(job: dict, prefix: str = "") -> str:
    """Generates a stable, collision-free widget key based on the job's unique identity."""
    pos = str(job.get("Position") or "")
    comp = str(job.get("Company") or "")
    ts = str(job.get("Status Updated") or job.get("Timestamp") or "")
    url = str(job.get("URL") or "").strip()
    raw_id = url if url else f"{pos}_{comp}_{ts}"
    digest = hashlib.sha256(raw_id.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"{prefix}_{digest}" if prefix else digest


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
    """
    Builds a vibrant, stage-proportional interactive Plotly Sankey diagram.
    Each stage has an exact specified horizontal length so visual branch length
    directly reflects how far an application has progressed:
      Stage 0 (0%): Start / Evaluated
      Stage 1 (25%): Eligibility Qualification Gate
      Stage 2 (50%): Application Submission Gate
      Stage 3 (75%): Screening & Employer Response Gate
      Stage 4 (100%): Interview Outcomes & Offers Milestone
    """
    if not data or data.get("total", 0) == 0:
        return None

    node_meta = {
        # Stage 0: Initial Intake
        "Evaluated": (f"Evaluated ({data['total']})", "#6366f1", 0.001),
        # Stage 1 (25% length): Qualification Gate (advancing node first)
        "Eligible": (f"Eligible ({len(data['eligible'])})", "#3b82f6", 0.25),
        "Ineligible": (f"Ineligible ({len(data['ineligible'])})", "#ef4444", 0.25),
        # Stage 2 (50% length): Application Action Gate
        "Applied": (f"Applied Pipeline ({len(data['applied_all'])})", "#f59e0b", 0.50),
        "Saved": (f"Saved / Reviewing ({len(data['not_applied'])})", "#94a3b8", 0.50),
        # Stage 3 (75% length): Response & Screening Gate
        "Interviewing": (f"Interviewing ({len(data['interviewing_all'])})", "#8b5cf6", 0.75),
        "Awaiting": (f"Awaiting Response ({len(data['awaiting_response'])})", "#fbbf24", 0.75),
        "Stale": (f"Ghosted / Stale ({len(data['stale_ghosted'])})", "#78716c", 0.75),
        "RejectedApp": (f"Rejected: App ({len(data['rejected_app'])})", "#f87171", 0.75),
        # Stage 4 (100% length): Final Outcomes & Offers
        "Offers": (f"Offers Received ({len(data['offers'])})", "#10b981", 0.999),
        "ActiveInterviews": (f"Active Interviews ({len(data['active_interviews'])})", "#a855f7", 0.999),
        "Waitlisted": (f"Waitlisted ({len(data['waitlisted'])})", "#ec4899", 0.999),
        "RejectedInt": (f"Rejected: Interview ({len(data['rejected_interview'])})", "#b91c1c", 0.999),
    }

    raw_links = []
    def add(src, tgt, val, link_color="rgba(148, 163, 184, 0.3)"):
        if val > 0:
            raw_links.append((src, tgt, val, link_color))

    add("Evaluated", "Eligible", len(data["eligible"]), "rgba(59, 130, 246, 0.35)")
    add("Evaluated", "Ineligible", len(data["ineligible"]), "rgba(239, 68, 68, 0.35)")
    add("Eligible", "Applied", len(data["applied_all"]), "rgba(245, 158, 11, 0.4)")
    add("Eligible", "Saved", len(data["not_applied"]), "rgba(148, 163, 184, 0.35)")
    add("Applied", "Interviewing", len(data["interviewing_all"]), "rgba(139, 92, 246, 0.45)")
    add("Applied", "Awaiting", len(data["awaiting_response"]), "rgba(251, 191, 36, 0.4)")
    add("Applied", "Stale", len(data["stale_ghosted"]), "rgba(120, 113, 108, 0.4)")
    add("Applied", "RejectedApp", len(data["rejected_app"]), "rgba(248, 113, 113, 0.4)")
    add("Interviewing", "Offers", len(data["offers"]), "rgba(16, 185, 129, 0.5)")
    add("Interviewing", "ActiveInterviews", len(data["active_interviews"]), "rgba(168, 85, 247, 0.45)")
    add("Interviewing", "Waitlisted", len(data["waitlisted"]), "rgba(236, 72, 153, 0.45)")
    add("Interviewing", "RejectedInt", len(data["rejected_interview"]), "rgba(185, 28, 28, 0.45)")

    active_keys = [k for k in node_meta if any(l[0] == k or l[1] == k for l in raw_links)]
    if not active_keys:
        return None

    k_to_idx = {k: i for i, k in enumerate(active_keys)}
    labels = [node_meta[k][0] for k in active_keys]
    colors = [node_meta[k][1] for k in active_keys]
    xs = [node_meta[k][2] for k in active_keys]

    links = [
        {
            "source": k_to_idx[l[0]],
            "target": k_to_idx[l[1]],
            "value": l[2],
            "color": l[3],
        }
        for l in raw_links
    ]

    fig = go.Figure(data=[go.Sankey(
        arrangement="snap",
        node=dict(
            pad=20,
            thickness=20,
            line=dict(color="#0f172a", width=1),
            label=labels,
            color=colors,
            x=xs
        ),
        link=dict(
            source=[l["source"] for l in links],
            target=[l["target"] for l in links],
            value=[l["value"] for l in links],
            color=[l["color"] for l in links]
        )
    )])
    fig.update_layout(
        margin=dict(l=15, r=15, t=30, b=25),
        height=480,
    )
    return fig


def render_sankey_section(history_data: list[dict]):
    """Renders the Sankey Conversion Funnel, KPI badges, and Stage Explorer."""
    col_kpi_title, col_s = st.columns([2.7, 1.3])
    with col_kpi_title:
        st.markdown("#### 📊 Application Progress & Stats")
    with col_s:
        stale_days = st.slider(
            "⏳ Mark Inactive After (Days)",
            min_value=7,
            max_value=30,
            value=14,
            step=1,
            key="sankey_stale_threshold_days",
            help="Applications in 'Applied' status with no activity for longer than this flow into 'Ghosted / Stale'. Updating a status resets the clock."
        )

    sankey_data = compute_sankey_data(history_data, stale_days=stale_days)
    if not sankey_data:
        st.info("No applications recorded yet.")
        return

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Active Applications", len(sankey_data["applied_all"]))
    m2.metric("Application Rate", f"{sankey_data['apply_rate']:.1f}%", help="Jobs applied to out of all matching jobs")
    m3.metric("Interview Rate", f"{sankey_data['screen_rate']:.1f}%", help="Interviews out of total jobs applied to")
    m4.metric("Job Offer Rate", f"{sankey_data['offer_rate']:.1f}%", help="Job offers out of total jobs applied to")

    t_metrics = db.get_pipeline_turnaround_metrics()
    if t_metrics.get("total_interviewed", 0) > 0 or t_metrics.get("total_rejected", 0) > 0 or t_metrics.get("ghosted_14d_count", 0) > 0:
        st.markdown("##### ⏱️ Employer Response Times")
        lat1, lat2, lat3 = st.columns(3)
        lat1.metric(
            "Avg. Days to Interview",
            f"{t_metrics['avg_interview_days']} days" if t_metrics['total_interviewed'] > 0 else "—",
            help="Average days from applying to getting an interview invitation."
        )
        lat2.metric(
            "Avg. Days to Rejection",
            f"{t_metrics['avg_rejection_days']} days" if t_metrics['total_rejected'] > 0 else "—",
            help="Average days from applying to receiving a rejection."
        )
        lat3.metric(
            "No Response After 14+ Days",
            t_metrics["ghosted_14d_count"],
            help="Applications waiting 14+ days without any update from the employer."
        )

    fig = build_sankey_figure(sankey_data)
    if fig:
        st.caption("📏 **Progress Steps**: **Step 1: Qualified** (25%) ➔ **Step 2: Applied** (50%) ➔ **Step 3: Screening** (75%) ➔ **Step 4: Interviews & Offers** (100%). Each step shows how far your applications have progressed.")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    st.markdown("---")
    st.markdown("#### 🔍 View by Stage & Update Status")
    st.caption("Inspect jobs in any stage. If an employer reaches out, advance its status to move it forward in your tracker.")

    stage_order = [
        ("applied_all", "All Active Applications"),
        ("awaiting_response", "Awaiting Response"),
        ("stale_ghosted", "Ghosted / Stale"),
        ("interviewing_all", "Interviewing / Screening"),
        ("offers", "Offers Received"),
        ("waitlisted", "Waitlisted"),
        ("rejected_app", "Rejected: Application"),
        ("rejected_interview", "Rejected: Interview"),
        ("not_applied", "Saved / Reviewing"),
        ("ineligible", "Ineligible / Disqualified"),
    ]

    stage_labels = {
        k: f"{lbl} ({len(sankey_data.get(k, []))})"
        for k, lbl in stage_order
    }

    selected_stage_key = st.selectbox(
        "Select Stage to View:",
        options=[k for k, _ in stage_order],
        format_func=lambda k: stage_labels.get(k, k),
        key="sankey_stage_filter_selection",
        index=0
    )
    selected_jobs = sankey_data.get(selected_stage_key, [])

    if not selected_jobs:
        st.info("No postings currently in this stage.")
    else:
        seen_keys = set()
        for job in selected_jobs:
            pos = job.get("Position") or "Untitled Role"
            comp = job.get("Company") or "Unknown Company"
            score = job.get("Score", 0)
            curr_status = job.get("Application Status", "Not Applied")
            url = (job.get("URL") or "").strip()
            ts = job.get("Status Updated") or job.get("Timestamp") or ""
            d = parse_date_safely(ts)
            days_ago = (datetime.now() - d).days if d else None
            age_str = f"{days_ago}d ago" if days_ago is not None else "Recently"

            # Generate stable, collision-free identifier independent of list position
            safe_id = generate_safe_job_key(job)
            if safe_id in seen_keys:
                safe_id = f"{safe_id}_{len(seen_keys)}"
            seen_keys.add(safe_id)

            select_key = f"sankey_status_{safe_id}"
            db_tracker_key = f"_sankey_db_status_{safe_id}"
            quick_adv_key = f"quick_adv_{safe_id}"

            # Synchronize session state with DB truth before rendering selectbox to eliminate stale race conditions
            if curr_status:
                if db_tracker_key not in st.session_state or st.session_state[db_tracker_key] != curr_status:
                    st.session_state[select_key] = curr_status
                    st.session_state[db_tracker_key] = curr_status

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
                    is_advancable = curr_status in ("Applied", "Ghosted / Stale") or selected_stage_key in ("awaiting_response", "stale_ghosted")
                    if is_advancable:
                        if st.button("Heard back: Interview ➔", key=quick_adv_key, width="stretch"):
                            if url:
                                db.update_job_field(url, "Application Status", "Interviewing")
                            st.session_state[select_key] = "Interviewing"
                            st.session_state[db_tracker_key] = "Interviewing"
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

                    def make_status_updater(target_url, widget_key, tracker_key, role_name):
                        def _handler():
                            chosen = st.session_state.get(widget_key)
                            if chosen and target_url:
                                db.update_job_field(target_url, "Application Status", chosen)
                                st.session_state[tracker_key] = chosen
                                st.toast(f"Updated {role_name} to {chosen}")
                        return _handler

                    curr_idx = statuses.index(curr_status) if curr_status in statuses else 0
                    st.selectbox(
                        "Status",
                        options=statuses,
                        index=curr_idx,
                        key=select_key,
                        on_change=make_status_updater(url, select_key, db_tracker_key, pos),
                        label_visibility="collapsed"
                    )
