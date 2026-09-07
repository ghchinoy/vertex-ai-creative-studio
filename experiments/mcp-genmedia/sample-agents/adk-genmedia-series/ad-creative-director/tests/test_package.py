# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit test for the DETERMINISTIC packager — the load-bearing non-generative
contract of the storyboard/dogfood profile.

The rest of the series follows a no-unit-test convention (the agents are demoed
live), but `build_manifest`/`write_package` (package.py) are pure, non-LLM code
that produces the versioned `manifest.json` the archivist depends on, so it is
worth locking cheaply. This test is deliberately **import-light**: it loads
`package.py` directly via importlib, BYPASSING the package `__init__` (which
imports `agent`, and therefore ADK), so it runs with NO ADK / credentials / suite
binaries — exactly like the offline fixture in the validation recipe.

Runnable either way:
    pytest tests/test_package.py          # collected as test_* functions
    python tests/test_package.py          # plain-Python, prints PASS/exits non-zero
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

# Load package.py directly (no `import ad_creative_director` -> no ADK).
_PKG_PY = Path(__file__).resolve().parents[1] / "ad_creative_director" / "package.py"
_spec = importlib.util.spec_from_file_location("_pkg_under_test", _PKG_PY)
package = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(package)

# A 2-panel plan (exercises the shot-0N.png index derivation for N>1).
_PLAN = {
    "subject": "a lighthouse keeper at dawn",
    "music_mood": "hopeful, cinematic",
    "shots": [
        {"beat": "keeper wakes", "prompt": "dim room, first light"},
        {"beat": "lamp lit", "prompt": "the lens glows against the dawn"},
    ],
}


def _seed_all_artifacts(d: Path) -> None:
    """Write every expected artifact for a full 2-panel package."""
    (d / "shots").mkdir(parents=True, exist_ok=True)
    (d / "audio").mkdir(parents=True, exist_ok=True)
    (d / "shots" / "shot-01.png").write_text("x")
    (d / "shots" / "shot-02.png").write_text("x")
    (d / "audio" / "narration.wav").write_text("x")
    (d / "audio" / "music.mp3").write_text("x")
    (d / "animatic.mp4").write_text("x")


def test_all_present_verifies_true_with_exact_shot_names() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        _seed_all_artifacts(d)
        m = package.build_manifest(
            _PLAN, d, profile="storyboard", brief="b", model="gemini-3.8-flash"
        )
        assert m["artifacts_verified"] is True
        assert m["manifest_version"] == "1"
        # Exact index-derived names + all verified flags true, in order.
        assert [s["image"] for s in m["shots"]] == [
            "shots/shot-01.png",
            "shots/shot-02.png",
        ]
        assert [s["index"] for s in m["shots"]] == [1, 2]
        assert all(s["verified"] for s in m["shots"])
        assert m["audio"] == {
            "narration": "audio/narration.wav",
            "music": "audio/music.mp3",
        }
        assert m["assembled"] == "animatic.mp4"


def test_one_missing_still_verifies_false_with_correct_flags() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        _seed_all_artifacts(d)
        (d / "shots" / "shot-02.png").unlink()  # drop exactly one still
        m = package.build_manifest(
            _PLAN, d, profile="storyboard", brief="b", model="gemini-3.8-flash"
        )
        assert m["artifacts_verified"] is False
        # Per-shot flags reflect reality: panel 1 present, panel 2 missing.
        assert m["shots"][0]["verified"] is True
        assert m["shots"][1]["verified"] is False


def test_missing_audio_or_animatic_verifies_false() -> None:
    for missing in ("audio/narration.wav", "audio/music.mp3", "animatic.mp4"):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            _seed_all_artifacts(d)
            (d / missing).unlink()
            m = package.build_manifest(
                _PLAN, d, profile="storyboard", brief="b", model="gemini-3.8-flash"
            )
            assert m["artifacts_verified"] is False, missing


def test_empty_plan_never_verifies() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        # Even with the fixed audio/animatic present, an empty plan must fail.
        (d / "audio").mkdir()
        (d / "audio" / "narration.wav").write_text("x")
        (d / "audio" / "music.mp3").write_text("x")
        (d / "animatic.mp4").write_text("x")
        m = package.build_manifest(
            {"shots": []}, d, profile="storyboard", brief="b", model="m"
        )
        assert m["artifacts_verified"] is False
        assert m["shots"] == []


def test_write_package_writes_both_files_and_returns_manifest() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / "pkg"
        # No artifacts on disk -> manifest still written, artifacts_verified false.
        m = package.write_package(
            _PLAN, d, profile="storyboard", brief="b", model="gemini-3.8-flash"
        )
        assert (d / "manifest.json").is_file()
        assert (d / "plan.json").is_file()
        assert m["artifacts_verified"] is False
        # manifest.json on disk matches the returned dict; plan.json is the plan.
        on_disk = json.loads((d / "manifest.json").read_text())
        assert on_disk == m
        assert json.loads((d / "plan.json").read_text()) == _PLAN


if __name__ == "__main__":
    _tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in _tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\nALL {len(_tests)} PACKAGER TESTS PASS")
