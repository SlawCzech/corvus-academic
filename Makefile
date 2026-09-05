COMPOSE = docker compose -f infra/docker-compose.yml

.PHONY: up down build logs ps restart migrate shell-app shell-agent

up:
	$(COMPOSE) up

build:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

down-volumes:
	$(COMPOSE) down -v

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

restart:
	$(COMPOSE) restart

migrate:
	$(COMPOSE) run --rm app alembic -c alembic_identity.ini upgrade head

shell-app:
	$(COMPOSE) exec app bash

shell-agent:
	$(COMPOSE) exec agent bash
