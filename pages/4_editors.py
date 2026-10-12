import streamlit as st
import os
import json
from utils import initialize_core_state

# 1. Guarantee state is initialized even if accessed directly via legacy routing
initialize_core_state()

st.subheader("📄 Edit Master Resume")
with st.form("resume_editor_form"):
    updated_resume = st.text_area("Master Resume Content:", value=st.session_state.resume_text, height=600, help="Press Ctrl+Enter to save")
    if st.form_submit_button("Save Changes", type="primary"):
        st.session_state.resume_text = updated_resume
        with open("resume.md", "w", encoding="utf-8") as f: f.write(updated_resume)
        st.success("Master resume saved successfully!")

st.markdown("---")
st.subheader("⚙️ Edit System Prompts")

def load_prompt_presets() -> dict:
    if os.path.exists("prompt_presets.json"):
        try:
            with open("prompt_presets.json", "r", encoding="utf-8") as f: return json.load(f)
        except Exception: pass
    return {"Default Boilerplate": "You are an advanced automated job-matching engine..."}

presets = load_prompt_presets()

# --- PRESET SELECTOR & DELETE BUTTON ---
col1, col2 = st.columns([4, 1])
with col1:
    selected_preset = st.selectbox("Load Preset", list(presets.keys()), key="preset_selector")
with col2:
    st.markdown("<br>", unsafe_allow_html=True) # Aligns the button with the dropdown
    if st.button("🗑️ Delete Selected"):
        if len(presets) > 1:
            del presets[selected_preset]
            with open("prompt_presets.json", "w", encoding="utf-8") as f: json.dump(presets, f, indent=4)
            st.rerun()
        else:
            st.error("You cannot delete the last remaining preset.")

# --- EDITOR FORM ---
with st.form("prompt_editor"):
    prompt_text = st.text_area("Instructions Editor", value=presets.get(selected_preset, ""), height=300)
    
    st.markdown("**Save Options**")
    new_preset_name = st.text_input("Name for New Preset (Only used when creating a new one):")
    
    c1, c2, c3 = st.columns(3)
    
    if c1.form_submit_button("➕ Create New Preset"):
        if new_preset_name.strip():
            presets[new_preset_name.strip()] = prompt_text
            with open("prompt_presets.json", "w", encoding="utf-8") as f: json.dump(presets, f, indent=4)
            st.success(f"Created new preset: '{new_preset_name.strip()}'")
        else:
            st.warning("Please enter a name for the new preset.")
            
    if c2.form_submit_button("💾 Update Current Preset"):
        presets[selected_preset] = prompt_text
        with open("prompt_presets.json", "w", encoding="utf-8") as f: json.dump(presets, f, indent=4)
        st.success(f"'{selected_preset}' updated successfully!")
        
    if c3.form_submit_button("✅ Set as Active Custom Prompt", type="primary"):
        st.session_state.system_instructions = prompt_text
        with open("custom_prompt.txt", "w", encoding="utf-8") as f: f.write(prompt_text)
        st.success("Active prompt updated! The evaluator will now use these instructions.")