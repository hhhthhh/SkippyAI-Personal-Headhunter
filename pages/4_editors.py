import streamlit as st
import os
import json
from utils import setup_sidebar

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
selected_preset = st.selectbox("Load Preset", list(presets.keys()), key="preset_selector")

with st.form("prompt_editor"):
    prompt_text = st.text_area("Instructions Editor", value=presets.get(selected_preset, ""), height=300)
    c1, c2 = st.columns(2)
    if c1.form_submit_button("💾 Save to Preset"):
        presets[selected_preset] = prompt_text
        with open("prompt_presets.json", "w", encoding="utf-8") as f: json.dump(presets, f, indent=4)
        st.success("Preset updated!")
    if c2.form_submit_button("Set as Active Custom Prompt", type="primary"):
        st.session_state.system_instructions = prompt_text
        with open("custom_prompt.txt", "w", encoding="utf-8") as f: f.write(prompt_text)
        st.success("Active prompt updated!")