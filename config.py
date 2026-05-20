import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUTS_DIR = DATA_DIR / "applications"

DATA_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = os.getenv("JOB_HUNTER_MODEL", "claude-sonnet-4-6")
DB_PATH = DATA_DIR / "jobs.db"
RESUME_PATH = DATA_DIR / "resume.txt"
