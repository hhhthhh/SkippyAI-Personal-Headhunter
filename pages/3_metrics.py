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


_INDUSTRY_ACRONYMS = {
    # Healthcare & Medicine
    "EHR", "EMR", "HIPAA", "BLS", "ACLS", "PALS", "NRP", "RN", "BSN", "MSN",
    "NP", "PA-C", "MD", "DO", "CMA", "LPN", "FDA", "CDC", "ICD-10", "CPT",
    # Legal & Compliance
    "JD", "LLM", "ABA", "CLE", "SEC", "FINRA", "GDPR", "CCPA", "SOX", "FCPA",
    "CLM", "FTC", "USPTO", "EEOC",
    # Logistics, Operations & Supply Chain
    "WMS", "TMS", "3PL", "4PL", "OSHA", "DOT", "FIFO", "LIFO", "SCM", "ERP",
    "SAP", "MRP", "EDI", "JIT", "BOM", "RFQ", "RFP", "PO",
    # HR & People Ops
    "HRIS", "SHRM", "HRCI", "PHR", "SPHR", "ATS", "DEI", "FLSA", "FMLA",
    # Finance, Audit & Accounting
    "GAAP", "IFRS", "CPA", "CFA", "CMA", "FP&A", "P&L", "EBITDA", "ROI",
    "KPI", "GL",
    # Tech, Data, Cloud & Security
    "AWS", "GCP", "SQL", "API", "SDK", "CI/CD", "SIEM", "IAM", "MFA", "SOC",
    "NIST", "ISO", "PCI", "CISSP", "CISM", "CEH", "OSCP", "NLP", "AI",
    "ML", "ETL", "SaaS", "MDE", "WAF", "CASB", "EDR", "XDR"
}


