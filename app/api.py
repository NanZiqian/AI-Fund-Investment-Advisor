import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select

from app.db import session_factory
from app.db.models import DailyRun, Instrument, Recommendation
from app.jobs.daily import run_daily
from app.portfolio import import_portfolio, portfolio_view
from app.schemas import PortfolioImport, ProfileUpdate, StrictModel

router = APIRouter()


def session(request: Request):
    with session_factory(request.app.state.settings.database_url)() as db:
        yield db


def auth(request: Request, authorization: str | None = Header(None)):
    token = request.app.state.settings.api_token.get_secret_value()
    if token and not secrets.compare_digest(authorization or "", f"Bearer {token}"):
        raise HTTPException(401, "Invalid API token")


def write_auth(request: Request, authorization: str | None = Header(None)):
    if not request.app.state.settings.api_token.get_secret_value():
        raise HTTPException(503, "请先设置 API_TOKEN 再调用写入接口；本地可使用 CLI 或仪表盘")
    auth(request, authorization)


@router.get("/portfolio", dependencies=[Depends(auth)])
def portfolio(db=Depends(session)):
    return portfolio_view(db)


@router.post("/portfolio/import", dependencies=[Depends(write_auth)])
def portfolio_import(payload: PortfolioImport, db=Depends(session)):
    record = import_portfolio(db, payload)
    db.commit()
    return {"snapshot_id": record.id, "portfolio": record.payload}


@router.get("/instruments", dependencies=[Depends(auth)])
def instruments(db=Depends(session)):
    return [
        {
            "symbol": i.symbol,
            "name": i.name,
            "category": i.category,
            "approved": i.approved,
            "confirmed": i.confirmed,
            "profile": i.profile,
        }
        for i in db.scalars(select(Instrument).order_by(Instrument.symbol))
    ]


@router.get("/instruments/{symbol}", dependencies=[Depends(auth)])
def instrument(symbol: str, db=Depends(session)):
    item = db.scalar(select(Instrument).where(Instrument.symbol == symbol))
    if item is None:
        raise HTTPException(404, "Unknown fund")
    return {
        "symbol": item.symbol,
        "name": item.name,
        "profile": item.profile,
        "source": item.source,
        "confirmed": item.confirmed,
    }


@router.put("/instruments/{symbol}/profile", dependencies=[Depends(write_auth)])
def update_profile(symbol: str, payload: ProfileUpdate, db=Depends(session)):
    item = db.scalar(select(Instrument).where(Instrument.symbol == symbol))
    if item is None:
        raise HTTPException(404, "Unknown fund")
    item.profile = payload.model_dump(mode="json")
    db.commit()
    return {"status": "saved"}


def run_view(r):
    return {
        "id": r.id,
        "started_at": r.started_at,
        "finished_at": r.finished_at,
        "status": r.status,
        "health": r.health,
        "telemetry": r.telemetry,
        "error_message": r.error_message,
    }


@router.get("/runs", dependencies=[Depends(auth)])
def runs(db=Depends(session)):
    return [
        run_view(r)
        for r in db.scalars(select(DailyRun).order_by(DailyRun.started_at.desc()).limit(100))
    ]


@router.get("/runs/{run_id}", dependencies=[Depends(auth)])
def run_detail(run_id: str, db=Depends(session)):
    item = db.get(DailyRun, run_id)
    if item is None:
        raise HTTPException(404, "Unknown run")
    return run_view(item) | {"report": item.report, "inputs": item.inputs}


class RunRequest(StrictModel):
    offline: bool = False
    refresh: bool = False


@router.post("/runs/daily", dependencies=[Depends(write_auth)])
def daily(payload: RunRequest, request: Request):
    try:
        return run_view(
            run_daily(request.app.state.settings, offline=payload.offline, refresh=payload.refresh)
        )
    except Exception:
        raise HTTPException(500, "运行失败，请查看 /runs 的错误状态") from None


@router.get("/recommendations/latest", dependencies=[Depends(auth)])
def latest(db=Depends(session)):
    run = db.scalar(
        select(DailyRun)
        .where(DailyRun.status.in_(["SUCCESS", "PARTIAL"]))
        .order_by(DailyRun.started_at.desc())
    )
    if run is None:
        return []
    return [
        r.payload | {"id": r.id, "run_id": r.daily_run_id}
        for r in db.scalars(select(Recommendation).where(Recommendation.daily_run_id == run.id))
    ]


@router.get("/recommendations/history", dependencies=[Depends(auth)])
def history(
    symbol: str | None = None,
    action: str | None = None,
    kind: str | None = None,
    db=Depends(session),
):
    query = select(Recommendation).join(Instrument)
    if symbol:
        query = query.where(Instrument.symbol == symbol)
    if action:
        query = query.where(Recommendation.action == action)
    if kind:
        query = query.where(Recommendation.recommendation_type == kind)
    return [
        r.payload | {"id": r.id, "run_id": r.daily_run_id}
        for r in db.scalars(query.order_by(Recommendation.created_at.desc()).limit(1000))
    ]


@router.get("/performance", dependencies=[Depends(auth)])
def performance(db=Depends(session)):
    from app.outcomes import evaluate

    return evaluate(db)
