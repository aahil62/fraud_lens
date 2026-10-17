"""ASGI entry point: uvicorn fraudlens.bank_simulator.main:app --port 8002."""

from fraudlens.bank_simulator.app import app, create_app

__all__ = ["app", "create_app"]
