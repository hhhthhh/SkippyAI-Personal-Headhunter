# 🤝 Skippy - AI Job Matcher & Scraper
A persistent, locally hosted Streamlit application that automates the job application process. Skippy scrapes job boards, evaluates roles against your master resume using AI, and automatically generates tailored resumes, cover letters, and custom interview prep materials.

All generated content and evaluation histories are saved locally to a persistent JSON database, keeping your data entirely private and seamlessly accessible across sessions.

## ✨ Features
Automated Scraping: Batch evaluate specific job URLs or use the Universal Auto-Scraper to extract and evaluate roles directly from search result pages.

Smart Evaluation: AI grades job descriptions against your resume, checking for hard blockers (e.g., clearances) and providing an alignment score (0-100).

Generative Tools: Instantly generate tailored Resumes, conversational Cover Letters, and STAR-method Interview Prep sheets in downloadable .docx formats from unlocked job tabs.

Flat UI Architecture: 100% flat UI design using standard Streamlit tabs and expanders for a stable, fast, and crash-free experience.

Model Agnostic: Works natively with Google Gemini (default), OpenAI, Anthropic, or fully offline using local Ollama instances.

Persistent History: Automatically saves match scores, synthesized position names, red flags, and generated text so you can review them later without burning API credits.

## 🚀 Zero-Prerequisite Deployment
Skippy is distributed in three distinct packages tailored for your environment. Download the specific .zip release for your operating system. There is no need to manually install Python dependencies or set up environments—the bootstrappers handle everything automatically.

### Option A: Windows Deployment (Skippy-Windows.zip)
This zero-prerequisite package isolates the entire runtime. It does not require Administrator privileges and will not interfere with any existing global Python installations.

Extract Skippy-Windows.zip to a local folder.

Double-click Launch-Windows.bat.

Press Y when prompted.

The script will automatically download a portable Python 3.11 engine, build a secure virtual environment, fetch the required Playwright Chromium binaries, and launch the application.

Note: Future launches will skip the download process and boot Skippy instantly.

### Option B: Linux / macOS / WSL Deployment (Skippy-Unix.zip)
This package requires Python 3 to be installed on the host machine but handles all isolated venv creation and dependency management automatically.

Extract Skippy-Unix.zip to a local directory.

Open your terminal in the extracted folder.

Make the script executable:

Bash
chmod +x launch.sh
Execute the bootstrapper:

Bash
./launch.sh
Press y when prompted. The script will configure the environment, prompt for sudo to install missing OS-level Chromium dependencies if necessary, and launch the UI.

### Option C: Docker Deployment (Skippy-Docker.zip)
The cleanest method for homelab environments. This pulls a lightweight Debian Python 3.11 image and maps your local directory as a volume, ensuring all generated .md documents and job_results.json histories persist across container restarts.

Requirement: Docker Engine / Docker Desktop installed and running.

Extract Skippy-Docker.zip.

Open the folder and run the appropriate launcher for your host OS:

Windows: Double-click Launch-Docker.bat

Mac/Linux: Run chmod +x launch-docker.sh && ./launch-docker.sh

The script will build the container in detached mode and provide the http://localhost:8501 link.

⚙️ First-Time Initialization
Before you can evaluate your first job posting, configure your local profile directly within the Skippy UI:

Provide Your Master Resume: Navigate to the "⚙️ Resume & Prompts Config" tab. Paste your full, plain-text master resume into the editor and click Save Resume. This generates the local resume.md file the AI uses as its baseline.

Configure Your API Key: Select your preferred AI Provider / Model (e.g., gemini-3.6-flash). Paste your API key in the designated field. (If using a local Ollama model, simply ensure your local server is running on port 11434 and leave the key blank).

Adjust Target Score: Set your "Minimum Target Score" slider. Jobs scoring above this threshold will be flagged as a ✅ Strong Match, while jobs below it will be flagged as a ⚠️ Reach.