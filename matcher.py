import os
from google import genai
from pydantic import BaseModel, Field

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Updated Schema with a hard-stop gatekeeper field
class JobMatch(BaseModel):
    is_eligible: bool = Field(description="False if the job has an absolute hard blocker (e.g., mandatory Top Secret clearance, specific citizenship) that the candidate completely lacks. True otherwise.")
    disqualification_reason: str = Field(description="If not eligible, explain the specific hard blocker. Otherwise, leave blank.")
    match_score: int = Field(description="An objective score from 0 to 100 representing overall skill alignment. Set to 0 if not eligible.")
    matching_skills: list[str] = Field(description="Key skills present in both the resume and the job description.")
    missing_skills: list[str] = Field(description="Technical gaps or missing requirements.")
    summary: str = Field(description="A concise overview explaining the fit.")

def load_file(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

def main():
    print("Reading local files...")
    # Read directly from your master resume file
    resume_text = load_file("resume.md")
    job_text = load_file("job_description.txt")

    prompt = f"""
    You are an automated job-matching engine evaluating a candidate's master resume against a job description.

    EVALUATION INSTRUCTIONS:
    1. **Hard Stop Check:** Identify if the job demands an absolute legal or compliance requirement (such as an active government security clearance, specific citizenship, or mandatory active-duty status) that is completely absent from the resume. If so, set `is_eligible` to False and `match_score` to 0.
    2. **Skill Matching:** Do not penalize the candidate for missing verbatim keywords if their technical projects or SOC experience imply competence (e.g., Linux, Wireshark, malware analysis, network configuration).
    
    RESUME:
    {resume_text}

    JOB DESCRIPTION:
    {job_text}
    """

    print("Analyzing alignment with Gemini...")
    
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": JobMatch,
        },
    )

    result: JobMatch = response.parsed

    print("\n" + "="*40)
    if not result.is_eligible:
        print(" STATUS: DISQUALIFIED (Hard Stop)")
        print(f" Reason: {result.disqualification_reason}")
    else:
        print(f" MATCH SCORE: {result.match_score}/100")
    print("="*40)
    print(f"\nSummary:\n{result.summary}")
    if result.is_eligible:
        print(f"\nMatching Skills:\n* " + "\n* ".join(result.matching_skills))
        print(f"\nMissing / Gaps:\n* " + "\n* ".join(result.missing_skills))
    print("\n" + "="*40)

if __name__ == "__main__":
    main()