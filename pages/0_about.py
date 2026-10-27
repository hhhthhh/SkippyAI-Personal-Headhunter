import streamlit as st
from utils import setup_sidebar, enforce_onboarding

st.title("🦘 About Skippy")
st.markdown("---")
st.markdown("### What is Skippy?")
st.write(
    "Skippy is a 100% free, private assistant that helps you find jobs, see if you're a real match, "
    "and create tailored resumes and interview prep—running right on your computer without ever "
    "sending your personal data to the cloud."
)

st.markdown("### Key Highlights")
st.markdown(
    "- **100% Private & Local:** Runs on your machine. Your resumes, notes, and searches stay safe on your hard drive.\n"
    "- **Easy Job Discovery:** Search live jobs across LinkedIn, top company hiring sites (Greenhouse, Ashby, Lever), or tech boards without needing an account or login.\n"
    "- **Choose Your AI Assistant:** Works with Google Gemini (free tier), ChatGPT, Claude, Grok, or run 100% offline with Ollama.\n"
    "- **Honest Match Scoring:** Scores jobs from 0 to 100 across skills, experience, team fit, and career goals, catching dealbreakers (like clearances or relocation) upfront.\n"
    "- **Fact-Checked Resumes:** Automatically writes customized resumes and cover letters, then double-checks them against your real background so nothing is made up.\n"
    "- **Complete Job Search Toolkit:** Prepares tailored resumes, cover letters, short answers for job applications, interview practice questions, follow-up messages, and personalized study guides.\n"
    "- **Built-in Safety Shield:** Automatically blocks hidden text, invisible characters, and malicious code from untrusted job listings before sending them to the AI."
)

st.markdown("---")
st.info("Developed by **Hayden Tanaka** — B.S. Cyber Intelligence and Security, Embry-Riddle Aeronautical University")
