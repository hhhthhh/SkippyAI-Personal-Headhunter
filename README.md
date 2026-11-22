# 🦘 Skippy — AI Job CRM

> ⚠️ **Project Status: Active Beta.** Skippy is in active development! The core job search, AI evaluator, application tracker, and document generator are fully up and running. If a job board gives you trouble or an AI takes a second to reply, check the tips below.

---

## 🌟 What is Skippy?

Searching and applying for jobs can feel like an endless chore. You have to read through dozens of long job postings, figure out if you're actually qualified, and rewrite your resume and cover letter over and over again.

**Skippy does the heavy lifting for you!**

Think of Skippy as your smart, local-first job search assistant that lives directly on your computer:
1. **Reads job descriptions in seconds** — search job boards directly, paste job text, drop in multiple links, or send jobs from LinkedIn with a single right-click.
2. **Checks if you're actually a match** — compares each job against your resume across 4 weighted dimensions and gives you an honest **Match Score from 0 to 100**.
3. **Catches dealbreakers upfront** — flags non-negotiable requirements like security clearances, mandatory licenses, or relocation before you waste time applying.
4. **Writes fact-checked resumes & application materials** — creates clean Word documents (`.docx`) and on-demand PDFs (`.pdf`) tailored to each role, automatically audited against your real resume so nothing is fabricated.
5. **Local-First & Private** — all your resumes, evaluations, notes, and API keys stay right on your computer in a local SQLite database behind your own password. Skippy has no cloud backend—when using a cloud AI provider, only the text needed for each request goes directly to the provider you chose using your own key, or choose **Local / Custom (Ollama)** to run 100% offline.

---

## ✨ What Skippy Can Do

| Feature | What it does | Why it helps |
| :--- | :--- | :--- |
| 🎯 **4-Pillar Match Scoring** | Evaluates roles across **Skills & Tools (30%)**, **Experience Match (25%)**, **Work Style & Team (15%)**, and **Career Goals (30%)**. | Delivers an objective 0–100 score instead of a simple keyword count. |
| 🔎 **Job Board Search** | Searches **LinkedIn** (public guest search), **Direct Company Hiring Pages** (**Greenhouse**, **Ashby**, **Lever**), and **FreeHire** with zero accounts or API keys needed. | Find and queue dozens of live openings in seconds without logging into job boards. |
| 🛑 **Dealbreaker & Gate Checks** | Checks **Requirements** and **Location** gates upfront, flagging clearances, mandatory licenses, travel, or relocation. | Keeps you from wasting time applying to roles with strict barriers to entry. |
| 👻 **Repeated Listing & Ghost Job Signals** | Detects postings that companies have repeatedly relisted over 14+ days. | Helps you focus on active, responsive hiring teams instead of stale listings. |
| 🌊 **Interactive Application Tracker** | Visualizes your active pipeline from review and application to interviews and offers in a clickable Sankey funnel (with **🗄️ Archived** separated cleanly). | Click any stage box or branch to auto-scroll to its postings, track **Employer Response Times**, jump straight to any evaluation, and advance stages in 1 click. |
| 📄 **Tailored Documents & Live Split View** | Generates **Tailored Resumes** (**Standard ATS**, **Harvard Style**, **Modern Slate**), **Cover Letters**, **Application Answers**, **Interview Prep**, **Follow-Up Notes**, **Outreach Messages**, and **Company Research Guides**. | Edit Markdown side-by-side with a live formatted ATS preview, click **💾 Apply Changes** to save to SQLite, and download `.docx` (and `.pdf` when LibreOffice is installed). |
| 🛡️ **Accuracy & Fact-Check Grounding Report** | Automatically runs a secondary AI grounding audit whenever you generate a **Tailored Resume** or **Cover Letter**, checking every claim against your real resume. | Displays a per-document **🛡️ Accuracy & Fact-Check Grounding Report** below each draft so you can verify why claims were kept or adjusted. |
| 📄 **Resume Library & ATS Editor** | Upload and manage multiple resumes (`.docx`, `.pdf`, `.md`, `.txt`) with offline **ATS Health Score** checks, **✨ Smart Auto-Fix Formatting**, and opt-in **🧠 AI Content Polish**. | Easily target different career tracks (e.g., Help Desk vs. Security Analyst) without rewriting your core files. |
| 🧹 **Smart Cleanup & Archive View** | Move postings into **🗄️ Archived** or bulk-clean low-scoring/rejected jobs while protecting active applications and saved documents. | Keeps **📋 Active Postings** tidy and marks deleted jobs as seen so future searches skip them. |
| 🎓 **Personalized Learning & Study Plan Generator** | Identifies recurring skill gaps across near-fit jobs in **📊 Skills & Insights** and builds personalized study plans. | Gives you realistic practice projects and 100% free study resources to close skill gaps. |
| 🛡️ **Job Text Safety Shield** | Deterministically strips hidden HTML, invisible Unicode characters, and prompt-injection lines from untrusted postings—zero AI calls required. | Keeps AI evaluations accurate and safe from poisoned web listings. |
| 🔗 **Skippy Job Catcher Extension** | Right-click any job on LinkedIn to capture and queue it straight into **🔗 Extension Inbox** (authenticated with your local **Extension Auth Token**). | Works with Chrome, Brave, Edge, Vivaldi, Firefox, Zen, LibreWolf, and Waterfox. |
| 🔒 **Local Password Protection** | Secures your local workspace with a password-protected login screen and brute-force lockout protection. | Your job history, notes, and resumes stay private on your machine. |
| 🤖 **Bring Your Own AI (Cloud or Offline)** | Supports **Google Gemini** (`gemini-2.5-flash`), **OpenAI ChatGPT** (`gpt-4o-mini`), **Anthropic Claude** (`claude-3-5-sonnet-20241022`), **xAI Grok** (`grok-2-latest`), optional **Model Version Override**, or **Local / Custom (Ollama)** (`llama3`). | Supports multi-key rotation for cloud quotas—or run 100% offline and free with Ollama. |

