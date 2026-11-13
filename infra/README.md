# Infrastructure as code

One IaC tool org-wide (CDK or Terraform, ADR-002). Stacks by account:

| Folder | Account | Contents |
| --- | --- | --- |
| org/ | Management | SCPs, Identity Center, Control Tower customizations |
| network/ | Network | TGW, firewall, DX/VPN, endpoints, Route 53 |
| observability/ | Observability | OAM, Grafana, Prometheus, dashboards, alarms, SLOs |
| data-platform/ | Data Platform | MSK, DMS, Glue, EMR, Flink, Iceberg, Lake Formation |
| ai-platform/ | AI Platform | Inference profiles, KBs, Guardrails, AgentCore |
| case-mgmt/ | Case Mgmt | Step Functions, DynamoDB, API, UI hosting |
| env/ | - | dev, test, stage, prod, dr configuration |
