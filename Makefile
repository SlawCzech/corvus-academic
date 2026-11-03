COMPOSE = docker compose -f infra/docker-compose.yml
# Dev stack: base + override. The override mounts source into the containers and
# sets DEBUG=true, which the entrypoints turn into uvicorn --reload.
COMPOSE_DEV = $(COMPOSE) -f infra/docker-compose.override.yml

.PHONY: help up build down down-volumes logs ps restart migrate seed-guidelines seed-demo demo-reset purge-drafts \
        dev dev-build eval eval-fragments eval-defence eval-progress eval-maps langfuse-up langfuse-down \
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

seed-guidelines:  ## Fill the guideline catalog (UPDATE=1 publishes changed seed data as a new version)
	$(COMPOSE) run --rm app python scripts/seed_guidelines.py $(if $(UPDATE),--update)

seed-demo:  ## Give a promoter the demo students, notes and theses (PROMOTOR=<e-mail>, required; AS_OF=today moves the dates)
	$(COMPOSE) run --rm app python scripts/seed_demo.py --promotor $(PROMOTOR) $(if $(AS_OF),--as-of $(AS_OF)) $(if $(ONLY),--only $(ONLY))

demo-reset:  ## Delete the demo students from a promoter's roster and seed them again (PROMOTOR=<e-mail>, required)
	$(COMPOSE) run --rm app python scripts/seed_demo.py --promotor $(PROMOTOR) --reset $(if $(AS_OF),--as-of $(AS_OF)) $(if $(ONLY),--only $(ONLY))

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

# ---------- evals: synthetic theses with planted defects (agent/evals) ----------
# Runs on the host against the host's Ollama, not in a container: an eval is a
# tool for whoever changes a prompt or a model, and it needs no stack.

eval:  ## Score a model on the eval cases (MODEL=qwen3:30b-a3b|claude|openai JUDGE=… CASES="a b")
	cd agent && uv run python -m evals.run --model $(or $(MODEL),qwen3:30b-a3b) \
		$(if $(JUDGE),--judge $(JUDGE)) $(if $(CASES),--cases $(CASES))

eval-fragments:  ## Score review_fragment: tone and direction (MODEL=… JUDGE=… CASES="a b")
	cd agent && uv run python -m evals.fragments --model $(or $(MODEL),qwen3:30b-a3b) \
		$(if $(JUDGE),--judge $(JUDGE)) $(if $(CASES),--cases $(CASES))

eval-defence:  ## Score defence_questions: short, general, spoken (MODEL=… JUDGE=… CASES="a b")
	cd agent && uv run python -m evals.defence --model $(or $(MODEL),qwen3:30b-a3b) \
		$(if $(JUDGE),--judge $(JUDGE)) $(if $(CASES),--cases $(CASES))

eval-progress:  ## Score check_progress: meeting notes as context (MODEL=… JUDGE=… CASES="a b")
	cd agent && uv run python -m evals.progress --model $(or $(MODEL),qwen3:30b-a3b) \
		$(if $(JUDGE),--judge $(JUDGE)) $(if $(CASES),--cases $(CASES))

eval-trial:  ## Score a trial review's advice and the mail from it (MODEL=… JUDGE=… CASES="a b")
	cd agent && uv run python -m evals.trial --model $(or $(MODEL),qwen3:30b-a3b) \
		$(if $(JUDGE),--judge $(JUDGE)) $(if $(CASES),--cases $(CASES))

eval-maps:  ## Recompute each eval case's document map with app's outline (after editing a thesis)
	for case in agent/evals/cases/*/; do \
		(cd app && uv run python scripts/document_map.py ../$$case/thesis.md) > $$case/document_map.json; \
	done

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
