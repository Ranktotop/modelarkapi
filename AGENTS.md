# Project development rules

## Local development servers

- Start development servers locally through the checked-in VS Code launch
  configurations in `.vscode/launch.json`.
- Use the compound configuration **Local Full Stack** when the complete
  application is needed. Use the individual launch configurations only when a
  single component is sufficient.
- Do not use `docker compose up`, `docker compose run`, `docker run`, or a
  directly invoked `uvicorn`/Vite process to start a development server.
- Docker is reserved for image/build validation and later deployment. Only
  start a Docker container when the user explicitly requests a Docker or
  deployment test.
- Local development ports are fixed by the launch file: proxy `8081`, studio
  backend `3000`, and Vite frontend `5173`. The proxy intentionally avoids port
  `8080`, which is used by another local project.
- Development launch configurations load repository secrets from `.env`.
  Never copy secret values into `.vscode/launch.json` or commit them.

## Live API safety

- A local server start does not authorize a paid Seedance generation.
- Prefer health checks and the read-only
  `/v1/real-human/configuration` endpoint before any asset or generation test.
- Run a paid or biometric live test only when the user explicitly requests it.
