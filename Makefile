.PHONY: setup test migrate daily dashboard api
setup:
	python -m pip install -e ".[dev]"
migrate:
	python -m alembic upgrade head
test:
	python -m pytest
daily:
	python -m app.jobs.daily
dashboard:
	python -m streamlit run dashboard/Home.py --server.address 127.0.0.1
api:
	python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
