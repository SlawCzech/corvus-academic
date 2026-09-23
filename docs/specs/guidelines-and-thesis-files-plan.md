# Guideline catalog and stored thesis files — implementation plan

> Status: approved 2026-09-23. Decision record: [ADR 0006](../adr/0006-guideline-catalog-and-thesis-file-retention.md).

## Why

Guidelines are two static markdown files in the `agent` image: no upload, no
original regulation, no record of which version a review used. An uploaded
thesis is discarded after extraction, and nothing is ever deleted.

## Design in brief

- **`guidelines` bounded context in `app`** — own package, schema, Alembic lineage.
  `universities` → `guideline_sets` (university, thesis type) → `guideline_versions`
  (`draft | published | superseded`, `rubric_md`, `thresholds`, `effective_from`,
  original source file). Published versions are immutable. Writes need
  `Permission.MANAGE_GUIDELINES` (admin); reads need `MANAGE_STUDENTS`.
- **Mentoring uses it one way.** `students.guideline_set_id` (plain UUID, no FK
  across contexts). For `generate_review` and `evaluate_methodology`, the current
  published rubric goes into `context["guidelines"]` and its ID into
  `input_ref["guideline_version_id"]`. The agent already skips its own loading when
  `guidelines` is present, so the agent is unchanged.
- **`FileStore` port** (`app/src/shared/files.py`) with a Postgres `bytea` adapter;
  each context keeps its blobs in its own schema.
- **Draft acceptance and retention.** `students.accepted_draft_id`,
  `draft_accepted_at`, `closed_at`; `thesis_drafts.purged_at`, nullable `text`.
  Pure rules in `mentoring/domain/retention.py`: non-accepted versions purged 30 days
  after acceptance, all versions 150 days after `graduated`/`archived`. One sweep,
  run daily from `app`'s lifespan and on demand via `make purge-drafts`. A purged
  row keeps number, date, filename, hash and size.
- **Uploads:** 25 MB limit, file type checked by content, not only by extension.

## Commits

| # | Commit | Status |
|---|---|---|
| 1 | `docs:` ADR 0006 and this spec | ✅ |
| 2 | `feat(mentoring):` keep the original thesis file — `FileStore`, `draft_files`, download endpoint, upload limit and content sniffing | ✅ |
| 3 | `feat(mentoring):` accept a final draft, purge the rest on a retention schedule | ✅ |
| 4 | `feat(guidelines):` admin-managed catalog — domain, schema, lineage, API, seed of the current files as version 1 | ☐ |
| 5 | `feat(mentoring):` assess against the student's chosen guideline set | ☐ |
| 6 | `feat(frontend):` download, accept and delete thesis versions | ☐ |
| 7 | `feat(frontend):` guideline catalog for admins and promoters | ☐ |
| 8 | `docs:` CLAUDE.md, architecture, `.env.example` | ☐ |

## Out of scope — next steps

- Check `thresholds` in code in `agent` (deterministic findings instead of the
  model comparing numbers).
- AI action "draft a rubric from the regulation", reviewed and published by the admin.
- Retrieval over the full regulation text (findings cite paragraphs); retire the
  static `.md` files and `analysis.guideline_chunks` in `agent`.
- A promoter overlay of own requirements (may only tighten).

## Verification

- Every commit green in the touched services: `uv run pytest --cov=src` (≥80%),
  `ruff check`, `pyright src`; frontend `lint`, `typecheck`, `test`.
- Migrations from scratch on `pgvector/pgvector:pg16`, then `make seed-guidelines`.
- Smoke through `docker compose`: publish a new version (previous becomes
  `superseded`); promoter downloads the original and picks a set; `generate_review`
  records `guideline_version_id`; accept a version and run the purge with a shifted
  `--now` to see the other versions purged while the action history still renders.
