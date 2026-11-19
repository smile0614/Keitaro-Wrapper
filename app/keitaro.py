from functools import lru_cache
from typing import Any

import httpx

from app.config import get_settings


class KeitaroError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class KeitaroClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 30):
        self._client = httpx.Client(
            base_url=base_url.rstrip("/") + "/admin_api/v1",
            headers={"Api-Key": api_key, "Accept": "application/json"},
            timeout=timeout,
        )

    def _request(self, method: str, path: str, **kwargs) -> Any:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as error:
            raise KeitaroError(502, f"Keitaro is unreachable: {error}") from error
        if response.status_code >= 400:
            raise KeitaroError(response.status_code, self._error_message(response))
        if not response.content:
            return None
        return response.json()

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            return f"Keitaro returned HTTP {response.status_code}"
        if isinstance(body, dict) and body.get("error"):
            return str(body["error"])
        return f"Keitaro returned HTTP {response.status_code}: {body}"

    def list_domains(self) -> list[dict]:
        return self._request("GET", "/domains")

    def list_campaign_groups(self) -> list[dict]:
        return self._request("GET", "/groups", params={"type": "campaigns"})

    def list_traffic_sources(self) -> list[dict]:
        return self._request("GET", "/traffic_sources")

    def list_offers(self) -> list[dict]:
        return self._request("GET", "/offers")

    def get_offer(self, offer_id: int) -> dict:
        return self._request("GET", f"/offers/{offer_id}")

    def get_campaign(self, campaign_id: int) -> dict:
        return self._request("GET", f"/campaigns/{campaign_id}")

    def create_campaign(self, payload: dict) -> dict:
        return self._request("POST", "/campaigns", json=payload)

    def delete_campaign(self, campaign_id: int) -> None:
        self._request("DELETE", f"/campaigns/{campaign_id}")

    def get_streams(self, campaign_id: int) -> list[dict]:
        return self._request("GET", f"/campaigns/{campaign_id}/streams")

    def create_stream(self, payload: dict) -> dict:
        return self._request("POST", "/streams", json=payload)

    def update_stream(self, stream_id: int, payload: dict) -> dict:
        return self._request("PUT", f"/streams/{stream_id}", json=payload)

    def build_report(self, payload: dict) -> list[dict]:
        return self._request("POST", "/report/build", json=payload).get("rows") or []


@lru_cache
def get_keitaro() -> KeitaroClient:
    settings = get_settings()
    return KeitaroClient(settings.keitaro_url, settings.keitaro_api_key)
