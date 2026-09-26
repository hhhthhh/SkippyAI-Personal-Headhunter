# 🛡️ AI Job Matcher & Scraper

A persistent, locally hosted Streamlit application that automates the job application process. It scrapes job boards, evaluates roles against your master resume using AI, and automatically generates tailored resumes, cover letters, and custom interview prep materials. 

All generated content and evaluation histories are saved locally to a persistent JSON database, keeping your data entirely private.

## ✨ Features
* **Automated Scraping:** Batch evaluate specific job URLs or use the Universal Auto-Scraper to extract and evaluate roles directly from search result pages.
* **Smart Evaluation:** AI grades job descriptions against your resume, checking for hard blockers (e.g., clearances) and providing an alignment score (0-100).
* **Generative Tools:** Instantly generate tailored Resumes, conversational Cover Letters, and STAR-method Interview Prep sheets in downloadable `.docx` formats.
* **Model Agnostic:** Works with Google Gemini, OpenAI (ChatGPT), Anthropic (Claude), xAI (Grok), or fully offline using local Ollama instances.
* **Persistent History:** Automatically saves match scores, red flags, and generated text so you can review them later without burning API credits.

---

## 🚀 Installation & Setup

You can run this application entirely containerized via Docker (Recommended) or directly on your machine. 

### Option A: Docker Deployment (Recommended)
This is the easiest method and requires zero Python knowledge. It pulls an official Microsoft Playwright image so you don't have to install browser binaries on your host machine.

**Requirements:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.

1. Clone or download this repository.
2. Open your terminal in the project folder.
3. Build and launch the container:
   ```bash
   docker compose build --no-cache
   docker compose up -d

### Option B: Windows Local Installation 
If you prefer running the application directly on your machine, you will need to use the automated install scripts. These scripts will check for Python, build a secure virtual environment, install the required libraries, and download the headless Chromium browser used for web scraping.

Requirements: Python 3.10+ (The Windows script will attempt to install this automatically if missing).

For Windows Users:
Double-click the install.bat file in the project folder.

⚠️ Note: If the script installs Python for you via winget, you must close the terminal, open a new one, and run install.bat again so Windows recognizes the new Python path.

Once the installation completes successfully, double-click start.bat to launch the application.

The app will open automatically in your default web browser at http://localhost:8501.

### For Linux / macOS / WSL Users Local Installation:
Open your terminal in the project directory.

Make the installation and startup scripts executable:

Bash
chmod +x install.sh start.sh
Run the installer (this uses apt-get to fetch Python if you are on Debian/Ubuntu):

Bash
./install.sh
Once complete, launch the application:

Bash
./start.sh
⚙️ First-Time Initialization
Before you can evaluate your first job posting, you must configure your local profile:

Provide Your Master Resume:

Navigate to the "⚙️ Resume & Prompts Config" page via the left sidebar.

Paste your full, plain-text master resume into the editor and click Save Resume. This generates the local resume.md file the AI uses as its baseline.

Configure Your API Key:

In the sidebar, select your preferred AI Provider / Model.

Paste your API key in the password field. (If using a local Ollama model, simply ensure your local server is running on port 11434 and leave the key blank).

Adjust Target Score:

Set your "Minimum Target Score" slider. Jobs scoring above this threshold will be flagged as a ✅ Strong Match, while jobs below it will be flagged as a ⚠️ Reach.