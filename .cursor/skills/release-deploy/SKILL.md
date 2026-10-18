# Skill: Release / deploy

1. Ensure CI green; bump version in `pyproject.toml` + `CHANGELOG.md`.
2. Confirm `.env` not in image; pass secrets via runtime env / compose `env_file`.
3. `docker compose up --build` with `LIVE_TRADING=false`.
4. Smoke: `/api/health`, setup wizard, validation page.
5. Do not enable live in deploy defaults.
6. Tag release only after paper/demo soak notes in `docs/runbooks/`.
