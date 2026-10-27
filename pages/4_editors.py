import streamlit as st
import os
import re
import json
from utils import (
    initialize_core_state,
    load_resumes,
    save_resumes,
    extract_text_from_uploaded_resume,
    combine_selected_resumes,
    render_resume_selector,
    get_active_prompt_details,
    set_active_prompt_mode,
    save_custom_user_prompt,
    PROMPT_MODE_CUSTOM,
    PROMPT_MODE_COMPASS,
)
from evaluator import render_ats_resume_html, generate_ats_resume_docx, generate_ats_resume_pdf, lint_ats_resume

from database import atomic_write_text, atomic_write_json

# 1. Guarantee state is initialized even if accessed directly via legacy routing
initialize_core_state()

st.subheader("📂 Resume Library & Editor")
st.caption(
    "Upload as many specialized resumes as you want (`.docx`, `.pdf`, `.md`, `.txt`) or create and edit them below. "
    "When you score jobs or create tailored applications, you can choose which resumes Skippy should pull details from."
)

resumes_vault = load_resumes()
st.session_state["resumes_vault"] = resumes_vault
resume_names = list(resumes_vault.keys())

if "resume_uploader_version" not in st.session_state:
    st.session_state["resume_uploader_version"] = 0

uploader_key = f"multi_resume_uploader_{st.session_state['resume_uploader_version']}"
has_staged_files = bool(st.session_state.get(uploader_key))

# --- MULTI-FILE UPLOADER ---
with st.expander(
    "📤 Upload One or More Resume Files (.docx, .pdf, .md, .txt)",
    expanded=has_staged_files,
):
    uploaded_files = st.file_uploader(
        "Drag & drop resume files here (you can select multiple files at once):",
        type=["md", "txt", "docx", "pdf"],
        accept_multiple_files=True,
        key=uploader_key,
    )
    if uploaded_files:
        if st.button(f"📥 Import {len(uploaded_files)} Uploaded Resume(s)", type="primary", width="stretch"):
            imported_names = []
            for uf in uploaded_files:
                raw_name = os.path.splitext(uf.name)[0].strip()
                clean_title = re.sub(r"[_]+", " ", raw_name).strip() or "Uploaded Resume"
                extracted = extract_text_from_uploaded_resume(uf)
                if extracted.strip():
                    resumes_vault[clean_title] = extracted
                    imported_names.append(clean_title)
            if imported_names:
                save_resumes(resumes_vault)
                st.session_state["resumes_vault"] = resumes_vault
                st.session_state["pending_resume_selector"] = imported_names[-1]
                st.session_state["pending_resume_editor_text"] = resumes_vault[imported_names[-1]]
                st.session_state["resume_uploader_version"] += 1
                st.session_state["resume_feedback"] = (
                    "success",
                    f"Imported {len(imported_names)} resume(s) into your library: {', '.join(imported_names)}",
                )
                st.rerun()
            else:
                st.warning("Could not extract text from the uploaded file(s). Please check the file contents.")

feedback_slot = st.empty()
if "resume_feedback" in st.session_state:
    rf_type, rf_msg = st.session_state.pop("resume_feedback")
    if rf_type == "success":
        feedback_slot.success(rf_msg)
    elif rf_type == "info":
        feedback_slot.info(rf_msg)
    elif rf_type == "warning":
        feedback_slot.warning(rf_msg)
    elif rf_type == "error":
        feedback_slot.error(rf_msg)

# Active Evaluation Resume Selector right at the top of the Vault
render_resume_selector(key_suffix="editors_page", in_sidebar=False)

# Apply pending widget updates before widgets are instantiated
if "pending_resume_selector" in st.session_state:
    st.session_state["vault_resume_selector"] = st.session_state.pop("pending_resume_selector")
if "pending_resume_editor_text" in st.session_state:
    st.session_state["vault_resume_editor_text"] = st.session_state.pop("pending_resume_editor_text")
if "pending_new_resume_name" in st.session_state:
    st.session_state["new_resume_name_input"] = st.session_state.pop("pending_new_resume_name")