---

## 🚀 Quick Start: How to Run Skippy

Choose your computer's operating system below. You don't need programming experience—everything is automated.

### 🪟 Option A: Windows (Easiest!)
*No programming knowledge required—you don't even need Python installed.*

1. **Download & Unzip:** Download `Skippy-Windows.zip` and extract the folder to your computer (like your Desktop or Documents folder).
2. **Launch:** Double-click **`skippy.bat`**.
3. **Sit back:** On your first run, a command window will appear and automatically install everything Skippy needs. After 1–2 minutes, Skippy opens automatically in your browser at `http://localhost:8501`.

> 💡 **Keep in mind:** Leave the command window open (or minimized to your taskbar) while using Skippy. Close it whenever you're ready to shut Skippy down.

---

### 🍎 Option B: Mac
*Works on modern Macs (Apple Silicon M1/M2/M3/M4 or Intel).*

1. **Download & Unzip:** Download `Skippy-Unix.zip` and extract it to a folder.
2. **One-Click Launch:** Double-click **`skippy.command`**.  
   *(Alternatively, open Terminal in the folder and run `./skippy.sh`.)*
3. Skippy sets up its environment, installs Chromium for web scraping, and opens `http://localhost:8501` in your browser.

> 💡 **Mac Security Note:** If macOS says *"cannot be opened because it is from an unidentified developer"*, right-click `skippy.command`, choose **Open**, and click **Open** on the prompt.

---

### 🐧 Option C: Linux
1. Open a terminal in the extracted Skippy folder.
2. Make the launch script executable and start it:
   ```bash
   chmod +x skippy.sh
   ./skippy.sh
   ```
3. Skippy builds its environment and launches your default browser automatically.

---

