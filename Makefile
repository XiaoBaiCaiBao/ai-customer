DEV_COMPOSE=docker compose -f docker-compose.dev.yml

.PHONY: dev-up dev-down dev-restart dev-ps dev-logs dev-check

dev-up:
	$(DEV_COMPOSE) up -d --build

dev-down:
	$(DEV_COMPOSE) down

dev-restart:
	$(DEV_COMPOSE) restart

dev-ps:
	$(DEV_COMPOSE) ps

dev-logs:
	$(DEV_COMPOSE) logs -f --tail=120

dev-check:
	curl -fsS http://127.0.0.1:8000/health
	curl -fsS http://127.0.0.1:8001/health
	curl -fsS http://127.0.0.1:8011/health
	curl -fsSI http://127.0.0.1:5173/chat >/dev/null
	curl -fsSI http://127.0.0.1:5174/admin >/dev/null
	@echo "All dev services are reachable."
