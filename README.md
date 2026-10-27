# 🦘 Skippy — Personal AI Headhunter

> ⚠️ **Project Status: Active Beta.** Skippy is in active development! The core scraper, AI evaluator, and document generator are fully up and running. If a weird job board gives you trouble or an AI takes a second to reply, don't worry—check the tips below!

---

## 🌟 What is Skippy?

Searching and applying for jobs can feel like an endless chore. You have to read through dozens of long, boring job postings, figure out if you're even qualified, and rewrite your resume and cover letter over and over again. 

**Skippy does the heavy lifting for you!** 

Think of Skippy as your smart, personal assistant that lives directly on your computer:
1. **Reads job descriptions in seconds** — paste in text, drop in web links, or send jobs directly from LinkedIn with a single right-click.
2. **Checks if you're actually a match** — compares the job description against your skills and gives you an honest **Match Score from 0 to 100**.
3. **Catches dealbreakers instantly** — spots things like required security clearances, strict citizenship rules, or extreme years of experience so you don't waste your time applying for roles you can't take.
4. **Writes tailored resumes & cover letters** — generates clean, professional Microsoft Word documents (`.docx`) customized specifically for each role with the click of a button.
5. **100% Private & Secure** — all your resumes, notes, and API keys stay right on your computer in a local database. Nothing is sent to a third-party cloud or sold to advertisers.

---

## ✨ Cool Things Skippy Can Do

| Feature | What it does | Why it's awesome |
| :--- | :--- | :--- |
| 🎯 **Smart Score Matching** | Evaluates roles across Technical Skills (30%), Experience Match (25%), Behavioral Fit (15%), and Career Alignment (30%). | Delivers an objective, holistic 0–100 score instead of a generic keyword count. |
| 🔎 **Native Job Board Search** | Search **LinkedIn** (guest mode) and **FreeHire** directly inside Skippy without an account or API key. | Find and evaluate hundreds of roles in seconds. |
| 🛑 **Dealbreaker & Red Flag Spotter** | Categorizes non-negotioables like security clearances, mandatory licenses, relocations, or on-call rotations. | Keeps you from wasting time applying to roles with tough barriers-to-entry. |
| 🌊 **Interactive Sankey Funnel** | Visualizes your entire pipeline from evaluation and application to interviews and job offers. | Track drop-offs, flag ghosted/stale postings, and advance active interview stages with 1 click. |
| 📄 **Tailored ATS Resumes & Portfolios** | Generates tailored resumes, cover letters, STAR interview prep guides, and portal Q&A packs. | Download ready-to-use ATS-optimized Word (`.docx`) and PDF (`.pdf`) documents. |
| 🛡️ **Drafter–Reviewer Fact Audits** | Automated secondary AI audit checks generated documents against your real resume. | Eliminates hallucinations and verifies factual truth before you submit applications. |
| 🗄️ **Multi-Resume Vault** | Upload and manage multiple specialized resumes (`.docx`, `.pdf`, `.md`, `.txt`). | Target different career tracks (e.g. SOC Analyst vs. Cloud Security Engineer) with ease. |
| 🎓 **Actionable Upskill Roadmaps** | Prioritizes recurring skill gaps across near-fit roles (Score ≥ 45) into study plans. | Unlocks step-by-step roadmaps, portfolio bridge projects, and 100% free study resources. |
| 🛡️ **Posting Guard Sanitization** | Deterministically strips prompt injections, hidden HTML, and invisible Unicode traps. | Keeps your AI evaluation reliable and secure against adversarial web postings. |
| 🔗 **LinkedIn Browser Extension** | Right-click any job on LinkedIn to capture and queue it directly into Skippy. | Flexible extension fallback for 1-click capture while browsing logged in. |
| 🤖 **Pick Your Favorite AI** | Works with Google Gemini, OpenAI (ChatGPT), Anthropic (Claude), xAI (Grok), or Ollama. | You choose the AI you prefer—or run 100% offline and free with Ollama! |

---

## 🚀 Quick Start: How to Run Skippy

Choose your computer's operating system below. You don't need to be a coding wizard—everything is automated!

