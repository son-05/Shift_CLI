#!/usr/bin/env python3
"""run_shift_cli.py — local development shortcut.
Delegates to shift_cli.cli which is the true entry point.

For production use:  pip install shift-cli && shift_cli
"""
from shift_cli.cli import main

if __name__ == "__main__":
    main()
