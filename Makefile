.PHONY: test backend-test frontend-build up down logs
backend-test:
	cd backend && .venv/Scripts/python.exe -m pytest -q
frontend-build:
	cd frontend && npm ci && npm run build
test: backend-test frontend-build
up:
	docker compose up --build
down:
	docker compose down
logs:
	docker compose logs -f --tail=150
