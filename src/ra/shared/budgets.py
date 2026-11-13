"""Per-case budgets enforced in code, not left to the model."""
from __future__ import annotations

from dataclasses import dataclass, field


class BudgetExceeded(RuntimeError):
    """Raised when an agent step would exceed its case budget."""


@dataclass
class CaseBudget:
    max_calls: int = 12
    max_input_tokens: int = 60_000
    max_output_tokens: int = 6_000
    calls: int = field(default=0, init=False)
    input_tokens: int = field(default=0, init=False)
    output_tokens: int = field(default=0, init=False)

    def reserve(self, input_tokens: int, output_tokens: int) -> None:
        """Check a planned call fits the remaining budget before making it."""
        if self.calls + 1 > self.max_calls:
            raise BudgetExceeded("call budget exhausted")
        if self.input_tokens + input_tokens > self.max_input_tokens:
            raise BudgetExceeded("input token budget exhausted")
        if self.output_tokens + output_tokens > self.max_output_tokens:
            raise BudgetExceeded("output token budget exhausted")

    def record(self, input_tokens: int, output_tokens: int) -> None:
        self.calls += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens

    @property
    def remaining_input_tokens(self) -> int:
        return self.max_input_tokens - self.input_tokens
