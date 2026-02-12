# Rotate JWT secret

Rotating the JWT signing secret invalidates all existing access tokens (users must log in again). Plan for a short window of re-login or do it during low traffic.

## 1. Generate new secret

Generate a long random value (e.g. 32+ bytes, base64):

```bash
openssl rand -base64 32
```

## 2. Update secret in AWS Secrets Manager (prod)

1. Open **Secrets Manager** → secret used by the app (e.g. `data-viewer-prod/app`).
2. **Retrieve secret value** → **Edit**.
3. Update the `secret_key` field in the JSON to the new value. Keep `DATABASE_URL` and any other keys unchanged.
4. Save.

## 3. Roll ECS tasks so they pick up the new secret

Tasks read secrets at startup. To apply the new value:

- **Force new deployment**: ECS → cluster → service → **Update** → check **Force new deployment** → Update.

New tasks will get the new `secret_key` from Secrets Manager. In-flight requests may still use old tokens until they expire; new logins will get tokens signed with the new secret.

## 4. (Optional) Restrict old token validity

If you cannot force new deployment immediately, you can reduce `access_token_expire_minutes` in config so existing tokens expire sooner. Rotate the secret and deploy that config change, then roll tasks as above.

## Local / non-ECS

- **Local**: Update `.env` or env with the new `secret_key` (or `SECRET_KEY`). Restart the backend. All existing cookies/tokens will be invalid.
- **Other hosts**: Update the secret in your config store or env and restart the app process.

## Summary

| Step | Action |
|------|--------|
| 1 | Generate new secret (e.g. `openssl rand -base64 32`) |
| 2 | Update `secret_key` in Secrets Manager (or local env) |
| 3 | Force new ECS deployment so tasks load new secret |
| 4 | Users with old tokens must log in again |
