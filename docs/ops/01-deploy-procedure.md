# Deploy procedure

Use this for standard deployments to ECS (staging or production).

## Staging

1. **Merge to `main`** — GitHub Actions runs the Deploy Staging workflow.
2. **Verify** — Check Actions tab; optional smoke test runs if `STAGING_BASE_URL` is set.
3. **Check ECS** — In AWS Console: ECS → cluster → service. New tasks should become healthy; old tasks drain.

## Production

1. **Tag release** — e.g. `git tag v1.2.3 && git push origin v1.2.3`.
2. **Deploy Production workflow** runs: build → push ECR → ECS service update → migrations → optional smoke.
3. **Verify** — `/healthz` and a quick API check; check CloudWatch logs for errors.

## Manual deploy (without CI)

1. **Build and push image**  
   `docker build -t <ecr-url>:<tag> backend && docker push <ecr-url>:<tag>`
2. **Update ECS service**  
   `aws ecs update-service --cluster <cluster> --service <service> --force-new-deployment`
3. **Run migrations** (if needed) — See [docs/deploy/aws-ecs.md](../deploy/aws-ecs.md) § Run migrations manually.

## After deploy

- Confirm ALB target health (target group healthy count).
- Spot-check logs in CloudWatch Logs (`/ecs/<name>`).
- If alarms are configured, ensure no new alarms fired (ALB 5xx, ECS tasks, RDS, WAF).

## Full reference

See [Deploy to AWS ECS (Fargate)](../deploy/aws-ecs.md) for Terraform, secrets, DNS, and CI/CD setup.