### 🐳 Option D: Docker (For Homelab & Advanced Users)
If you prefer Docker:
- **Windows:** Double-click `Skippy-Docker-Windows.bat`
- **Mac / Linux:** Run `./Skippy-LinuxOrMac-Docker-Launch.sh`
- To stop Skippy later: Run `docker compose down` in the folder.

---

## ⚙️ First-Time Setup (Takes 2 Minutes!)

When Skippy opens for the first time, you'll create a local password and walk through a 3-step onboarding flow:

```
+---------------------------------------------------------+
|  Login:   Secure Your Skippy Account (local password)   |
|  Step 1:  Connect Your AI Provider & Test Connection    |
|  Step 2:  Add Your Master Resume (upload or paste)      |
|  Step 3:  Choose Your Career Field & Direction          |
+---------------------------------------------------------+
```

### Login: 🛡️ Secure Your Skippy Account
Skippy starts with a quick local account setup screen where you choose an **Admin Username** and **Admin Password** (encrypted locally with PBKDF2-HMAC-SHA256).

### Step 1 of 3: Connect Your AI Provider
An **API key** lets Skippy talk to your chosen AI model:
- **Google Gemini (Recommended Cloud):** Default model `gemini-2.5-flash`
  - Go to [Google AI Studio](https://aistudio.google.com/), sign in, and click **Get API Key**.
  - Copy your key (starts with `AQ.Ab...` or `AIza...`), paste it into Skippy, and click **🧪 Test Connection**.
  - 💡 **Multi-Key Rotation:** You can paste multiple API keys separated by commas or newlines in the sidebar—Skippy automatically rotates to the next key if one hits a rate limit.
  - 💡 **Free Tier vs. Tier 1:**
    - **Free Tier ($0):** Google provides a free key with a small daily allowance (~20 requests/day on flagship models). Great for testing, though batch reviews will hit rate limits.
    - **Tier 1 ($5 One-Time Deposit — Recommended):** Adding a one-time $5 deposit in Google AI Studio billing unlocks commercial speed (**1,000+ requests/minute**). Evaluating one full job posting costs roughly **$0.0004** (~12,500 evaluations per $5). *Paid directly to Google—Skippy charges no fees.*
- **Local / Custom (Ollama) (100% Free & Offline):** Install [Ollama](https://ollama.com/), select **Local / Custom (Ollama)** in the **Select AI Provider** dropdown, and run locally (default model `llama3`) with zero costs, no API keys, and no rate limits.
- **Other Cloud Providers:** Choose **OpenAI ChatGPT** (`gpt-4o-mini`), **Anthropic Claude** (`claude-3-5-sonnet-20241022`), or **xAI Grok** (`grok-2-latest`), or set a **Model Version Override (Optional)** under **⚙️ Advanced Settings** in the sidebar.

### Step 2 of 3: Add Your Master Resume
Your **Master Resume** holds your full work history, skills, certifications, and projects:
- **Upload a file:** Drop in an existing `.docx`, `.pdf`, `.md`, or `.txt` resume.
- **Or paste directly:** Paste your resume text into the editor box.

Don't worry about keeping it to one page—Skippy pulls the strongest relevant details from your master resume when generating tailored versions for specific roles.

### Step 3 of 3: Choose Your Career Field & Direction
Skippy adapts to any profession—from skilled trades, first responders, and military transitions to healthcare, corporate, and engineering:
- **⚡ Generate Career Profile with AI:** Analyzes your master resume automatically to build a custom industry profile and scoring rubric.
- **Pick a preset track:** Choose from common career fields and click **Save Career Track & Continue ➔** (offline, zero AI calls).
- **📝 Or Take the Detailed 7-Question Career Direction Quiz:** Answer 7 quick questions to map your career interests (offline, zero AI calls).
- Or click **⏭️ Skip for Now & Launch Skippy** to configure it later from **🧭 Career Profile**.

---

## 🤖 How Skippy Uses AI (vs. Offline Tools)

Skippy keeps AI usage focused and transparent so your API budget stretches as far as possible:

- **Uses AI (calls your chosen provider or local Ollama):**
  - **Job Evaluations:** Scores postings across all 4 pillars, checks Requirements and Location gates, and extracts matching skills, missing skills, and red flags (cloud batches run up to 4 jobs in parallel in the background with a live progress banner; Ollama runs serially).
  - **Document Generation & Automatic Fact-Checking:** Generates Tailored Resumes, Cover Letters, Application Answers, Interview Prep, Follow-Up Notes, Outreach Messages, and Company Research Guides—and automatically runs a grounding audit on tailored resumes and cover letters.
  - **Opt-In AI Helpers:** **🧠 Deep Analysis with AI** (Career Profile), **🧠 AI Content Polish** (Resume Library), and **🎓 Personalized Learning & Study Plan Generator** (Skills & Insights).
- **100% Offline & Deterministic (zero AI calls):**
  - Live job discovery (**LinkedIn**, **Greenhouse**, **Ashby**, **Lever**, **FreeHire**), browser extension capture, **Job Text Safety Shield** (`posting_guard`), repeated-listing / ghost-job detection, **ATS Health Score** & **✨ Smart Auto-Fix Formatting**, **⚡ Quick Re-Detect (Regex / Instant)** career profiling, **Application Tracker**, and `.docx`/`.pdf` exports.

---

## 🧭 Tour of Skippy: Sidebar Workspaces

Once you finish onboarding, all 9 workspaces are in the left sidebar (alongside **🔌 LLM Configuration**, **Prompt Mode**, **❓ Help & Setup**, and **🛡️ Account & Password**):

### 1. 🔍 Job Search
Your starting point for finding and queuing jobs across four intake modes:
- **🔎 Job Board Search:** Opens **🔎 LinkedIn Search** (public guest search, zero login required) with **⚙️ Advanced Search Portals (Company Career Pages & FreeHire)** tucked neatly below for **Greenhouse**, **Ashby**, **Lever**, and **FreeHire**. Discovered listings accumulate in your **Saved Search Queue** (**📋 Discovered Postings**) so you can combine multiple searches, filter by **🆕 New Only** / **All Postings** / **👁️ Seen** / **✅ Evaluated**, review top or selected postings in the background, or click **🗑️ Clear** to reset the queue.
- **📝 Paste Job Text:** Paste any job description directly. Automatically sanitized by the **Job Text Safety Shield** before evaluation.
- **🌐 Paste Multiple Links:** Paste individual job URLs (one per line) from LinkedIn, Built In, or company career pages to evaluate them back-to-back in the background.
- **🧭 Search by Category:** Quick-fill category search links across Healthcare / Biotech, Operations & HR, Data & Analytics, Cybersecurity, Software Engineering, and Cloud & DevOps.

### 2. 🔗 Extension Inbox
A holding queue for postings captured while browsing LinkedIn (nested right under **🔍 Job Search** with a live unread count):
- Right-click any LinkedIn job posting with the **Skippy Job Catcher** extension and choose **⚡ Send Listing to Skippy**.
- Click **🚀 Review All Inbox Jobs** to evaluate queued jobs in the background (with an animated live progress banner across every page), or remove postings you want to skip.
- Includes the **📦 Download Extension (.zip)** button and your local **🔑 Extension Auth Token (Required by Skippy Job Catcher v1.4+)**.

### 3. 📁 Evaluations
Your local job evaluation workspace:
- **📋 Active Postings & 🗄️ Archived Views:** Switch between active postings and archived postings, filter by keyword, source, fit band, or evaluation date, and optionally toggle **Show 4-Pillar Breakdown in Table**.
- **📊 Match Score Breakdown:** Displays **🛠️ Skills & Tools (30%)**, **📈 Experience Match (25%)**, **🤝 Work Style & Team (15%)**, and **🎯 Career Goals (30%)**, plus **Requirements** and **Location** gates, repeated-listing signals, and **🚨 Red Flags & Dealbreakers**.
- **Smart Cleanup Tools:** Delete individual postings or bulk-clean low-scoring, disqualified, or rejected roles while automatically protecting active applications and saved documents.
- **8 Workspace Tabs per Posting:**
  - **Overview & Fit:** Match breakdown, summary, matching/missing skills, red flags, and application status.
  - **⚡ Tailored Resume:** Re-targets your bullets for the role with 3 templates (**Standard ATS**, **Harvard Style**, **Modern Slate**), **🔀 Live Split View** Markdown editor, **💾 Apply Changes**, and **📥 Download ATS (.docx)** / **📕 Prepare ATS PDF**.
  - **✉️ Cover Letter:** Grounded 3-paragraph cover letter tailored to the role.
  - **📋 Application Answers:** Concise, character-counted responses for online application questions.
  - **🎤 Interview Prep:** Tailored interview questions with structured STAR answers and honest talking points for skill gaps.
  - **📬 Follow-Up Notes:** Professional post-application and post-interview follow-ups.
  - **🎯 Outreach Messages:** Short LinkedIn connection notes and direct outreach emails.
  - **🏢 Company Research Guide:** Overview covering company focus, tools, culture, and interview talking points.
- **🛡️ Accuracy & Fact-Check Grounding Report:** Generated automatically for every Tailored Resume and Cover Letter and displayed in an expandable report beneath each draft.

### 4. 🖼️ Saved Documents
A searchable library for every document you've generated:
- **Search & Filter:** Filter by job title, company, document type, or fit score, and click **🔍 Jump to Posting Details ➔** to open that job's full workspace in **📁 Evaluations**.
- **📄 Document Viewer Modal:** Edit Markdown in **🔀 Live Split View** or **✏️ Edit Markdown**, switch ATS templates (**Standard ATS**, **Harvard Style**, **Modern Professional / Slate**), click **💾 Apply Changes** to save and refresh the preview in place, inspect the **🛡️ Accuracy & Fact-Check Grounding Report**, and download `.docx` or on-demand `.pdf`.

### 5. 🌊 Application Tracker
A visual pipeline tracking your active job search:
- **Interactive Sankey Funnel:** Displays active (non-archived) evaluated postings across every stage (**Step 1: Qualified** ➔ **Step 2: Applied** ➔ **Step 3: Screening** ➔ **Step 4: Interviews & Offers**). Click any stage box or connecting branch on the chart to filter and **auto-scroll** directly to the matching postings below (click again or double-click to reset).
- **📊 Application Progress & Stats:** Tracks **Active Applications**, **Application Rate**, **Interview Rate**, and **Job Offer Rate**, plus a **⏳ Mark Inactive After (Days)** slider (default 14 days).
- **⏱️ Employer Response Times:** Measures **Avg. Days to Interview**, **Avg. Days to Rejection**, and **No Response After 14+ Days**.
- **🔍 View by Stage & Update Status:** Paginated stage explorer (20 postings per page for large stages) with **Select Stage to View** (including **🗄️ Archived**), 1-click **Heard back: Interview ➔**, direct status updates, and **🔍 Jump to Posting ➔** to open the full card in **📁 Evaluations**.

### 6. 📊 Skills & Insights
Market intelligence and study guidance built from your evaluated postings (**📊 Skills & Market Insights**):
- **Eligible Alignment & Skill Trends:** Shows your **Average Alignment Score** across eligible matches, top matching skills, most requested missing skills, and **🚨 Common Job Hurdles & Warnings** grouped by category.
- **🎓 Personalized Learning & Study Plan Generator:** Turns recurring skill gaps from near-fit roles into an actionable study plan with practice projects and free learning resources.

### 7. 📄 Resume Library
Your multi-resume vault (**📄 Resume Library & ATS Editor**):
- **Manage Multiple Resumes:** Upload (`.docx`, `.pdf`, `.md`, `.txt`), edit side-by-side with **📄 Live ATS Template Preview**, save changes or create new resume profiles, and download formatted ATS `.docx` files.
- **🛡️ Check Resume Formatting & Scanner Compatibility:** Offline **ATS Health Score** audit catching formatting mistakes and problematic symbols, with 1-click **✨ Smart Auto-Fix Formatting** (zero AI calls) and opt-in **🧠 AI Content Polish**.
- **⚙️ Advanced AI Prompt Instructions & Presets:** Collapsed expander where power users can customize evaluation instructions and manage saved prompt presets.

### 8. 🧭 Career Profile
Tailors Skippy's scoring rubric, keywords, and search suggestions to your profession (**🧭 Career Profile & Direction**):
- **Works for Any Trade or Profession:** Covers 14 domain vectors including First Responders, Military & Defense, Public Sector / Civil Service, Skilled Trades, Manufacturing, Logistics & Transportation, Healthcare & Clinical Care, Corporate, Legal, HR, Finance, Tech, and Cyber.
- **Instant or AI Profiling:** Re-scan your resume anytime with **⚡ Quick Re-Detect (Regex / Instant)** (offline) or **🧠 Deep Analysis with AI**.
- **Interactive Controls:** View your radar chart, click **🔍 Recommended Job Titles & Scraper Quick-Launch** chips to search immediately, add or remove skills under **✏️ Customize Your Career Profile & Skills**, tune weights under **🎚️ Fine-Tune Your Career Interests (Sliders)**, retake **📝 Retake the 7 Career Direction Questions**, or inspect **📜 View Industry Evaluation Prompt**.

### 9. 👋 About Skippy
Quick reference covering how Skippy works, local-first privacy guarantees, and key highlights.

---

## 🧩 Installing the Browser Extension (Skippy Job Catcher v1.4)

Send LinkedIn job listings straight into Skippy with a right-click in **Chromium-based** (**Chrome**, **Brave**, **Edge**, **Vivaldi**) or **Firefox-based** (**Firefox**, **Zen**, **LibreWolf**, **Waterfox**) browsers:

1. In Skippy, open **🔗 Extension Inbox** in the left sidebar.
2. Click **📦 Download Extension (.zip)**.
3. Unzip the file to get a folder named `skippy-extension` *(keep it in a permanent folder like your Skippy directory so cleanup tools don't remove it)*.
4. **Chromium Browsers (Chrome, Brave, Edge, Vivaldi):**
   - Open `chrome://extensions` (or `edge://extensions` / `vivaldi://extensions`).
   - Turn on **Developer mode** (top-right), click **Load unpacked**, and select the `skippy-extension` folder.
5. **Firefox Browsers (Firefox, Zen, LibreWolf, Waterfox):**
   - Open `about:debugging#/runtime/this-firefox`.
   - Click **Load Temporary Add-on...** and select `manifest.json` inside the `skippy-extension` folder.
6. **Authorize the Extension (One Time):** Click the **Skippy Job Catcher** icon in your browser toolbar, copy your **Extension Auth Token** from **🔗 Extension Inbox**, paste it in the popup, and click **Save Token**.
7. **Capture Jobs:** Open any job on [LinkedIn](https://www.linkedin.com/jobs), right-click on the job details pane, and select **⚡ Send Listing to Skippy**. It appears directly in **🔗 Extension Inbox**.

---

## 🔒 Privacy & Safety: Why Skippy is Different

Most job-search platforms ask you to upload your resume to their cloud servers, charge monthly subscriptions, and track your activity. Skippy is built differently:

- 🏠 **Local-First:** Runs locally on `localhost` (`127.0.0.1`). Your SQLite database (`skippy.db`), resumes, and settings stay on your hard drive.
- 🔒 **Local Password Protection:** Protected by a PBKDF2-HMAC-SHA256 hashed local password with automatic brute-force lockout protection.
- 🔑 **Authenticated Local Webhook:** Your browser extension communicates only with `127.0.0.1:8000` using a per-install random `X-Skippy-Token` stored in `.env`.
- 🛡️ **Job Text Safety Shield:** Deterministically removes hidden HTML, invisible Unicode characters, and prompt-injection lines before untrusted job descriptions reach your AI.
- 🔐 **Private API Keys:** Stored locally in your `.env` file (`0600` permissions) and sent only to the AI provider you select.

---

## ❓ Frequently Asked Questions (FAQ)

<details>
<summary><b>Do I have to leave the command window open?</b></summary>
Yes. That window runs Skippy's local Streamlit server and extension listener on your computer. You can minimize it while you work and close it when you're done.
</details>

<details>
<summary><b>Does Skippy cost anything? Is it really free?</b></summary>
Skippy itself is 100% free and open-source software with zero subscriptions, paywalls, or hidden fees.

Your choice of AI determines API costs:
- **Local / Custom (Ollama):** 100% free and offline on your own hardware with no API keys or rate limits.
- **Google Gemini (Recommended Cloud):** Offers a free tier (~20 requests/day), or a one-time $5 deposit in Google AI Studio to unlock Tier 1 speed (1,000+ requests/min). At roughly $0.0004 per evaluation, $5 covers ~12,500 full job evaluations.
- **OpenAI ChatGPT / Anthropic Claude / xAI Grok:** Standard pay-as-you-go rates on your own provider account.
</details>

<details>
<summary><b>Can I edit and download documents as PDF as well as Word?</b></summary>
Yes. You can edit generated resumes side-by-side in <b>🔀 Live Split View</b> inside <b>📁 Evaluations</b> and <b>🖼️ Saved Documents</b>, switch between <b>Standard ATS</b>, <b>Harvard Style</b>, and <b>Modern Slate</b> templates, and click <b>💾 Apply Changes</b> to save to SQLite. Word (<code>.docx</code>) downloads work everywhere, and on-demand PDF (<code>.pdf</code>) conversion via <b>📕 Prepare ATS PDF</b> is enabled automatically whenever LibreOffice (<code>soffice</code>) is installed locally.
</details>

<details>
<summary><b>Why did a job get a 0 score or show as Disqualified?</b></summary>
Open the job's <b>Overview & Fit</b> tab in <b>📁 Evaluations</b> and check the <b>❌ DISQUALIFIED</b> notice (and the <b>Requirements</b> / <b>Location</b> gates). This means the AI spotted a hard dealbreaker such as a required security clearance, mandatory license, or non-negotiable relocation requirement.
</details>

<details>
<summary><b>Why does Saved Search Queue show a different count than Evaluations?</b></summary>
<b>Saved Search Queue</b> on <b>🔍 Job Search</b> counts accumulated postings from your job board searches until you click <b>🗑️ Clear</b>. <b>📁 Evaluations</b> shows all evaluated postings across every intake source (Job Search, Extension Inbox, Paste Job Text, and Paste Multiple Links), split cleanly between <b>📋 Active Postings</b> and <b>🗄️ Archived</b>.
</details>

<details>
<summary><b>Where are my saved jobs, resumes, and settings stored?</b></summary>
Right inside your Skippy folder:
- <code>skippy.db</code> — SQLite database holding evaluations, application statuses, generated documents, search queue, and hashed login credentials
- <code>resumes.json</code> &amp; <code>resume.md</code> — your Resume Library and master resume
- <code>profile_alignment.json</code> — your Career Profile backup
- <code>prompt_presets.json</code> — saved custom prompt presets (seeded from <code>prompt_presets.template.json</code>)
- <code>inbox.json</code> — pending jobs captured by the browser extension
- <code>app_settings.json</code> &amp; <code>.env</code> — local app preferences, API keys, and webhook auth token
</details>

---

Enjoying Skippy? Star the repository and share it with friends tackling the job hunt!
