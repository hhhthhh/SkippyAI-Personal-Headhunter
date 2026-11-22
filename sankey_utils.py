import hashlib
import math
from datetime import datetime
import streamlit as st

import database as db
from database import parse_date_safely

SANKEY_CARDS_PER_PAGE = 20

STAGE_ORDER = (
    ("applied_all", "All Active Applications"),
    ("awaiting_response", "Awaiting Response"),
    ("stale_ghosted", "Ghosted / Stale"),
    ("interviewing_all", "Interviewing / Screening"),
    ("active_interviews", "Active Interviews"),
    ("offers", "Offers Received"),
    ("waitlisted", "Waitlisted"),
    ("rejected_app", "Rejected: Application"),
    ("rejected_interview", "Rejected: Interview"),
    ("not_applied", "Saved / Reviewing"),
    ("eligible", "Eligible Matches"),
    ("ineligible", "Ineligible / Disqualified"),
    ("all_active", "All Evaluated (Active)"),
    ("archived", "🗄️ Archived"),
)

JOB_STATUS_OPTIONS = (
    "Not Applied",
    "Applied",
    "Interviewing",
    "Waitlisted",
    "Offer",
    "Rejected (Application)",
    "Rejected (Interview)",
    "Ghosted / Stale",
    "Archived",
)


