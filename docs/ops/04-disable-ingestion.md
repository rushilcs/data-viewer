# Disable ingestion (feature flag)

Use this to temporarily stop publish/append (dataset publishing) without redeploying. Useful during an incident or maintenance.

## Behavior

- **`INGEST_ENABLED=true`** (default): Publish and append work as normal.
- **`INGEST_ENABLED=false`**: Requests to **publish** or **append** return **503** with body `{"detail": "Ingestion is temporarily disabled"}`. Other ingest endpoints (create dataset, get upload URLs, PUT upload) remain available so publishers can prepare; only the final publish/append is blocked.

## ECS (Secrets Manager or task env)

1. **Secrets Manager**  
   Add or update the app secret JSON with:
   ```json
   "INGEST_ENABLED": "false"
   ```
   Then force a new ECS deployment so tasks pick up the new value.

2. **Task definition env (if you manage env there)**  
   Add or set `INGEST_ENABLED=false` in the container environment, then update the task definition and force new deployment.

## Re-enable

Set `INGEST_ENABLED=true` (or remove the key so the app default `True` is used) in the same place, then force new deployment.

## Local

- In `.env`: `INGEST_ENABLED=false`
- Or export before run: `export INGEST_ENABLED=false`

## Summary

| Goal | Action |
|------|--------|
| Disable publish/append | Set `INGEST_ENABLED=false`, roll ECS (or restart local). |
| Re-enable | Set `INGEST_ENABLED=true` (or unset), roll ECS (or restart). |
