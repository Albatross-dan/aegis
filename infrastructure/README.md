# Infrastructure

This directory contains local runtime configuration for the backend stack.

## Environment file

- Copy `infrastructure/.env.example` to `infrastructure/.env`.
- Fill in local-only PostgreSQL credentials.
- Do not commit `infrastructure/.env`; it is ignored by the repository root `.gitignore`.
- Rotate credentials before using the project in any shared or production environment.

## Notes

The backend settings loader reads `infrastructure/.env` from the repository root, so the path is stable regardless of the working directory used to start the app or tests.

For production-facing secret handling and rotation, see [docs/ops/secret-management.md](../docs/ops/secret-management.md).
