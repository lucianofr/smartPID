"""PyInstaller entry point for the Smart PID backend daemon.

PyInstaller follows imports starting from this file to assemble the
frozen executable. Keeping it trivial makes the dependency graph easy
to reason about.
"""
from __future__ import annotations

from smart_pid_core.main import main

if __name__ == "__main__":
    main()
