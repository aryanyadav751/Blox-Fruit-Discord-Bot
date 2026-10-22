"""
Blox Fruit Services - Payment Calculator & Rounding Rules.
Calculates initial deposits and remaining balances for:
1. 50/50 Payment (50% upfront, 50% on completion)
2. One-Time Full Payment (100% upfront, 0M balance)

Guarantees the mathematical invariant:
    initial_amount + remaining_amount == total_amount
"""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class PaymentPlan(str, Enum):
    SPLIT_50_50 = "SPLIT_50_50"
    FULL_UPFRONT = "FULL_UPFRONT"

    @classmethod
    def from_input(cls, value: str) -> "PaymentPlan":
        val = value.strip().upper()
        if "50" in val or "SPLIT" in val or "HALF" in val:
            return cls.SPLIT_50_50
        if "FULL" in val or "ONE" in val or "100" in val or "UPFRONT" in val:
            return cls.FULL_UPFRONT
        raise ValueError(f"Unknown payment plan: {value}. Expected 50/50 or One-Time Full.")

    @property
    def label(self) -> str:
        if self == PaymentPlan.SPLIT_50_50:
            return "50/50 Payment (50% Upfront, 50% on Completion)"
        return "One-Time Full Payment (100% Upfront)"


class PaymentMethod(str, Enum):
    FRUITS = "FRUITS"
    GAMEPASSES = "GAMEPASSES"
    COMBINATION = "COMBINATION"

    @property
    def label(self) -> str:
        if self == PaymentMethod.FRUITS:
            return "🍎 Fruits Only"
        elif self == PaymentMethod.GAMEPASSES:
            return "🎟️ Gamepasses Only"
        return "🍎+🎟️ Combination of Fruits & Gamepasses"


@dataclass(frozen=True)
class PaymentBreakdown:
    total_price_m: float
    plan: PaymentPlan
    initial_payment_m: float
    remaining_balance_m: float

    def __post_init__(self):
        # Strict validation of invariant
        combined = round(self.initial_payment_m + self.remaining_balance_m, 2)
        expected = round(self.total_price_m, 2)
        if combined != expected:
            raise ValueError(
                f"Calculation error: initial ({self.initial_payment_m}) + "
                f"remaining ({self.remaining_balance_m}) = {combined} does not equal total ({expected})"
            )


def calculate_payment(total_price_m: float, plan: PaymentPlan | str) -> PaymentBreakdown:
    """
    Calculates initial payment and remaining balance.
    Guarantees initial + remaining == total.
    """
    if isinstance(plan, str):
        plan = PaymentPlan.from_input(plan)

    if total_price_m < 0:
        raise ValueError("Total price cannot be negative.")

    total = round(float(total_price_m), 2)

    if plan == PaymentPlan.FULL_UPFRONT:
        initial = total
        remaining = 0.0
    elif plan == PaymentPlan.SPLIT_50_50:
        # Round upfront deposit to 2 decimal places
        initial = round(total / 2.0, 2)
        # Remaining balance is strictly the difference to prevent any rounding drift
        remaining = round(total - initial, 2)
    else:
        raise ValueError(f"Unsupported plan: {plan}")

    return PaymentBreakdown(
        total_price_m=total,
        plan=plan,
        initial_payment_m=initial,
        remaining_balance_m=remaining,
    )


def format_m(amount_m: float) -> str:
    """Formats an amount in M for Discord embeds and user messages."""
    val = round(amount_m, 2)
    if val.is_integer():
        return f"{int(val)}M"
    return f"{val:g}M"
