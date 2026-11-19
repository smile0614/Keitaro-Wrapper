from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.keitaro import KeitaroClient

TREND_DAYS = 7


def _number(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def campaign_stats(client: KeitaroClient, campaign_keitaro_id: int, timezone: str, today: date | None = None) -> dict:
    today = today or datetime.now(ZoneInfo(timezone)).date()
    days = [today - timedelta(days=offset) for offset in range(TREND_DAYS - 1, -1, -1)]
    rows = client.build_report(
        {
            "range": {"from": days[0].isoformat(), "to": today.isoformat(), "timezone": timezone},
            "dimensions": ["stream_id", "offer_id", "day"],
            "measures": ["clicks", "conversions", "revenue"],
            "filters": [{"name": "campaign_id", "operator": "EQUALS", "expression": campaign_keitaro_id}],
        }
    )
    return summarize(rows, days)


def summarize(rows: list[dict], days: list[date]) -> dict:
    day_index = {day.isoformat(): index for index, day in enumerate(days)}
    today_key = days[-1].isoformat()
    streams: dict[str, dict] = {}
    offers: dict[str, dict] = {}

    for row in rows:
        stream_id = row.get("stream_id")
        day = str(row.get("day", ""))[:10]
        clicks = int(_number(row.get("clicks")))
        stream = streams.setdefault(str(stream_id), {"clicks_today": 0})
        if day == today_key:
            stream["clicks_today"] += clicks

        offer_id = row.get("offer_id")
        if not offer_id:
            continue
        key = f"{stream_id}:{offer_id}"
        offer = offers.setdefault(
            key, {"clicks": 0, "conversions": 0, "revenue": 0.0, "daily_clicks": [0] * len(days)}
        )
        offer["clicks"] += clicks
        offer["conversions"] += int(_number(row.get("conversions")))
        offer["revenue"] = round(offer["revenue"] + _number(row.get("revenue")), 2)
        if day in day_index:
            offer["daily_clicks"][day_index[day]] += clicks

    return {"days": [day.isoformat() for day in days], "streams": streams, "offers": offers}
