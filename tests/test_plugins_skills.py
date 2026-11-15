import pytest

from ra import db, plugins, skills
from ra.plugins import builtin
from ra.tools import registry


def test_every_skill_uses_known_tools():
    all_skills = skills.load_all()
    assert "general-investigation" in all_skills and len(all_skills) >= 8
    for s in all_skills.values():
        assert set(s.tools) <= set(registry.REGISTRY), s.name
        assert s.body().strip()
    assert skills.select("RC11_partner_variance").name == "investigate-partner-variance"
    assert skills.select("RC08_tax_error").name == "general-investigation"


def test_only_one_write_tool():
    assert [t.name for t in registry.REGISTRY.values() if t.write] == ["propose_adjustment"]


def test_webhook_is_signed_in_dry_run():
    out = builtin.Webhook("w", {"url": "https://example.invalid/h"}, dry_run=True).deliver(
        "adjustment.approved", {"id": "adj-1", "amount": 10.0})
    assert out["dry_run"] and out["body"]["event"] == "adjustment.approved"


def test_live_plugin_without_secret_fails_closed():
    p = builtin.Slack("s", {"webhook_url_env": "RA_UNSET_VARIABLE"}, dry_run=False)
    with pytest.raises(RuntimeError):
        p.deliver("run.completed", {"id": "run-1"})


def test_ledger_journal_is_balanced(tmp_path):
    p = builtin.LedgerJournalFile("erp", {"directory": str(tmp_path)}, dry_run=False)
    out = p.deliver("adjustment.approved", {"id": "adj-9", "amount": 120.5, "currency": "USD",
                                           "account_id": "ACC-00001", "action": "rebill"})
    rows = (tmp_path / "RAJ-adj-9.csv").read_text().splitlines()[1:]
    assert out["posting_ref"] == "RAJ-adj-9"
    assert sum(float(r.split(",")[3]) for r in rows) == 0


def test_csv_source(tmp_path):
    f = tmp_path / "s1-2026-10.csv"
    f.write_text("account_id,service_id,product_code,qty,amount,feed_complete\n"
                 "ACC-1,SVC-1,DATA-GB,12.5,0,true\n")
    src = builtin.CsvSource("s1", {"path": str(tmp_path / "s1-{period}.csv"), "source": "S1",
                                   "kind": "usage"})
    rec = next(iter(src.fetch("2026-10")))
    assert rec["qty"] == 12.5 and rec["attrs"] == {"feed_complete": True}


def test_outbox_is_idempotent_and_retries(client, monkeypatch):
    class Flaky(plugins.SinkPlugin):
        type = "flaky"
        calls = 0

        def deliver(self, event, payload):
            Flaky.calls += 1
            if Flaky.calls == 1:
                raise RuntimeError("external system down")
            return {"ok": True}

    inst = [(Flaky("flaky-1", {}, False), ("case.opened",))]
    monkeypatch.setattr(plugins, "instances", lambda: inst)
    assert plugins.emit("case.opened", "case-zz", {"id": "case-zz"}) == 1
    assert plugins.emit("case.opened", "case-zz", {"id": "case-zz"}) == 0   # same key
    assert plugins.dispatch()["failed"] == 1
    assert plugins.dispatch()["delivered"] == 1
    row = db.one("SELECT * FROM outbox WHERE idem_key='flaky-1:case.opened:case-zz'")
    assert row["status"] == "delivered" and row["attempts"] == 2
