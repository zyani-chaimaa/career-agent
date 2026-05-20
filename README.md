# career-agent

An AI-powered job hunting agent built for Data / AI / ML roles. Automates the full pipeline — from discovering relevant jobs to tailoring your resume, tracking applications, and preparing for interviews.

## Features

- **Job Discovery** — searches job boards and remote job APIs, scored for fit against your resume
- **Resume & Cover Letter Tailoring** — rewrites your bullets and drafts a cover letter per job posting, ATS-optimized
- **Application Tracker** — SQLite-backed dashboard tracking every application through the hiring pipeline
- **Interview Prep** — company research briefs, behavioral + technical question banks, and study plans

## Quick Start

```bash
# 1. Clone and set up environment
git clone https://github.com/zyani-chaimaa/career-agent.git
cd career-agent
conda create -n job_hunter python=3.11 -y
conda activate job_hunter
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

# 3. Import your resume
python main.py import-resume path/to/your/resume.pdf

# 4. Start hunting
python main.py search --role "data scientist" --location "remote"
```

## CLI Reference

| Command | Description |
|---|---|
| `import-resume <path>` | Import your PDF or text resume |
| `search` | Discover and score jobs matching your profile |
| `jobs` | List all discovered jobs |
| `apply <job_id>` | Generate tailored resume + cover letter |
| `track` | View your full application dashboard |
| `update <job_id>` | Update application status |
| `prep <job_id>` | Generate interview prep materials |

## Project Structure

```
career-agent/
├── main.py              # CLI entry point
├── config.py            # Configuration
├── database.py          # Application tracking (SQLite)
├── agents/
│   ├── job_searcher.py  # Job discovery agent
│   ├── tailoring.py     # Resume & cover letter agent
│   └── interview_prep.py # Interview prep agent
├── tools/
│   └── search.py        # Web search & scraping utilities
└── data/                # Local data (gitignored)
    └── applications/    # Generated resumes & cover letters
```

## Requirements

- Python 3.11+
- [Anthropic API key](https://console.anthropic.com/)
- conda (recommended) or any Python virtual environment

## License

MIT
