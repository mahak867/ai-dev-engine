#!/usr/bin/env python3
"""APEX Personal AI Desktop — launch script"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("PYTHONUTF8", "1")
from core.ai.apex_desktop import main
main()
