from datetime import date, timedelta

from app.stats import campaign_stats, summarize

TODAY = date(2026, 11, 19)
DAYS = [TODAY - timedelta(days=offset) for offset in range(6, -1, -1)]


def test_summarize_groups_by_stream_and_offer():
    rows = [
        {"stream_id": 11, "offer_id": 1, "day": "2026-11-19", "clicks": 5, "conversions": 1, "revenue": "2.5"},
        {"stream_id": 11, "offer_id": 1, "day": "2026-11-17", "clicks": 3, "conversions": 0, "revenue": 0},
        {"stream_id": 11, "offer_id": 2, "day": "2026-11-19", "clicks": 2, "conversions": 0, "revenue": 0},
        {"stream_id": 10, "offer_id": None, "day": "2026-11-19", "clicks": 7, "conversions": 0, "revenue": 0},
    ]
    result = summarize(rows, DAYS)

    assert result["days"][-1] == "2026-11-19"
    assert result["streams"]["11"]["clicks_today"] == 7
    assert result["streams"]["10"]["clicks_today"] == 7
    assert result["offers"]["11:1"] == {
        "clicks": 8,
        "conversions": 1,
        "revenue": 2.5,
        "daily_clicks": [0, 0, 0, 0, 3, 0, 5],
    }
    assert result["offers"]["11:2"]["daily_clicks"][-1] == 2
    assert "10:None" not in result["offers"]


def test_campaign_stats_sends_seven_day_range():
    class Client:
        def build_report(self, payload):
            self.payload = payload
            return []

    client = Client()
    result = campaign_stats(client, 214834, "Europe/Moscow", today=TODAY)
    assert client.payload["range"] == {"from": "2026-11-13", "to": "2026-11-19", "timezone": "Europe/Moscow"}
    assert client.payload["filters"][0]["expression"] == 214834
    assert result == {"days": [day.isoformat() for day in DAYS], "streams": {}, "offers": {}}
