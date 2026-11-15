# Plug-ins for external systems

| Type | Kind | Connects to | Events it usually takes |
| --- | --- | --- | --- |
| `ledger_journal_file` | sink | ERP general ledger (journal file drop) | `adjustment.approved` |
| `jira` | sink | Jira (issue per case) | `case.opened` |
| `servicenow` | sink | ServiceNow Table API | `adjustment.rejected`, `case.opened` |
| `slack` | sink | Slack incoming webhook | `adjustment.proposed`, `run.completed` |
| `webhook` | sink | Any HTTPS endpoint, HMAC-signed | any |
| `csv_source` | source | CSV extracts from a source system | n/a |
| `teams` (example package) | sink | Microsoft Teams webhook | any |

Built-in types live in `src/ra/plugins/builtin.py`. Instances are declared in
`config/plugins.yaml`. Each instance starts with `dry_run: true`.

## Write your own

1. Subclass `ra.plugins.SinkPlugin` (implement `deliver`) or `ra.plugins.SourcePlugin`
   (implement `fetch`).
2. Register it under the entry-point group `ra.plugins` in your package's `pyproject.toml`.
3. `pip install` the package next to the product and reference the type in `config/plugins.yaml`.

`ra-plugin-example/` is a complete package you can copy.

Rules the framework enforces for you: at-least-once delivery with an idempotency key per
plug-in, event and resource; five attempts, then the row is parked as `dead`; secrets are read
from environment variables named in config; every delivery is traced and audited.
