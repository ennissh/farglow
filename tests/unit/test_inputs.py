"""scripts/inputs.py: an image's content hash covers exactly what its Dockerfile COPYs."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("inputs", ROOT / "scripts/inputs.py")
inp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inp)


def test_hash_is_stable_and_salted():
    assert inp.inputs_hash("api") == inp.inputs_hash("api")
    assert inp.inputs_hash("api", "linux/amd64") != inp.inputs_hash("api", "linux/amd64,linux/arm64")


def test_sources_follow_the_copy_lines():
    api = inp.copy_sources(ROOT / "containers/api/Dockerfile")
    db = inp.copy_sources(ROOT / "containers/db/Dockerfile")
    assert "farglow" in api and "config" in api and "containers/api/requirements.txt" in api
    assert all(src.startswith("containers/db/") for src in db)      # app code changes never rebuild db


def test_build_metadata_is_stamped_last_in_every_dockerfile():
    """The stamp (time, revision) changes every build: above the RUN/COPY layers it would void the cache."""
    for df in sorted((ROOT / "containers").glob("*/Dockerfile")):
        lines = [ln.strip() for ln in df.read_text().splitlines() if ln.strip() and not ln.strip().startswith("#")]
        first_arg = next(i for i, ln in enumerate(lines) if ln.startswith("ARG FARGLOW_BUILD"))
        later = lines[first_arg:]
        assert not any(ln.startswith(("RUN", "COPY", "ADD")) for ln in later), f"{df}: a RUN/COPY after the stamp"
