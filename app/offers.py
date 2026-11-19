import time

from app.keitaro import KeitaroClient, KeitaroError

CACHE_SECONDS = 60


class OfferDirectory:
    def __init__(self, client: KeitaroClient):
        self._client = client
        self._offers: dict[int, dict] = {}
        self._unavailable: dict[int, dict] = {}
        self._loaded_at = 0.0

    def _ensure_loaded(self) -> None:
        if time.monotonic() - self._loaded_at < CACHE_SECONDS:
            return
        self._offers = {offer["id"]: offer for offer in self._client.list_offers()}
        self._unavailable = {}
        self._loaded_at = time.monotonic()

    def search(self, query: str, limit: int = 20) -> list[dict]:
        self._ensure_loaded()
        query = query.strip().lower()
        matches = [
            self._short(offer)
            for offer in self._offers.values()
            if not query or query in str(offer["id"]) or query in offer["name"].lower()
        ]
        if query.isdigit() and not any(match["id"] == int(query) for match in matches):
            matches.insert(0, self._lookup(int(query)))
        return matches[:limit]

    def info(self, offer_id: int) -> dict:
        return self._lookup(offer_id)

    def all(self) -> list[dict]:
        self._ensure_loaded()
        return [self._short(offer) for offer in sorted(self._offers.values(), key=lambda offer: offer["id"])]

    def _lookup(self, offer_id: int) -> dict:
        self._ensure_loaded()
        if offer_id in self._offers:
            return self._short(self._offers[offer_id])
        if offer_id in self._unavailable:
            return self._unavailable[offer_id]
        try:
            offer = self._client.get_offer(offer_id)
        except KeitaroError:
            placeholder = {"id": offer_id, "name": f"Offer #{offer_id}", "preview_path": None, "country": [], "state": None}
            self._unavailable[offer_id] = placeholder
            return placeholder
        self._offers[offer_id] = offer
        return self._short(offer)

    @staticmethod
    def _short(offer: dict) -> dict:
        return {
            "id": offer["id"],
            "name": offer["name"],
            "preview_path": offer.get("preview_path") or None,
            "country": offer.get("country") or [],
            "state": offer.get("state"),
        }
