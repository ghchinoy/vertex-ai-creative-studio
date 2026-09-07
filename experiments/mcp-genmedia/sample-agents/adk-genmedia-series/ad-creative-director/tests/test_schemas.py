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

"""Import-light unit test for the PR-7 QC critic schema (`QCVerdict`).

Like `test_package.py`, this loads `schemas.py` DIRECTLY via importlib, BYPASSING
the package `__init__` (which imports `agent`, and therefore ADK). `schemas.py`
imports only `pydantic`, so this runs with NO ADK / credentials / suite binaries —
it needs only `pydantic` installed (the same dependency the engine already pins).

It locks the load-bearing contract of the Editor's QC Room verdict: `acceptable`
is REQUIRED (a malformed verdict must fail LOUD, never be silently treated as a
pass), and `issues`/`correction_notes` default to empty for an accepting verdict.

Runnable either way:
    pytest tests/test_schemas.py          # collected as test_* functions
    python tests/test_schemas.py          # plain-Python, prints PASS/exits non-zero
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

# Load schemas.py directly (no `import ad_creative_director` -> no ADK).
_SCHEMAS_PY = (
    Path(__file__).resolve().parents[1] / "ad_creative_director" / "schemas.py"
)
_spec = importlib.util.spec_from_file_location("_schemas_under_test", _SCHEMAS_PY)
schemas = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(schemas)

QCVerdict = schemas.QCVerdict


def test_accepting_verdict_defaults_empty() -> None:
    v = QCVerdict(acceptable=True)
    assert v.acceptable is True
    assert v.issues == []
    assert v.correction_notes == ""


def test_failing_verdict_carries_issues_and_notes() -> None:
    v = QCVerdict(
        acceptable=False,
        issues=["final 30.10s exceeds video 20.00s by 10.10s (> 1.0s)"],
        correction_notes=(
            "re-run trim_audio_to_video_length on the mixed audio against the "
            "video, then re-combine and re-verify"
        ),
    )
    assert v.acceptable is False
    assert len(v.issues) == 1
    assert "trim_audio_to_video_length" in v.correction_notes


def test_acceptable_is_required_fails_loud() -> None:
    # A verdict without `acceptable` must NOT validate — it must never be silently
    # treated as a pass. (pydantic raises ValidationError, a subclass of
    # ValueError; we assert on ValueError to avoid importing pydantic here.)
    raised = False
    try:
        QCVerdict(issues=["x"])  # type: ignore[call-arg]
    except ValueError:
        raised = True
    assert raised, "QCVerdict(acceptable=...) must be required"


def test_validate_json_roundtrip_matches_write_path() -> None:
    # Mirrors ADK's write path: model_validate_json(...).model_dump(). The stored
    # state value is a dict, which is what the assembler reads via {qc_verdict?}.
    v = QCVerdict.model_validate_json(
        '{"acceptable": false, "issues": ["overrun"], '
        '"correction_notes": "re-trim and re-combine"}'
    )
    dumped = v.model_dump(exclude_none=True)
    assert dumped["acceptable"] is False
    assert dumped["issues"] == ["overrun"]
    assert dumped["correction_notes"] == "re-trim and re-combine"


if __name__ == "__main__":
    _tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in _tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\nALL {len(_tests)} QCVerdict SCHEMA TESTS PASS")
