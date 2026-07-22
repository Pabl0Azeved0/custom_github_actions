"""Guards on the shipped packaging that unit tests would otherwise never see.

The Dockerfile and the publish workflow carry security properties (non-root runtime,
immutable action refs) that are easy to lose in an unrelated edit.
"""
from __future__ import annotations

import pathlib
import re

_ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_dockerfile_drops_root_before_entrypoint():
    lines = (_ROOT / "Dockerfile").read_text().splitlines()
    users = [i for i, line in enumerate(lines) if line.startswith("USER ")]
    entry = [i for i, line in enumerate(lines) if line.startswith("ENTRYPOINT")]
    assert users, "Dockerfile must switch away from root"
    assert lines[users[-1]].split()[1] != "root"
    assert users[-1] < entry[0]
