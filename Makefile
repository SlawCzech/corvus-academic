COMPOSE = docker compose -f infra/docker-compose.yml
# Dev stack: base + override. The override mounts source into the containers and
# sets DEBUG=true, which the entrypoints turn into uvicorn --reload.
COMPOSE_DEV = $(COMPOSE) -f infra/docker-compose.override.yml

.PHONY: help up build down down-volumes logs ps restart migrate ingest-guidelines seed-guidelines purge-drafts \
        dev dev-build langfuse-up langfuse-down \
        front-up front-down front-restart front-logs front-dev \
        shell-app shell-agent

help:  ## Show this list of targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ---------- whole stack ----------

up:  ## Start every service (foreground)
	$(COMPOSE) up

build:  ## Rebuild images and start every service
	$(COMPOSE) up --build

down:  ## Stop and remove all containers
	$(COMPOSE) down

down-volumes:  ## Stop everything and DELETE volumes (wipes the database)
	$(COMPOSE) down -v

logs:  ## Follow logs from every service
	$(COMPOSE) logs -f

ps:  ## Show container status
	$(COMPOSE) ps

restart:  ## Restart every service
	$(COMPOSE) restart

migrate:  ## Run database migrations (all app lineages: identity, mentoring, guidelines)
	$(COMPOSE) run --rm app alembic -c alembic_identity.ini upgrade head
	$(COMPOSE) run --rm app alembic -c alembic_mentoring.ini upgrade head
	$(COMPOSE) run --rm app alembic -c alembic_guidelines.ini upgrade head

ingest-guidelines:  ## Embed the university requirements into the vector store
	$(COMPOSE) run --rm agent python scripts/ingest_guidelines.py

seed-guidelines:  ## Fill the guideline catalog (UPDATE=1 publishes changed seed data as a new version)
	$(COMPOSE) run --rm app python scripts/seed_guidelines.py $(if $(UPDATE),--update)

purge-drafts:  ## Run the thesis-version retention sweep once (NOW=<iso> to shift the clock)
	$(COMPOSE) run --rm app python scripts/purge_drafts.py $(if $(NOW),--now $(NOW))

# ---------- dev stack (hot reload) ----------
# Edits to app/src, agent/src and frontend/ take effect without a rebuild.
# Stop with `make down` — it is the same compose project.

dev:  ## Start everything with hot reload (source mounted, uvicorn --reload)
	$(COMPOSE_DEV) up

dev-build:  ## Rebuild images, then start with hot reload
	$(COMPOSE_DEV) up --build

# ---------- frontend: in docker ----------
# Needs port 3000 free — stop a local `make front-dev` first, they collide.

front-up:  ## Start the frontend container (pulls up `app` too)
	$(COMPOSE) up -d frontend

front-down:  ## Stop the frontend container, leave the rest running
	$(COMPOSE) stop frontend

front-restart:  ## Restart just the frontend container
	$(COMPOSE) restart frontend

front-logs:  ## Follow frontend container logs
	$(COMPOSE) logs -f frontend

# ---------- frontend: local dev server ----------

front-dev:  ## Run the Next.js dev server locally with hot reload (Ctrl+C to stop)
	cd frontend && npm run dev

# ---------- tracing: self-hosted Langfuse (optional, own compose project) ----------

LANGFUSE = docker compose -f infra/langfuse/docker-compose.yml

langfuse-up:  ## Start Langfuse on http://localhost:3100 (traces of every graph run)
	$(LANGFUSE) up -d

langfuse-down:  ## Stop Langfuse (traces are kept in its volumes)
	$(LANGFUSE) down

# ---------- shells ----------

shell-app:  ## Open a shell inside the app container
	$(COMPOSE) exec app bash

shell-agent:  ## Open a shell inside the agent container
	$(COMPOSE) exec agent bash