### 🪟 Option A: Windows (Easiest!)
*No programming knowledge required! You don't even need to have Python installed.*

1. **Download & Unzip:** Download `Skippy-Windows.zip` and extract the folder to your computer (like your Desktop or Documents folder).
2. **Launch:** Double-click the file named **`skippy.bat`**.
3. **Sit back:** On your first run, a friendly black window will appear and automatically download everything Skippy needs. After 1–2 minutes, Skippy will pop right open in your web browser!

> 💡 **Keep in mind:** Leave the black command window open (or minimized to your taskbar) while you use Skippy. When you're all done, simply close the window to shut Skippy down.

---

### 🍎 Option B: Mac
*Works on all modern Macs (Apple Silicon M1/M2/M3/M4 or Intel).*

1. **Download & Unzip:** Download `Skippy-Unix.zip` and extract it to a folder.
2. **One-Click Launch:** Double-click **`skippy.command`**.
   *(Alternatively, open Terminal, go to the folder, and run `./skippy.sh`)*.
3. Skippy will set up its environment, install Chromium for web scraping, and open `http://localhost:8501` in your browser.

> 💡 **Mac Security Note:** If macOS says *"cannot be opened because it is from an unidentified developer"*, right-click `skippy.command`, choose **Open**, and click **Open** on the prompt.

---

### 🐧 Option C: Linux
1. Open your terminal in the extracted Skippy folder.
2. Make sure the script is runnable and start it:
   ```bash
   chmod +x skippy.sh
   ./skippy.sh
   ```
3. Skippy will build its virtual environment and launch your default browser automatically.

---

### 🐳 Option D: Docker (For Homelab & Advanced Users)
If you love Docker and container setups:
- **Windows:** Double-click `Skippy-Docker-Windows.bat`
- **Mac / Linux:** Run `./Skippy-LinuxOrMac-Docker-Launch.sh`
- To stop Skippy later: Run `docker compose down` in the folder.

---

## ⚙️ First-Time Setup (Takes 2 Minutes!)

When Skippy opens in your browser for the first time, you'll see a quick welcome screen asking for two things:

```
+---------------------------------------------------------+
|  1. Select your AI Provider & enter your API Key        |
|  2. Paste your Master Resume into the text box          |
|  3. Click "Save & Unlock Skippy"                        |
+---------------------------------------------------------+
```

### 1. What is an API Key? (And how do I get one for free?)
An **API key** is like a digital library card or password that lets Skippy communicate with an AI model.

