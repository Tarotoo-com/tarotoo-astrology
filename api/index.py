"""Vercel entry point: the FastAPI app served as one Python serverless function.

Vercel routes every request to this file (see vercel.json), and FastAPI handles the
paths (/health, /places, /chart) exactly as the systemd deployment does.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: E402,F401
