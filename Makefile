.PHONY: install lint test eval-quick eval-final perf docs-serve

install:
	pip install -e ".[dev]"

lint:
	ruff check .

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

seed:
	python -m ra.cli seed

run:
	python -m ra.cli run --period 2026-10

serve:
	python -m ra.cli serve

report:
	python -m ra.cli report --format html > before-after.html