if "vault_resume_selector" not in st.session_state or st.session_state.vault_resume_selector not in resumes_vault:
    st.session_state.vault_resume_selector = resume_names[0] if resume_names else "Master Resume"

if "vault_resume_editor_text" not in st.session_state:
    st.session_state.vault_resume_editor_text = resumes_vault.get(st.session_state.vault_resume_selector, "")

def on_vault_resume_change():
    chosen_res = st.session_state.vault_resume_selector
    if chosen_res in resumes_vault:
        st.session_state.vault_resume_editor_text = resumes_vault[chosen_res]

r_col1, r_col2, r_col3 = st.columns([3.0, 2.2, 1.2])
with r_col1:
    selected_resume_name = st.selectbox(
        f"📄 Select Resume to View / Edit ({len(resume_names)} saved):",
        resume_names if resume_names else ["Master Resume"],
        key="vault_resume_selector",
        on_change=on_vault_resume_change,
    )
with r_col2:
    editor_view_mode = st.radio(
        "Editor Mode:",
        ["✏️ Edit Text", "📄 Clean Template Preview", "🔀 Split View (Edit & Preview)"],
        horizontal=True,
        key="vault_editor_view_mode",
    )
with r_col3:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🗑️ Delete Resume", width="stretch"):
        if len(resumes_vault) > 1:
            del resumes_vault[selected_resume_name]
            save_resumes(resumes_vault)
            remaining_res = list(resumes_vault.keys())
            st.session_state["resumes_vault"] = resumes_vault
            st.session_state["selected_resumes"] = [
                n for n in st.session_state.get("selected_resumes", []) if n in resumes_vault
            ] or [remaining_res[0]]
            st.session_state.resume_text = combine_selected_resumes(st.session_state["selected_resumes"], resumes_vault)
            st.session_state["pending_resume_selector"] = remaining_res[0]
            st.session_state["pending_resume_editor_text"] = resumes_vault[remaining_res[0]]
            st.session_state["resume_feedback"] = ("info", f"Deleted resume '{selected_resume_name}'.")
            st.rerun()
        else:
            st.error("You must keep at least one resume in your vault.")

if editor_view_mode == "📄 ATS Template Preview":
    current_vault_text = st.session_state.get("vault_resume_editor_text", resumes_vault.get(selected_resume_name, ""))
    st.markdown(render_ats_resume_html(current_vault_text, template_style="classic"), unsafe_allow_html=True)
elif editor_view_mode == "🔀 Live Split View":
    sp1, sp2 = st.columns([1, 1.15])
    with sp1:
        current_vault_text = st.text_area(
            f"Editing '{selected_resume_name}' (Press Ctrl+Enter to refresh preview):",
            key="vault_resume_editor_text",
            height=520,
        )
    with sp2:
        st.caption("📄 **Live ATS Template Preview**")
        st.markdown(render_ats_resume_html(current_vault_text, template_style="classic"), unsafe_allow_html=True)
else:
    current_vault_text = st.text_area(
        f"Resume Content ({selected_resume_name}):",
        key="vault_resume_editor_text",
        height=460,
        help="Press Ctrl+Enter to apply changes before saving.",
    )

new_res_name = st.text_input(
    "Name for New Resume Profile (Optional — used when clicking '➕ Save as New Resume'):",
    key="new_resume_name_input",
    placeholder="e.g., Clinical Specialist Resume, Corporate Counsel Resume, Logistics Lead Resume, Security Analyst Resume...",
)

rc1, rc2, rc3 = st.columns(3)
with rc1:
    if st.button("💾 Save Changes to Current Resume", type="primary", width="stretch"):
        resumes_vault[selected_resume_name] = current_vault_text
        save_resumes(resumes_vault)
        st.session_state["resumes_vault"] = resumes_vault
        st.session_state.resume_text = combine_selected_resumes(
            st.session_state.get("selected_resumes", [selected_resume_name]), resumes_vault
        )
        st.success(f"Saved changes to '{selected_resume_name}'!")
