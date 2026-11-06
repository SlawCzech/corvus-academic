# ADR 0027: Corvus is the promoter's processor

- Status: Accepted
- Date: 2026-11-06
- Amends: [ADR 0006](0006-guideline-catalog-and-thesis-file-retention.md) (retention periods)

## Context

Corvus was going to serve 10–20 promoters, not three testers who know the operator. Their students' theses, names and meeting notes are personal data, and the operator runs the service as a private person, with no wish to sign anything with a university. Under the GDPR whoever holds someone else's data on their behalf needs an art. 28 agreement with the controller; without one the operator processes without a basis and is easier to treat as a controller themselves — the worse position, not a neutral one.

## Decision

- **The operator is a processor, the promoter (or the university behind them) the controller.** The terms of service carry the data processing agreement (§ 5), shaped after the Commission's standard contractual clauses between controllers and processors (Implementing Decision 2021/915), cut down to a click-through. The promoter declares a legal basis and authority to enter their students' data. No agreement with any university.
- **The providers are the promoter's, not the operator's subprocessors.** Every action runs on the promoter's own key (ADR 0022), under their own contract with Anthropic or OpenAI; the terms say so. Subprocessors are OVHcloud (the server) and Cloudflare R2 (encrypted backups).
- **No student data before acceptance.** `identity.terms_acceptances` keeps a row per user and version. The mentoring router as a whole depends on `require_current_terms`: a promoter without the current version gets 403 `terms_not_accepted` on every route, which the frontend's API client turns into `/terms/accept?next=…`. An admin is not asked: they never see students (ADR 0008). A new version (`CURRENT_TERMS_VERSION` in `identity/domain/terms.py` and `frontend/content/legal/version.ts`, a test keeps them equal) asks everyone again.
- **Less data held.** The student's index number is gone from the card: nothing used it (the title page's album number is still pseudonymized, ADR 0023). Thesis files and text go 14 days after a final version is accepted (was 30) and 30 days after supervision ends or a one-off review is created (was 150). Login events — address and browser — are pruned after 90 days on every login. The meeting notes form asks for no health or other special-category data.
- **The documents name the operator from the server's environment** (`OPERATOR_NAME`, `OPERATOR_EMAIL`), not from the repository. Unset, the pages show a visible gap.
- **Routes in English** (`/terms`, `/privacy`, `/terms/accept`), text in Polish.

## Consequences

- Every promoter accepts once on the first visit after the deploy; until then their screens show the terms.
- The documents describe what the code does: retention periods, the 60-day backup lifecycle, the security measures. Changing any of them means changing the text and bumping the version.
- Notes and AI results still stay until the promoter deletes the student; the terms say so. Deleted data lives on in encrypted backups for up to 60 days.
- The `index_number` column is emptied by mentoring migration 0013 and dropped in a later release, so a rollback to the previous image still finds it.
- The documents are drafts written from the code, not legal advice; the operator should have someone read them.
- The register of processing categories (art. 30(2)) is in [docs/gdpr-register.md](../gdpr-register.md).
