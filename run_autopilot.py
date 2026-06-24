#!/usr/bin/env python3
"""run_autopilot.py — local development shortcut.
Delegates to autopilot.cli which is the true entry point.

For production use:  pip install autopilot-cli && autopilot
"""
from autopilot.cli import main

if __name__ == "__main__":
    main()
