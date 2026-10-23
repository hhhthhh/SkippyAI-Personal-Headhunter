import re
import importlib
from datetime import datetime
import streamlit as st
import pandas as pd
from collections import Counter, defaultdict
import plotly.graph_objects as go
import database as db
from utils import setup_sidebar, enforce_onboarding
from evaluator import generate_upskill_roadmap, generate_docx_from_markdown


def split_skills_preserving_parens(raw_csv: str) -> list[str]:
    """
    Splits a comma-separated skill string without breaking inside parentheses.
    Example:
      'Identity Access & MFA (Okta, Duo), CompTIA Security+'
      -> ['Identity Access & MFA (Okta, Duo)', 'CompTIA Security+']
    """
    if not raw_csv or str(raw_csv).lower() == "nan":
        return []
    items = []
    buf = []
    depth = 0
    for ch in str(raw_csv):
        if ch == "(":
            depth += 1
            buf.append(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            buf.append(ch)
        elif ch == "," and depth == 0:
            token = "".join(buf).strip()
            if token:
                items.append(token)
            buf = []
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        items.append(tail)
    return items


def canonicalize_skill_label(raw_skill: str) -> str:
    """
    Normalizes synonymous skill phrases across LLM evaluations so charts and
    gap rankings reflect true multi-posting frequency rather than fragmented wording.
    """
    s = re.sub(r"\s+", " ", (raw_skill or "").strip())
    if not s:
        return ""
    low = s.lower()

    # 1. Years-of-experience requirement variations
    if re.search(r"\b\d+\+?\s*(?:to\s*\d+\s*)?(?:years?|yrs?)\b", low) and "experience" in low:
        return "3-4+ Years Required Experience"

    # 2. Common cybersecurity / IT / engineering synonyms
    if "microsoft defender" in low or low in ("mde", "defender for endpoint"):
        return "Microsoft Defender (MDE)"
    if "sentinel" in low:
        return "Microsoft Sentinel"
    if "entra id" in low or "active directory" in low or "azure ad" in low:
        return "Microsoft Entra ID / Active Directory"
    if "security+" in low:
        return "CompTIA Security+"
    if "wireshark" in low or "packet inspection" in low or ("network" in low and "traffic analysis" in low):
        return "Network Traffic Analysis (Wireshark)"
    if ("okta" in low or "duo" in low or "mfa" in low or "identity" in low) and (
        "access" in low or "iam" in low or "mfa" in low
    ):
        return "IAM & MFA (Okta / Duo)"
    if "vulnerability management" in low:
        return "Vulnerability Management"
    if "siem" in low and ("triage" in low or "alert" in low or "monitoring" in low):
        return "SIEM Alert Triage"
    if "phishing" in low:
        return "Phishing Analysis"
    if "malware" in low:
        return "Malware Analysis"
    if "incident response" in low:
        return "Incident Response"
    if "mitre" in low and "att&ck" in low:
        return "MITRE ATT&CK Framework"
    if any(fw in low for fw in ("nist csf", "iso 27001", "pci dss")) or "governance & frameworks" in low:
        return "GRC Frameworks (NIST / ISO 27001 / PCI)"
    if "crowdstrike" in low:
        return "CrowdStrike Falcon"

    # 3. Generic cleanup: strip trailing filler words like 'Certification', 'Workflows', 'Platforms'
    cleaned = re.sub(
        r"\s+(?:Certification|Workflows|Platforms|Processes|Operations)\b$",
        "",
        s,
        flags=re.IGNORECASE,
    ).strip()
    words = []
    for w in cleaned.split():
        bare = re.sub(r"[^A-Za-z0-9+/&-]", "", w)
        if bare.isupper() and len(bare) >= 2:
            words.append(w)
        else:
            words.append(w.capitalize() if w.islower() else w)
    return " ".join(words)


_RED_FLAG_CATEGORIES = [
    (
        "⏳ Experience / Seniority Gate Stretch",
        re.compile(
            r"\b(?:\d+\+?\s*(?:to\s*\d+\s*)?(?:years?|yrs?)|minimum\s+\d+\s+years|experience\s+gate|exceeds\s+the\s+candidate|seniority)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "📍 On-Site / Hybrid / Relocation Requirement",
        re.compile(
            r"\b(?:on-?site|hybrid|relocat(?:e|ion)|in-?office|days?\s+per\s+week|presence\s+in|commute)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "🌙 On-Call Rotation / After-Hours / Weekend Shift",
        re.compile(
            r"\b(?:on-?call|after-?hours|outside\s+standard\s+working\s+hours|overnight|weekend|holiday|24/7|shift\s+work|rotation)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "🔐 Security Clearance / Citizenship / Sponsorship Gate",
        re.compile(
            r"\b(?:clearance|ts/sci|secret|polygraph|citizen(?:ship)?|sponsorship|visa|itar)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "🛠️ Specialized Platform / Tool SME Expectation",
        re.compile(
            r"\b(?:subject\s+matter\s+expertise|not\s+explicitly\s+showcased|expects\s+expertise|missing\s+required\s+tool|sentinel|splunk|crowdstrike)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "👻 Ghost / Reposted / Stale Listing Alert",
        re.compile(
            r"\b(?:repost(?:ed)?|fake\s+freshness|ghost\s+job|closed_at|stale\s+listing)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "🛡️ Prompt-Injection / Unicode Tampering Alert",
        re.compile(
            r"\b(?:security\s+alert|prompt\s+injection|unicode\s+tampering|homoglyph)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "📜 Strict Degree / License / Certification Gate",
        re.compile(
            r"\b(?:degree\s+required|cissp|cism|oscp|license\s+required|bar\s+admission)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "💰 Compensation / Contract / Overtime Concern",
        re.compile(
            r"\b(?:unpaid|below\s+market|commission\s+only|contract-to-hire|overtime)\b",
            re.IGNORECASE,
        ),
    ),
]


def classify_red_flag(flag_text: str) -> str:
    """
    Maps a full-sentence LLM red flag into a canonical Market Red Flag Category
    so recurring market friction points aggregate accurately across postings.
    """
    text = (flag_text or "").strip()
    if not text:
        return "⚠️ Other Role Caveat"
    for category_label, pattern in _RED_FLAG_CATEGORIES:
        if pattern.search(text):
            return category_label
    return "⚠️ Domain / Role-Specific Caveat"


# Re-export Sankey funnel utilities from pages.8_pipeline_funnel for backwards compatibility
_funnel_mod = importlib.import_module("pages.8_pipeline_funnel")
parse_date_safely = _funnel_mod.parse_date_safely
compute_sankey_data = _funnel_mod.compute_sankey_data
build_sankey_figure = _funnel_mod.build_sankey_figure
render_sankey_section = _funnel_mod.render_sankey_section


def render_market_skills_section(history_data: list[dict], total_jobs: int):
    """Renders market intelligence, skills charts, and red flags."""
    eligible_jobs = sum(1 for item in history_data if item.get("Eligible", True))
    avg_score = sum(item.get("Score", 0) for item in history_data) / total_jobs if total_jobs > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Postings Analyzed", total_jobs)
    col2.metric("Eligible Matches", eligible_jobs)
    col3.metric("Average Alignment Score", f"{avg_score:.1f} / 100")

    sub_scored_jobs = [
        item for item in history_data
        if item.get("Eligible", True) and any(
            int(item.get(col, 0) or 0) > 0
            for col in ("Technical Score", "Experience Score", "Behavioral Score", "Career Score")
        )
    ]
    if sub_scored_jobs:
        st.markdown("#### 🎯 Score Averages *(Eligible Roles)*")
        n_sub = len(sub_scored_jobs)
        avg_tech = sum(int(j.get("Technical Score", 0) or 0) for j in sub_scored_jobs) / n_sub
        avg_exp = sum(int(j.get("Experience Score", 0) or 0) for j in sub_scored_jobs) / n_sub
        avg_beh = sum(int(j.get("Behavioral Score", 0) or 0) for j in sub_scored_jobs) / n_sub
        avg_car = sum(int(j.get("Career Score", 0) or 0) for j in sub_scored_jobs) / n_sub

        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("💻 Technical Skills (30%)", f"{avg_tech:.1f} / 100")
        mc2.metric("📈 Experience Match (25%)", f"{avg_exp:.1f} / 100")
        mc3.metric("🤝 Behavioral Fit (15%)", f"{avg_beh:.1f} / 100")
        mc4.metric("🎯 Career Alignment (30%)", f"{avg_car:.1f} / 100")

    st.markdown("---")
    matching_skill_counts = Counter()
    missing_skill_counts = Counter()
    flag_category_counts = Counter()
    flag_category_examples = defaultdict(list)

    for item in history_data:
        role_title = str(item.get("Position") or "Role").strip()
        comp_name = str(item.get("Company") or "").strip()
        job_label = f"{role_title} ({comp_name})" if comp_name and comp_name != "Unknown Company" else role_title

        if m_skills := item.get("Matching Skills", ""):
            seen_match = set()
            for raw_s in split_skills_preserving_parens(m_skills):
                canon_s = canonicalize_skill_label(raw_s)
                if canon_s and canon_s not in seen_match:
                    seen_match.add(canon_s)
                    matching_skill_counts[canon_s] += 1

        if mis_skills := item.get("Missing Skills", ""):
            seen_miss = set()
            for raw_g in split_skills_preserving_parens(mis_skills):
                canon_g = canonicalize_skill_label(raw_g)
                if canon_g and canon_g not in seen_miss:
                    seen_miss.add(canon_g)
                    missing_skill_counts[canon_g] += 1

        seen_flag_cats = set()
        raw_flags = [rf.strip() for rf in str(item.get("Red Flags") or "").split("|") if rf.strip()]
        if not item.get("Eligible", True) and item.get("Disqualification Reason"):
            raw_flags.append(f"Disqualified: {item.get('Disqualification Reason')}")

        for rf in raw_flags:
            cat = classify_red_flag(rf)
            flag_category_examples[cat].append((job_label, rf))
            if cat not in seen_flag_cats:
                seen_flag_cats.add(cat)
                flag_category_counts[cat] += 1

    top_matching = matching_skill_counts.most_common(10)
    top_missing = missing_skill_counts.most_common(10)
    top_flags = flag_category_counts.most_common(8)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("### ✨ Skills That Shine *(Postings Matched)*")
        if top_matching:
            match_df = pd.DataFrame(top_matching, columns=["Skill", "Postings"]).set_index("Skill")
            st.bar_chart(match_df, color="#2baf2b", horizontal=True)
        else:
            st.caption("No matching skills recorded yet.")
    with col_b:
        st.markdown("### ⚠️ In-Demand Gaps *(Postings Requesting)*")
        if top_missing:
            miss_df = pd.DataFrame(top_missing, columns=["Skill", "Postings"]).set_index("Skill")
            st.bar_chart(miss_df, color="#ff4b4b", horizontal=True)
        else:
            st.caption("No skill gaps recorded yet.")

    st.markdown("---")
    st.subheader("🚨 Common Market Red Flags *(Grouped by Theme)*")
    st.caption(
        "LLM red-flag notes are automatically grouped into canonical themes so recurring friction points "
        "(e.g., on-call rotations, hybrid/relocation requirements, experience gates) show true frequency across your evaluated postings."
    )
    if top_flags:
        flag_chart_df = pd.DataFrame(
            [(cat, count) for cat, count in top_flags],
            columns=["Red Flag Theme", "Postings Affected"]
        ).set_index("Red Flag Theme")
        st.bar_chart(flag_chart_df, color="#f57c00", horizontal=True)

        for cat, count in top_flags:
            pct = round((count / total_jobs) * 100) if total_jobs else 0
            with st.expander(f"**{cat}** — **{count} / {total_jobs} postings ({pct}%)**", expanded=False):
                for job_lbl, exact_note in flag_category_examples[cat]:
                    st.markdown(f"- **{job_lbl}:** {exact_note}")
    else:
        st.caption("No recurring red flags detected across your evaluated postings.")


def render_upskill_section(history_data: list[dict]):
    """Renders the Actionable Upskill & Learning Plan Generator."""
    st.subheader("🎓 Actionable Upskill & Learning Plan Generator")
    st.write(
        "Prioritizes missing skills across your viable target roles (**Score ≥ 45**, weighted by `gap_weight = (100 - Score) / 100` "
        "so near-fit roles with high upside carry strong priority) and generates a concrete study roadmap, portfolio bridge projects, and 100% free study resources."
    )

    viable_jobs = [
        item for item in history_data
        if item.get("Eligible", True) and int(item.get("Score", 0) or 0) >= 45 and str(item.get("Missing Skills") or "").strip()
    ]
    gap_source_jobs = viable_jobs if viable_jobs else [
        item for item in history_data if str(item.get("Missing Skills") or "").strip()
    ]

    if not gap_source_jobs:
        st.info("No missing skills recorded across your evaluated postings yet. Evaluate more jobs to unlock your personalized Upskill Roadmap!")
    else:
        skill_freq = Counter()
        skill_weighted = defaultdict(float)
        skill_roles = defaultdict(list)

        for item in gap_source_jobs:
            score = int(item.get("Score", 0) or 0)
            weight = max(0.15, round((100 - score) / 100.0, 2))
            role_label = str(item.get("Position") or "Role").strip()
            comp = str(item.get("Company") or "").strip()
            if comp and comp != "Unknown Company":
                role_label = f"{role_label} ({comp})"

            raw_gaps = str(item.get("Missing Skills") or "")
            seen_in_job = set()
            for raw_g in split_skills_preserving_parens(raw_gaps):
                clean_g = canonicalize_skill_label(raw_g)
                if not clean_g or clean_g.lower() == "nan" or clean_g == "3-4+ Years Required Experience":
                    continue
                if clean_g not in seen_in_job:
                    seen_in_job.add(clean_g)
                    skill_freq[clean_g] += 1
                    skill_weighted[clean_g] += weight
                    if role_label not in skill_roles[clean_g] and len(skill_roles[clean_g]) < 3:
                        skill_roles[clean_g].append(role_label)

        ranked_gaps = sorted(
            skill_freq.keys(),
            key=lambda k: (skill_weighted[k], skill_freq[k]),
            reverse=True
        )[:15]

        if ranked_gaps:
            gap_rows = []
            for idx, sk in enumerate(ranked_gaps, start=1):
                gap_rows.append({
                    "Rank": f"#{idx}",
                    "Missing Skill / Gap": sk,
                    "Postings Mentioned": skill_freq[sk],
                    "Weighted Priority Score": round(skill_weighted[sk], 2),
                    "Target Roles Unlocked": ", ".join(skill_roles[sk]),
                })
            gap_df = pd.DataFrame(gap_rows)
            st.dataframe(gap_df, width="stretch", hide_index=True)

            weighted_gaps_payload = [
                {
                    "skill": sk,
                    "count": skill_freq[sk],
                    "weight": round(skill_weighted[sk], 2),
                    "roles": skill_roles[sk],
                }
                for sk in ranked_gaps
            ]
            all_target_roles = list(dict.fromkeys(
                str(item.get("Position") or "Role").strip()
                for item in gap_source_jobs
                if str(item.get("Position") or "").strip()
            ))

            if "upskill_roadmap_md" not in st.session_state:
                st.session_state["upskill_roadmap_md"] = ""

            col_gen, col_clear, _ = st.columns([3.2, 1.8, 5.0])
            with col_gen:
                if st.button("🎓 Generate Personalized Upskill & Study Roadmap", type="primary", width="stretch"):
                    with st.spinner("Analyzing skill gaps across your target roles and building your learning plan..."):
                        try:
                            roadmap_md = generate_upskill_roadmap(
                                master_resume=st.session_state.get("resume_text", ""),
                                weighted_gaps=weighted_gaps_payload,
                                target_roles=all_target_roles,
                                model_choice=st.session_state.get("model_choice"),
                                api_key=st.session_state.get("user_api_key"),
                                local_base_url=st.session_state.get("local_base_url", ""),
                                local_model_name=st.session_state.get("local_model_name", ""),
                                model_override=st.session_state.get("model_override", ""),
                            )
                            st.session_state["upskill_roadmap_md"] = roadmap_md
                            st.rerun()
                        except Exception as up_err:
                            st.error(f"⚠️ Could not generate Upskill Roadmap: {up_err}")
            with col_clear:
                if st.session_state.get("upskill_roadmap_md"):
                    if st.button("🔄 Clear Roadmap", width="stretch"):
                        st.session_state["upskill_roadmap_md"] = ""
                        st.rerun()

            if st.session_state.get("upskill_roadmap_md"):
                roadmap_val = st.session_state["upskill_roadmap_md"]
                with st.container(border=True):
                    st.markdown(roadmap_val)
                dl_col, _ = st.columns([3.0, 7.0])
                with dl_col:
                    st.download_button(
                        "📥 Download Upskill Roadmap (.docx)",
                        data=generate_docx_from_markdown(roadmap_val),
                        file_name="Skippy_Personalized_Upskill_Roadmap.docx",
                        type="primary",
                        width="stretch",
                        key="dl_upskill_roadmap_docx",
                    )


# --- MAIN PAGE ENTRY POINT ---
st.subheader("📊 Market Intelligence & Skill Analytics")
st.write("Aggregated market skill intelligence, red flag friction patterns, and personalized upskill planning.")

history_data = db.load_all_jobs()

if not history_data:
    st.info("No job history found yet. Run the scraper or evaluate postings to start collecting market and skill intelligence!")
else:
    tab_skills, tab_upskill = st.tabs([
        "📊 Market & Skill Intelligence",
        "🎓 Actionable Upskill Roadmap"
    ])

    with tab_skills:
        render_market_skills_section(history_data, len(history_data))

    with tab_upskill:
        render_upskill_section(history_data)
