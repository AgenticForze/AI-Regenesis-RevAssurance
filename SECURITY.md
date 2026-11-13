# Security policy

## Reporting a vulnerability
Report suspected vulnerabilities privately to the security lead through your internal
security channel. Do not open a public issue. Include steps to reproduce and impact.

## Security model (summary)
- Multi-account AWS Organization; workloads have no internet route; VPC endpoints only.
- Agents use read-only tools; the only write tool creates a pending proposal. Posting to
  billing or ERP requires human approval and runs in a separate service.
- Bedrock Guardrails on every untrusted input; AgentCore Policy allow-lists per agent.
- PII is tokenized before any model call; audit evidence is stored with S3 Object Lock.
- Claude Code sessions are denied production credentials, secrets and raw data by
  `.claude/settings.json`; hooks block PII and secrets in commits.

See docs/architecture/deployment.md and docs/asdlc/05-evaluation.md (red-team).
