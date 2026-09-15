import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
TEXT_EXTENSIONS = {".py", ".md", ".sh", ".txt", ".yaml", ".yml"}
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
USER_PATH_RE = re.compile("/" + "Users" + r"/[^/\s]+")
QUICK_TUNNEL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.I)
DISALLOWED_BACKEND = "supabase" + ".co"


def source_files():
    for path in ROOT.rglob("*"):
        if path.resolve() == SELF:
            continue
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        if any(part in {".git", ".venv", "__pycache__"} for part in path.parts):
            continue
        yield path


class PublicHygieneTests(unittest.TestCase):
    def test_no_email_addresses_are_committed(self):
        for path in source_files():
            self.assertIsNone(EMAIL_RE.search(path.read_text(errors="ignore")),
                              str(path.relative_to(ROOT)))

    def test_no_absolute_user_home_paths_are_committed(self):
        for path in source_files():
            self.assertIsNone(USER_PATH_RE.search(path.read_text(errors="ignore")),
                              str(path.relative_to(ROOT)))

    def test_no_disallowed_backend_dependency_is_committed(self):
        for path in source_files():
            text = path.read_text(errors="ignore").lower()
            self.assertNotIn(DISALLOWED_BACKEND, text, str(path.relative_to(ROOT)))

    def test_no_live_quick_tunnel_url_is_committed(self):
        for path in source_files():
            self.assertIsNone(QUICK_TUNNEL_RE.search(path.read_text(errors="ignore")),
                              str(path.relative_to(ROOT)))


if __name__ == "__main__":
    unittest.main()
