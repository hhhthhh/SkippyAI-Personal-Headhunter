import os
import sys
import streamlit as st
import plotly.graph_objects as go

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import database as db
import career_compass
from utils import (
    atomic_write_text,
    get_active_prompt_details,
    set_active_prompt_mode,
    PROMPT_MODE_COMPASS,
    PROMPT_MODE_CUSTOM,
)

st.title("🧭 Career Profile & Direction")
st.caption(
    "Skippy tailors its match scoring, keywords, and resume tailoring to your exact field or profession. "
    "Choose from common career fields, adjust sliders, or let AI automatically build a custom profile for your trade."
)

profile = st.session_state.get("user_profile") or db.load_user_profile()

# ---------------------------------------------------------------------------
# AI Industry Profile Studio (Build for ANY Industry or Trade)
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.markdown("### 🤖 Custom Career Profile Studio (Any Trade or Field)")
    st.caption(
        "Working in a specialized trade, technical field, or unique industry? Enter your focus below "
        "(or leave blank to detect it from your resume). Skippy's AI will build a tailored industry profile with "
        "relevant skills, certifications, and scoring criteria."
    )
    col_input, col_btn = st.columns([3.2, 1.8], vertical_alignment="bottom")
    with col_input:
        niche_hint = st.text_input(
            "🎯 Industry, Trade, or Field Focus (Optional Guidance)",
            placeholder="e.g. Autonomous Subsea Robotics, Precision Watchmaking, Ammonia Refrigeration, Equine Sports Medicine, Museum Paper Conservation",
            key="niche_industry_focus_input",
            help="Specify your exact industry, craft, or specialization to guide the AI profile setup."
        )
    with col_btn:
        generate_ai_arch = st.button("⚡ Generate Profile with AI", type="primary", width="stretch", key="btn_synthesize_ai_archetype")

    if generate_ai_arch:
        resume_content = st.session_state.get("resume_text", "")
        if not resume_content.strip() and not (niche_hint and niche_hint.strip()):
            st.warning("⚠️ Please upload a master resume in Settings or enter an industry/trade focus above so Skippy can build your industry profile.")
        else:
            with st.spinner("Analyzing background and building your industry profile..."):
                try:
                    synth_profile = career_compass.detect_alignment_with_ai(
                        resume_text=resume_content,
                        industry_hint=niche_hint,
                        model_choice=st.session_state.get("model_choice"),
                        api_key=st.session_state.get("user_api_key")
                    )
                    adapted = career_compass.generate_adapted_custom_prompt(synth_profile)
                    synth_profile["adapted_prompt"] = adapted
                    db.save_user_profile(synth_profile)
                    st.session_state["user_profile"] = synth_profile
                    set_active_prompt_mode(PROMPT_MODE_COMPASS)
                    disp_title = synth_profile.get("industry_title") or synth_profile.get("archetype_title")
                    st.success(f"🎉 Industry Profile Created: **{disp_title}**!")
                    st.rerun()
                except Exception as ex:
                    st.error(f"❌ Profile creation error: {ex}")

if not profile:
    st.info("No career alignment profile detected yet. Take the quick quiz, generate with AI above, or auto-detect from your resume below!")
    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("⚡ Auto-Detect Career Profile from Resume", type="secondary", width="stretch"):
            with st.spinner("Detecting alignment..."):
                existing_cs = (st.session_state.get("user_profile") or {}).get("custom_skills", [])
                profile = career_compass.auto_detect_alignment_from_resume(
                    st.session_state.get("resume_text", ""),
                    use_ai=True,
                    model_choice=st.session_state.get("model_choice"),
                    api_key=st.session_state.get("user_api_key"),
                    existing_custom_skills=existing_cs
                )
                adapted = career_compass.generate_adapted_custom_prompt(profile)
                profile["adapted_prompt"] = adapted
                db.save_user_profile(profile)
                st.session_state["user_profile"] = profile
                set_active_prompt_mode(PROMPT_MODE_COMPASS)
                st.toast("🎯 Profile Detected & Saved!", icon="✅")
                st.rerun()