- **Recommended & Free:** **Google Gemini**
  - Go to [Google AI Studio](https://aistudio.google.com/).
  - Sign in with your Google account and click **Get API Key**.
  - Copy your key and paste it into Skippy! Google gives a generous free tier that works great.
- **Other Providers:** You can also use OpenAI, Anthropic (Claude), or xAI (Grok) if you already have accounts there.
- **Want 100% Free & Offline?** Install [Ollama](https://ollama.com/), select Ollama in the dropdown, and Skippy will run entirely on your own graphics card without touching the internet!

### 2. What is a "Master Resume"?
Your **Master Resume** is one big document containing *everything* you've ever done:
- Every job, summer gig, or internship you've held.
- Projects you've built, clubs you've joined, and volunteer work.
- All your technical skills, certifications, and awards.

Don't worry about keeping it under one page! Skippy will pick and choose the best parts of this master resume whenever it creates a custom version for a specific job.

---

## 🧭 Tour of Skippy: How to Use It

Once you finish onboarding, you'll see all of Skippy's tools in the left sidebar:

### 1. 🔍 Job Search
Your command center for sourcing and feeding job descriptions to the AI:
- **🔎 Native Job Board Search (No Login Required):** Search live postings on **LinkedIn** (public guest endpoint), **Direct Company ATS Boards** (**Greenhouse**, **Ashby**, **Lever** — zero authentication), and **FreeHire** by role, location, workplace type (Remote, Hybrid, On-site), and recency.
- **📝 Paste a Job Description:** Copy and paste raw job posting text from any job board. Protected automatically by **Job Text Safety Shield** against prompt-injections, invisible Unicode tampering, and hidden text blocks.
- **🔗 Multi-URL Search:** Paste direct job links from supported sites (LinkedIn, Built In, corporate career portals) to evaluate them back-to-back.
- **🧭 Universal Search:** Quick-fill category presets across Healthcare/Biotech, Operations/HR, Data/Analytics, Cybersecurity, Software Engineering, and Cloud.

### 2. 📋 Search Results
A dedicated curation and review hub for discovered postings:
- **Interactive Results Table:** Filter discovered jobs by company, role, workplace type, and status (`new`, `seen`, `evaluated`).
- **👻 Ghost Job & Repost Signals:** Live indicator flags requisitions repeatedly relisted over 14+ days.
- **Batch Evaluation:** Select multiple jobs or evaluate the top new postings with 1 click.
- **Mark as Seen:** Automatically or manually mark postings as seen so subsequent searches never re-evaluate duplicates.

### 3. 📥 LinkedIn Inbox
Browse LinkedIn with Skippy's browser extension while logged into your account:
- Right-click any posting on LinkedIn and choose **⚡ Send Listing to Skippy**.
- Captured postings line up in your queue ready for bulk AI evaluation with 1 click.

### 4. 📁 Job History
Your persistent job search archive stored locally in `skippy.db`:
- **Daily Grouped Postings:** Postings are neatly organized by calendar day (*Today*, *Yesterday*, or earlier) for fast review.
- **Multi-Dimensional Rubric:** View detailed breakdowns across Hard Skills / Tech (30%), Experience Match (25%), Behavioral Fit (15%), and Career Alignment (30%).
- **Ghost Job & Repost Detector:** Automatically cross-references postings across 30/60/90 days to warn when a company has repeatedly relisted stale or churned requisitions.
- **Application Latency Tracking:** Automatically tracks your application submission timeline and measures turnaround latency to interview or rejection.
- **Generate Tailored Documents:** Click into any job to produce:
  - 📝 **Tailored ATS Resume:** Re-targets your bullet points to match the employer's specific domain requirements across medicine, law, logistics, HR, finance, or tech.
  - ✉️ **Custom Cover Letter:** An authentic, grounded 3-paragraph narrative highlighting verified achievements.
  - 🎤 **STAR Interview Prep:** Custom domain and behavioral questions using the proven STAR framework with ready-made honest gap bridges.
  - 📋 **Application Q&A Pack:** Programmatically character-counted form-field responses (`<=140` and `<=280` characters) ready for online portals.
  - 📬 **Follow-Up Note:** Professional outreach messages to recruiters and hiring managers.
  - 🎯 **Outreach & Networking Notes:** Persona-tuned LinkedIn connection notes (strictly capped at `<= 300 characters` for Hiring Managers, Recruiters, and Peers) plus high-converting direct cold emails.
  - 🏢 **Deep Company Briefing Dossier:** 6-axis pre-interview intelligence covering business models, operating platforms, recent signals, operational challenges, culture, and winning interview talking points.
- **🛡️ Drafter–Reviewer Fact Audit:** Run a secondary verification pass that audits generated documents against your real resume to guarantee zero factual hallucinations.

### 5. 🖼️ Saved Documents
A dedicated centralized hub to manage all generated career documents:
- **Filter & Search:** Filter by job title, company name, document type, or alignment score.
- **Browse All Materials:** Access Tailored Resumes, Cover Letters, Application Answers, Interview Prep, Follow-Up Notes, Networking Messages, and Company Research in one place.
- **In-App Markdown Editor:** Live edit and fine-tune your materials with real-time saving to the database.
- **Dual Format Downloads:** Export ready-to-send documents as stylized Word files (`.docx`) or pixel-perfect, ATS-compliant PDFs (`.pdf`).

### 6. 🌊 Application Tracker
A dedicated pipeline conversion visualizer:
- **Interactive Sankey Diagram:** Visualizes your entire pipeline from initial discovery and evaluation to screening, active interviews, and offers received. Nodes can be dragged to customize layout.
- **Conversion KPI Badges:** Tracks Active in Pipeline count, Application Rate, Screen/Interview Rate, and Offer Conversion Rate.
- **Turnaround & Rejection Latency:** Displays average days to interview response, average days to rejection, and highlights ghosted applications (>14d without response).
- **Stale Threshold Slider:** Set customizable staleness timers (7–30 days) to automatically flag stalled applications in *Ghosted / Stale*.
- **Stage Explorer & Status Manager:** Inspect roles in any stage and advance applications with 1 click (*"Heard back: Interview ➔"*).

### 7. 📊 Skills & Insights
Comprehensive market intelligence and upskill guidance across any profession:
- **Market & Skill Intelligence:** Aggregates top matching skills across postings, highlights the most common missing skill gaps, and clusters recurring red flag themes (clinical platforms, ERP systems, licensing gates, clearance demands, or relocation).
- **🎓 Personalized Learning Plan Generator:** Weights skill gaps across near-fit roles (Score ≥ 45) and generates a personalized study roadmap complete with hands-on bridge projects, clinical/legal simulations, 100% free study resources, and downloadable `.docx` study plans.

### 8. ⚙️ Resumes & AI Settings
- **Multi-Resume Vault:** Upload, store, and manage multiple resume profiles (`.docx`, `.pdf`, `.md`, `.txt`). Use the live split-view ATS preview to inspect formatting in real time.
- **🛡️ ATS Formatting & Compatibility Linter:** Programmatically audits resumes against automated ATS parsing rules, section headers, character anomalies (like garbled Unicode dashes), and bullet length—with a 1-click **Auto-Fix** button.
- **Prompt Preset Manager:** Customize and switch evaluation system instructions and prompt presets.

### 9. 🧭 Career Profile & Direction
Skippy's intelligent, universal career orientation hub:
- **7-Question Operational Compass:** Replaces hardcoded industry tags with an engaging assessment of your real-world problem-solving instincts, shift environments, trade/field tools, and crisis troubleshooting reflexes.
- **14 Universal Career Tracks:** Purpose-built for **First Responders** (Fire, EMS/Paramedic, NIMS/ICS), **Military & Defense Operations / Veteran Transitions** (MOS/AFSC translation, Security Clearances, DD-214), **Public Sector & Civil Service** (FAR/DFARS, Civil Service Exams), **Skilled Trades** (Electricians, HVAC, Plumbing, Welding, EPA 608, Journeyman), **Manufacturing & Precision Machining** (CNC, Mastercam, ISO 9001), **Transportation & Fleet Logistics** (CDL-A, ELD, DOT, HazMat), **Healthcare & Clinical Services** (RN, BLS/ACLS, EMR), **Hospitality & Culinary**, **Protective Services**, and all digital, corporate, and tech professions.
- **Hybrid Cross-Domain Industry Profiles:** Automatically creates high-impact cross-industry profiles (e.g., *Industrial Automation & Mechatronics*, *Defense Logistics Director*, *Flight Paramedic*, *FAR/DFARS Contracting Officer*).
- **Interactive Plotly Radar Visualizer:** Inspect your multidimensional alignment distribution in real time.
- **Full-System Adaptation:** Automatically tunes your evaluation rubric (`custom_prompt.template.txt`), Scraper search presets, and document drafters to your exact industry and target role.
- **Manual Weight Sliders & 1-Click Auto-Detect:** Fine-tune your alignment percentages directly with sliders or auto-detect your profile from your master resume in 1 click.

### 10. 🌐 100% Industry & Trade Agnostic
Skippy is universally engineered for candidates across the entire workforce:
- **First Responders & Defense:** Structural/wildland fire suppression, field trauma stabilization, tactical operations, defense systems, security clearances (Secret/TS-SCI).
- **Blue-Collar & Trades:** Hands-on wiring, refrigerant handling, CNC machining, commercial truck driving (CDL-A), and warehouse distribution.
- **Public Sector & Civil Governance:** Statutory compliance, municipal administration, public policy, and government acquisition.
- **Clinical & Applied Care:** Bedside nursing, emergency triage, HIPAA privacy, and clinical protocols.
- **Corporate, Legal & Tech:** Software engineering, threat defense, corporate law, people operations, and quantitative finance.

### 11. 🦘 About Skippy
Application documentation, security overview, and quick-reference guides.
Application documentation, security overview, and quick-reference guides.

---

## 🧩 Installing the LinkedIn Browser Extension

Want to send jobs from LinkedIn directly into Skippy with a right-click? Here is how to install the extension in **Chromium-based** (**Chrome**, **Brave**, **Edge**, **Vivaldi**) or **Firefox-based** (**Firefox**, **Zen**, **LibreWolf**, **Waterfox**) browsers:

1. In Skippy, click on the **LinkedIn Evaluator** tab on the left.
2. Click the purple button: **📦 Download Extension (.zip)**.
3. Unzip the downloaded file so you have a regular folder named `skippy-extension`. *(Keep this folder inside your Skippy project folder so it doesn't get accidentally deleted).*
4. **For Chromium Browsers (Chrome, Brave, Edge, Vivaldi):**
   - In your address bar, go to `chrome://extensions` (or `edge://extensions`).
   - Turn on the **Developer mode** toggle switch in the top-right corner.
   - Click **Load unpacked** in the top-left and select the `skippy-extension` folder.
5. **For Firefox Browsers (Firefox, Zen, LibreWolf, Waterfox):**
   - In your address bar, go to `about:debugging#/runtime/this-firefox`.
   - Click **Load Temporary Add-on...** and select the `manifest.json` file inside your `skippy-extension` folder.
6. **That's it!** Now go to any job on [LinkedIn](https://www.linkedin.com/jobs), right-click on the job posting, and click **⚡ Send Listing to Skippy**. It will appear right in your Skippy inbox!

---

## 🔒 Privacy & Safety: Why Skippy is Different

Most job-search tools ask you to upload your resume to their cloud servers, charge you monthly subscriptions, and track your data. Skippy is built differently:

- 🏠 **Local-First:** Skippy runs locally on `localhost`. Your database (`skippy.db`) and resume live on your hard drive.
- 🛡️ **Prompt-Injection Defense:** Untrusted text in internet job descriptions can sometimes trick AI models into doing goofy things. Skippy wraps all job content in XML safety boundaries to keep the AI focused and accurate.
- 🔑 **Isolated Credentials:** Your API keys are kept in your private local `.env` file and never shared.

---

## ❓ Frequently Asked Questions (FAQ)

<details>
<summary><b>Do I have to leave the black command window open?</b></summary>
Yes! That window is the mini-engine running Skippy on your computer. You can minimize it to your taskbar while you work. When you're ready to shut Skippy down, just close that window.
</details>

<details>
<summary><b>Does Skippy cost anything?</b></summary>
Skippy itself is 100% free and open-source! If you use Google Gemini's free tier or Ollama, using it won't cost you a single penny. If you use paid AI keys (like OpenAI GPT-4o), evaluations typically cost less than a fraction of a cent per job.
</details>

<details>
<summary><b>Can I edit and download documents as PDF as well as Word?</b></summary>
Yes! You can edit generated documents right inside Skippy using the built-in markdown editor in the <b>Document Gallery</b> and <b>History</b>. You can then download them as standard Microsoft Word (<code>.docx</code>) documents or pixel-perfect, ATS-compliant PDFs (<code>.pdf</code>).
</details>

<details>
<summary><b>Why did a job get a 0% score?</b></summary>
If a role receives a 0 score, check the "Disqualification Reason" card. It usually means the AI detected a non-negotiable requirement (like a US Top Secret clearance, a professional license you don't hold, or a requirement to live in another country) that would prevent you from getting hired.
</details>

<details>
<summary><b>Where are my saved jobs and resumes stored?</b></summary>
Right inside your Skippy folder! Your jobs live in <code>skippy.db</code> (a local SQLite database file with WAL journal mode), your multi-resume vault lives in <code>resumes.json</code> (with your initial resume in <code>resume.md</code>), and your local settings live in <code>.env</code>.
</details>

---

## 👨‍💻 Created By

Developed by **Hayden Tanaka**  
*B.S. Cyber Intelligence and Security, Embry-Riddle Aeronautical University*

Enjoying Skippy? Star the repository and share it with friends who are tackling the job hunt!