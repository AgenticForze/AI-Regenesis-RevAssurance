# From this build to production on AWS

The container is stateless apart from its database, so it maps directly onto the target
architecture in `docs/architecture/deployment.md`.

| Concern | This build | Production |
| --- | --- | --- |
| Compute | One container | ECS Fargate or EKS service behind an ALB; agent tier on AgentCore Runtime when volumes need it |
| Identity | Built-in provider | Cognito or your IdP (`RA_OIDC_ISSUER`); machine clients via client credentials |
| Database | SQLite file | Aurora PostgreSQL. The SQL in `src/ra/db.py` is portable; swap the connection |
| Data in | Synthetic generator, CSV source plug-in | Lakehouse pipeline writes exceptions; source plug-ins for small systems |
| Model | Offline reasoner | Bedrock: `RA_LLM_MODE=bedrock`, inference-profile ARNs in `RA_BEDROCK_*_MODEL` |
| Outbox worker | Runs inline after each request | A scheduled task running `ra dispatch` |
| Audit | Hash chain in the database | Plus S3 Object Lock copy in the Log Archive account |
| Telemetry | In-memory spans, `/metrics` | OTLP to the collector; X-Ray, CloudWatch, managed Prometheus |
| Secrets | Environment variables | Secrets Manager injected as environment variables |

## Before go-live

1. Run the gold-set evaluation and the release gates in `docs/asdlc/05-evaluation.md`. The
   bundled synthetic accuracy is not evidence.
2. Test the Bedrock path and the OIDC path against your accounts. Neither is covered by the
   offline test suite.
3. Test each plug-in against your instance, then set `dry_run: false` one at a time.
4. Replace `config/baseline.yaml` with your measured baseline.
5. Load-test at your volume. This build processes a few thousand records per run in one
   process; the 4M-a-day design uses the Spark and Flink engine in `docs/architecture/`.
