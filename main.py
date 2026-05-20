import sys
import click
from rich.console import Console
from rich.table import Table
from rich import box
from database import init_db, list_jobs, list_applications, update_application, get_job, create_application
from config import ANTHROPIC_API_KEY, RESUME_PATH

console = Console()

STATUSES = ["saved", "applied", "phone_screen", "interview", "offer", "rejected", "withdrawn"]
STATUS_COLORS = {
    "saved": "dim",
    "applied": "cyan",
    "phone_screen": "yellow",
    "interview": "blue",
    "offer": "green",
    "rejected": "red",
    "withdrawn": "dim",
}


def check_setup():
    if not ANTHROPIC_API_KEY:
        console.print("[red]ANTHROPIC_API_KEY not set.[/red] Copy .env.example to .env and add your key.")
        sys.exit(1)
    init_db()


@click.group()
def hunt():
    """career-agent — AI-powered job hunting for Data/AI/ML roles."""


@hunt.command("import-resume")
@click.argument("path", type=click.Path(exists=True))
def import_resume(path):
    """Import your resume (PDF or .txt) as the base for all tailoring."""
    from tools.search import extract_resume_text
    text = extract_resume_text(path)
    RESUME_PATH.write_text(text, encoding="utf-8")
    preview = text[:200].replace("\n", " ")
    console.print(f"[green]Resume imported[/green] ({len(text)} chars)\n[dim]{preview}...[/dim]")


@hunt.command("search")
@click.option("--role", default="data scientist", show_default=True, help="Job title to search for")
@click.option("--location", default="remote", show_default=True, help="Location or 'remote'")
@click.option("--max-results", default=10, show_default=True, help="Max jobs to surface")
def search(role, location, max_results):
    """Discover and score jobs that match your resume."""
    check_setup()
    if not RESUME_PATH.exists():
        console.print("[yellow]No resume found.[/yellow] Run: hunt import-resume <path>")
        sys.exit(1)
    from agents.job_searcher import JobSearchAgent
    agent = JobSearchAgent()
    agent.run(role=role, location=location, max_results=max_results)


@hunt.command("jobs")
@click.option("--min-score", default=0, show_default=True, help="Minimum fit score (1-10)")
def jobs(min_score):
    """List all discovered jobs."""
    check_setup()
    rows = list_jobs(min_score=min_score)
    if not rows:
        console.print("[dim]No jobs found. Run: hunt search[/dim]")
        return

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim", width=4)
    table.add_column("Score", width=6, justify="center")
    table.add_column("Title", min_width=28)
    table.add_column("Company", min_width=18)
    table.add_column("Location", min_width=14)
    table.add_column("Salary", min_width=14)

    for r in rows:
        score = r.get("fit_score") or 0
        score_str = f"[green]{score}[/green]" if score >= 7 else (f"[yellow]{score}[/yellow]" if score >= 5 else f"[red]{score}[/red]")
        table.add_row(
            str(r["id"]), score_str, r["title"], r["company"],
            r.get("location") or "—", r.get("salary_range") or "—",
        )

    console.print(table)
    console.print(f"[dim]{len(rows)} jobs | hunt apply <id> to generate your application[/dim]")


@hunt.command("apply")
@click.argument("job_id", type=int)
def apply(job_id):
    """Generate a tailored resume and cover letter for a job."""
    check_setup()
    if not RESUME_PATH.exists():
        console.print("[yellow]No resume found.[/yellow] Run: hunt import-resume <path>")
        sys.exit(1)
    job = get_job(job_id)
    if not job:
        console.print(f"[red]Job {job_id} not found.[/red] Run: hunt jobs")
        sys.exit(1)
    from agents.tailoring import TailoringAgent
    agent = TailoringAgent()
    agent.run(job)


@hunt.command("track")
def track():
    """View your full application pipeline."""
    check_setup()
    apps = list_applications()
    if not apps:
        console.print("[dim]No applications yet. Run: hunt apply <id>[/dim]")
        return

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan", title="Application Pipeline")
    table.add_column("ID", style="dim", width=4)
    table.add_column("Status", min_width=13)
    table.add_column("Title", min_width=28)
    table.add_column("Company", min_width=18)
    table.add_column("Score", width=6, justify="center")
    table.add_column("Last Updated", min_width=12)

    for a in apps:
        status = a.get("status", "saved")
        color = STATUS_COLORS.get(status, "white")
        score = a.get("fit_score") or 0
        score_str = f"[green]{score}[/green]" if score >= 7 else (f"[yellow]{score}[/yellow]" if score >= 5 else f"[dim]{score}[/dim]")
        updated = (a.get("last_updated") or "")[:10]
        table.add_row(
            str(a["job_id"]), f"[{color}]{status}[/{color}]",
            a["title"], a["company"], score_str, updated,
        )

    console.print(table)

    from collections import Counter
    counts = Counter(a["status"] for a in apps)
    summary = "  ".join(f"[{STATUS_COLORS[s]}]{s}[/{STATUS_COLORS[s]}]: {counts[s]}" for s in STATUSES if counts[s])
    console.print(f"\n[dim]Pipeline:[/dim]  {summary}")


@hunt.command("update")
@click.argument("job_id", type=int)
@click.option("--status", type=click.Choice(STATUSES), required=True, help="New application status")
@click.option("--notes", default=None, help="Optional notes to append")
def update(job_id, status, notes):
    """Update the status of an application."""
    check_setup()
    job = get_job(job_id)
    if not job:
        console.print(f"[red]Job {job_id} not found.[/red]")
        sys.exit(1)
    create_application(job_id)
    kwargs = {"status": status}
    if notes:
        kwargs["notes"] = notes
    update_application(job_id, **kwargs)
    color = STATUS_COLORS.get(status, "white")
    console.print(f"[green]Updated[/green] [{color}]{status}[/{color}] — {job['title']} @ {job['company']}")


@hunt.command("prep")
@click.argument("job_id", type=int)
def prep(job_id):
    """Generate interview prep: company brief, questions, and study plan."""
    check_setup()
    job = get_job(job_id)
    if not job:
        console.print(f"[red]Job {job_id} not found.[/red] Run: hunt jobs")
        sys.exit(1)
    from agents.interview_prep import InterviewPrepAgent
    agent = InterviewPrepAgent()
    agent.run(job)


if __name__ == "__main__":
    hunt()
