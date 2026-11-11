"""API routes: demos."""
from __future__ import annotations

from fastapi import FastAPI

from app.core.errors import AppError
from app.store.db import Store


def register(app: FastAPI, store: Store) -> None:
    # ---------------- stage 7: demo library + Error Microscope ----------------
    @app.get("/api/v1/demos")
    def list_demos() -> dict:
        from app.services.demos import load_manifest
        return load_manifest()

    @app.post("/api/v1/demos/{demo_id}/run")
    def run_demo_endpoint(demo_id: str) -> dict:
        from app.services.demos import DemoError, run_demo
        try:
            return run_demo(store, demo_id)
        except DemoError as e:
            raise AppError(e.code, e.message, e.status)

    @app.post("/api/v1/demos/{demo_id}/analyze")
    def analyze_demo_endpoint(demo_id: str) -> dict:
        from app.services.demos import DemoError, analyze_demo
        try:
            return analyze_demo(store, demo_id)
        except DemoError as e:
            raise AppError(e.code, e.message, e.status)

    @app.post("/api/v1/demos/{demo_id}/optimize")
    def optimize_demo_endpoint(demo_id: str) -> dict:
        from app.services.demos import DemoError, optimize_demo
        try:
            return optimize_demo(store, demo_id)
        except DemoError as e:
            raise AppError(e.code, e.message, e.status)

    @app.get("/api/v1/demos/{demo_id}/report")
    def demo_report_endpoint(demo_id: str) -> dict:
        from app.services.demos import DemoError, demo_report
        try:
            return demo_report(store, demo_id)
        except DemoError as e:
            raise AppError(e.code, e.message, e.status)

    @app.get("/api/v1/demos/errors")
    def list_error_fixtures() -> dict:
        from app.services.demos import ERROR_MANIFEST
        return {"fixtures": ERROR_MANIFEST}

    @app.post("/api/v1/demos/errors/{fixture_id}/run")
    def run_error_fixture_endpoint(fixture_id: str) -> dict:
        from app.services.demos import DemoError, run_error_fixture
        try:
            return run_error_fixture(store, fixture_id)
        except DemoError as e:
            raise AppError(e.code, e.message, e.status)
