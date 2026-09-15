from fastapi import FastAPI
from sqlalchemy import text

from app.config import Settings
from app.db import make_engine


def create_app(settings=None):
    settings = settings or Settings()
    api = FastAPI(title="中国公募基金研究助手", version="0.1.0")
    api.state.settings = settings
    from app.api import router

    api.include_router(router)

    @api.get("/health")
    def health():
        engine = make_engine(settings.database_url)
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return {"status": "ok", "currency": "CNY", "execution": "disabled"}
        finally:
            engine.dispose()

    return api


app = create_app()
