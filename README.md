> ⚠️ **Project Status: Active Beta.** Skippy is a locally-hosted engineering tool in active development. While the core scraping and evaluation pipelines are fully operational, you may encounter edge cases with highly obfuscated job boards or transient API timeouts. Tracked issues and roadmap items can be found in the Issues tab.

# 🤝 Skippy - Local-First AI Job CRM & Automated Pipeline

Skippy is a privacy-first, locally hosted Streamlit application designed to automate the friction out of the job application process. Built as a secure alternative to expensive SaaS platforms, Skippy scrapes job boards, evaluates roles against your master resume using AI, and generates tailored application materials entirely on your local machine.

All generated content, API credentials, and evaluation histories are sandboxed locally, keeping your data strictly private.

## ✨ Core Architecture & Features
* **Event-Driven Scraping:** Utilize the Universal Auto-Scraper to bypass Single Page Application (SPA) restrictions and extract clean DOM content directly from search result pages.
* **Security & Prompt Defense:** Implements secure local state management by isolating API credentials via `.env` variables and utilizes XML-delimited prompt boundaries to mitigate LLM injection vulnerabilities from malformed job descriptions.
* **Smart Evaluation:** AI grades job descriptions against your resume, checking for hard blockers (e.g., clearances) and providing an alignment score (0-100).
* **Generative Tools:** Instantly generate tailored Resumes, conversational Cover Letters, and STAR-method Interview Prep sheets in downloadable `.docx` formats.
* **Model Agnostic:** Works natively with Google Gemini (default), OpenAI, Anthropic, xAI Grok, or fully offline using local Ollama instances.
* **Persistent History:** Automatically saves match scores, synthesized position names, red flags, and generated text to a persistent SQLite database (`skippy.db`) so you can review them later without burning API credits.

## 🚀 Zero-Prerequisite Deployment
Skippy is distributed in three distinct packages tailored for your operating system/environment. Download the specific `.zip` release for your operating system. There is no need to manually install Python dependencies or anything to for the tool to function correctly, the script will handle everything automatically.

### Option A: Windows Deployment (`Skippy-Windows.zip`)
This zero-prerequisite package isolates the entire runtime. It does not require Administrator privileges and will not interfere with any existing global Python installations.
1. Extract `Skippy-Windows.zip` to a local folder.
2. Double-click `skippy.bat`.
3. Press `Y` when prompted.
*(The script will automatically download a portable Python engine, build a secure virtual environment, fetch the required Playwright Chromium binaries, and launch the application. Future launches will boot instantly.)*

### Option B: Linux / macOS / WSL Deployment (`Skippy-Unix.zip`)
This package requires Python 3 to be installed on the host machine but handles all isolated venv creation and dependency management automatically.
1. Extract `Skippy-Unix.zip` to a local directory.
2. Open your terminal in the extracted folder and run: `chmod +x launch.sh`
3. Execute the bootstrapper: `./launch.sh`
4. Press `y` when prompted.

### Option C: Docker Deployment (`Skippy-Docker.zip`)
The cleanest method for homelab environments. This pulls a lightweight Debian Python image and maps your local directory as a volume, ensuring all generated documents and SQLite databases persist across container restarts. *(Requires Docker Engine / Docker Desktop).*
1. Extract `Skippy-Docker.zip`.
2. Open the folder and run the appropriate launcher for your host OS:
   * **Windows:** Double-click `Skippy-Docker-Windows.bat`
   * **Mac/Linux:** Run `chmod +x Skippy-LinuxOrMac-Docker-Launch.sh && ./Skippy-LinuxOrMac-Docker-Launch.sh`

## ⚙️ First-Time Initialization
Upon your first launch, Skippy will pause the application and prompt you to configure your local profile:

1. **Connect Your Provider:** On the main screen, select your preferred AI Provider (e.g., Google Gemini) and securely input your API key. (If using Ollama, simply provide your local `localhost:11434` URL).
2. **Provide Your Master Resume:** Paste your full, plain-text master resume into the onboarding text area. 

Once both steps are completed, skippy will initialize your `.env` and `resume.md` files, unlock the sidebar navigation, and grant access to the Scraper and History dashboards.