def generate_safe_job_key(job: dict, prefix: str = "") -> str:
    """Generates a stable, collision-free widget key based on the job's unique identity."""
    pos = str(job.get("Position") or "")
    comp = str(job.get("Company") or "")
    ts = str(job.get("Status Updated") or job.get("Timestamp") or "")
    url = str(job.get("URL") or "").strip()
    raw_id = url if url else f"{pos}_{comp}_{ts}"
    digest = hashlib.sha256(raw_id.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"{prefix}_{digest}" if prefix else digest


def compute_sankey_data(jobs: list[dict], stale_days: int = 14) -> dict:
    """
    Calculates exact drop-off and conversion stages across evaluated jobs,
    accounting for user status updates and stale application thresholds.
    """
    now = datetime.now()
    total = len(jobs)
    if not total:
        return {}

    archived = [
        j for j in jobs
        if "archive" in str(j.get("Application Status") or "").strip().lower()
    ]
    active_jobs = [
        j for j in jobs
        if "archive" not in str(j.get("Application Status") or "").strip().lower()
    ]
    ineligible = [j for j in active_jobs if not j.get("Eligible", True)]
    eligible = [j for j in active_jobs if j.get("Eligible", True)]

    not_applied = []
    eligible_applied = []
    for j in eligible:
        st_val = str(j.get("Application Status") or "Not Applied").strip()
        if not st_val or st_val == "Not Applied":
            not_applied.append(j)
        else:
            eligible_applied.append(j)

    ineligible_applied = [
        j for j in ineligible
        if str(j.get("Application Status") or "Not Applied").strip() not in ("", "Not Applied")
    ]
    applied_all = eligible_applied + ineligible_applied

    awaiting_response = []
    stale_ghosted = []
    rejected_app = []
    interviewing_all = []

    for j in applied_all:
        st_val = str(j.get("Application Status") or "").strip().lower()
        if "ghost" in st_val or "stale" in st_val:
            stale_ghosted.append(j)
        elif st_val == "rejected (interview)":
            interviewing_all.append(j)
        elif "reject" in st_val:
            rejected_app.append(j)
        elif any(k in st_val for k in ("interview", "offer", "waitlist")):
            interviewing_all.append(j)
        else:
            # Standard 'Applied' - check staleness timer
            date_str = j.get("Applied Date") or j.get("Status Updated") or j.get("Timestamp") or ""
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
        "active_total": len(active_jobs),
        "all_active": active_jobs,
        "ineligible": ineligible,
        "eligible": eligible,
        "archived": archived,
        "not_applied": not_applied,
        "eligible_applied": eligible_applied,
        "ineligible_applied": ineligible_applied,
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


def build_sankey_echarts_spec(data: dict) -> tuple[dict, list[str], list[str]] | None:
    """
    Builds an interactive Apache ECharts Sankey option dict with clickable nodes and branches (links).
    Returns `(option_dict, node_stage_keys, link_stage_keys)` or `None` if there are no active postings.
    """
    active_total = data.get("active_total", len(data.get("eligible", [])) + len(data.get("ineligible", [])))
    if not data or active_total == 0:
        return None

    # key -> (display_label, hex_color, depth_column, mapped_stage_key)
    node_meta = {
        "Evaluated": (f"Evaluated ({active_total})", "#6366f1", 0, "all_active"),
        "Eligible": (f"Eligible ({len(data['eligible'])})", "#3b82f6", 1, "eligible"),
        "Ineligible": (f"Ineligible ({len(data['ineligible'])})", "#ef4444", 1, "ineligible"),
        "Applied": (f"Applied Pipeline ({len(data['applied_all'])})", "#f59e0b", 2, "applied_all"),
        "Saved": (f"Saved / Reviewing ({len(data['not_applied'])})", "#94a3b8", 2, "not_applied"),
        "Interviewing": (f"Interviewing ({len(data['interviewing_all'])})", "#8b5cf6", 3, "interviewing_all"),
        "Awaiting": (f"Awaiting Response ({len(data['awaiting_response'])})", "#fbbf24", 3, "awaiting_response"),
        "Stale": (f"Ghosted / Stale ({len(data['stale_ghosted'])})", "#78716c", 3, "stale_ghosted"),
        "RejectedApp": (f"Rejected: App ({len(data['rejected_app'])})", "#f87171", 3, "rejected_app"),
        "Offers": (f"Offers Received ({len(data['offers'])})", "#10b981", 4, "offers"),
        "ActiveInterviews": (f"Active Interviews ({len(data['active_interviews'])})", "#a855f7", 4, "active_interviews"),
        "Waitlisted": (f"Waitlisted ({len(data['waitlisted'])})", "#ec4899", 4, "waitlisted"),
        "RejectedInt": (f"Rejected: Interview ({len(data['rejected_interview'])})", "#b91c1c", 4, "rejected_interview"),
    }

    raw_links: list[tuple[str, str, int]] = []

    def add(src: str, tgt: str, val: int):
        if val > 0:
            raw_links.append((src, tgt, int(val)))

    elig_applied_cnt = len(data.get("eligible_applied", data["applied_all"]))
    inelig_applied_cnt = len(data.get("ineligible_applied", []))

    add("Evaluated", "Eligible", len(data["eligible"]))
    add("Evaluated", "Ineligible", len(data["ineligible"]))
    add("Eligible", "Applied", elig_applied_cnt)
    add("Ineligible", "Applied", inelig_applied_cnt)
    add("Eligible", "Saved", len(data["not_applied"]))
    add("Applied", "Interviewing", len(data["interviewing_all"]))
    add("Applied", "Awaiting", len(data["awaiting_response"]))
    add("Applied", "Stale", len(data["stale_ghosted"]))
    add("Applied", "RejectedApp", len(data["rejected_app"]))
    add("Interviewing", "Offers", len(data["offers"]))
    add("Interviewing", "ActiveInterviews", len(data["active_interviews"]))
    add("Interviewing", "Waitlisted", len(data["waitlisted"]))
    add("Interviewing", "RejectedInt", len(data["rejected_interview"]))

    active_keys = [k for k in node_meta if any(l[0] == k or l[1] == k for l in raw_links)]
    if not active_keys:
        return None

    nodes = []
    node_stage_keys: list[str] = []
    for k in active_keys:
        label, color, depth, stage_key = node_meta[k]
        nodes.append({
            "name": label,
            "depth": depth,
            "itemStyle": {"color": color, "borderColor": color},
        })
        node_stage_keys.append(stage_key)

    links = []
    link_stage_keys: list[str] = []
    for src, tgt, val in raw_links:
        links.append({
            "source": node_meta[src][0],
            "target": node_meta[tgt][0],
            "value": val,
        })
        link_stage_keys.append(node_meta[tgt][3])

    spec = {
        "animation": False,
        "tooltip": {
            "trigger": "item",
            "triggerOn": "mousemove",
        },
        "series": [
            {
                "type": "sankey",
                "animation": False,
                "left": 16,
                "right": 175,
                "top": 20,
                "bottom": 20,
                "nodeWidth": 18,
                "nodeGap": 18,
                "nodeAlign": "left",
                "draggable": False,
                "selectedMode": "single",
                "emphasis": {"focus": "adjacency"},
                "label": {"fontSize": 13, "fontWeight": 500},
                "lineStyle": {
                    "color": "gradient",
                    "curveness": 0.5,
                    "opacity": 0.42,
                },
                "select": {
                    "itemStyle": {
                        "borderColor": "#ffffff",
                        "borderWidth": 2,
                    },
                    "lineStyle": {
                        "opacity": 0.85,
                    },
                },
                "data": nodes,
                "links": links,
            }
        ],
    }
    return spec, node_stage_keys, link_stage_keys


def resolve_sankey_selection(
    event,
    node_stage_keys: list[str],
    link_stage_keys: list[str],
) -> tuple[str | None, tuple | None]:
    """
    Maps a Streamlit `st.echarts_chart` selection event on the Sankey diagram
    to `(stage_key, selection_signature)`. Supports clicking either a branch (`edge`)
    or a status box (`node`).
    """
    if not event:
        return None, None

    selection = getattr(event, "selection", None)
    if selection is None and isinstance(event, dict):
        selection = event.get("selection")
    if not selection:
        return None, None

    selected_groups = getattr(selection, "selected", None)
    if selected_groups is None and isinstance(selection, dict):
        selected_groups = selection.get("selected")
    if not selected_groups:
        return None, None

    edge_indices: list[int] = []
    node_indices: list[int] = []
    for grp in selected_groups:
        if not isinstance(grp, dict):
            continue
        dtype = str(grp.get("data_type") or "main").lower()
        indices = [int(i) for i in (grp.get("data_indices") or []) if isinstance(i, int) or str(i).isdigit()]
        if not indices:
            continue
        if dtype == "edge":
            edge_indices.extend(indices)
        else:
            node_indices.extend(indices)

    if edge_indices:
        idx = edge_indices[0]
        sig = ("edge", tuple(edge_indices))
        if 0 <= idx < len(link_stage_keys):
            return link_stage_keys[idx], sig
        return None, sig

    if node_indices:
        idx = node_indices[0]
        sig = ("node", tuple(node_indices))
        if 0 <= idx < len(node_stage_keys):
            return node_stage_keys[idx], sig
        return None, sig

    return None, None


def sync_sankey_stage_selection(
    session_state,
    clicked_stage: str | None,
    chart_sig: tuple | None,
    layout_sig: str,
    stage_keys: list[str],
    default_stage_key: str,
) -> bool:
    """
    Keeps the Sankey chart click selection, stage dropdown, and pagination page in sync.
    Returns True only when the user actively clicked a chart node or branch (to trigger auto-scroll):
    - When the active node layout shifts (e.g. a stage becomes empty after a status update),
      silently resets the tracked chart signature without jumping the user's current stage.
    - When the user clicks a node or branch, updates the stage filter and resets to page 1.
    - When the user clears chart selection (toggle-off or double-click), resets to the default stage.
    """
    should_scroll = False
    if session_state.get("_sankey_last_layout_sig") != layout_sig:
        session_state["_sankey_last_layout_sig"] = layout_sig
        session_state["_sankey_last_chart_sel"] = chart_sig
    else:
        last_chart_sig = session_state.get("_sankey_last_chart_sel")
        if chart_sig != last_chart_sig:
            session_state["_sankey_last_chart_sel"] = chart_sig
            if clicked_stage and clicked_stage in stage_keys:
                session_state["sankey_stage_filter_selection"] = clicked_stage
                session_state["_sankey_page"] = 1
                session_state["_sankey_scroll_nonce"] = session_state.get("_sankey_scroll_nonce", 0) + 1
                should_scroll = True
            elif chart_sig is None:
                session_state["sankey_stage_filter_selection"] = default_stage_key
                session_state["_sankey_page"] = 1

    if (
        "sankey_stage_filter_selection" not in session_state
        or session_state["sankey_stage_filter_selection"] not in stage_keys
    ):
        session_state["sankey_stage_filter_selection"] = default_stage_key

    return should_scroll


def _on_stage_dropdown_change():
    """Clears stale ECharts selection and resets pagination when the user picks a stage manually."""
    st.session_state["_sankey_chart_rev"] = st.session_state.get("_sankey_chart_rev", 0) + 1
    st.session_state["_sankey_last_chart_sel"] = None
    st.session_state["_sankey_page"] = 1


def _set_sankey_page(target_page: int):
    st.session_state["_sankey_page"] = target_page


def _make_status_updater(target_url: str, widget_key: str, tracker_key: str, role_name: str):
    def _handler():
        chosen = st.session_state.get(widget_key)
        if chosen and target_url:
            db.update_job_field(target_url, "Application Status", chosen)
            st.session_state[tracker_key] = chosen
            st.session_state["_sankey_pending_toast"] = f"Updated {role_name} to {chosen}"
            st.session_state["_sankey_needs_app_rerun"] = True
    return _handler


@st.fragment
def _render_interactive_sankey_explorer(sankey_data: dict):
    """
    Fragment-scoped interactive Sankey chart + paginated Stage Explorer.
    Chart clicks, dropdown switches, and page turns rerun only this fragment with zero DB queries.
    Status mutations and deletions trigger a full app rerun so KPIs and chart counts refresh.
    """
    if st.session_state.pop("_sankey_needs_app_rerun", False):
        st.rerun(scope="app")

    stage_keys = [k for k, _ in STAGE_ORDER]
    archived_cnt = len(sankey_data.get("archived", []))
    echarts_bundle = build_sankey_echarts_spec(sankey_data)
    clicked_stage: str | None = None
    chart_sig: tuple | None = None
    layout_sig = "empty"

    if echarts_bundle:
        echarts_spec, node_stage_keys, link_stage_keys = echarts_bundle
        layout_sig = hashlib.sha1(",".join(node_stage_keys).encode("utf-8")).hexdigest()[:8]
        chart_rev = st.session_state.get("_sankey_chart_rev", 0)
        st.caption(
            "📏 **Progress Steps**: **Step 1: Qualified** ➔ **Step 2: Applied** ➔ **Step 3: Screening** ➔ **Step 4: Interviews & Offers**. "
            "Click any box or branch on the chart (or use the dropdown below) to filter postings; click again or double-click to reset."
        )
        if archived_cnt > 0:
            st.caption(
                f"🗄️ {archived_cnt} archived posting{'s' if archived_cnt != 1 else ''} excluded from the active funnel "
                "(view under **🗄️ Archived** below)."
            )
        chart_event = st.echarts_chart(
            echarts_spec,
            height=480,
            width="stretch",
            key=f"sankey_interactive_chart_{layout_sig}_{chart_rev}",
            on_select="rerun",
            alt="Interactive application tracker Sankey funnel showing active evaluated postings by stage",
        )
        clicked_stage, chart_sig = resolve_sankey_selection(chart_event, node_stage_keys, link_stage_keys)
    elif archived_cnt > 0:
        st.info(
            f"All {archived_cnt} saved posting{'s are' if archived_cnt != 1 else ' is'} currently archived. "
            "Select **🗄️ Archived** below to inspect or restore them."
        )

    default_stage_key = "applied_all"
    if not sankey_data.get("applied_all"):
        if sankey_data.get("not_applied"):
            default_stage_key = "not_applied"
        elif sankey_data.get("ineligible"):
            default_stage_key = "ineligible"
        elif sankey_data.get("archived"):
            default_stage_key = "archived"

    should_scroll = sync_sankey_stage_selection(
        st.session_state,
        clicked_stage=clicked_stage,
        chart_sig=chart_sig,
        layout_sig=layout_sig,
        stage_keys=stage_keys,
        default_stage_key=default_stage_key,
    )

    st.markdown("---")
    if should_scroll:
        scroll_nonce = int(st.session_state.get("_sankey_scroll_nonce", 0))
        st.html(
            "<div id='sankey_stage_list_anchor' style='scroll-margin-top: 72px;'></div>"
            f"<script>(function(){{/* scroll:{scroll_nonce} */ setTimeout(function(){{"
            "var el=document.getElementById('sankey_stage_list_anchor');"
            "if(el){el.scrollIntoView({behavior:'smooth',block:'start'});}"
            "},60);})();</script>",
            unsafe_allow_javascript=True,
        )
    else:
        st.html("<div id='sankey_stage_list_anchor' style='scroll-margin-top: 72px;'></div>")

    st.markdown("#### 🔍 View by Stage & Update Status")
    st.caption("Inspect jobs in any stage. Click a branch above or pick a stage below; advance a job's status when an employer reaches out.")

    stage_labels = {
        k: f"{lbl} ({len(sankey_data.get(k, []))})"
        for k, lbl in STAGE_ORDER
    }

    selected_stage_key = st.selectbox(
        "Select Stage to View:",
        options=stage_keys,
        format_func=lambda k: stage_labels.get(k, k),
        key="sankey_stage_filter_selection",
        on_change=_on_stage_dropdown_change,
    )
    selected_jobs = sankey_data.get(selected_stage_key, [])

    if not selected_jobs:
        st.info("No postings currently in this stage.")
        return

    total_items = len(selected_jobs)
    total_pages = max(1, math.ceil(total_items / SANKEY_CARDS_PER_PAGE))
    curr_page = int(st.session_state.get("_sankey_page", 1) or 1)
    curr_page = max(1, min(curr_page, total_pages))
    st.session_state["_sankey_page"] = curr_page

    start_idx = (curr_page - 1) * SANKEY_CARDS_PER_PAGE
    end_idx = min(start_idx + SANKEY_CARDS_PER_PAGE, total_items)
    page_jobs = selected_jobs[start_idx:end_idx]

    if total_pages > 1:
        p_info, p_prev, p_next = st.columns([4.0, 1.2, 1.2], vertical_alignment="center")
        with p_info:
            st.caption(f"Showing **{start_idx + 1}–{end_idx}** of **{total_items}** postings (Page {curr_page} of {total_pages})")
        with p_prev:
            st.button(
                "⬅️ Previous",
                key="sankey_page_prev",
                width="stretch",
                disabled=(curr_page <= 1),
                on_click=_set_sankey_page,
                args=(curr_page - 1,),
            )
        with p_next:
            st.button(
                "Next ➡️",
                key="sankey_page_next",
                width="stretch",
                disabled=(curr_page >= total_pages),
                on_click=_set_sankey_page,
                args=(curr_page + 1,),
            )

    now = datetime.now()
    seen_keys = set()
    for job in page_jobs:
        pos = job.get("Position") or "Untitled Role"
        comp = job.get("Company") or "Unknown Company"
        score = job.get("Score", 0)
        curr_status = str(job.get("Application Status") or "Not Applied").strip() or "Not Applied"
        url = (job.get("URL") or "").strip()
        ts = job.get("Status Updated") or job.get("Timestamp") or ""
        d = parse_date_safely(ts)
        days_ago = (now - d).days if d else None
        age_str = f"{days_ago}d ago" if days_ago is not None else "Recently"

        # Generate stable, collision-free identifier independent of list position
        safe_id = generate_safe_job_key(job)
        if safe_id in seen_keys:
            safe_id = f"{safe_id}_{len(seen_keys)}"
        seen_keys.add(safe_id)

        select_key = f"sankey_status_{safe_id}"
        db_tracker_key = f"_sankey_db_status_{safe_id}"
        quick_adv_key = f"quick_adv_{safe_id}"

        # Synchronize session state with DB truth before rendering selectbox.
        # Re-seed `select_key` whenever it was unmounted/cleared (e.g. after switching pages or stages).
        if (
            select_key not in st.session_state
            or db_tracker_key not in st.session_state
            or st.session_state[db_tracker_key] != curr_status
        ):
            st.session_state[select_key] = curr_status
            st.session_state[db_tracker_key] = curr_status

        is_advancable = curr_status in ("Applied", "Ghosted / Stale") or selected_stage_key in ("awaiting_response", "stale_ghosted")

        with st.container(border=True):
            if is_advancable:
                r1, r2, r_jump, r3, r4, r5 = st.columns([3.0, 1.1, 1.8, 1.8, 2.0, 0.5], vertical_alignment="center")
            else:
                r1, r2, r_jump, r4, r5 = st.columns([3.2, 1.2, 2.1, 2.4, 0.5], vertical_alignment="center")

            with r1:
                if url and url.startswith("http"):
                    st.markdown(f"**[{pos}]({url})**")
                else:
                    st.markdown(f"**{pos}**")
                st.caption(f"🏢 {comp} • Updated: {age_str}")
            with r2:
                if score >= 75:
                    st.success(f"🎯 Score: {score}")
                elif score >= 50:
                    st.info(f"⚖️ Score: {score}")
                else:
                    st.warning(f"⚠️ Score: {score}")
            with r_jump:
                if st.button(
                    "🔍 Jump to Posting ➔",
                    key=f"sankey_jump_{safe_id}",
                    width="stretch",
                    type="secondary",
                    help="Jump directly to this posting's card, evaluation, and tailored documents on the Evaluations page"
                ):
                    if url:
                        st.session_state["active_job_url"] = url
                        st.session_state["jump_to_card"] = True
                        st.session_state["_hist_jump_nonce"] = st.session_state.get("_hist_jump_nonce", 0) + 1
                        st.switch_page("pages/2_history.py")
            if is_advancable:
                with r3:
                    if st.button("Heard back: Interview ➔", key=quick_adv_key, width="stretch", help="1-click advance to Interviewing"):
                        if url:
                            db.update_job_field(url, "Application Status", "Interviewing")
                        st.session_state[select_key] = "Interviewing"
                        st.session_state[db_tracker_key] = "Interviewing"
                        st.toast(f"🎉 Moved {pos} to Interviewing!")
                        st.rerun(scope="app")
            with r4:
                statuses = list(JOB_STATUS_OPTIONS)
                if curr_status not in statuses:
                    statuses.append(curr_status)

                st.selectbox(
                    "Status",
                    options=statuses,
                    key=select_key,
                    on_change=_make_status_updater(url, select_key, db_tracker_key, pos),
                    label_visibility="collapsed"
                )
            with r5:
                if st.button("🗑️", key=f"sankey_del_{safe_id}", width="stretch", help="Delete this posting (keeps it marked as Seen)"):
                    if url:
                        db.delete_job_by_url(url, keep_seen=True)
                    st.toast(f"🗑️ Removed '{pos}' (marked as Seen).")
                    st.rerun(scope="app")


def render_sankey_section(history_data: list[dict]):
    """Renders the Sankey Conversion Funnel, KPI badges, and Stage Explorer."""
    pending_toast = st.session_state.pop("_sankey_pending_toast", None)
    if pending_toast:
        st.toast(pending_toast)

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

    t_metrics = db.get_pipeline_turnaround_metrics(stale_days=stale_days, jobs=history_data)
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
            f"No Response After {stale_days}+ Days",
            t_metrics["ghosted_14d_count"],
            help=f"Applications waiting {stale_days}+ days without any update from the employer."
        )

    _render_interactive_sankey_explorer(sankey_data)
