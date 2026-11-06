# Contributing

Corvus is a personal project with one maintainer, so the pace and the scope are mine to
set. Still, issues, ideas and pull requests are welcome.

## Before you start

- **Bugs and ideas:** open an issue first. For anything bigger than a small fix, wait for
  a reply before writing code — the design may already have a decision against it.
- **Design decisions** live in [`docs/adr/`](docs/adr/). A change that reverses one needs
  a new ADR that supersedes it.
- **Security issues** go through [SECURITY.md](SECURITY.md), not the issue tracker.

## Setting up

See [Quick start](README.md#quick-start) and [Development](README.md#development) in the
README. You need Docker, `make`, [`uv`](https://docs.astral.sh/uv/) and Node.js 22.

## Making a change

1. Branch from `main`.
2. Keep the layers clean: `infrastructure → application → domain`, never the other way.
   In `app`, context boundaries are checked by `uv run lint-imports`.
3. Add tests. Coverage is checked at 80%.
4. If you change a prompt or a graph, run the matching eval (`make eval`, `make
   eval-fragments`, …) on a provider key and put the numbers in the PR. A unit test
   cannot tell whether a review got better.
5. Never use real students' theses in tests, fixtures, evals or traces. The demo theses
   in `app/scripts/seed_data/theses/` are synthetic for that reason.
6. Run the checks CI runs (listed in the README) and `uvx pre-commit run --all-files`.

## Commits and pull requests

- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):
  `feat(agent): …`, `fix(app): …`, `docs: …`.
- One topic per PR. Describe what changes for the supervisor, not only in the code.
- Code, identifiers, commits and ADRs are in English; prompts and UI are in Polish.

By contributing you agree that your contribution is licensed under the [MIT License](LICENSE).

## Code of conduct

Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
