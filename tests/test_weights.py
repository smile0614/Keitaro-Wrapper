import pytest

from app.weights import WeightError, WeightItem, rebalance


def items(*specs):
    return [WeightItem(key=index, active=active, pinned=pinned, share=share) for index, (active, pinned, share) in enumerate(specs)]


def test_equal_split_puts_remainder_first():
    assert rebalance(items((True, False, 0), (True, False, 0), (True, False, 0))) == {0: 34, 1: 33, 2: 33}


def test_four_offers_get_25_each():
    shares = rebalance(items(*[(True, False, 0)] * 4))
    assert set(shares.values()) == {25}


def test_removed_offer_gets_zero():
    assert rebalance(items((True, False, 50), (False, False, 50), (True, False, 0))) == {0: 50, 1: 0, 2: 50}


def test_pinned_share_is_kept():
    assert rebalance(items((True, True, 25), (True, False, 0), (True, False, 0))) == {0: 25, 1: 38, 2: 37}


def test_only_pinned_offers_keep_their_values():
    assert rebalance(items((True, True, 30), (True, True, 30))) == {0: 30, 1: 30}


def test_pinned_over_100_is_rejected():
    with pytest.raises(WeightError):
        rebalance(items((True, True, 70), (True, True, 40)))
