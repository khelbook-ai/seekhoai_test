"""Walkthrough generator validation (spec 04 §1). The UI must never receive an out-of-bounds
highlight range, so _validate clamps ranges to each file's real line count and drops steps
that reference nothing usable."""
import pytest

from app.agents.generators.walkthrough import _validate


def _file(name, n):
    return {"name": name, "language": "python", "content": "\n".join(f"line{i}" for i in range(1, n + 1))}


def test_clamps_out_of_bounds_ranges():
    data = {"title": "T", "files": [_file("server.py", 10)],
            "steps": [{"title": "s1", "file": "server.py", "highlight": [[5, 99]]},   # end past EOF
                      {"title": "s2", "file": "server.py", "highlight": [[8, 3]]}]}    # reversed
    out = _validate(data)
    assert out["steps"][0]["highlight"] == [[5, 10]]        # clamped to file length
    assert out["steps"][1]["highlight"] == [[3, 8]]         # reordered


def test_unknown_file_falls_back_to_first():
    data = {"title": "T", "files": [_file("a.py", 4)],
            "steps": [{"title": "s", "file": "missing.py", "highlight": [[1, 2]]}]}
    out = _validate(data)
    assert out["steps"][0]["file"] == "a.py"


def test_requires_files_and_steps():
    with pytest.raises(ValueError):
        _validate({"files": [], "steps": []})
    with pytest.raises(ValueError):
        _validate({"files": [_file("a.py", 3)], "steps": []})
