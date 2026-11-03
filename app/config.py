from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def _rooted_path(env_name: str, default: str) -> Path:
    value = Path(os.getenv(env_name, default))
    return value if value.is_absolute() else ROOT_DIR / value


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001").strip()
GEMINI_EMBEDDING_DIMENSIONS = int(os.getenv("GEMINI_EMBEDDING_DIMENSIONS", "768"))
DATABASE_PATH = _rooted_path("DATABASE_PATH", "data/copilot.db")
CHROMA_PATH = _rooted_path("CHROMA_PATH", "data/chroma")
POLICY_PATH = _rooted_path("POLICY_PATH", "data/policies")
FRONTEND_PATH = ROOT_DIR / "frontend"
