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
)
from evaluator import render_ats_resume_html, generate_ats_resume_docx, generate_ats_resume_pdf

# 1. Guarantee state is initialized even if accessed directly via legacy routing
initialize_core_state()

def _secure_file(path: str):
    if os.path.exists(path):
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

st.subheader("📂 Multi-Resume Vault & Editor")
st.caption(
    "Upload as many specialized resumes as you want (`.docx`, `.pdf`, `.md`, `.txt`) or create/edit them below. "
    "When you run an evaluation or generate materials, you can pick which resume(s) to match and harvest from."
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
        if st.button(f"📥 Import {len(uploaded_files)} Uploaded Resume(s) into Vault", type="primary", use_container_width=True):
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
                    f"Imported {len(imported_names)} resume(s) into your vault: {', '.join(imported_names)}",
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
        f"📄 Select Resume to View / Edit ({len(resume_names)} saved in vault):",
        resume_names if resume_names else ["Master Resume"],
        key="vault_resume_selector",
        on_change=on_vault_resume_change,
    )
with r_col2:
    editor_view_mode = st.radio(
        "Editor Mode:",
        ["✏️ Edit Markdown", "📄 ATS Template Preview", "🔀 Live Split View"],
        horizontal=True,
        key="vault_editor_view_mode",
    )
with r_col3:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🗑️ Delete Resume", use_container_width=True):
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
    placeholder="e.g., SOC Analyst Resume, Cloud Security Resume, Red Team Resume...",
)

rc1, rc2, rc3 = st.columns(3)
with rc1:
    if st.button("💾 Save Changes to Current Resume", type="primary", use_container_width=True):
        resumes_vault[selected_resume_name] = current_vault_text
        save_resumes(resumes_vault)
        st.session_state["resumes_vault"] = resumes_vault
        st.session_state.resume_text = combine_selected_resumes(
            st.session_state.get("selected_resumes", [selected_resume_name]), resumes_vault
        )
        st.success(f"Saved changes to '{selected_resume_name}'!")
with rc2:
    if st.button("➕ Save as New Resume Profile", use_container_width=True):
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
        use_container_width=True,
        key=f"dl_vault_{safe_rname}",
    )

st.markdown("---")
st.subheader("⚙️ Edit System Prompts")

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
    tmp_file = "prompt_presets.json.tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(presets_data, f, indent=4)
    _secure_file(tmp_file)
    try:
        os.replace(tmp_file, "prompt_presets.json")
    except OSError:
        with open("prompt_presets.json", "w", encoding="utf-8") as f:
            json.dump(presets_data, f, indent=4)
        _secure_file("prompt_presets.json")
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except OSError:
                pass

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
    if st.button("➕ Create New Preset", use_container_width=True):
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
    if st.button("💾 Update Current Preset", use_container_width=True):
        presets[selected_preset] = prompt_text
        save_prompt_presets(presets)
        st.success(f"'{selected_preset}' updated successfully!")

with c3:
    if st.button("✅ Set as Active Custom Prompt", type="primary", use_container_width=True):
        st.session_state.system_instructions = prompt_text
        tmp_file = "custom_prompt.txt.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(prompt_text)
        _secure_file(tmp_file)
        try:
            os.replace(tmp_file, "custom_prompt.txt")
        except OSError:
            with open("custom_prompt.txt", "w", encoding="utf-8") as f:
                f.write(prompt_text)
            _secure_file("custom_prompt.txt")
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except OSError:
                    pass
        st.success("Active prompt updated! The evaluator will now use these instructions.")