# Secret Management Runbook

This runbook covers environment secrets for AEGIS deployments and local development.

## Scope

- PostgreSQL credentials used by the backend.
- Any future API keys, service tokens, or broker credentials.

## Principles

- Never commit real secrets to the repository.
- Keep local development secrets separate from production secrets.
- Rotate credentials on a schedule and immediately after any suspected exposure.
- Verify both the application and the database after every credential change.

## Local Development

1. Copy `infrastructure/.env.example` to `infrastructure/.env`.
2. Fill in local-only values.
3. Confirm the file remains untracked with `git status --short`.
4. Start the backend and verify `/health` responds as expected.

## Production Rotation Procedure

1. Choose a maintenance window.
2. Generate a new secret using a trusted local secret manager or OS tool.
3. Update the production secret store or deployment environment with the new value.
4. Rotate the database role password to match the new secret.
5. Restart or reload the backend and any dependent workers.
6. Verify connectivity through the application health endpoint and a direct database connection test.
7. Confirm logs do not contain the old secret or unexpected authentication failures.
8. Revoke the previous secret only after the new one is confirmed working.

## Verification Checklist

- `psql` connects successfully with the new credential.
- `GET /health` returns healthy.
- Background jobs can still connect to the database.
- No secret material appears in logs, shell history, or tracked files.

## Incident Response

- If a secret is exposed, rotate it immediately.
- Update all dependent services before ending the maintenance window.
- Record the rotation time, affected services, and verification results in the operational log.