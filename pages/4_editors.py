import streamlit as st
import os
import re
import json
from utils import initialize_core_state

# 1. Guarantee state is initialized even if accessed directly via legacy routing
initialize_core_state()

def _secure_file(path: str):
    if os.path.exists(path):
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

st.subheader("📄 Edit Master Resume")
with st.form("resume_editor_form"):
    updated_resume = st.text_area("Master Resume Content:", value=st.session_state.resume_text, height=600, help="Press Ctrl+Enter to save")
    if st.form_submit_button("Save Changes", type="primary"):
        st.session_state.resume_text = updated_resume
        with open("resume.md", "w", encoding="utf-8") as f:
            f.write(updated_resume)
        _secure_file("resume.md")
        st.success("Master resume saved successfully!")

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