#!/usr/bin/env python3
"""Aurora MCP Domain Server: cloud"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hub import serve_stdio

if __name__ == "__main__":
    serve_stdio("cloud")
