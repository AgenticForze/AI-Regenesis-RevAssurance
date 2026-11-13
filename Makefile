.PHONY: install lint test eval-quick eval-final perf docs-serve

install:
	pip install -e ".[dev]"

lint:
	ruff check src tests .claude/hooks
	ruff format --check src tests .claude/hooks

test:
	pytest -q

eval-quick:
	python -m evals.harness --suite triage --subset regression-100

eval-final:
	@echo "Held-out evaluation: run only from the verification workspace (Phase 5)."
	python -m evals.harness --suite all --dataset heldout --rc $(RC)

perf:
	@echo "Replay scenario $(SCENARIO) in $(ENV) - see docs/asdlc/05-evaluation.md"

docs-serve:
	python -m http.server -d website 8000
