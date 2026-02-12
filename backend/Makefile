.PHONY: run migrate upgrade seed test demo up reset

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

migrate:
	alembic revision --autogenerate -m "$(msg)"

upgrade:
	alembic upgrade head

seed:
	python scripts/seed_dev.py

demo: upgrade seed
	python scripts/generate_demo_data.py --seed 42 --items-per-dataset 50

# Generate 10k-item dataset and measure list/item-detail latency (run after seed + upgrade)
load-test:
	PYTHONPATH=. python scripts/load_test_large_dataset.py --items 10000

test:
	PYTHONPATH=. pytest tests/ -v

# Start Postgres only (run backend and frontend in separate terminals)
up:
	docker-compose up -d

# Drop DB, recreate schema, seed, then demo data (for a clean local state)
reset:
	alembic downgrade base || true
	alembic upgrade head
	$(MAKE) seed
	python scripts/generate_demo_data.py --seed 42 --items-per-dataset 50
