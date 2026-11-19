from pydantic import BaseModel, Field

from app.config import get_settings
from app.models import Campaign, Stream


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    geo: str = Field(min_length=2)
    offer_id: int = Field(gt=0)
    domain_id: int = Field(gt=0)
    group_id: int = Field(gt=0)
    traffic_source_id: int = Field(gt=0)


class CampaignImport(BaseModel):
    keitaro_id: int = Field(gt=0)


class OfferAdd(BaseModel):
    offer_id: int = Field(gt=0)


class PinUpdate(BaseModel):
    pinned: bool
    share: int | None = Field(default=None, ge=0, le=100)


class OfferOut(BaseModel):
    offer_id: int
    name: str
    preview_url: str | None
    state: str
    share: int
    pinned: bool
    published_state: str | None
    published_share: int
    dirty: bool


class StreamOut(BaseModel):
    id: int
    keitaro_id: int
    name: str
    position: int
    has_offers: bool
    dirty: bool
    total_share: int
    offers: list[OfferOut]


class CampaignOut(BaseModel):
    id: int
    keitaro_id: int
    name: str
    alias: str | None
    keitaro_url: str


class CampaignDetail(CampaignOut):
    streams: list[StreamOut]


def preview_url(preview_path: str | None) -> str | None:
    if not preview_path:
        return None
    return get_settings().keitaro_url.rstrip("/") + preview_path


def stream_out(stream: Stream) -> StreamOut:
    offers = [
        OfferOut(
            offer_id=row.offer_id,
            name=row.offer_name,
            preview_url=preview_url(row.preview_path),
            state=row.state,
            share=row.share,
            pinned=row.pinned,
            published_state=row.published_state,
            published_share=row.published_share,
            dirty=row.is_dirty,
        )
        for row in stream.offers
    ]
    return StreamOut(
        id=stream.id,
        keitaro_id=stream.keitaro_id,
        name=stream.name,
        position=stream.position,
        has_offers=stream.has_offers,
        dirty=any(offer.dirty for offer in offers),
        total_share=sum(offer.share for offer in offers if offer.state == "active"),
        offers=offers,
    )


def campaign_out(campaign: Campaign, keitaro_url: str) -> CampaignOut:
    return CampaignOut(
        id=campaign.id,
        keitaro_id=campaign.keitaro_id,
        name=campaign.name,
        alias=campaign.alias,
        keitaro_url=f"{keitaro_url.rstrip('/')}/admin/#!/campaign/{campaign.keitaro_id}/main",
    )


def campaign_detail(campaign: Campaign, keitaro_url: str) -> CampaignDetail:
    return CampaignDetail(
        **campaign_out(campaign, keitaro_url).model_dump(),
        streams=[stream_out(stream) for stream in campaign.streams],
    )
