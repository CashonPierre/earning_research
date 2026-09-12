"""Fail if the API key could reach the repository.

- .env must be git-ignored.
- If MASSIVE_API_KEY is set in the environment, its value must not appear in any
  tracked or untracked non-ignored file.
- No source file may pass the key as an `apiKey=` query parameter.
"""
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _repo_files() -> list[pathlib.Path]:
    try:
        out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        return [ROOT / p for p in out.split("\n") if p]
    except Exception:
        return [p for p in ROOT.rglob("*") if p.is_file() and ".venv" not in p.parts and ".git" not in p.parts and p.name != ".env"]


def test_env_is_ignored():
    gi = (ROOT / ".gitignore").read_text()
    assert ".env" in gi.splitlines()


def test_key_value_not_in_repo():
    key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if not key:
        return  # nothing to scan for
    for p in _repo_files():
        if p.name == ".env" or p.suffix in {".parquet", ".png", ".pdf"}:
            continue
        try:
            text = p.read_text(errors="ignore")
        except Exception:
            continue
        assert key not in text, f"API key value found in {p}"


def test_no_apikey_query_param():
    for p in (ROOT / "src").rglob("*.py"):
        assert "apiKey=" not in p.read_text(), f"{p} passes the key in a URL"
