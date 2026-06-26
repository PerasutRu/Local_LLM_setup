"""Default on-disk paths for generated output and saved profiles."""

from pathlib import Path

DATA_DIR = Path("llm_local")
OUTPUT_DIR = DATA_DIR / "output"
PROFILES_DIR = DATA_DIR / "profiles"