with rc2:
    if st.button("➕ Save as New Resume Profile", width="stretch"):
        clean_new = new_res_name.strip()
        if not clean_new:
            st.warning("Please enter a name above for the new resume profile.")
        elif len(clean_new) > 80 or re.search(r"[\x00-\x1f]", clean_new):
            st.warning("Please enter a valid resume name (under 80 characters).")
        else:
            resumes_vault[clean_new] = current_vault_text
            save_resumes(resumes_vault)
            st.session_state["resumes_vault"] = resumes_vault
            st.session_state["pending_resume_selector"] = clean_new
            st.session_state["pending_resume_editor_text"] = current_vault_text
            st.session_state["pending_new_resume_name"] = ""
            st.session_state["resume_feedback"] = ("success", f"Created new resume profile: '{clean_new}'!")
            st.rerun()
with rc3:
    safe_rname = re.sub(r"[^\w\-_\.]", "_", selected_resume_name.replace(" ", "_"))
    st.download_button(
        "📥 Download ATS (.docx)",
        data=generate_ats_resume_docx(current_vault_text, template_style="classic"),
        file_name=f"ATS_{safe_rname}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        width="stretch",
        key=f"dl_vault_{safe_rname}",
    )

with st.expander("🛡️ Check Resume Formatting & Scanner Compatibility", expanded=False):
    st.caption("Checks your resume against automated scanner rules (ATS), section titles, character issues (like weird symbols), and formatting mistakes.")
    lint_res = lint_ats_resume(current_vault_text)

    col_l1, col_l2, col_l3 = st.columns([1.5, 2.0, 3.5])
    with col_l1:
        st.metric("ATS Health Score", f"{lint_res['score']}/100")
    with col_l2:
        st.metric("Grade", lint_res["grade"])
    with col_l3:
        st.caption(f"**Metrics:** {lint_res['total_words']} words · {lint_res['bullet_count']} bullets ({lint_res['metric_bullet_count']} quantified)")

    if lint_res["issues"]:
        for iss in lint_res["issues"]:
            sev = iss.get("severity", "info")
            if sev == "critical":
                st.error(f"❌ **{iss['rule']}**: {iss['message']}")
            elif sev == "warning":
                st.warning(f"⚠️ **{iss['rule']}**: {iss['message']}")
            else:
                st.info(f"ℹ️ **{iss['rule']}**: {iss['message']}")

        if st.button("✨ Auto-Fix Formatting Issues (Clean Up Dashes, Bullets & Dates)", key=f"btn_autofix_{safe_rname}", width="stretch"):
            resumes_vault[selected_resume_name] = lint_res["clean_markdown"]
            save_resumes(resumes_vault)
            st.session_state["resumes_vault"] = resumes_vault
            st.session_state["pending_resume_editor_text"] = lint_res["clean_markdown"]
            st.toast("✅ Formatting cleaned up (standard hyphens, clean bullets, and standardized dates).")
            st.rerun()
    else:
        st.success("🎉 Zero formatting issues detected! This resume is clean and easy for job scanners to read.")

st.markdown("---")
st.subheader("⚙️ AI Instructions & Presets")

active_details = get_active_prompt_details()
if active_details["mode"] == PROMPT_MODE_CUSTOM:
    st.success("🟢 **Active in Job Review:** Evaluations currently use your **Custom Instructions**.", icon="✅")
else:
    col_stat, col_btn = st.columns([3.5, 1.5])
    with col_stat:
        st.info(
            f"🧭 **Evaluator is currently using your Career Profile:** `{active_details['title']}`.\n\n"
            "Edits below are saved to your Custom Instruction presets. To apply custom guidelines to the evaluator, click **Activate Custom Instructions**.",
            icon="ℹ️"
        )
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Activate Custom Instructions", type="primary", key="btn_activate_custom_prompt_top", width="stretch"):
            set_active_prompt_mode(PROMPT_MODE_CUSTOM)
            st.toast("🎯 Switched evaluation instructions to Custom Guidelines!", icon="✅")
            st.rerun()

if "preset_feedback" in st.session_state:
    fb_type, fb_msg = st.session_state.pop("preset_feedback")
    if fb_type == "success":
        st.success(fb_msg)
    elif fb_type == "info":
        st.info(fb_msg)
    elif fb_type == "warning":
        st.warning(fb_msg)
    elif fb_type == "error":
        st.error(fb_msg)

