"""
Tests for core/calculator.py:
- 50/50 payment plan calculations and rounding guarantees
- One-Time Full payment plan calculations
- Invariant equation: initial_payment + remaining_balance == total_price
- Formatting utilities
"""

import pytest
from core.calculator import calculate_payment, format_m, PaymentPlan, PaymentMethod, PaymentBreakdown


def test_one_time_full_payment():
    breakdown = calculate_payment(150.0, PaymentPlan.FULL_UPFRONT)
    assert breakdown.total_price_m == 150.0
    assert breakdown.plan == PaymentPlan.FULL_UPFRONT
    assert breakdown.initial_payment_m == 150.0
    assert breakdown.remaining_balance_m == 0.0
    assert breakdown.initial_payment_m + breakdown.remaining_balance_m == breakdown.total_price_m


def test_50_50_split_even_amount():
    breakdown = calculate_payment(150.0, PaymentPlan.SPLIT_50_50)
    assert breakdown.total_price_m == 150.0
    assert breakdown.initial_payment_m == 75.0
    assert breakdown.remaining_balance_m == 75.0
    assert breakdown.initial_payment_m + breakdown.remaining_balance_m == breakdown.total_price_m


def test_50_50_split_odd_amount():
    breakdown = calculate_payment(75.0, PaymentPlan.SPLIT_50_50)
    assert breakdown.total_price_m == 75.0
    assert breakdown.initial_payment_m == 37.5
    assert breakdown.remaining_balance_m == 37.5
    assert breakdown.initial_payment_m + breakdown.remaining_balance_m == breakdown.total_price_m


def test_50_50_split_fractional_amounts():
    # Low raids: 2.5M
    breakdown = calculate_payment(2.5, PaymentPlan.SPLIT_50_50)
    assert breakdown.total_price_m == 2.5
    assert breakdown.initial_payment_m == 1.25
    assert breakdown.remaining_balance_m == 1.25
    assert round(breakdown.initial_payment_m + breakdown.remaining_balance_m, 2) == 2.5

    # Scrap metal: 0.1M (100K)
    breakdown_small = calculate_payment(0.1, PaymentPlan.SPLIT_50_50)
    assert breakdown_small.total_price_m == 0.1
    assert breakdown_small.initial_payment_m == 0.05
    assert breakdown_small.remaining_balance_m == 0.05
    assert round(breakdown_small.initial_payment_m + breakdown_small.remaining_balance_m, 2) == 0.1


def test_invariant_across_multiple_values():
    """Verify initial + remaining == total across a wide spread of real values."""
    prices = [1.0, 2.0, 5.0, 7.0, 10.0, 15.0, 17.0, 20.0, 30.0, 35.0, 45.0, 50.0, 55.0, 60.0, 75.0, 85.0, 90.0, 100.0, 120.0, 125.0, 130.0, 145.0, 150.0, 170.0, 175.0]
    for p in prices:
        for plan in [PaymentPlan.SPLIT_50_50, PaymentPlan.FULL_UPFRONT]:
            b = calculate_payment(p, plan)
            assert round(b.initial_payment_m + b.remaining_balance_m, 2) == round(p, 2)


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
