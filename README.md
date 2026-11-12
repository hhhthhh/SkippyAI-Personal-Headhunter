# 🦘 Skippy — Personal AI Headhunter

> ⚠️ **Project Status: Active Beta.** Skippy is in active development! The core scraper, AI evaluator, and document generator are fully up and running. If a weird job board gives you trouble or an AI takes a second to reply, don't worry—check the tips below!

---

## 🌟 What is Skippy?

Searching and applying for jobs can feel like an endless chore. You have to read through dozens of long job postings, figure out if you're actually qualified, and rewrite your resume and cover letter over and over again.

**Skippy does the heavy lifting for you!**

Think of Skippy as your smart, personal assistant that lives directly on your computer:
1. **Reads job descriptions in seconds** — paste in text, drop in web links, search job boards directly, or send jobs from your browser with a single right-click.
2. **Checks if you're actually a match** — compares the job description against your background and gives you an honest **Match Score from 0 to 100**.
3. **Catches dealbreakers instantly** — spots requirements like security clearances, mandatory licenses, or extreme experience requirements before you waste time applying.
4. **Writes tailored resumes & documents** — creates clean, professional Word documents (`.docx`) and PDFs (`.pdf`) tailored specifically for each role with one click.
5. **100% Private & Secure** — all your resumes, notes, search history, and API keys stay right on your computer in a local database protected by your own password. Nothing is sent to a third-party cloud or sold to advertisers.

---

## ✨ Cool Things Skippy Can Do

| Feature | What it does | Why it's awesome |
| :--- | :--- | :--- |
| 🎯 **Smart Match Scoring** | Evaluates roles across Technical Skills (30%), Experience Match (25%), Team Fit (15%), and Career Goals (30%). | Delivers an objective 0–100 score instead of a simple keyword count. |
| 🔎 **Live Job Board Search** | Search **LinkedIn** (guest mode), **Direct Company Hiring Pages** (**Greenhouse**, **Ashby**, **Lever**), and **FreeHire** with zero accounts or API keys needed. | Find and review dozens of openings in seconds without logging into job boards. |
| 🛑 **Dealbreaker Spotter** | Flags non-negotiables like security clearances, required licenses, heavy travel, or relocation upfront. | Keeps you from wasting time applying to roles with strict barriers to entry. |
| 👻 **Repost & Ghost Job Signals** | Detects postings that companies have repeatedly relisted over 14+ days. | Helps you focus on active, responsive hiring teams instead of stale listings. |
| 🌊 **Interactive Application Tracker** | Visualizes your entire pipeline from review and application to interviews and job offers. | Track response times, spot stale applications, and advance interview stages with 1 click. |
| 📄 **Tailored Documents & Portfolios** | Generates tailored resumes, cover letters, STAR interview prep guides, application answers, networking notes, and company research. | Download ready-to-use Word (`.docx`) and PDF (`.pdf`) files formatted for job scanners. |
| 🛡️ **Fact-Check Verification** | Secondary AI review checks generated documents against your real resume. | Catches mistakes and makes sure everything in your application is factually true. |
| 🗄️ **Multi-Resume Library** | Upload and manage multiple specialized resumes (`.docx`, `.pdf`, `.md`, `.txt`). | Easily target different career tracks (e.g. Help Desk vs. Security Analyst). |
| 🧹 **Smart History Cleanup** | Clean up low-scoring or rejected jobs with 1 click while protecting active applications and saved work. | Keeps your workspace tidy, and marks deleted jobs as seen so future searches skip them. |
| 🎓 **Step-by-Step Study Roadmaps** | Identifies recurring skill gaps across near-fit jobs and builds personalized study guides. | Gives you realistic practice projects and 100% free study resources to close skill gaps. |
| 🛡️ **Job Text Safety Shield** | Automatically removes hidden text, invisible symbols, and tricky formatting from untrusted job postings. | Keeps your AI evaluations accurate and safe from bad web listings. |
| 🔗 **Browser Extension** | Right-click any job on LinkedIn to capture and queue it directly into Skippy. | Works seamlessly with Chrome, Brave, Edge, Firefox, and other modern browsers. |
| 🔒 **Local Password Protection** | Keeps your job search private with a password-protected local login screen. | Your search history, notes, and resumes stay safe on your computer. |
| 🤖 **Pick Your Favorite AI** | Works with Google Gemini, OpenAI (ChatGPT), Anthropic (Claude), xAI (Grok), or Ollama. | You choose the AI you prefer—or run 100% offline and free with Ollama! |

