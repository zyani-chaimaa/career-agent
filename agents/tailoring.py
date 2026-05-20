import anthropic
from pathlib import Path
from rich.console import Console
from rich.rule import Rule
from config import ANTHROPIC_API_KEY, MODEL, RESUME_PATH, OUTPUTS_DIR
from database import create_application, update_application

console = Console()

SYSTEM_PROMPT = """You are an expert resume writer and career coach specializing in Data/AI/ML roles.
Your job is to help candidates tailor their existing resume and write a compelling cover letter
for a specific job posting — maximizing ATS keyword match and human readability.

Guidelines:
- Keep the candidate's authentic voice and real experience; never invent facts
- Rewrite resume bullets to mirror the job description's language and priority order
- Lead bullets with strong action verbs and include quantified impact where possible
- For the cover letter: open with a specific hook (not "I am applying for..."), connect
  2-3 concrete achievements to the role's key needs, close with confidence
- Use the company name and role title naturally throughout the cover letter
- Format output as clean markdown with clear section headers"""


class TailoringAgent:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def run(self, job: dict):
        resume = RESUME_PATH.read_text(encoding="utf-8")
        job_id = job["id"]
        title = job["title"]
        company = job["company"]

        console.print(f"\n[bold cyan]Tailoring application for:[/bold cyan] {title} @ {company}\n")

        output_dir = OUTPUTS_DIR / str(job_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        console.print(Rule("[dim]Tailored Resume[/dim]"))
        tailored_resume = self._stream_section(resume, job, "resume")
        (output_dir / "resume.md").write_text(tailored_resume, encoding="utf-8")

        console.print(f"\n[dim]Saved to data/applications/{job_id}/resume.md[/dim]\n")

        console.print(Rule("[dim]Cover Letter[/dim]"))
        cover_letter = self._stream_section(resume, job, "cover_letter")
        (output_dir / "cover_letter.md").write_text(cover_letter, encoding="utf-8")

        console.print(f"\n[dim]Saved to data/applications/{job_id}/cover_letter.md[/dim]\n")

        create_application(job_id)
        update_application(job_id, tailored_resume=tailored_resume, cover_letter=cover_letter)

        console.print(
            f"[green]Done.[/green] Files saved in [bold]data/applications/{job_id}/[/bold]\n"
            f"Run [bold]hunt update {job_id} --status applied[/bold] when you submit."
        )

    def _stream_section(self, resume: str, job: dict, section: str) -> str:
        if section == "resume":
            task_prompt = (
                "Rewrite the candidate's resume to be optimally tailored for this job posting. "
                "Keep ALL real experience and dates — only reframe language and reorder bullets "
                "to match the job's priorities. Output the full resume in markdown."
            )
        else:
            task_prompt = (
                "Write a compelling, personalized cover letter for this job. "
                "3-4 paragraphs. Reference specific details from the job description. "
                "Output in markdown."
            )

        full_text = ""
        with self.client.messages.stream(
            model=MODEL,
            max_tokens=2048,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"## My Resume\n{resume}",
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": (
                            f"## Job Posting\n"
                            f"**{job['title']}** at **{job['company']}**\n"
                            f"Location: {job.get('location', 'N/A')}\n\n"
                            f"{job.get('description', '')}\n\n"
                            f"Skills required: {', '.join(job.get('skills') or [])}\n\n"
                            f"## Task\n{task_prompt}"
                        ),
                    },
                ],
            }],
        ) as stream:
            for text in stream.text_stream:
                console.print(text, end="", markup=False)
                full_text += text

        console.print()
        return full_text
