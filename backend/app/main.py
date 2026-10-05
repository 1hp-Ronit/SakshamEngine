"""FastAPI app factory. One process serves API, /mock/* services and (if built) the frontend."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.core.database import create_all
from app.core.errors import install_error_handlers
from app.core.logging import get_logger, setup_logging

log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    setup_logging(s.env.log_level)
    await create_all()
    try:
        from app.services.scoring import get_scoring_service

        import asyncio

        from app.services.explainability import get_explainer

        def warm() -> str:  # first SHAP call JIT-compiles; do it now, not during someone's first application
            import pandas as pd

            from app.services.feature_pipeline import FEATURE_NAMES

            svc = get_scoring_service()
            get_explainer().explain(pd.Series(0.0, index=FEATURE_NAMES))
            return svc.model_version

        log.info("Model loaded and warmed: %s", await asyncio.to_thread(warm))
    except Exception as exc:  # noqa: BLE001
        log.warning("Model not loaded (%s). Run `make train`.", getattr(exc, "message", type(exc).__name__))
    log.info("Saksham Engine started (messaging_mode=%s, policy=%s)", s.env.messaging_mode, s.policy.policy_version)
    yield
    from app.core.http import close_http_client

    await close_http_client()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Saksham Engine", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.env.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)

    @app.get("/health", tags=["meta"])
    async def health():
        return {"status": "ok"}

    _register_routers(app)
    _mount_frontend(app, Path(s.env.frontend_dist_dir))
    return app


def _register_routers(app: FastAPI) -> None:
    from app.api import applications, consent, demo, lms, messages, webhooks
    from app.mock_services.routers import router as mock_router

    for r in (applications.router, consent.router, lms.router, messages.router, webhooks.router, demo.router, mock_router):
        app.include_router(r)


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    """Single-origin mode: serve the built SPA (with history-API fallback) when frontend/dist exists."""
    index = dist / "index.html"
    if not index.exists():
        return
    api_prefixes = ("api/", "mock/", "webhooks/", "demo/", "health")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        if path.startswith(api_prefixes):
            from app.core.errors import AppError
            raise AppError("NOT_FOUND", "Not found", 404)
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