def load_prompt_presets() -> dict:
    if os.path.exists("prompt_presets.json"):
        try:
            with open("prompt_presets.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {"Default Boilerplate": "You are an advanced automated job-matching engine..."}

def save_prompt_presets(presets_data: dict):
    atomic_write_json("prompt_presets.json", presets_data, indent=4)

presets = load_prompt_presets()
preset_names = list(presets.keys())

# Apply pending widget updates before widgets are instantiated
if "pending_preset_selector" in st.session_state:
    st.session_state["preset_selector"] = st.session_state.pop("pending_preset_selector")

if "pending_prompt_text" in st.session_state:
    st.session_state["prompt_editor_text"] = st.session_state.pop("pending_prompt_text")

if "pending_new_preset_name" in st.session_state:
    st.session_state["new_preset_name_input"] = st.session_state.pop("pending_new_preset_name")

# Ensure default preset exists in state
if "preset_selector" not in st.session_state or st.session_state.preset_selector not in presets:
    st.session_state.preset_selector = preset_names[0]

# Ensure text area session state is synchronized
if "prompt_editor_text" not in st.session_state:
    st.session_state.prompt_editor_text = presets.get(st.session_state.preset_selector, "")

def on_preset_change():
    """Triggered instantly upon dropdown selection before the page renders downstream widgets."""
    chosen = st.session_state.preset_selector
    if chosen in presets:
        st.session_state.prompt_editor_text = presets[chosen]

# --- PRESET SELECTOR & DELETE BUTTON ---
col1, col2 = st.columns([4, 1])
with col1:
    selected_preset = st.selectbox(
        "Load Preset",
        preset_names,
        key="preset_selector",
        on_change=on_preset_change
    )
with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🗑️ Delete Selected"):
        if len(presets) > 1:
            del presets[selected_preset]
            save_prompt_presets(presets)
            # Fall back to the first available preset
            remaining_keys = list(presets.keys())
            st.session_state["pending_preset_selector"] = remaining_keys[0]
            st.session_state["pending_prompt_text"] = presets[remaining_keys[0]]
            st.session_state["preset_feedback"] = ("info", f"Deleted preset '{selected_preset}'.")
            st.rerun()
        else:
            st.error("You cannot delete the last remaining preset.")

# --- INSTRUCTIONS EDITOR ---
prompt_text = st.text_area("Instructions Editor", key="prompt_editor_text", height=300)

st.markdown("**Save Options**")
new_preset_name = st.text_input("Name for New Preset (Only used when creating a new one):", key="new_preset_name_input")

c1, c2, c3 = st.columns(3)

with c1:
    if st.button("➕ Create New Preset", width="stretch"):
        clean_name = new_preset_name.strip()
        if not clean_name:
            st.warning("Please enter a name for the new preset.")
        elif len(clean_name) > 80:
            st.warning("Preset name is too long (maximum 80 characters).")
        elif re.search(r'[\x00-\x1f]', clean_name):
            st.warning("Preset name contains invalid characters.")
        else:
            presets[clean_name] = prompt_text
            save_prompt_presets(presets)
            st.session_state["pending_preset_selector"] = clean_name
            st.session_state["pending_prompt_text"] = prompt_text
            st.session_state["pending_new_preset_name"] = ""
            st.session_state["preset_feedback"] = ("success", f"Created new preset: '{clean_name}'")
            st.rerun()

with c2:
    if st.button("💾 Update Current Preset", width="stretch"):
        presets[selected_preset] = prompt_text
        save_prompt_presets(presets)
        st.success(f"'{selected_preset}' updated successfully!")

with c3:
    if st.button("✅ Set as Active Custom Prompt", type="primary", width="stretch"):
        save_custom_user_prompt(prompt_text)
        set_active_prompt_mode(PROMPT_MODE_CUSTOM)
        st.session_state.system_instructions = prompt_text
        st.success("Active prompt updated! The evaluator will now use these custom instructions.")
        st.rerun()