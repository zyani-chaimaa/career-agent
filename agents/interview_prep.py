import anthropic
from rich.console import Console
from rich.rule import Rule
from config import ANTHROPIC_API_KEY, MODEL, RESUME_PATH, OUTPUTS_DIR
from tools.search import search_duckduckgo

console = Console()

SYSTEM_PROMPT = """You are a senior interview coach with deep expertise in Data/AI/ML hiring.
You help candidates prepare thoroughly for technical and behavioral interviews.
Be specific, practical, and tailored to the actual role and company — never generic.
Format your output in clean, readable markdown."""


class InterviewPrepAgent:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def run(self, job: dict):
        resume = RESUME_PATH.read_text(encoding="utf-8") if RESUME_PATH.exists() else ""
        job_id = job["id"]
        company = job["company"]
        title = job["title"]

        console.print(f"\n[bold cyan]Interview Prep:[/bold cyan] {title} @ {company}\n")

        company_intel = self._gather_company_intel(company)

        output_dir = OUTPUTS_DIR / str(job_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        prompt = self._build_prompt(job, resume, company_intel)

        console.print(Rule("[dim]Interview Prep Guide[/dim]"))
        full_output = ""
        with self.client.messages.stream(
            model=MODEL,
            max_tokens=3000,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"## My Resume\n{resume}" if resume else "## Resume\n(not provided)",
                        "cache_control": {"type": "ephemeral"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        ) as stream:
            for text in stream.text_stream:
                console.print(text, end="", markup=False)
                full_output += text

        console.print()
        out_path = output_dir / "prep.md"
        out_path.write_text(full_output, encoding="utf-8")
        console.print(f"\n[dim]Saved to data/applications/{job_id}/prep.md[/dim]")

    def _gather_company_intel(self, company: str) -> str:
        if not company:
            return ""
        console.print(f"[dim]Researching {company}...[/dim]")
        results = search_duckduckgo(f"{company} company AI data science 2024 2025", max_results=5)
        snippets = "\n".join(f"- {r['title']}: {r['snippet']}" for r in results[:4])
        return snippets

    def _build_prompt(self, job: dict, resume: str, company_intel: str) -> str:
        skills = ", ".join(job.get("skills") or [])
        return f"""## Job Posting
**{job['title']}** at **{job['company']}**
Location: {job.get('location', 'N/A')} | Salary: {job.get('salary_range') or 'N/A'}
Key Skills: {skills}

Description:
{job.get('description', '')}

## Company Intelligence (recent web search)
{company_intel or 'No results found.'}

---

Please generate a complete interview prep guide with these sections:

### 1. Company Brief
- What they do, their AI/data strategy, recent news, and culture signals
- 2-3 smart questions to ask the interviewer about the company

### 2. Behavioral Questions (STAR format)
- 5 likely behavioral questions for this role
- For each: suggest a STAR-structured talking point based on the resume

### 3. Technical Questions
- 8-10 technical questions likely to appear for this specific role and skill set
- Indicate difficulty (Easy / Medium / Hard)

### 4. Study Plan
- Priority topics to review before the interview (be specific: e.g. "gradient boosting internals", not just "ML")
- Suggested resources (papers, docs, or well-known references)

### 5. Red Flags to Address
- Based on the job requirements vs the resume, highlight any gaps to prepare answers for
"""
