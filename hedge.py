#!/usr/bin/env python3
"""
HEDGE - Hierarchical Evolutionary Domain-Guided Engine
======================================================

"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from cli.main import cli

if __name__ == '__main__':
    cli()