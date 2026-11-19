from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import services
from app.config import get_settings
from app.db import get_db
from app.keitaro import KeitaroClient, KeitaroError, get_keitaro
from app.models import Campaign
from app.offers import OfferDirectory
from app.schemas import (
    CampaignCreate,
    CampaignDetail,
    CampaignImport,
    CampaignOut,
    OfferAdd,
    PinUpdate,
    StreamOut,
    campaign_detail,
    campaign_out,
    preview_url,
    stream_out,
)
from app.stats import campaign_stats

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Keitaro Wrapper")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@lru_cache
def get_directory() -> OfferDirectory:
    return OfferDirectory(get_keitaro())


@app.exception_handler(KeitaroError)
def keitaro_error_handler(request: Request, error: KeitaroError):
    status = error.status_code if 400 <= error.status_code < 500 else 502
    return JSONResponse({"detail": f"Keitaro: {error.message}"}, status_code=status)


@app.exception_handler(services.ServiceError)
def service_error_handler(request: Request, error: services.ServiceError):
    return JSONResponse({"detail": error.message}, status_code=error.status_code)


@app.get("/", include_in_schema=False)
def index_page():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/campaigns/{campaign_id}", include_in_schema=False)
def campaign_page(campaign_id: int):
    return FileResponse(STATIC_DIR / "campaign.html")


@app.get("/api/settings")
def read_settings():
    settings = get_settings()
    return {"campaign_prefix": settings.campaign_prefix, "keitaro_url": settings.keitaro_url}


@app.get("/api/keitaro/options")
def keitaro_options(client: KeitaroClient = Depends(get_keitaro)):
    def short(items):
        return [{"id": item["id"], "name": item["name"]} for item in items]

    return {
        "domains": short(client.list_domains()),
        "groups": short(client.list_campaign_groups()),
        "traffic_sources": short(client.list_traffic_sources()),
    }


@app.get("/api/offers")
def search_offers(q: str = "", directory: OfferDirectory = Depends(get_directory)):
    return directory.search(q)


@app.get("/api/offers/all")
def all_offers(directory: OfferDirectory = Depends(get_directory)):
    return [{**offer, "preview_url": preview_url(offer["preview_path"])} for offer in directory.all()]


@app.get("/api/campaigns", response_model=list[CampaignOut])
def list_campaigns(db: Session = Depends(get_db)):
    campaigns = db.scalars(select(Campaign).order_by(Campaign.id.desc())).all()
    url = get_settings().keitaro_url
    return [campaign_out(campaign, url) for campaign in campaigns]


@app.post("/api/campaigns", response_model=CampaignDetail, status_code=201)
def create_campaign(
    body: CampaignCreate,
    db: Session = Depends(get_db),
    client: KeitaroClient = Depends(get_keitaro),
    directory: OfferDirectory = Depends(get_directory),
):
    campaign = services.create_campaign(db, client, directory, **body.model_dump())
    return campaign_detail(campaign, get_settings().keitaro_url)


@app.post("/api/campaigns/import", response_model=CampaignDetail)
def import_campaign(
    body: CampaignImport,
    db: Session = Depends(get_db),
    client: KeitaroClient = Depends(get_keitaro),
    directory: OfferDirectory = Depends(get_directory),
):
    campaign = services.import_campaign(db, client, directory, body.keitaro_id)
    return campaign_detail(campaign, get_settings().keitaro_url)


@app.get("/api/campaigns/{campaign_id}", response_model=CampaignDetail)
def read_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise services.ServiceError("Campaign not found", 404)
    return campaign_detail(campaign, get_settings().keitaro_url)


@app.get("/api/campaigns/{campaign_id}/stats")
def read_campaign_stats(
    campaign_id: int,
    db: Session = Depends(get_db),
    client: KeitaroClient = Depends(get_keitaro),
):
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise services.ServiceError("Campaign not found", 404)
    return campaign_stats(client, campaign.keitaro_id, get_settings().keitaro_timezone)


@app.post("/api/campaigns/{campaign_id}/fetch", response_model=CampaignDetail)
def fetch_streams(
    campaign_id: int,
    db: Session = Depends(get_db),
    client: KeitaroClient = Depends(get_keitaro),
    directory: OfferDirectory = Depends(get_directory),
):
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise services.ServiceError("Campaign not found", 404)
    services.sync_campaign(db, client, directory, campaign)
    db.commit()
    return campaign_detail(campaign, get_settings().keitaro_url)


@app.post("/api/streams/{stream_id}/offers", response_model=StreamOut)
def add_offer(
    stream_id: int,
    body: OfferAdd,
    db: Session = Depends(get_db),
    directory: OfferDirectory = Depends(get_directory),
):
    return stream_out(services.add_offer(db, directory, stream_id, body.offer_id))


@app.post("/api/streams/{stream_id}/offers/{offer_id}/remove", response_model=StreamOut)
def remove_offer(stream_id: int, offer_id: int, db: Session = Depends(get_db)):
    return stream_out(services.remove_offer(db, stream_id, offer_id))


@app.post("/api/streams/{stream_id}/offers/{offer_id}/bring-back", response_model=StreamOut)
def bring_back(stream_id: int, offer_id: int, db: Session = Depends(get_db)):
    return stream_out(services.bring_back(db, stream_id, offer_id))


@app.post("/api/streams/{stream_id}/offers/{offer_id}/pin", response_model=StreamOut)
def pin_offer(stream_id: int, offer_id: int, body: PinUpdate, db: Session = Depends(get_db)):
    return stream_out(services.set_pin(db, stream_id, offer_id, body.pinned, body.share))


@app.post("/api/streams/{stream_id}/cancel", response_model=StreamOut)
def cancel_changes(stream_id: int, db: Session = Depends(get_db)):
    return stream_out(services.cancel(db, stream_id))


@app.post("/api/streams/{stream_id}/publish", response_model=StreamOut)
def publish_stream(
    stream_id: int,
    db: Session = Depends(get_db),
    client: KeitaroClient = Depends(get_keitaro),
    directory: OfferDirectory = Depends(get_directory),
):
    return stream_out(services.publish(db, client, directory, stream_id))
