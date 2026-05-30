COMPOSE = docker compose -f infra/docker-compose.yml

.PHONY: up down build logs ps restart migrate shell-gateway shell-agent

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
	$(COMPOSE) run --rm migrate

shell-gateway:
	$(COMPOSE) exec gateway bash

shell-agent:
	$(COMPOSE) exec agent bash
