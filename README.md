# Corvus

Local web application supporting thesis reviewers and supervisors in analysing student diploma theses.

## What it does

Upload a PDF or DOCX thesis. Corvus analyses its structure, methodology, and compliance with university requirements, then generates a draft review with a point score. A thesis can be reviewed once, without a student profile, and promoted to a student later.

> **In transition.** Corvus is being reshaped from a one-document analyser into a
> platform for supervising students across the whole thesis lifecycle — meeting
> notes, topic proposals, progress checks, final review. The reasoning is in
> [docs/adr/](docs/adr/); the phased plan and its current status are in
> [docs/specs/mentoring-platform-implementation-plan.md](docs/specs/mentoring-platform-implementation-plan.md).

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js (TypeScript) |
| app | FastAPI — auth/users/roles, document extraction, (soon) mentoring domain |
| agent | FastAPI + LangGraph + Celery — analysis and review |
| Models | Claude API / OpenAI via user-supplied key; local chat models off by default (ADR 0016) |
| Broker | Redis |
| Database | PostgreSQL + Alembic |

## Quick start

```bash
cp .env.example .env
```

Fill in the required values in `.env` — `JWT_SECRET`, `FERNET_KEY`, `DATABASE_URL`,
`ADMIN_EMAIL`, `ADMIN_PASSWORD`, `AGENT_URL`. Key generation commands are in the
comments of `.env.example`. Then:

```bash
docker compose -f infra/docker-compose.yml up -d
```

Frontend: http://localhost:3000
API: http://localhost:8000/docs
Flower: http://localhost:5555

## Development

`Makefile` holds shortcuts for the docker-compose commands:

```bash
make help
```

`make dev` starts the stack with hot reload — edits under `app/src/` and `agent/src/`
take effect in a few seconds, no rebuild. (Editing `main.py` still needs a container
restart; see the note in `infra/docker-compose.override.yml`.) `make up` runs the same
stack from the built images, without reload.

Frontend has two modes: `make front-up` / `make front-down` run it as a container,
`make front-dev` runs the Next.js dev server locally with hot reload. Both bind
port 3000, so only one at a time.

Per-service checks (run from `app/` or `agent/`):

```bash
uv run pytest -q
uv run ruff check .
```

## License

Private / academic use.