# ---------------------------------------------------------------------------
# Active Industry Profile Card & Visual Breakdown
# ---------------------------------------------------------------------------
if profile:
    with st.container(border=True):
        col_hdr, col_acts = st.columns([3.5, 1.5])
        with col_hdr:
            title_prefix = "🤖" if profile.get("ai_synthesized") else "🎯"
            active_title = profile.get("industry_title") or profile.get("archetype_title", "Industry Specialist")
            st.markdown(f"### {title_prefix} {active_title}")
            
            badge_parts = []
            if profile.get("ai_synthesized"):
                badge_parts.append(":violet-background[**🤖 AI-Generated Industry Profile**]")
            if profile.get("primary_title"):
                badge_parts.append(f"**Primary Industry:** {profile.get('primary_title')}")
            if profile.get("secondary_title"):
                badge_parts.append(f"**Secondary Focus:** {profile.get('secondary_title')}")
            if badge_parts:
                st.markdown(" • ".join(badge_parts))
            
            desc_text = profile.get("industry_description") or profile.get("archetype_description")
            if desc_text:
                st.caption(desc_text)
            if profile.get("rubric_focus"):
                st.markdown(f"**🎯 Scoring Criteria Focus:** *{profile.get('rubric_focus')}*")

            active_p_details = get_active_prompt_details()
            if active_p_details["is_compass"]:
                st.markdown(":green-background[**🟢 Active in Job Evaluator**] — *Evaluations currently use this industry profile's criteria.*")
            else:
                st.markdown(":blue-background[**⚙️ Inactive in Evaluator**] — *Evaluations are currently using your **Custom / Vault Prompt**.*")
        with col_acts:
            st.caption(f"🕒 Updated: {profile.get('updated_at', 'Recently')}")
            if not active_p_details["is_compass"]:
                if st.button("Activate Industry Profile for Evaluator", key="btn_activate_compass_card", type="primary", width="stretch"):
                    set_active_prompt_mode(PROMPT_MODE_COMPASS)
                    st.toast(f"🎯 Evaluator activated with {active_title} criteria!", icon="✅")
                    st.rerun()
            if st.button("⚡ Quick Re-Detect from Resume", key="compass_redetect", width="stretch"):
                with st.spinner("Analyzing master resume..."):
                    updated_profile = career_compass.auto_detect_alignment_from_resume(
                        st.session_state.get("resume_text", ""),
                        use_ai=True,
                        model_choice=st.session_state.get("model_choice"),
                        api_key=st.session_state.get("user_api_key"),
                        existing_custom_skills=profile.get("custom_skills", [])
                    )
                    adapted = career_compass.generate_adapted_custom_prompt(updated_profile)
                    updated_profile["adapted_prompt"] = adapted
                    db.save_user_profile(updated_profile)
                    st.session_state["user_profile"] = updated_profile
                    set_active_prompt_mode(PROMPT_MODE_COMPASS)
                    st.toast("Updated alignment from master resume!", icon="✅")
                    st.rerun()

    # Visual Alignment Breakdown
    scores = profile.get("scores", {})
    r_col, l_col = st.columns([2.2, 1.8])
    with r_col:
        st.markdown("#### 📊 Industry Alignment Chart")
        radar_fig = career_compass.render_alignment_radar_chart(scores)
        if radar_fig:
            st.plotly_chart(radar_fig, width="stretch")
        else:
            st.info("No score distribution to display.")

    with l_col:
        st.markdown("#### 🏆 Top Industry Matches")
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        primary_tracks = [item for item in sorted_scores if item[1] > 0][:7]
        long_tail_tracks = [item for item in sorted_scores if item[1] > 0][7:]

        if primary_tracks:
            for dom_key, pct in primary_tracks:
                dom_info = career_compass.DOMAIN_VECTORS.get(dom_key, {})
                icon = dom_info.get("icon", "🔹")
                title = dom_info.get("title", dom_key.replace("_", " ").title())
                st.markdown(f"**{icon} {title}**: `{pct:.1f}%`")
                st.progress(min(pct / 100.0, 1.0))
        else:
            st.info("No active domain scores detected.")

        if long_tail_tracks:
            with st.expander(f"➕ Additional Field Affinities (+{len(long_tail_tracks)} fields)"):
                for dom_key, pct in long_tail_tracks:
                    dom_info = career_compass.DOMAIN_VECTORS.get(dom_key, {})
                    icon = dom_info.get("icon", "🔹")
                    title = dom_info.get("title", dom_key.replace("_", " ").title())
                    st.markdown(f"**{icon} {title}**: `{pct:.1f}%`")
                    st.progress(min(pct / 100.0, 1.0))

    st.markdown("---")

    # -----------------------------------------------------------------------
    # Focus Keywords & Required Credentials Vault
    # -----------------------------------------------------------------------
    c_kw, c_gt = st.columns(2)
    with c_kw:
        st.markdown("#### 🔑 Key Skills & Tools")
        st.caption("Skippy's AI actively evaluates and highlights these keywords for your industry:")

        custom_skills = profile.get("custom_skills", [])
        all_keywords = profile.get("keywords", [])
        industry_keywords = [kw for kw in all_keywords if kw not in custom_skills]

        if custom_skills:
            st.markdown("**Your Added Skills & Tools:**")
            chips_custom = " ".join([f":violet-background[✨ **{cs}**]" for cs in custom_skills])
            st.markdown(chips_custom)
            with st.popover("🗑️ Manage / Remove Skills", use_container_width=True):
                st.caption("Click ✕ to remove any skill:")
                for idx, cs in enumerate(custom_skills):
                    r_c1, r_c2 = st.columns([3.5, 1])
                    r_c1.markdown(f"✨ **{cs}**")
                    if r_c2.button("✕", key=f"del_cs_{idx}_{cs}", type="secondary", use_container_width=True):
                        new_cs = [s for s in custom_skills if s != cs]
                        new_kw = [k for k in all_keywords if k != cs]
                        profile["custom_skills"] = new_cs
                        profile["keywords"] = new_kw
                        profile["adapted_prompt"] = career_compass.generate_adapted_custom_prompt(profile)
                        db.save_user_profile(profile)
                        st.session_state["user_profile"] = profile
                        st.toast(f"Removed '{cs}'", icon="🗑️")
                        st.rerun()

        if industry_keywords:
            st.markdown("**Industry Core Keywords:**")
            chips = " ".join([f"`{kw}`" for kw in industry_keywords])
            st.markdown(chips)
        elif not custom_skills:
            st.info("No specialized keywords assigned.")

        # Inline form to add candidate's own skills/tools
        with st.form("add_custom_skill_form", clear_on_submit=True):
            st.markdown("##### ➕ Add Custom Skill or Tool")
            ask_c1, ask_c2 = st.columns([3, 1])
            with ask_c1:
                new_skill_in = st.text_input(
                    "Skill Name",
                    placeholder="e.g. LangChain, Snowflake, GraphQL",
                    label_visibility="collapsed"
                )
            with ask_c2:
                btn_add_skill = st.form_submit_button("Add Skill", type="secondary", use_container_width=True)

            if btn_add_skill and new_skill_in:
                cur_custom = list(profile.get("custom_skills", []))
                cur_keywords = list(profile.get("keywords", []))
                entries = [e.strip() for e in new_skill_in.split(",") if e.strip()]
                added = []
                for entry in entries:
                    if not any(entry.lower() == s.lower() for s in cur_custom):
                        cur_custom.append(entry)
                        added.append(entry)
                    if not any(entry.lower() == k.lower() for k in cur_keywords):
                        cur_keywords.append(entry)

                if added:
                    profile["custom_skills"] = cur_custom
                    profile["keywords"] = cur_keywords
                    profile["adapted_prompt"] = career_compass.generate_adapted_custom_prompt(profile)
                    db.save_user_profile(profile)
                    st.session_state["user_profile"] = profile
                    st.toast(f"Added {', '.join(added)} to your skills!", icon="✨")
                    st.rerun()
                else:
                    st.warning("Entered skill(s) are already in your profile.")

    with c_gt:
        st.markdown("#### 🛡️ Required Licenses & Certifications")
        st.caption("Key qualifications checked when scoring jobs:")
        gates = profile.get("compliance_gates", [])
        if gates:
            for g in gates:
                st.markdown(f"- ✅ **{g}**")
        else:
            st.info("Standard general suitability checks apply.")

    st.markdown("---")

    # -----------------------------------------------------------------------
    # Target Roles & 1-Click Scraper Quick-Launch
    # -----------------------------------------------------------------------
    st.markdown("#### 🔍 Recommended Job Titles & Scraper Quick-Launch")
    st.caption("Click any role to jump directly to the Scraper with that role title pre-filled:")
    search_queries = profile.get("search_queries", [])
    if search_queries:
        q_cols = st.columns(min(max(len(search_queries), 1), 4))
        for idx, role in enumerate(search_queries[:8]):
            col = q_cols[idx % min(len(search_queries), 4)]
            with col:
                if st.button(f"{role}", key=f"btn_search_role_{idx}", width="stretch"):
                    st.session_state["li_search_query"] = role
                    st.switch_page("pages/1_scraper.py")

    st.markdown("---")

    # -----------------------------------------------------------------------
    # Manual Customization / Override Form
    # -----------------------------------------------------------------------
    with st.expander("✏️ Customize Your Career Profile & Skills"):
        st.caption("Directly customize your industry title, field, key skills, certifications, and scoring criteria:")
        with st.form("manual_archetype_customization_form"):
            form_c1, form_c2 = st.columns(2)
            with form_c1:
                custom_title = st.text_input(
                    "Industry / Role Title",
                    value=profile.get("industry_title") or profile.get("archetype_title", ""),
                    help="The exact title used in job matching and tailored applications."
                )
                custom_primary = st.text_input(
                    "Primary Industry / Field",
                    value=profile.get("primary_title") or profile.get("primary_domain", ""),
                    help="Your primary field of work (e.g. Maritime Robotics, Precision Machining)."
                )
            with form_c2:
                custom_secondary = st.text_input(
                    "Secondary Specialization / Field (Optional)",
                    value=profile.get("secondary_title") or profile.get("secondary_domain", "") or "",
                    help="Sub-discipline or hybrid crossover area."
                )
                custom_rubric = st.text_input(
                    "Scoring Criteria Focus",
                    value=profile.get("rubric_focus", ""),
                    help="What matters most in job post evaluations (e.g. verified equipment hours, ISO compliance)."
                )

            custom_desc = st.text_area(
                "Industry Focus & Description",
                value=profile.get("industry_description") or profile.get("archetype_description", ""),
                height=80,
                help="Summary of operational philosophy, safety mindset, or career objective."
            )

            custom_keywords_str = st.text_area(
                "Key Skills, Tools & Equipment (comma-separated)",
                value=", ".join(profile.get("keywords", [])),
                height=100,
                help="Keywords prioritized during scoring and matched in resumes."
            )

            custom_gates_str = st.text_area(
                "Required Licenses, Certifications & Credentials (one per line)",
                value="\n".join(profile.get("compliance_gates", [])),
                height=100,
                help="Certifications, statutory licenses, or security clearances verified during scoring."
            )

            custom_queries_str = st.text_area(
                "Recommended Job Titles for Scraper (comma-separated)",
                value=", ".join(profile.get("search_queries", [])),
                height=80,
                help="Search presets shown as quick-launch buttons on the Scraper page."
            )

            save_custom_profile = st.form_submit_button("💾 Save Custom Industry Profile", type="primary", width="stretch")
            if save_custom_profile:
                parsed_keywords = [k.strip() for k in custom_keywords_str.split(",") if k.strip()]
                parsed_gates = [g.strip() for g in custom_gates_str.split("\n") if g.strip()]
                parsed_queries = [q.strip() for q in custom_queries_str.split(",") if q.strip()]

                updated_p = dict(profile)
                c_title = custom_title.strip()
                c_desc = custom_desc.strip()
                updated_p["industry_title"] = c_title
                updated_p["archetype_title"] = c_title
                updated_p["primary_title"] = custom_primary.strip()
                updated_p["primary_domain"] = custom_primary.strip().lower().replace(" ", "_")
                updated_p["secondary_title"] = custom_secondary.strip()
                updated_p["secondary_domain"] = custom_secondary.strip().lower().replace(" ", "_") if custom_secondary.strip() else None
                updated_p["industry_description"] = c_desc
                updated_p["archetype_description"] = c_desc
                updated_p["rubric_focus"] = custom_rubric.strip()
                updated_p["keywords"] = parsed_keywords
                updated_p["compliance_gates"] = parsed_gates
                updated_p["search_queries"] = parsed_queries

                new_prompt = career_compass.generate_adapted_custom_prompt(updated_p)
                updated_p["adapted_prompt"] = new_prompt
                db.save_user_profile(updated_p)
                st.session_state["user_profile"] = updated_p
                set_active_prompt_mode(PROMPT_MODE_COMPASS)
                st.toast("Custom industry profile saved!", icon="✅")
                st.rerun()

    # -----------------------------------------------------------------------
    # Manual Fine-Tuning Sliders
    # -----------------------------------------------------------------------
    with st.expander("🎚️ Fine-Tune Your Career Interests (Sliders)"):
        st.caption("Manually adjust your interest percentages across career fields without retaking the quiz:")
        slider_vals = {}
        s_cols = st.columns(2)
        dom_keys = list(career_compass.DOMAIN_VECTORS.keys())
        for idx, k in enumerate(dom_keys):
            d_info = career_compass.DOMAIN_VECTORS[k]
            curr_val = float(scores.get(k, 0.0))
            col = s_cols[idx % 2]
            with col:
                slider_vals[k] = st.slider(
                    f"{d_info.get('icon', '🔹')} {d_info.get('title')}",
                    min_value=0.0,
                    max_value=100.0,
                    value=curr_val,
                    step=5.0,
                    key=f"compass_slider_{k}"
                )

        if st.button("💾 Save Adjusted Weights & Recalibrate Skippy", type="primary", width="stretch"):
            total_sum = sum(slider_vals.values())
            if total_sum > 0:
                normalized = {k: round((v / total_sum) * 100.0, 1) for k, v in slider_vals.items()}
            else:
                normalized = {k: 0.0 for k in slider_vals}

            sorted_adj = sorted(normalized.items(), key=lambda x: x[1], reverse=True)
            p_dom = sorted_adj[0][0]
            s_dom = sorted_adj[1][0] if len(sorted_adj) > 1 and sorted_adj[1][1] >= 15.0 else None

            arch_def = career_compass.INDUSTRY_DEFINITIONS.get((p_dom, s_dom))
            if not arch_def:
                arch_def = career_compass.INDUSTRY_DEFINITIONS.get((p_dom, None))
            if not arch_def:
                arch_def = {
                    "title": f"{career_compass.DOMAIN_VECTORS[p_dom]['short_title']} Operations Specialist",
                    "desc": f"Specialist aligned with {career_compass.DOMAIN_VECTORS[p_dom]['title']} standards."
                }

            p_data = career_compass.DOMAIN_VECTORS[p_dom]
            s_data = career_compass.DOMAIN_VECTORS.get(s_dom, {}) if s_dom else {}

            existing_custom = list(profile.get("custom_skills", []))
            merged_kw = list(p_data.get("core_keywords", []))[:18]
            for cs in existing_custom:
                if cs not in merged_kw:
                    merged_kw.append(cs)

            new_profile = {
                "primary_domain": p_dom,
                "secondary_domain": s_dom,
                "primary_title": p_data.get("title", ""),
                "secondary_title": s_data.get("title", "") if s_data else "",
                "industry_title": arch_def["title"],
                "archetype_title": arch_def["title"],
                "industry_description": arch_def["desc"],
                "archetype_description": arch_def["desc"],
                "scores": normalized,
                "keywords": merged_kw,
                "custom_skills": existing_custom,
                "search_queries": list(p_data.get("recommended_roles", []))[:8],
                "compliance_gates": list(p_data.get("compliance_gates", []))[:4],
                "ai_synthesized": False,
            }
            new_prompt = career_compass.generate_adapted_custom_prompt(new_profile)
            new_profile["adapted_prompt"] = new_prompt
            db.save_user_profile(new_profile)
            st.session_state["user_profile"] = new_profile
            set_active_prompt_mode(PROMPT_MODE_COMPASS)
            st.toast("Recalibrated alignment profile!", icon="✅")
            st.rerun()

    # -----------------------------------------------------------------------
    # Retake Universal Compass Quiz
    # -----------------------------------------------------------------------
    with st.expander("📝 Retake the 7 Career Direction Questions"):
        st.caption("Re-answer the 7 questions to recalculate your career profile from scratch:")
        with st.form("retake_career_compass_quiz_form"):
            retake_answers = {}
            for q in career_compass.UNIVERSAL_QUIZ_QUESTIONS:
                st.markdown(f"**{q['title']}**")
                st.caption(q["question"])
                labels = [opt["label"] for opt in q["options"]]
                chosen_label = st.radio(
                    label=q["title"],
                    options=labels,
                    index=0,
                    key=f"retake_q_{q['id']}",
                    label_visibility="collapsed"
                )
                retake_answers[q["id"]] = labels.index(chosen_label)
                st.markdown("<br>", unsafe_allow_html=True)

            retake_submitted = st.form_submit_button("Recalculate Alignment & Save Profile 🚀", type="primary", width="stretch")
            if retake_submitted:
                recalculated = career_compass.score_quiz_responses(
                    retake_answers,
                    existing_custom_skills=profile.get("custom_skills", [])
                )
                recalculated["ai_synthesized"] = False
                adapted_prompt = career_compass.generate_adapted_custom_prompt(recalculated)
                recalculated["adapted_prompt"] = adapted_prompt
                db.save_user_profile(recalculated)
                st.session_state["user_profile"] = recalculated
                set_active_prompt_mode(PROMPT_MODE_COMPASS)
                disp_title = recalculated.get("industry_title") or recalculated.get("archetype_title")
                st.success(f"🎯 Recalibrated Profile: {disp_title}!")
                st.rerun()

    # -----------------------------------------------------------------------
    # Adapted System Instructions Inspector
    # -----------------------------------------------------------------------
    with st.expander("📜 View Industry Evaluation Prompt"):
        active_p_details = get_active_prompt_details()
        if active_p_details["is_compass"]:
            st.success("🟢 **Currently Active in Job Evaluator:** This industry prompt is governing your job match scores.", icon="✅")
        else:
            col_exp_inact, col_exp_act = st.columns([3.5, 1.5])
            with col_exp_inact:
                st.warning("⚙️ **Currently Inactive:** Evaluations are using your Custom Prompt from the Resume & Prompts page.", icon="⚠️")
            with col_exp_act:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Activate Industry Prompt", key="compass_activate_from_expander", type="primary", width="stretch"):
                    set_active_prompt_mode(PROMPT_MODE_COMPASS)
                    disp_title = profile.get("industry_title") or profile.get("archetype_title")
                    st.toast(f"🎯 Evaluator activated with {disp_title} criteria!", icon="✅")
                    st.rerun()

        arch_prompt = profile.get("adapted_prompt", "") or career_compass.generate_adapted_custom_prompt(profile)
        st.code(arch_prompt, language="markdown")
        if st.button("🔄 Regenerate & Re-Apply Prompt from Current Industry Profile", key="compass_reapply_prompt", width="stretch"):
            fresh_prompt = career_compass.generate_adapted_custom_prompt(profile)
            profile["adapted_prompt"] = fresh_prompt
            db.save_user_profile(profile)
            st.session_state["user_profile"] = profile
            set_active_prompt_mode(PROMPT_MODE_COMPASS)
            st.toast("Regenerated and applied evaluation prompt!", icon="✅")
            st.rerun()
