# ADR 0008: Admin and promoter are separate roles, with no overlap

- Status: Accepted
- Date: 2026-09-23
- Supersedes: the "admin sees every roster" rule in the mentoring implementation plan (Phase 1, `VIEW_ALL_STUDENTS`)

## Context

The admin role was built as a superset: `Role.ADMIN` held `frozenset(Permission)`, meaning every permission, including `MANAGE_STUDENTS`, `VIEW_ALL_STUDENTS` and `SUBMIT_ANALYSIS`. In the UI, an admin therefore got everything a promoter has (Dashboard, Studenci, BYOK and AI defaults in the profile) on top of the admin screens. They also got two separate guideline tabs: the promoter's read-only one and the admin's catalog.

That is wrong for this platform. Theses and meeting notes are between a promoter and their students. The person who runs the server has no reason to read them. An admin account that could open any student's record was also the one account whose compromise would expose everything.

## Decision

- **Two roles that do not overlap.** An admin gets `MANAGE_USERS`, `MANAGE_GUIDELINES` and `MANAGE_MODELS`. A promoter gets `MANAGE_STUDENTS` and `SUBMIT_ANALYSIS`. No role holds `VIEW_ALL_STUDENTS` any more.
- **An admin who also supervises uses a second account**, with the promoter role. This is a cost we accept: one person, two logins.
- **BYOK is promoter-only.** `/settings/api-key*` requires `SUBMIT_ANALYSIS`, because a key pays for AI actions and an admin runs none.
- **The UI follows the roles.**
  - An admin's menu has Użytkownicy, Wytyczne (the catalog they manage, merged into one tab), Modele AI, Logi logowań and Profil (password only). An admin lands on `/admin/users`.
  - The middleware sends an admin away from `/dashboard` and `/students`.
  - The page of a single guideline version (`/guidelines/<id>`) stays shared, because the admin catalog links to it.
- **Existing data was moved**, not orphaned. On the local instance, the student created from the admin account during the learning sessions, with its notes, drafts and action history, was reassigned to a promoter account (`saek@saek.pl`).

## Consequences

- `Caller.can_view_all` and the "view all" branches in the mentoring repositories are now unreachable. They are kept for now and listed as debt, not removed in this change.
- Any deployment where the admin account owns students has to reassign them before upgrading, or those students become unreachable. There is no migration for this, because the target account is a human decision.
- Tests that asserted admin reach into rosters now assert the opposite (403).
