# Corvus — frontend

Next.js 16 (App Router), React 19, TypeScript strict. The browser talks only to `app`;
see the [main README](../README.md) for the whole system.

```bash
npm ci
npm run dev        # http://localhost:3000, expects `app` on APP_URL (default http://localhost:8000)
npm test           # Vitest
npm run lint
npm run typecheck
```

From the repository root, `make front-dev` does the same against the running stack, and
`make front-up` runs the frontend as a container instead. Both use port 3000.

Notes for coding agents working here are in [AGENTS.md](AGENTS.md).
