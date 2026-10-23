"""
Blox Fruit Services - Payment Calculator & Rounding Rules.
Uses Python Decimal for exact fixed-point precision (avoiding floating point errors).
Calculates initial deposits and remaining balances for:
1. 50/50 Payment (50% upfront, 50% on completion)
2. One-Time Full Payment (100% upfront, 0M balance)

Guarantees exact mathematical invariant:
    initial_payment_m + remaining_balance_m == total_price_m
"""

from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Union


TWOPLACES = Decimal("0.01")


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


class PaymentBreakdown:
    def __init__(
        self,
        total_price_m: Decimal,
        plan: PaymentPlan,
        initial_payment_m: Decimal,
        remaining_balance_m: Decimal,
    ):
        self.total_price_m = total_price_m.quantize(TWOPLACES)
        self.plan = plan
        self.initial_payment_m = initial_payment_m.quantize(TWOPLACES)
        self.remaining_balance_m = remaining_balance_m.quantize(TWOPLACES)

        # Invariant verification
        combined = (self.initial_payment_m + self.remaining_balance_m).quantize(TWOPLACES)
        if combined != self.total_price_m:
            raise ValueError(
                f"Calculation error: initial ({self.initial_payment_m}) + "
                f"remaining ({self.remaining_balance_m}) = {combined} does not equal total ({self.total_price_m})"
            )

    @property
    def total_price_float(self) -> float:
        return float(self.total_price_m)

    @property
    def initial_payment_float(self) -> float:
        return float(self.initial_payment_m)

    @property
    def remaining_balance_float(self) -> float:
        return float(self.remaining_balance_m)


def to_decimal(val: Union[Decimal, float, int, str]) -> Decimal:
    """Safely converts input to Decimal with 2 decimal places using ROUND_HALF_UP."""
    if isinstance(val, Decimal):
        return val.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    if isinstance(val, float):
        return Decimal(f"{val:.6f}").quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    return Decimal(str(val).strip()).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def calculate_payment(
    total_price: Union[Decimal, float, int, str],
    plan: Union[PaymentPlan, str],
) -> PaymentBreakdown:
    """
    Calculates initial payment and remaining balance using fixed-point Decimal precision.
    Guarantees initial + remaining == total.
    """
    if isinstance(plan, str):
        plan = PaymentPlan.from_input(plan)

    total = to_decimal(total_price)
    if total < Decimal("0"):
        raise ValueError("Total price cannot be negative.")

    if plan == PaymentPlan.FULL_UPFRONT:
        initial = total
        remaining = Decimal("0.00")
    elif plan == PaymentPlan.SPLIT_50_50:
        # Split in half with ROUND_HALF_UP
        initial = (total / Decimal("2")).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        # Remaining balance is strictly total - initial to guarantee exact invariant
        remaining = total - initial
    else:
        raise ValueError(f"Unsupported plan: {plan}")

    return PaymentBreakdown(
        total_price_m=total,
        plan=plan,
        initial_payment_m=initial,
        remaining_balance_m=remaining,
    )


def format_m(amount: Union[Decimal, float, int, str]) -> str:
    """Formats an amount in M for Discord embeds and user messages."""
    dec = to_decimal(amount)
    # If ends with .00, format as integer
    if dec == dec.to_integral_value():
        return f"{int(dec)}M"
    # Normalize trailing zeros (e.g. 37.50 -> 37.5)
    normalized = dec.normalize()
    # Format cleanly without exponential notation
    formatted = f"{dec:.2f}".rstrip("0").rstrip(".")
    return f"{formatted}M"
