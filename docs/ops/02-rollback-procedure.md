# Rollback procedure

Use when a deployment causes errors and you need to revert to the previous task definition or image.

## Option A: Redeploy previous image (recommended)

1. **Identify last known good tag** — From your release process or ECR (e.g. `v1.2.2` if current bad deploy is `v1.2.3`).
2. **Update ECS service to previous task definition**  
   - In AWS Console: ECS → cluster → service → Update → Revision: select previous revision → Update.  
   - Or force new deployment with the same image tag that was previously running (re-deploy that tag so ECS pulls it again).
3. **Or push previous tag and force new deployment**  
   - If you use “latest” in production, re-tag the previous image in ECR as `latest`, then in ECS run “Update service” → “Force new deployment”. New tasks will pull the re-tagged image.

## Option B: Rollback via task definition revision

1. ECS → cluster → service → **Tasks** tab. Note the **Task definition** of a healthy (or last good) task.
2. **Update service** → Task definition: choose the previous revision (e.g. `data-viewer-prod:42` → `data-viewer-prod:41`) → Update.
3. ECS will start tasks with the old revision and drain the new ones.

## Option C: CI/CD re-run with previous tag

- For production: check out the previous tag, re-run the deploy workflow (or trigger deploy of that tag). Ensures the exact image and config for that release are deployed.

## After rollback

- Confirm target group healthy count and `/healthz` (and `/readyz` if used).
- Check CloudWatch logs for the rolled-back service.
- Fix the issue in code, test, then redeploy when ready.
- Document the incident and root cause.
