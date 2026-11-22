import streamlit as st

st.title("🦘 About Skippy")
st.markdown("---")
st.markdown("### What is Skippy?")
st.write(
    "Skippy is a 100% free, local-first job search assistant that helps you discover openings, "
    "score real fit against your resumes, track applications, and draft fact-checked resumes and interview prep—"
    "with all your history and files stored right on your computer."
)

st.markdown("### Key Highlights")
st.markdown(
    "- **Local-First Privacy:** Your database (`skippy.db`), resumes, and notes stay on your hard drive behind a local password. Skippy has no cloud servers—cloud AI requests go straight to the provider you choose using your own key, or use **Ollama** to run 100% offline.\n"
    "- **Zero-Login Job Discovery:** Search live openings on **LinkedIn** (guest search), direct company boards (**Greenhouse**, **Ashby**, **Lever**), and **FreeHire**, or right-click LinkedIn postings with the browser extension.\n"
    "- **Bring Your Own AI:** Works with **Google Gemini** (`gemini-2.5-flash`, ~$0.0004/evaluation with multi-key rotation), **OpenAI**, **Claude**, **Grok**, custom model overrides, or 100% offline **Ollama**.\n"
    "- **4-Pillar Match Scoring:** Evaluates Technical Skills (30%), Experience (25%), Team Fit (15%), and Career Alignment (30%), catching dealbreakers (clearances, mandatory licenses, relocation) upfront.\n"
    "- **Fact-Checked Resumes & Live Split Editor:** Drafts tailored resumes (**Standard ATS**, **Harvard Style**, **Modern Slate**) and cover letters with side-by-side live Markdown editing, **Apply Changes**, and an automatic **Accuracy & Fact-Check Grounding Report** below each draft.\n"
    "- **Application Tracker & Archive View:** Visualizes your funnel from review to offers, separates **Archived** postings into their own view, and lets you jump directly to any job card in 1 click.\n"
    "- **Built-in Safety Shield:** Deterministically strips hidden HTML, invisible Unicode characters, and prompt-injection lines from untrusted job listings before they ever reach your AI."
)


