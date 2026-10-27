"""Entrypoint for uvicorn (`uvicorn main:app`) and for Vercel (`main:app`)."""

from europa.api import create_app

app = create_app()