---

## 🚀 Quick Start: How to Run Skippy

Choose your computer's operating system below. You don't need programming experience—everything is automated!

### 🪟 Option A: Windows (Easiest!)
*No programming knowledge required! You don't even need to have Python installed.*

1. **Download & Unzip:** Download `Skippy-Windows.zip` and extract the folder to your computer (like your Desktop or Documents folder).
2. **Launch:** Double-click the file named **`skippy.bat`**.
3. **Sit back:** On your first run, a friendly black window will appear and automatically download everything Skippy needs. After 1–2 minutes, Skippy will open automatically in your web browser at `http://localhost:8501`!

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
3. Skippy will build its environment and launch your default browser automatically.

---

### 🐳 Option D: Docker (For Homelab & Advanced Users)
If you love Docker and container setups:
- **Windows:** Double-click `Skippy-Docker-Windows.bat`
- **Mac / Linux:** Run `./Skippy-LinuxOrMac-Docker-Launch.sh`
- To stop Skippy later: Run `docker compose down` in the folder.

---

## ⚙️ First-Time Setup (Takes 2 Minutes!)

When Skippy opens in your browser for the first time, you'll be guided through a simple setup:

```
+---------------------------------------------------------+
|  1. Create your local password to protect your data     |
|  2. Step 1: Connect your AI Provider & test connection  |
|  3. Step 2: Add your Master Resume (file, sample, paste)|
|  4. Step 3: Choose your Career Field & Direction        |
+---------------------------------------------------------+
```

### 1. Create Your Local Password
Skippy starts with a quick login screen where you set a password. This keeps your job applications, notes, and resumes private and safe on your computer.

