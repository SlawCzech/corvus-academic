# Security policy

Corvus stores supervisors' API keys and unpublished student theses, so security reports
are taken seriously.

## Reporting a vulnerability

Please **do not open a public issue**. Report privately through GitHub:
[Security → Report a vulnerability](https://github.com/SlawCzech/corvus-academic/security/advisories/new).

Include what you found, how to reproduce it, and what an attacker could do with it.
You can expect an acknowledgement within a week. This is a solo project, so there is no
bug bounty, but reporters are credited in the advisory unless they prefer otherwise.

## Supported versions

Only the latest commit on `main` is supported; there are no release branches.

## Scope

Of particular interest:

- access to another supervisor's students, theses or results;
- an admin account reaching student data (admins and supervisors are disjoint roles,
  [ADR 0008](docs/adr/0008-admin-and-promoter-are-separate-roles.md));
- leaking a provider API key — at rest, in the task queue, in logs, in graph state or
  in checkpoints ([ADR 0012](docs/adr/0012-seal-the-provider-key-for-the-task-queue.md));
- personal data reaching the AI provider despite pseudonymisation
  ([ADR 0023](docs/adr/0023-names-stay-in-corvus.md));
- thesis text leaving the server through the bibliography check, which should send only
  bibliographic entries.

Out of scope: findings that require a compromised host or `.env`, denial of service by
volume, and the behaviour of third-party AI providers.
