# Incident triage checklist

Use this when the service is unhealthy or alarms fire.

## 1. Confirm scope

- **What is affected?** (e.g. 5xx, timeouts, no response, auth failures.)
- **Where?** (ALB, ECS, RDS, WAF; single AZ vs whole region.)
- **When did it start?** (recent deploy, config change, traffic spike.)

## 2. Check health and alarms

- **ALB**  
  - Target group: healthy target count. If 0, tasks are failing health checks.  
  - Listeners: 5xx count in CloudWatch (e.g. `HTTPCode_Target_5XX_Count`).
- **ECS**  
  - Service: desired vs running count. Stopped tasks → Events tab for stop reason.  
  - Logs: CloudWatch Log group `/ecs/<name>` — errors, stack traces, request_id.
- **RDS**  
  - CPU, connections, storage (CloudWatch).  
  - If CPU or storage alarms fired, check slow queries or growth.
- **WAF**  
  - Blocked request spike can indicate attack or misconfigured rule; adjust or allowlist if false positive.

## 3. Recent changes

- Last deploy (tag or commit) and time.
- Terraform or config changes (secrets, env, feature flags).
- `INGEST_ENABLED` or other flags if ingestion/auth is affected.

## 4. Quick mitigations

| Symptom | Action |
|--------|--------|
| Bad deploy | [Rollback](02-rollback-procedure.md) to previous task definition/image. |
| High 5xx / errors in logs | Rollback or scale up; fix config/DB and redeploy. |
| DB overload | Check RDS metrics; optimize or scale; consider read replica if applicable. |
| Ingestion causing load | [Disable ingestion](04-disable-ingestion.md) temporarily. |
| Suspected auth/secret issue | [Rotate JWT secret](03-rotate-jwt-secret.md) if needed after fixing leak. |

## 5. Logs and request_id

- ECS logs are structured (when `LOG_JSON=1`): one JSON line per request with `request_id`, route, status, latency.
- Use `request_id` (also in response header `X-Request-ID`) to trace a request across logs.

## 6. After resolution

- Document timeline, root cause, and actions taken.
- Update runbooks or alarms if the incident suggests gaps.
- If secrets were compromised, rotate them and notify as per security policy.
