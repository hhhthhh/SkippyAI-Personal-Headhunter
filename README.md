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
| 🎯 **Smart Match Scoring** | Grades job fit from 0 to 100 based on your real experience. | You immediately know which jobs are worth your time. |
| 🛑 **Dealbreaker Spotter** | Flags missing clearances, mandatory licenses, or hard blockers. | Keeps you from spending an hour applying for a job that requires a Top Secret clearance. |
| 📄 **1-Click Document Generator** | Creates custom Resumes, Cover Letters, and Interview Prep sheets. | Download ready-to-use Microsoft Word (`.docx`) files with one click. |
| 🔗 **LinkedIn Browser Extension** | Right-click any job on LinkedIn and send it straight into Skippy. | No more tedious copy-pasting between tabs. |
| 📊 **Skill Insights & Analytics** | Visual charts showing what skills employers are asking for most. | See exactly what skills you should learn next to level up your resume. |
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

### 1. 🔍 Scraper
Your command center for feeding job descriptions to the AI:
- **Paste a Job Description:** Found a cool job on a company website or job board? Copy the job posting text, paste it here, and hit Evaluate.
- **Multi-URL Posting:** Have a list of direct job links from supported sites? Drop them in to evaluate them back-to-back.
- **Universal Search:** Search verified tech boards like Built In (`builtin.com`) by role title and location to scrape and score multiple jobs in a batch!

### 2. 🔗 LinkedIn Evaluator (Superpower!)
Browse jobs on LinkedIn like you normally do, and send them straight into Skippy with one click:
- Check out the **Connect the LinkedIn Extension** box on this page to download the helper extension.
- Jobs you send will line up in your inbox ready to be evaluated in bulk!

### 3. 📁 History & Document Gallery
Every job you evaluate is saved here permanently in your local database (`skippy.db`):
- **Overview Table:** See positions, scores, application status, and dates at a glance.
- **Status Badges:** Tag jobs as *Not Applied*, *Applied*, *Interviewing*, *Waitlisted*, *Rejected*, or *Offer*.
- **Generate Custom Materials:** Click into any job to generate:
  - 📝 **Tailored Resume:** Rewrites your bullet points to emphasize what that employer cares about.
  - ✉️ **Cover Letter:** A friendly, authentic letter explaining why you're a great fit.
  - 🎤 **Interview Prep:** Gives you practice questions using the proven **STAR method** (Situation, Task, Action, Result) so you ace your interview.
  - 💾 **Download Word Docs:** Click **Download (.docx)** to save real Word files straight to your computer!

### 4. 📊 Metrics
Visual graphs showing:
- **Skills That Shine:** The skills you have that employers want the most.
- **In-Demand Gaps:** The top skills mentioned in job postings that aren't on your resume yet. (A cheat sheet of what you should learn next!)
- **Common Red Flags:** Frequent warnings spotted across job postings.

### 5. ⚙️ Editors
- **Edit Master Resume:** Add new accomplishments, projects, or degrees whenever you want.
- **Edit System Prompts:** Fine-tune how strict or forgiving the AI is when scoring jobs.

---

## 🧩 Installing the LinkedIn Browser Extension

Want to send jobs from LinkedIn directly into Skippy with a right-click? Here is how to install the extension in **Chrome**, **Brave**, **Edge**, or **Vivaldi**:

1. In Skippy, click on the **LinkedIn Evaluator** tab on the left.
2. Click the purple button: **📦 Download Extension (.zip)**.
3. Unzip the downloaded file so you have a regular folder named `skippy-extension`. *(Keep this folder inside your Skippy project folder so it doesn't get accidentally deleted).*
4. In your browser's address bar, type:
   - For Chrome / Brave: `chrome://extensions`
   - For Edge: `edge://extensions`
5. In the top-right corner, turn on the toggle switch that says **Developer mode**.
6. In the top-left, click the button that says **Load unpacked**.
7. Select the `skippy-extension` folder and click **Select**.
8. **That's it!** Now go to any job on [LinkedIn](https://www.linkedin.com/jobs), right-click on the job posting, and click **⚡ Send Listing to Skippy**. It will appear right in your Skippy inbox!

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
<summary><b>Can I edit the documents after Skippy generates them?</b></summary>
Yes! When you click download, Skippy saves them as standard Microsoft Word (`.docx`) files. You can open them in Microsoft Word, Google Docs, Apple Pages, or LibreOffice and make whatever edits you like.
</details>

<details>
<summary><b>Why did a job get a 0% score?</b></summary>
If a role receives a 0 score, check the "Disqualification Reason" card. It usually means the AI detected a non-negotiable requirement (like a US Top Secret clearance, a professional license you don't hold, or a requirement to live in another country) that would prevent you from getting hired.
</details>

<details>
<summary><b>Where are my saved jobs and resumes stored?</b></summary>
Right inside your Skippy folder! Your jobs live in `skippy.db` (a standard SQLite database file), your resume lives in `resume.md`, and your settings live in `.env`.
</details>

---

## 👨‍💻 Created By

Developed with care by **Hayden Tanaka**  
*B.S. Cyber Intelligence and Security, Embry-Riddle Aeronautical University*

Enjoying Skippy? Star the repository and share it with friends who are tackling the job hunt!