### 2. Step 1: Connect Your AI Provider
An **API key** is like a password that lets Skippy communicate with an AI model:
- **Recommended & Free:** **Google Gemini**
  - Go to [Google AI Studio](https://aistudio.google.com/).
  - Sign in with your Google account and click **Get API Key**.
  - Copy your key, paste it into Skippy, and click **Test Connection**! Google gives a generous free tier that works great.
- **Other Providers:** You can also use OpenAI, Anthropic (Claude), or xAI (Grok) if you already have accounts there.
- **Want 100% Free & Offline?** Install [Ollama](https://ollama.com/), select Ollama in the dropdown, and Skippy will run entirely on your own computer without touching the internet!

### 3. Step 2: Add Your Master Resume
Your **Master Resume** is your complete work history containing all your jobs, skills, certifications, and projects:
- **Drag & drop a file:** Upload your existing resume (`.docx`, `.pdf`, `.md`, or `.txt`).
- **Test-drive with a sample:** Pick one of the built-in sample resumes to test Skippy right away.
- **Or paste directly:** Copy and paste your resume text into the box.

Don't worry about keeping it under one page! Skippy will pick and choose the best parts of this master resume whenever it creates a custom version for a specific job.

### 4. Step 3: Choose Your Career Field & Direction
Skippy works for any industry—from skilled trades, first responders, and military transitions to healthcare, corporate, and engineering:
- **1-Click Auto-Detect:** Let AI read your resume and configure your career profile automatically.
- **Pick a preset track:** Choose from common fields.
- **Or take the quick assessment:** Answer 7 quick questions to help Skippy understand how you work.

---

## 🧭 Tour of Skippy: How to Use It

Once you finish onboarding, you'll find all of Skippy's tools in the left sidebar:

### 1. 🔍 Job Search
Your starting point for finding and reviewing jobs:
- **🔎 Live Job Board Search:** Search live postings on **LinkedIn** (public guest search), **Direct Company Hiring Pages** (**Greenhouse**, **Ashby**, **Lever**), and **FreeHire** by role, location, workplace type (Remote, Hybrid, On-site), and date posted—with zero accounts or login required.
- **📝 Paste a Job Description:** Copy and paste job posting text from any website. Protected automatically by the **Job Text Safety Shield** against hidden text and tricky formatting.
- **🔗 Multi-URL Search:** Paste links to job postings from supported sites to review them back-to-back.
- **🧭 Search by Category:** Quick-fill category searches across healthcare, operations, data, cybersecurity, engineering, and more.

### 2. 🔗 Extension Inbox
A dedicated holding area for jobs you find while browsing the web:
- Right-click any job on LinkedIn using Skippy's browser extension and choose **⚡ Send Listing to Skippy**.
- Captured postings line up in your inbox with a live unread counter.
- Review them with AI in the background with 1 click, or delete postings you don't want.

### 3. 📋 Search Results
A clean table to review openings found through the job board search:
- **Interactive Results Table:** Filter discovered jobs by company, role, workplace type, and status (`new`, `seen`, `evaluated`).
- **👻 Repost & Ghost Job Signals:** Alerts you when a job has been repeatedly relisted over 14+ days.
- **Batch Evaluation:** Select multiple jobs and review them with AI all at once in the background.
- **Mark as Seen:** Postings are automatically marked as seen so subsequent searches won't evaluate duplicates.

### 4. 📁 Job History
Your job search archive stored locally on your machine:
- **Daily Grouped Postings:** Organized by calendar day (*Today*, *Yesterday*, or earlier) for easy reading.
- **Match Score Breakdown:** See clear scores for Technical Skills (30%), Experience Match (25%), Team Fit (15%), and Career Goals (30%).
- **Signals Column:** Highlights repost warnings and active application statuses at a glance.
- **Smart Cleanup Tools:** Delete individual jobs, clear history, or run smart bulk cleanups (e.g. remove low scores or rejections while protecting active applications and saved documents).
- **Generate Tailored Documents:** Open any job card to create:
  - 📝 **Tailored ATS Resume:** Re-targets your bullet points to match the employer's specific requirements.
  - ✉️ **Custom Cover Letter:** An authentic, grounded 3-paragraph letter highlighting your achievements.
  - 📋 **Application Answers:** Short, character-counted responses sized for online form fields (under 140 and 280 characters).
  - 🎤 **STAR Interview Prep:** Custom interview questions with structured STAR answers and honest talking points for any skill gaps.
  - 📬 **Follow-Up Notes:** Professional outreach messages to recruiters and hiring managers.
  - 🎯 **Networking Messages:** Short LinkedIn connection notes (under 300 characters) and direct cold emails.
  - 🏢 **Company Research Guide:** Helpful overview covering what the company does, tools they use, recent news, team culture, and interview talking points.
- **🛡️ Fact-Check Audit:** Run a secondary AI check that compares generated documents against your real resume to prevent made-up details.

### 5. 🖼️ Saved Documents
A centralized library for all your generated career documents:
- **Search & Filter:** Find documents quickly by job title, company, document type, or match score.
- **In-App Editor:** Make quick edits right in your browser before saving or exporting.
- **Dual Format Downloads:** Download any document as a formatted Microsoft Word file (`.docx`) or a clean, ATS-compliant PDF (`.pdf`).

### 6. 🌊 Application Tracker
A visual chart tracking your job hunt progress:
- **Interactive Pipeline Chart:** Visualizes your entire pipeline from initial review to applications, interviews, and offers received. Drag boxes to rearrange your chart.
- **Conversion Metrics:** Track your active pipeline count, application rate, interview rate, and offer rate.
- **Response Time Tracking:** Measures average days to hear back for an interview or rejection, and highlights applications that have gone quiet (>14 days without a response).
- **1-Click Stage Updates:** Advance jobs to the next stage (e.g. *"Heard back: Interview ➔"*) with one click.

### 7. 📊 Skills & Insights
Market trends and study guidance based on the jobs you review:
- **Skill Demand & Gaps:** See the top skills companies ask for, common skill gaps in your profile, and recurring red flag requirements (like required travel or certifications).
- **🎓 Personalized Study Roadmap:** Turns common skill gaps from near-fit jobs into a step-by-step study plan with hands-on practice projects and 100% free learning resources.

### 8. ⚙️ Resumes & AI Settings
- **Multi-Resume Library:** Upload and manage multiple resume versions (`.docx`, `.pdf`, `.md`, `.txt`). Use the live split-view preview to inspect your resume.
- **🛡️ Scanner Compatibility Check:** Audits your resume for formatting mistakes, weird symbols, and readability, with a 1-click **Auto-Fix** button.
- **Prompt Presets & AI Instructions:** Customize your AI instructions and save presets for different search styles.

### 9. 🧭 Career Profile & Direction
Adapts Skippy's scoring and document generation to your exact profession:
- **Works for Any Trade or Profession:** Preconfigured for **First Responders** (Fire, EMS), **Military & Veteran Transitions** (clearances, military skills translation), **Public Sector & Civil Service**, **Skilled Trades** (Electricians, HVAC, Welding, Plumbing), **Manufacturing & Machining**, **Logistics & Transportation** (CDL-A), **Healthcare & Clinical Care** (RN, BLS/ACLS), **Corporate, Legal & Tech**, and more.
- **AI Career Profile Studio:** Enter your trade or let AI analyze your resume to automatically configure customized scoring criteria.
- **Radar Visualizer & Sliders:** Adjust your alignment weights directly with sliders to emphasize the skills that matter most to you.

### 10. 👋 About Skippy
Quick overview of Skippy, security principles, and tips for getting the best results.

---

## 🧩 Installing the Browser Extension

Want to send jobs from LinkedIn directly into Skippy with a right-click? Here is how to install the extension in **Chromium-based** (**Chrome**, **Brave**, **Edge**, **Vivaldi**) or **Firefox-based** (**Firefox**, **Zen**, **LibreWolf**, **Waterfox**) browsers:

1. In Skippy, click on the **Extension Inbox** tab on the left sidebar.
2. Click the purple button: **📦 Download Extension (.zip)**.
3. Unzip the downloaded file so you have a regular folder named `skippy-extension`. *(Keep this folder inside your Skippy project folder so it doesn't get accidentally deleted).*
4. **For Chromium Browsers (Chrome, Brave, Edge, Vivaldi):**
   - In your address bar, go to `chrome://extensions` (or `edge://extensions`).
   - Turn on the **Developer mode** toggle switch in the top-right corner.
   - Click **Load unpacked** in the top-left and select the `skippy-extension` folder.
5. **For Firefox Browsers (Firefox, Zen, LibreWolf, Waterfox):**
   - In your address bar, go to `about:debugging#/runtime/this-firefox`.
   - Click **Load Temporary Add-on...** and select the `manifest.json` file inside your `skippy-extension` folder.
6. **That's it!** Now go to any job on [LinkedIn](https://www.linkedin.com/jobs), right-click on the job posting, and click **⚡ Send Listing to Skippy**. It will appear right in your Skippy Extension Inbox!

---

## 🔒 Privacy & Safety: Why Skippy is Different

Most job-search tools ask you to upload your resume to their cloud servers, charge you monthly subscriptions, and track your data. Skippy is built differently:

- 🏠 **Local-First:** Skippy runs locally on `localhost`. Your database (`skippy.db`), resumes, and notes live safely on your hard drive.
- 🔒 **Password Protection:** Your job search data is protected by a local password on your computer.
- 🛡️ **Job Text Safety Shield:** Internet job descriptions can sometimes contain hidden text or confusing instructions. Skippy automatically cleans job text before sending it to the AI to keep reviews accurate.
- 🔑 **Private API Keys:** Your API keys are saved in your private local `.env` file and are never shared.

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
Yes! You can edit generated documents right inside Skippy using the built-in editor in <b>Saved Documents</b> and <b>Job History</b>. You can then download them as standard Microsoft Word (<code>.docx</code>) documents or clean, ATS-compliant PDFs (<code>.pdf</code>).
</details>

<details>
<summary><b>Why did a job get a 0% score?</b></summary>
If a role receives a 0 score, check the "Disqualification Reason" card. It usually means the AI detected a non-negotiable requirement (like a security clearance, a mandatory license you don't hold, or a requirement to live in another state/country) that would prevent you from getting hired.
</details>

<details>
<summary><b>Where are my saved jobs and resumes stored?</b></summary>
Right inside your Skippy folder! Your jobs and application stages live in <code>skippy.db</code> (a local SQLite database file), your resume library lives in <code>resumes.json</code> (with your initial resume in <code>resume.md</code>), your prompt presets live in <code>prompt_presets.json</code>, and your local settings live in <code>.env</code>.
</details>

---

## 👨‍💻 Created By

Developed by **Hayden Tanaka**  
*B.S. Cyber Intelligence and Security, Embry-Riddle Aeronautical University*

Enjoying Skippy? Star the repository and share it with friends who are tackling the job hunt!
