"""Put the skill directory on the import path, as running lint_prose.py as a script does."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
