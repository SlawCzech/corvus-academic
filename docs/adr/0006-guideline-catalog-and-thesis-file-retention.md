# ADR 0006: An admin-managed guideline catalog, and stored thesis files with retention

- Status: Accepted
- Date: 2026-09-23

## Context

**Guidelines.** The university requirements the review is judged against are two
hand-written markdown files baked into the `agent` image
(`agent/src/application/prompts/guidelines/`). Changing them takes a deploy, the
original regulation they summarise (Zarządzenie 117/22) is nowhere in the system,
and nothing records which version of them a given review was produced under.
They also mix two things: what the university requires, and Corvus's own
interpretation of it (the CRITICAL/MAJOR/MINOR classification is ours, not the
regulation's).

One university has one set of rules for every promoter, so asking each promoter
to upload and curate their own copy would duplicate expert work and let the
copies drift.

**Thesis files.** An uploaded draft is thrown away after text extraction; only
the text is kept. So an improvement to extraction (`outline.py` has already had
one) cannot be applied to old versions, formal requirements that live in the file
(fonts, margins, styles) cannot be checked, and the promoter cannot download what
the student handed in. At the same time nothing is ever deleted: a graduated
student's every version stays in the database forever.

Not storing the file does not buy much privacy: the full extracted text, the
sensitive part, is already stored.

## Decision

**A global guideline catalog, owned by a new `guidelines` bounded context in `app`.**
Its own package (`app/src/guidelines/`), Postgres schema and Alembic lineage, like
`identity` and `mentoring`. `universities` → `guideline_sets` (university, thesis
type) → `guideline_versions`. An admin uploads the original regulation, writes or
edits the rubric (the checklist the model reads) and numeric thresholds, and
publishes. A published version is immutable; a correction is a new version. A
promoter reads the catalog, downloads the original and picks a set per student.
`mentoring` holds only the set's ID and calls the catalog in one direction.

When a student has a set, `app` puts the current published rubric into the
action context and records `guideline_version_id` in the action's `input_ref`.
The agent already skips its own guideline loading when the context carries
`guidelines`, so the agent does not change. A student without a set keeps the
old path (static file + retrieval) until those files are retired.

**Store the original thesis file, behind a `FileStore` port, with retention.**
`app/src/shared/files.py` defines the port and a Postgres (`bytea`) adapter; each
context keeps its blobs in its own schema (`mentoring.draft_files`,
`guidelines.source_files`) so no schema is shared across contexts.

A promoter can accept one version as final. Retention rules, evaluated by pure
functions and applied by one daily sweep in `app`:

- versions other than the accepted one lose their file and text 30 days after
  the acceptance;
- every version loses its file and text 150 days (about five months) after the
  student is marked `graduated` or `archived`.

(Shortened to 14 and 30 days on 2026-11-06, ADR 0027.)

A purged version keeps its row (number, date, filename, hash, size) so the
action history still says which version each result was about.

## Rejected options

- **Per-promoter upload of guidelines.** No bottleneck, but N diverging copies of
  one regulation, curated by people for whom it is not their job.
- **Guidelines inside the `mentoring` schema.** Less ceremony, but admin-owned
  reference data would mix with promoter-owned records.
- **Object storage (MinIO/S3) now.** The industry standard and a better fit at
  scale, but an eleventh service for about 2 GB of files. The `FileStore` port
  keeps that move to one new adapter.
- **Keep not storing files.** Cheapest, but gives up re-extraction, formal checks
  and downloads, while the text, the sensitive part, is stored anyway.
- **Deleting other versions immediately on acceptance.** Irreversible on a
  mis-click or a reviewer sending the thesis back; the 30-day window costs nothing.

## Consequences

- A third migration lineage: `alembic_guidelines.ini`, run by `make migrate`,
  `entrypoint.sh`, CI and Jenkins alongside the other two.
- Reviews become auditable against a guideline version, and guidelines change
  without a deploy.
- The rubric is the prompt, so the admin's editing is prompt engineering; the
  seed marks Corvus's own interpretation explicitly so a promoter can tell it from
  the regulation.
- Numeric thresholds are stored as structured data but are not yet checked by
  code; that, an AI-drafted rubric, and retrieval over the full regulation are
  follow-ups (see `docs/specs/guidelines-and-thesis-files-plan.md`).
- The database grows by the files. Acceptable at this scale; revisit with the
  adapter if it is not.
