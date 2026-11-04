"""Print the current v2 golden values (run after an INTENTIONAL engine or rules change)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from farglow.engine import rules as R  # noqa: E402
from farglow.engine import state as st  # noqa: E402
from test_golden import FOUND, GOLDEN_SEED  # noqa: E402

rules = R.load()
print("rules", rules.hash)
print("found_then_48", st.replay(GOLDEN_SEED, {1: [FOUND]}, 49, rules=rules)[-1])
