# ADR 0026: A promoter's home university

- Status: Accepted
- Date: 2026-11-06
- Builds on: [ADR 0024](0024-a-rubric-in-four-sections-and-no-default.md), [ADR 0025](0025-the-model-drafts-the-rubric-from-the-regulation.md)

## Context

Every thesis needs a guideline set (ADR 0024), and with drafting from a regulation (ADR 0025) the catalog grows by a university at a time. The pickers listed every set for the kind of thesis, from every university. A promoter works at one university nearly always, and reviews a thesis from elsewhere now and then.

## Decision

- **A user has an optional home university**, `identity.users.home_university_id`: a plain id, no foreign key, since identity does not know the catalog (migration `0005_home_university`). The promoter sets it in the profile ("Moja uczelnia"); an admin may set it when creating the account. `GET`/`PATCH /users/me/settings` read and change it.
- **Pickers show the home university's sets** — the student form, the one-off review form, the picker by the actions — with the rest one choice away under "Inna uczelnia…". A set already chosen from elsewhere shows everything. When the home university has exactly one set for the kind of thesis, the two forms pick it on their own. The catalog page lists the home university's sets, with "Pokaż też inne uczelnie".
- **Without a home university nothing changes**: every set is offered.
- **One university per promoter.** Someone who works at two picks the other under "Inna uczelnia…"; a list comes when someone asks for it.

## Consequences

- Adding a student at one's own university needs no click on guidelines when the university has one set for that kind of thesis.
- An id that names no university (a deleted one) narrows nothing: the pickers fall back to every set.
