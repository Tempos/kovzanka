.PHONY: run dev test install compose-up compose-down compose-logs migrate

# Run with uv
run:
	uv run uvicorn main:app --host 0.0.0.0 --port 8000
dev:
	uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
test:
	uv run pytest
install:
	uv sync

# Docker Compose commands
up:
	docker compose up --build -d
down:
	docker compose down
logs:
	docker compose logs -f

# DB
migrate:
	uv run python migrate_sqlite_to_mysql.py