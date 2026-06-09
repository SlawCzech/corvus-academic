# Corvus

Local web application supporting thesis reviewers and supervisors in analysing student diploma theses.

## What it does

Upload a PDF or DOCX thesis. Corvus analyses its structure, methodology, and compliance with university requirements, then generates a draft review with a point score.

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js (TypeScript) |
| Gateway | FastAPI + JWT |
| Parser | FastAPI + PyMuPDF / python-docx |
| Agent | LangGraph + Celery |
| Models | Ollama (local) · Claude API · OpenAI |
| Broker | Redis |
| Database | PostgreSQL + Alembic |

## Quick start

```bash
cp .env.example .env
# fill in required values in .env
docker compose -f infra/docker-compose.yml up -d
```

Frontend: http://localhost:3000  
API: http://localhost:8000/docs  
Flower: http://localhost:5555

## Development

```bash
make help
```

## License

Private / academic use.
