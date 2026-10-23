"""
Tests for core/calculator.py:
- Fixed-point Decimal precision
- 50/50 payment plan calculations and rounding guarantees
- One-Time Full payment plan calculations
- Invariant equation: initial_payment + remaining_balance == total_price across odd, fractional, and large prices
- Formatting utilities
"""

from decimal import Decimal
import pytest
from core.calculator import calculate_payment, format_m, PaymentPlan, PaymentMethod, to_decimal


def test_one_time_full_payment():
    breakdown = calculate_payment(150.0, PaymentPlan.FULL_UPFRONT)
    assert breakdown.total_price_m == Decimal("150.00")
    assert breakdown.plan == PaymentPlan.FULL_UPFRONT
    assert breakdown.initial_payment_m == Decimal("150.00")
    assert breakdown.remaining_balance_m == Decimal("0.00")
    assert breakdown.initial_payment_m + breakdown.remaining_balance_m == breakdown.total_price_m


def test_50_50_split_even_amount():
    breakdown = calculate_payment(150.0, PaymentPlan.SPLIT_50_50)
    assert breakdown.total_price_m == Decimal("150.00")
    assert breakdown.initial_payment_m == Decimal("75.00")
    assert breakdown.remaining_balance_m == Decimal("75.00")
    assert breakdown.initial_payment_m + breakdown.remaining_balance_m == breakdown.total_price_m


def test_50_50_split_odd_amount():
    # 75M odd price
    breakdown = calculate_payment(75.0, PaymentPlan.SPLIT_50_50)
    assert breakdown.total_price_m == Decimal("75.00")
    assert breakdown.initial_payment_m == Decimal("37.50")
    assert breakdown.remaining_balance_m == Decimal("37.50")
    assert breakdown.initial_payment_m + breakdown.remaining_balance_m == breakdown.total_price_m

    # 35M odd price
    breakdown35 = calculate_payment(35.0, PaymentPlan.SPLIT_50_50)
    assert breakdown35.total_price_m == Decimal("35.00")
    assert breakdown35.initial_payment_m == Decimal("17.50")
    assert breakdown35.remaining_balance_m == Decimal("17.50")
    assert breakdown35.initial_payment_m + breakdown35.remaining_balance_m == breakdown35.total_price_m

    # 1M odd price
    breakdown1 = calculate_payment(1.0, PaymentPlan.SPLIT_50_50)
    assert breakdown1.total_price_m == Decimal("1.00")
    assert breakdown1.initial_payment_m == Decimal("0.50")
    assert breakdown1.remaining_balance_m == Decimal("0.50")
    assert breakdown1.initial_payment_m + breakdown1.remaining_balance_m == breakdown1.total_price_m


def test_50_50_split_fractional_amounts():
    # Low raids: 2.5M
    breakdown = calculate_payment(2.5, PaymentPlan.SPLIT_50_50)
    assert breakdown.total_price_m == Decimal("2.50")
    assert breakdown.initial_payment_m == Decimal("1.25")
    assert breakdown.remaining_balance_m == Decimal("1.25")
    assert breakdown.initial_payment_m + breakdown.remaining_balance_m == breakdown.total_price_m

    # Scrap metal: 0.1M (100K)
    breakdown_small = calculate_payment(0.1, PaymentPlan.SPLIT_50_50)
    assert breakdown_small.total_price_m == Decimal("0.10")
    assert breakdown_small.initial_payment_m == Decimal("0.05")
    assert breakdown_small.remaining_balance_m == Decimal("0.05")
    assert breakdown_small.initial_payment_m + breakdown_small.remaining_balance_m == breakdown_small.total_price_m

    # 0.05M
    b_odd_cents = calculate_payment("0.05", PaymentPlan.SPLIT_50_50)
    assert b_odd_cents.total_price_m == Decimal("0.05")
    assert b_odd_cents.initial_payment_m == Decimal("0.03")
    assert b_odd_cents.remaining_balance_m == Decimal("0.02")
    assert b_odd_cents.initial_payment_m + b_odd_cents.remaining_balance_m == Decimal("0.05")


def test_invariant_broad_exact_equality():
    """Verify initial + remaining == total across all catalog prices and odd decimals."""
    prices = [
        "0.1", "0.25", "0.5", "1.0", "2.0", "2.5", "5.0", "7.0", "10.0", "15.0",
        "17.0", "20.0", "30.0", "35.0", "40.0", "45.0", "50.0", "55.0", "60.0",
        "70.0", "75.0", "85.0", "90.0", "100.0", "120.0", "125.0", "130.0",
        "145.0", "150.0", "160.0", "170.0", "175.0", "333.33", "99.99"
    ]
    for p in prices:
        for plan in [PaymentPlan.SPLIT_50_50, PaymentPlan.FULL_UPFRONT]:
            b = calculate_payment(p, plan)
            assert (b.initial_payment_m + b.remaining_balance_m) == b.total_price_m


def test_invalid_plan():
    with pytest.raises(ValueError):
        calculate_payment(100.0, "INVALID_PLAN")


def test_negative_price():
    with pytest.raises(ValueError):
        calculate_payment(-50.0, PaymentPlan.SPLIT_50_50)


def test_format_m():
    assert format_m(150.0) == "150M"
    assert format_m(37.5) == "37.5M"
    assert format_m(0.1) == "0.1M"
    assert format_m(1.25) == "1.25M"
    assert format_m("0.05") == "0.05M"
