import pytest

from ra.shared.budgets import BudgetExceeded, CaseBudget


def test_budget_blocks_extra_call():
    budget = CaseBudget(max_calls=1)
    budget.reserve(100, 10)
    budget.record(100, 10)
    with pytest.raises(BudgetExceeded):
        budget.reserve(100, 10)


def test_budget_blocks_tokens():
    budget = CaseBudget(max_input_tokens=1000)
    with pytest.raises(BudgetExceeded):
        budget.reserve(1001, 0)
