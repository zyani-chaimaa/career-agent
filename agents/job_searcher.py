import json
import anthropic
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import box
from config import ANTHROPIC_API_KEY, MODEL, RESUME_PATH
from database import init_db, save_job, create_application
from tools.search import search_duckduckgo, fetch_page_text, get_remoteok_jobs

console = Console()

_TAGS_BY_ROLE = {
    "data scientist": ["data-science", "machine-learning", "python", "statistics", "analytics"],
    "ml engineer": ["machine-learning", "mlops", "deep-learning", "python", "pytorch"],
    "ai engineer": ["ai", "machine-learning", "llm", "python", "deep-learning"],
    "data engineer": ["data-engineering", "python", "sql", "spark", "airflow"],
    "nlp engineer": ["nlp", "machine-learning", "python", "deep-learning", "transformers"],
    "research scientist": ["machine-learning", "deep-learning", "research", "python", "pytorch"],
}

SYSTEM_PROMPT = """You are a job search analyst specializing in Data/AI/ML roles.
Given a list of raw job postings and the user's resume, your task is to:
1. Filter out irrelevant, duplicate, or low-quality listings
2. Extract structured information for each valid job
3. Score each job 1-10 for fit based on the resume (skills match, seniority, domain)
4. Return ONLY a JSON object — no prose, no markdown fences

Output format:
{
  "jobs": [
    {
      "title": "...",
      "company": "...",
      "location": "...",
      "url": "...",
      "salary_range": "..." or null,
      "job_type": "full-time" | "contract" | "part-time" | null,
      "skills": ["Python", "PyTorch", ...],
      "fit_score": 7,
      "fit_notes": "Strong ML skills match; requires AWS experience candidate may lack",
      "description": "2-3 sentence summary of the role",
      "source": "..."
    }
  ]
}"""


class JobSearchAgent:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        init_db()

    def run(self, role: str, location: str, max_results: int):
        resume = RESUME_PATH.read_text(encoding="utf-8")
        raw_jobs = self._collect_raw_jobs(role, location)

        if not raw_jobs:
            console.print("[yellow]No raw results found. Try a different role or location.[/yellow]")
            return

        console.print(f"[dim]Collected {len(raw_jobs)} raw listings. Scoring with Claude...[/dim]")
        scored = self._score_jobs(raw_jobs, resume, role, max_results)

        saved = 0
        for job in scored:
            jid = save_job(job)
            if jid > 0:
                create_application(jid)
                saved += 1

        self._display_results(scored)
        console.print(f"\n[green]{saved} jobs saved.[/green] Run [bold]hunt apply <id>[/bold] to generate your application.")

    def _collect_raw_jobs(self, role: str, location: str) -> list[dict]:
        raw = []

        with Progress(SpinnerColumn(), TextColumn("[cyan]{task.description}"), transient=True) as p:
            t = p.add_task("Searching RemoteOK...", total=None)
            tags = self._role_to_tags(role)
            remoteok = get_remoteok_jobs(tags, max_results=25)
            raw.extend(remoteok)
            p.update(t, description=f"RemoteOK: {len(remoteok)} results")

            p.update(t, description="Searching the web...")
            loc_str = "remote" if location.lower() == "remote" else location
            queries = [
                f"{role} jobs {loc_str} 2025 site:linkedin.com OR site:greenhouse.io OR site:lever.co",
                f'"{role}" job posting {loc_str} -site:indeed.com',
            ]
            for q in queries:
                results = search_duckduckgo(q, max_results=10)
                for r in results:
                    raw.append({
                        "title": r["title"],
                        "company": "",
                        "location": location,
                        "url": r["url"],
                        "description": r["snippet"],
                        "source": "web",
                    })

        return raw

    def _score_jobs(self, raw_jobs: list[dict], resume: str, role: str, max_results: int) -> list[dict]:
        jobs_text = json.dumps(raw_jobs[:40], indent=2)

        with Progress(SpinnerColumn(), TextColumn("[cyan]Claude is analyzing fit..."), transient=True) as p:
            p.add_task("", total=None)
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"## Resume\n{resume}",
                            "cache_control": {"type": "ephemeral"},
                        },
                        {
                            "type": "text",
                            "text": (
                                f"## Target Role\n{role}\n\n"
                                f"## Raw Job Listings (return top {max_results} by fit)\n{jobs_text}"
                            ),
                        },
                    ],
                }],
            )

        try:
            data = json.loads(response.content[0].text)
            return data.get("jobs", [])[:max_results]
        except (json.JSONDecodeError, IndexError, KeyError):
            console.print("[red]Could not parse Claude's response. Raw output saved to debug.json[/red]")
            with open("debug.json", "w") as f:
                f.write(response.content[0].text if response.content else "")
            return []

    def _role_to_tags(self, role: str) -> list[str]:
        role_lower = role.lower()
        for key, tags in _TAGS_BY_ROLE.items():
            if key in role_lower or any(w in role_lower for w in key.split()):
                return tags
        return ["machine-learning", "python", "data-science", "ai"]

    def _display_results(self, jobs: list[dict]):
        if not jobs:
            console.print("[yellow]No suitable jobs found.[/yellow]")
            return

        table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan", title="Discovered Jobs")
        table.add_column("Score", width=6, justify="center")
        table.add_column("Title", min_width=28)
        table.add_column("Company", min_width=18)
        table.add_column("Location", min_width=14)
        table.add_column("Salary", min_width=14)
        table.add_column("Notes", min_width=30)

        for job in jobs:
            score = job.get("fit_score", 0)
            score_str = f"[green]{score}[/green]" if score >= 7 else (f"[yellow]{score}[/yellow]" if score >= 5 else f"[red]{score}[/red]")
            notes = (job.get("fit_notes") or "")[:60]
            table.add_row(
                score_str, job.get("title", ""), job.get("company", ""),
                job.get("location", ""), job.get("salary_range") or "—", notes,
            )

        console.print(table)
