.PHONY: setup test migrate daily dashboard api
setup:
	uv sync --extra dev
migrate:
	uv run alembic upgrade head
test:
	uv run pytest
daily:
	uv run python -m app.jobs.daily
dashboard:
	uv run streamlit run dashboard/Home.py --server.address 127.0.0.1
api:
	uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
