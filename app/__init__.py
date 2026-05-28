"""FastAPI web layer for the forensic economic calculator.

This layer never performs damages math. It builds typed inputs, calls the
engine, and renders the typed result. Requires the optional 'web' dependencies
(see pyproject.toml): pip install -e ".[web,export]"
"""
