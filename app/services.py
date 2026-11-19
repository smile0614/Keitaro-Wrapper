import re
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.keitaro import KeitaroClient, KeitaroError
from app.models import ACTIVE, REMOVED, Campaign, Stream, StreamOffer
from app.offers import OfferDirectory
from app.weights import WeightItem, rebalance


class ServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


GEO_PATTERN = re.compile(r"^[A-Z]{2}$")


def parse_geos(raw: str) -> list[str]:
    geos = [part.strip().upper() for part in re.split(r"[,\s]+", raw) if part.strip()]
    if not geos:
        raise ServiceError("Specify at least one country code")
    invalid = [geo for geo in geos if not GEO_PATTERN.match(geo)]
    if invalid:
        raise ServiceError(f"Invalid country codes: {', '.join(invalid)}. Use two letters, e.g. AU, MX")
    return list(dict.fromkeys(geos))


def with_prefix(name: str) -> str:
    name = name.strip()
    if not name:
        raise ServiceError("Campaign name is required")
    prefix = get_settings().campaign_prefix
    return name if name.startswith(prefix) else prefix + name


def make_alias(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "campaign"
    return f"{slug}-{secrets.token_hex(3)}"


def create_campaign(
    db: Session,
    client: KeitaroClient,
    directory: OfferDirectory,
    *,
    name: str,
    geo: str,
    offer_id: int,
    domain_id: int,
    group_id: int,
    traffic_source_id: int,
) -> Campaign:
    geos = parse_geos(geo)
    full_name = with_prefix(name)

    created = client.create_campaign(
        {
            "name": full_name,
            "alias": make_alias(full_name),
            "type": "position",
            "domain_id": domain_id,
            "group_id": group_id,
            "traffic_source_id": traffic_source_id,
        }
    )
    keitaro_id = created["id"]
    try:
        client.create_stream(
            {
                "campaign_id": keitaro_id,
                "type": "regular",
                "name": f"{','.join(geos)} -> Google",
                "position": 1,
                "state": "active",
                "action_type": "http",
                "action_payload": get_settings().google_url,
                "schema": "redirect",
                "filters": [{"name": "country", "mode": "accept", "payload": geos}],
            }
        )
        client.create_stream(
            {
                "campaign_id": keitaro_id,
                "type": "regular",
                "name": "Offers",
                "position": 2,
                "state": "active",
                "action_type": "http",
                "schema": "landings",
                "offers": [{"offer_id": offer_id, "share": 100, "state": "active"}],
            }
        )
    except KeitaroError:
        try:
            client.delete_campaign(keitaro_id)
        except KeitaroError:
            pass
        raise

    campaign = Campaign(keitaro_id=keitaro_id, name=created["name"], alias=created.get("alias"))
    db.add(campaign)
    db.flush()
    sync_campaign(db, client, directory, campaign)
    db.commit()
    return campaign


def import_campaign(db: Session, client: KeitaroClient, directory: OfferDirectory, keitaro_id: int) -> Campaign:
    remote = client.get_campaign(keitaro_id)
    campaign = db.scalar(select(Campaign).where(Campaign.keitaro_id == keitaro_id))
    if campaign is None:
        campaign = Campaign(keitaro_id=keitaro_id, name=remote["name"], alias=remote.get("alias"))
        db.add(campaign)
    else:
        campaign.name = remote["name"]
        campaign.alias = remote.get("alias")
    db.flush()
    sync_campaign(db, client, directory, campaign)
    db.commit()
    return campaign


def sync_campaign(
    db: Session,
    client: KeitaroClient,
    directory: OfferDirectory,
    campaign: Campaign,
) -> None:
    remote_streams = client.get_streams(campaign.keitaro_id)
    local_streams = {stream.keitaro_id: stream for stream in campaign.streams}
    remote_ids = set()

    for remote in remote_streams:
        remote_ids.add(remote["id"])
        stream = local_streams.get(remote["id"])
        if stream is None:
            stream = Stream(keitaro_id=remote["id"], campaign=campaign, has_offers=False)
            db.add(stream)
        stream.name = remote.get("name") or f"Stream #{remote['id']}"
        stream.position = remote.get("position") or 0
        remote_offers = {
            link["offer_id"]: link["share"]
            for link in remote.get("offers") or []
            if link.get("state", ACTIVE) == ACTIVE
        }
        if remote_offers:
            stream.has_offers = True
        if stream.has_offers:
            _sync_stream_offers(directory, stream, remote_offers)

    for keitaro_id, stream in local_streams.items():
        if keitaro_id not in remote_ids:
            campaign.streams.remove(stream)


def _sync_stream_offers(directory: OfferDirectory, stream: Stream, remote_offers: dict[int, int]) -> None:
    local = {row.offer_id: row for row in stream.offers}

    for offer_id, row in local.items():
        if offer_id in remote_offers:
            continue
        if row.published_state is None:
            stream.offers.remove(row)
            continue
        row.state = REMOVED
        row.published_state = REMOVED
        row.share = 0
        row.published_share = 0
        row.pinned = False

    for offer_id, share in remote_offers.items():
        row = local.get(offer_id)
        if row is None:
            row = _new_row(directory.info(offer_id))
            stream.offers.append(row)
        elif row.preview_path is None:
            row.preview_path = directory.info(offer_id)["preview_path"]
        row.state = ACTIVE
        row.published_state = ACTIVE
        row.share = share
        row.published_share = share


def _new_row(offer: dict) -> StreamOffer:
    return StreamOffer(
        offer_id=offer["id"],
        offer_name=offer["name"],
        preview_path=offer["preview_path"],
        state=ACTIVE,
        share=0,
        pinned=False,
        published_state=None,
        published_share=0,
    )


def _rebalance(stream: Stream) -> None:
    items = [
        WeightItem(key=row.offer_id, active=row.state == ACTIVE, pinned=row.pinned, share=row.share)
        for row in stream.offers
    ]
    try:
        shares = rebalance(items)
    except ValueError as error:
        raise ServiceError(str(error)) from error
    for row in stream.offers:
        row.share = shares[row.offer_id]


def get_stream(db: Session, stream_id: int) -> Stream:
    stream = db.get(Stream, stream_id)
    if stream is None:
        raise ServiceError("Stream not found", 404)
    return stream


def get_row(db: Session, stream_id: int, offer_id: int) -> StreamOffer:
    row = db.scalar(
        select(StreamOffer).where(StreamOffer.stream_id == stream_id, StreamOffer.offer_id == offer_id)
    )
    if row is None:
        raise ServiceError("Offer is not in this stream", 404)
    return row


def add_offer(db: Session, directory: OfferDirectory, stream_id: int, offer_id: int) -> Stream:
    stream = get_stream(db, stream_id)
    if not stream.has_offers:
        raise ServiceError("This stream does not distribute traffic between offers")
    existing = next((row for row in stream.offers if row.offer_id == offer_id), None)
    if existing is not None and existing.state == ACTIVE:
        raise ServiceError("This offer is already in the stream")
    if existing is not None:
        existing.state = ACTIVE
    else:
        stream.offers.append(_new_row(directory.info(offer_id)))
    _rebalance(stream)
    db.commit()
    return stream


def remove_offer(db: Session, stream_id: int, offer_id: int) -> Stream:
    stream = get_stream(db, stream_id)
    row = get_row(db, stream_id, offer_id)
    if row.published_state is None:
        stream.offers.remove(row)
    else:
        row.state = REMOVED
        row.pinned = False
    _rebalance(stream)
    db.commit()
    return stream


def bring_back(db: Session, stream_id: int, offer_id: int) -> Stream:
    stream = get_stream(db, stream_id)
    row = get_row(db, stream_id, offer_id)
    if row.state == ACTIVE:
        raise ServiceError("This offer is already active")
    row.state = ACTIVE
    _rebalance(stream)
    db.commit()
    return stream


def set_pin(db: Session, stream_id: int, offer_id: int, pinned: bool, share: int | None) -> Stream:
    stream = get_stream(db, stream_id)
    row = get_row(db, stream_id, offer_id)
    if row.state != ACTIVE:
        raise ServiceError("Only active offers can be pinned")
    row.pinned = pinned
    if share is not None:
        if not 0 <= share <= 100:
            raise ServiceError("Share must be between 0 and 100")
        row.share = share
        _rebalance(stream)
    db.commit()
    return stream


def cancel(db: Session, stream_id: int) -> Stream:
    stream = get_stream(db, stream_id)
    for row in list(stream.offers):
        if row.published_state is None:
            stream.offers.remove(row)
            continue
        row.state = row.published_state
        row.share = row.published_share
        if row.state != ACTIVE:
            row.pinned = False
    db.commit()
    return stream


def publish(db: Session, client: KeitaroClient, directory: OfferDirectory, stream_id: int) -> Stream:
    stream = get_stream(db, stream_id)
    active = [row for row in stream.offers if row.state == ACTIVE]
    if not active:
        raise ServiceError("A stream needs at least one active offer")
    total = sum(row.share for row in active)
    if total != 100:
        raise ServiceError(f"Shares must add up to 100%, now {total}%")

    updated = client.update_stream(
        stream.keitaro_id,
        {"offers": [{"offer_id": row.offer_id, "share": row.share, "state": ACTIVE} for row in active]},
    )

    remote_offers = {
        link["offer_id"]: link["share"]
        for link in updated.get("offers") or []
        if link.get("state", ACTIVE) == ACTIVE
    }
    _sync_stream_offers(directory, stream, remote_offers)
    db.commit()
    return stream


def is_stream_dirty(stream: Stream) -> bool:
    return any(row.is_dirty for row in stream.offers)
