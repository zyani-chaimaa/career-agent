import requests
from bs4 import BeautifulSoup
from pathlib import Path


def extract_resume_text(path: str) -> str:
    p = Path(path)
    if p.suffix.lower() == ".pdf":
        import pdfplumber
        text_parts = []
        with pdfplumber.open(p) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        return "\n".join(text_parts)
    return p.read_text(encoding="utf-8")


def search_duckduckgo(query: str, max_results: int = 15) -> list[dict]:
    from duckduckgo_search import DDGS
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
    except Exception:
        pass
    return results


def fetch_page_text(url: str, max_chars: int = 4000) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        lines = [line.strip() for line in soup.get_text(separator="\n").splitlines() if line.strip()]
        return "\n".join(lines)[:max_chars]
    except Exception as e:
        return f"[fetch error: {e}]"


def get_remoteok_jobs(tags: list[str], max_results: int = 30) -> list[dict]:
    try:
        headers = {"User-Agent": "career-agent/1.0"}
        resp = requests.get("https://remoteok.com/api", headers=headers, timeout=15)
        resp.raise_for_status()
        all_jobs = [j for j in resp.json() if isinstance(j, dict) and "position" in j]
        tags_lower = {t.lower() for t in tags}
        matched = []
        for job in all_jobs:
            job_tags = {t.lower() for t in job.get("tags", [])}
            if job_tags & tags_lower:
                matched.append({
                    "title": job.get("position", ""),
                    "company": job.get("company", ""),
                    "location": job.get("location") or "Remote",
                    "url": job.get("url", ""),
                    "salary_range": _salary(job),
                    "skills": list(job.get("tags", [])),
                    "description": BeautifulSoup(job.get("description", ""), "html.parser").get_text()[:2000],
                    "source": "remoteok",
                })
        return matched[:max_results]
    except Exception:
        return []


def _salary(job: dict) -> str | None:
    lo, hi = job.get("salary_min"), job.get("salary_max")
    if lo and hi:
        return f"${lo:,}–${hi:,}"
    if lo:
        return f"${lo:,}+"
    return None
