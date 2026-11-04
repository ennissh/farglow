"""scripts/versions.py: pushed build numbers are always new and higher."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("versions", Path(__file__).resolve().parents[2] / "scripts/versions.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def test_first_build_of_a_release_is_1():
    assert v.next_build("0.0.0", []) == (True, "0.0.0-1")
    assert v.next_build("0.0.0", ["latest", "local"]) == (True, "0.0.0-1")


def test_next_build_counts_up_and_ignores_other_tags():
    assert v.next_build("0.0.0", ["0.0.0-1", "0.0.0-2", "0.0.0-2-abc123", "latest"]) == (True, "0.0.0-3")
    assert v.next_build("0.1.0", ["0.0.0-9", "0.0.0"]) == (True, "0.1.0-1")
    assert v.next_build("0.1.0", ["0.1.0", "0.1.0-4"]) == (True, "0.1.0-5")


def test_version_behind_the_registry_is_refused():
    ok, msg = v.next_build("0.0.0", ["0.1.0-2"])
    assert not ok and "bump VERSION" in msg


def test_check_refuses_existing_and_lower():
    assert v.check("0.0.0-3", ["0.0.0-2"])[0]
    assert not v.check("0.0.0-2", ["0.0.0-2"])[0]
    assert v.check("0.0.0-2", ["0.0.0-2"], replace=True)[0]
    assert not v.check("0.0.0-1", ["0.0.0-2"])[0]
    assert not v.check("0.0.0", [])[0]           # a release is not a build number


def test_release_once_only():
    assert v.release_ok("0.1.0", ["0.0.0-5"])[0]
    assert not v.release_ok("0.1.0", ["0.1.0"])[0]
    assert not v.release_ok("0.1.0", ["0.1.0-3"])[0]   # 0.1.0-3 sorts after 0.1.0: bump VERSION instead


def test_build_sh_dry_run_picks_the_next_number():
    import os
    import shutil
    import subprocess
    import pytest
    if not shutil.which("docker") or subprocess.run(["docker", "info"], capture_output=True).returncode:
        pytest.skip("needs Docker (build.sh checks it first)")
    root = Path(__file__).resolve().parents[2]
    version = (root / "VERSION").read_text().strip()
    env = dict(os.environ, FARGLOW_TEST_TAGS=f"{version}-1\n{version}-7\nlatest")
    out = subprocess.run([str(root / "build.sh"), "--dry-run"], capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr
    assert f"this push is" in out.stdout and f"{version}-8" in out.stdout
