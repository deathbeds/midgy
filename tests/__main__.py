from pathlib import Path
from tomli import loads

ROOT = Path(__file__).parent

cases = loads((ROOT / "test_indented_code.toml").read_text())

print(cases)