def canonicalize_skill_label(raw_skill: str) -> str:
    """
    Normalizes synonymous skill phrases across LLM evaluations so charts and
    gap rankings reflect true multi-posting frequency across industries (tech, medicine,
    law, logistics, HR, finance, etc.) rather than fragmented wording.
    """
    s = re.sub(r"\s+", " ", (raw_skill or "").strip())
    if not s:
        return ""
    low = s.lower()

    # 1. Years-of-experience requirement variations
    if re.search(r"\b\d+\+?\s*(?:to\s*\d+\s*)?(?:years?|yrs?)\b", low) and "experience" in low:
        return "3-4+ Years Required Experience"

    # 2. Healthcare & Medicine Synonyms
    if any(k in low for k in ("epic ehr", "epic systems", "cerner", "electronic health record", "electronic medical record")) or low in ("ehr", "emr"):
        return "Electronic Health Records (EHR / Epic / Cerner)"
    if "hipaa" in low:
        return "HIPAA Compliance & Patient Privacy"
    if low in ("bls", "basic life support") or "bls certification" in low:
        return "Basic Life Support (BLS)"
    if low in ("acls", "advanced cardiac life support") or "acls certification" in low:
        return "Advanced Cardiac Life Support (ACLS)"
    if "patient triage" in low or "clinical triage" in low or "patient assessment" in low:
        return "Patient Triage & Clinical Assessment"
    if "phlebotomy" in low:
        return "Phlebotomy & Specimen Collection"
    if "telehealth" in low or "telemedicine" in low:
        return "Telehealth & Ambulatory Care"
    if "infection control" in low:
        return "Infection Control & Clinical Safety"

    # 3. Legal & Regulatory Synonyms
    if "westlaw" in low or "lexisnexis" in low or ("legal research" in low and "research" in low):
        return "Legal Research (Westlaw / LexisNexis)"
    if "clm" in low or "contract management" in low or "contract lifecycle" in low or "contract drafting" in low:
        return "Contract Drafting & Lifecycle Management (CLM)"
    if "regulatory compliance" in low or "statutory compliance" in low:
        return "Regulatory & Statutory Compliance"
    if "litigation" in low or "e-discovery" in low or "ediscovery" in low or "brief writing" in low:
        return "Litigation & e-Discovery"
    if "due diligence" in low:
        return "Legal Due Diligence & M&A"
    if "intellectual property" in low or low in ("ip", "patent", "trademark"):
        return "Intellectual Property (IP)"

    # 4. Logistics, Operations & Supply Chain Synonyms
    if "wms" in low or "warehouse management" in low:
        return "Warehouse Management Systems (WMS)"
    if "tms" in low or "transportation management" in low:
        return "Transportation Management Systems (TMS)"
    if "supply chain" in low or low in ("scm", "supply chain management"):
        return "Supply Chain Management (SCM)"
    if "inventory control" in low or "inventory management" in low:
        return "Inventory Control & Demand Planning"
    if "six sigma" in low or "lean manufacturing" in low or "kaizen" in low or low == "lean":
        return "Lean / Six Sigma"
    if "freight" in low or "customs clearance" in low or "customs broker" in low:
        return "Freight Forwarding & Customs Clearance"
    if "osha" in low:
        return "OSHA Workplace Safety"
    if "3pl" in low or "third-party logistics" in low:
        return "3PL / Carrier Vendor Management"

    # 5. HR & People Operations Synonyms
    if any(k in low for k in ("workday", "adp", "bamboohr", "hris", "human resources information")):
        return "HRIS (Workday / ADP)"
    if "talent acquisition" in low or "full-cycle recruiting" in low or "recruiting" in low:
        return "Talent Acquisition & Full-Cycle Recruiting"
    if "shrm" in low or "hrci" in low or "phr" in low or "sphr" in low:
        return "SHRM / HRCI Certification"
    if "employee relations" in low or "labor relations" in low:
        return "Employee Relations & Dispute Resolution"
    if "compensation" in low or "total rewards" in low or "benefits administration" in low:
        return "Total Rewards (Compensation & Benefits)"
    if "dei" in low or "diversity" in low:
        return "DEI & People Strategy"

    # 6. Finance & Accounting Synonyms
    if "gaap" in low or "ifrs" in low:
        return "GAAP / IFRS Accounting Standards"
    if "financial modeling" in low or "fp&a" in low or "financial planning" in low:
        return "Financial Modeling & FP&A"
    if low in ("cpa", "cpa certified") or "certified public accountant" in low:
        return "CPA / Financial Audit"
    if "accounts payable" in low or "accounts receivable" in low or low in ("ap/ar", "ar/ap"):
        return "Accounts Payable & Receivable (AP/AR)"
    if "netsuite" in low or ("sap" in low and "erp" in low):
        return "ERP Systems (SAP / NetSuite)"

    # 7. Common cybersecurity / IT / engineering synonyms
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

    # 8. Generic cleanup: strip trailing filler words like 'Certification', 'Workflows', 'Platforms'
    cleaned = re.sub(
        r"\s+(?:Certification|Workflows|Platforms|Processes|Operations)\b$",
        "",
        s,
        flags=re.IGNORECASE,
    ).strip()
    words = []
    for w in cleaned.split():
        bare = re.sub(r"[^A-Za-z0-9+/&-]", "", w).upper()
        if bare in _INDUSTRY_ACRONYMS:
            prefix = re.match(r"^[^A-Za-z0-9]*", w).group(0)
            suffix = re.search(r"[^A-Za-z0-9]*$", w).group(0)
            words.append(f"{prefix}{bare}{suffix}")
        elif w.isupper() and len(w) >= 2:
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
        "🌙 On-Call Rotation / Shift Work / Weekend Demand",
        re.compile(
            r"\b(?:on-?call|after-?hours|outside\s+standard\s+working\s+hours|overnight|weekend|holiday|24/7|shift\s+work|rotation|night\s+shift|rounding)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "🔐 Clearance / Citizenship / Authorization Gate",
        re.compile(
            r"\b(?:clearance|ts/sci|secret|polygraph|citizen(?:ship)?|sponsorship|visa|itar|work\s+authorization)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "🛠️ Specialized Platform / System SME Expectation",
        re.compile(
            r"\b(?:subject\s+matter\s+expertise|not\s+explicitly\s+showcased|expects\s+expertise|missing\s+required\s+tool|missing\s+platform|specialized\s+system|clinical\s+platform|legal\s+research\s+tool|erp\s+system|sentinel|splunk|crowdstrike|workday|epic|cerner|westlaw|netsuite)\b",
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
        "📜 Strict Degree / License / Credential Gate",
        re.compile(
            r"\b(?:degree\s+required|license\s+required|mandatory\s+license|board\s+certif(?:ied|ication)|state\s+bar|bar\s+admission|rn\s+license|bls|acls|cpa|shrm|pe\s+license|cissp|cism|oscp|juris\s+doctor)\b",
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


# Re-export Sankey funnel utilities from sankey_utils for backwards compatibility
from sankey_utils import (
    parse_date_safely,
    compute_sankey_data,
    build_sankey_figure,
    render_sankey_section,
    generate_safe_job_key,
)


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
        mc1.metric("🛠️ Hard / Tech Skills (30%)", f"{avg_tech:.1f} / 100")
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
    st.subheader("🚨 Common Job Hurdles & Warnings *(Grouped by Category)*")
    st.caption(
        "Common dealbreakers and job requirements (like required clearances, licenses, or travel) "
        "are grouped together so you can see recurring hurdles across jobs you've reviewed."
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
    st.subheader("🎓 Personalized Learning & Study Plan Generator")
    st.write(
        "Finds the most common skills you are missing for jobs you're close to qualifying for (**Score ≥ 45**), "
        "then creates a step-by-step study plan, hands-on practice projects, and free learning resources."
    )

    viable_jobs = [
        item for item in history_data
        if item.get("Eligible", True) and int(item.get("Score", 0) or 0) >= 45 and str(item.get("Missing Skills") or "").strip()
    ]
    gap_source_jobs = viable_jobs if viable_jobs else [
        item for item in history_data if str(item.get("Missing Skills") or "").strip()
    ]

    if not gap_source_jobs:
        st.info("No missing skills recorded across your evaluated jobs yet. Review more jobs to unlock your personalized Learning Plan!")
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
                            st.session_state["metrics_active_tab"] = "🎓 Personalized Learning Plan"
                            st.toast("🎉 Learning plan successfully generated!", icon="🎓")
                        except Exception as up_err:
                            st.error(f"⚠️ Could not generate Learning Plan: {up_err}")
            with col_clear:
                if st.session_state.get("upskill_roadmap_md"):
                    if st.button("🔄 Clear Roadmap", width="stretch"):
                        st.session_state["upskill_roadmap_md"] = ""
                        st.session_state["metrics_active_tab"] = "🎓 Personalized Learning Plan"
                        st.toast("Roadmap cleared", icon="🗑️")
                        st.rerun()

            if st.session_state.get("upskill_roadmap_md"):
                roadmap_val = st.session_state["upskill_roadmap_md"]
                with st.container(border=True):
                    st.markdown(roadmap_val)
                dl_col, _ = st.columns([3.0, 7.0])
                with dl_col:
                    st.download_button(
                        "📥 Download Learning Plan (.docx)",
                        data=generate_docx_from_markdown(roadmap_val),
                        file_name="Skippy_Personalized_Learning_Plan.docx",
                        type="primary",
                        width="stretch",
                        key="dl_upskill_roadmap_docx",
                    )


# --- MAIN PAGE ENTRY POINT ---
st.subheader("📊 Skills & Market Insights")
st.write("Overview of in-demand skills, common job requirements, and personalized learning plans.")

history_data = db.load_all_jobs(summary_only=True)

if not history_data:
    with st.container(border=True):
        st.subheader("📊 Skills & Market Insights")
        st.write(
            "Reviewing jobs enables Skippy to analyze high-demand market skills, cluster common workplace hurdles, "
            "and generate your personalized learning plan with free study resources."
        )
        c1, _ = st.columns([2.5, 4.5])
        with c1:
            if st.button("🔍 Review Jobs to Unlock Insights ➔", type="primary", width="stretch", key="btn_metrics_empty_goto_search"):
                st.switch_page("pages/1_scraper.py")
else:
    active_tab = st.session_state.pop("metrics_active_tab", None)
    if active_tab in ("🎓 Actionable Upskill Roadmap", "🎓 Personalized Learning Plan"):
        active_tab = "🎓 Personalized Learning Plan"
    elif active_tab in ("📊 Market & Skill Intelligence", "📊 In-Demand Skills & Hurdles"):
        active_tab = "📊 In-Demand Skills & Hurdles"

    tab_skills, tab_upskill = st.tabs([
        "📊 In-Demand Skills & Hurdles",
        "🎓 Personalized Learning Plan"
    ], default=active_tab)

    with tab_skills:
        render_market_skills_section(history_data, len(history_data))

    with tab_upskill:
        render_upskill_section(history_data)
