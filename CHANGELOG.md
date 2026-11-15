# Changelog

All notable changes are recorded here, newest first. Each release references its
release manifest (docs/templates/release-manifest.json).

## 0.2.0

- Working product in `src/ra`: API and console, authentication (OIDC or built-in), authorization (roles, business unit, approval limit, four-eyes), 9 controls over 10 synthetic sources, triage, skill-driven investigation, verifier, approval workflow.
- Tools registry served to agents, REST and MCP (streamable HTTP and stdio).
- A2A 0.3: outbound partner-statement queries, inbound agent card and three skills.
- Plug-in framework with transactional outbox; ERP journal, Jira, ServiceNow, Slack, webhook, CSV source; example third-party package.
- Hash-chained audit trail, OpenTelemetry traces, Prometheus metrics and alert rules.
- Before/after reporting (JSON, CSV, HTML).
- Dockerfile, docker-compose with collector, Jaeger, Prometheus, Grafana.

## [Unreleased]
- Initial reference scaffold: architecture, aSDLC playbooks, Claude Code setup, specs, evals, website.
