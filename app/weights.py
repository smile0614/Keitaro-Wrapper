from dataclasses import dataclass


@dataclass
class WeightItem:
    key: int
    active: bool
    pinned: bool
    share: int


class WeightError(ValueError):
    pass


def rebalance(items: list[WeightItem]) -> dict[int, int]:
    result = {item.key: 0 for item in items}
    active = [item for item in items if item.active]
    pinned = [item for item in active if item.pinned]
    free = [item for item in active if not item.pinned]

    pinned_total = sum(item.share for item in pinned)
    if pinned_total > 100:
        raise WeightError(f"Pinned shares add up to {pinned_total}%, which is more than 100%")

    for item in pinned:
        result[item.key] = item.share

    if not free:
        return result

    remaining = 100 - pinned_total
    base, extra = divmod(remaining, len(free))
    for index, item in enumerate(free):
        result[item.key] = base + (1 if index < extra else 0)
    return result


def total_share(shares: dict[int, int]) -> int:
    return sum(shares.values())
