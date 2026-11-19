import pytest
from sqlalchemy.orm import Session

from app import services
from app.db import Base, make_engine
from app.models import ACTIVE, REMOVED, Campaign
from app.offers import OfferDirectory


class FakeKeitaro:
    def __init__(self):
        self.streams = {
            10: {"id": 10, "name": "AU -> Google", "position": 1, "offers": []},
            11: {
                "id": 11,
                "name": "Offers",
                "position": 2,
                "offers": [
                    {"offer_id": 1, "share": 34, "state": "active"},
                    {"offer_id": 2, "share": 33, "state": "active"},
                    {"offer_id": 3, "share": 33, "state": "active"},
                ],
            },
        }

    def list_offers(self):
        return [{"id": offer_id, "name": f"Offer {offer_id}"} for offer_id in range(1, 6)]

    def get_offer(self, offer_id):
        return {"id": offer_id, "name": f"Offer {offer_id}"}

    def get_streams(self, campaign_id):
        return list(self.streams.values())

    def update_stream(self, stream_id, payload):
        self.streams[stream_id]["offers"] = payload["offers"]
        return self.streams[stream_id]


@pytest.fixture
def setup():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    client = FakeKeitaro()
    directory = OfferDirectory(client)
    campaign = Campaign(keitaro_id=1, name="test_campaign")
    db.add(campaign)
    db.flush()
    services.sync_campaign(db, client, directory, campaign)
    db.commit()
    offers_stream = next(stream for stream in campaign.streams if stream.has_offers)
    yield db, client, directory, campaign, offers_stream
    db.close()


def shares(stream):
    return {row.offer_id: (row.state, row.share) for row in stream.offers}


def test_fetch_keeps_stream_without_offers_as_plain_stream(setup):
    db, client, directory, campaign, stream = setup
    plain = next(stream for stream in campaign.streams if not stream.has_offers)
    assert plain.offers == []
    assert services.is_stream_dirty(stream) is False


def test_add_recalculates_and_marks_dirty(setup):
    db, client, directory, campaign, stream = setup
    services.add_offer(db, directory, stream.id, 4)
    assert shares(stream) == {1: (ACTIVE, 25), 2: (ACTIVE, 25), 3: (ACTIVE, 25), 4: (ACTIVE, 25)}
    assert services.is_stream_dirty(stream)
    assert len(client.streams[11]["offers"]) == 3


def test_cancel_drops_unpublished_additions(setup):
    db, client, directory, campaign, stream = setup
    services.add_offer(db, directory, stream.id, 4)
    services.cancel(db, stream.id)
    assert shares(stream) == {1: (ACTIVE, 34), 2: (ACTIVE, 33), 3: (ACTIVE, 33)}
    assert not services.is_stream_dirty(stream)


def test_publish_pushes_offers_to_keitaro(setup):
    db, client, directory, campaign, stream = setup
    services.add_offer(db, directory, stream.id, 4)
    services.publish(db, client, directory, stream.id)
    assert [offer["share"] for offer in client.streams[11]["offers"]] == [25, 25, 25, 25]
    assert not services.is_stream_dirty(stream)


def test_remove_publish_and_bring_back(setup):
    db, client, directory, campaign, stream = setup
    services.remove_offer(db, stream.id, 2)
    assert shares(stream)[2] == (REMOVED, 0)
    services.publish(db, client, directory, stream.id)
    assert [offer["offer_id"] for offer in client.streams[11]["offers"]] == [1, 3]
    assert shares(stream)[2] == (REMOVED, 0)

    services.bring_back(db, stream.id, 2)
    assert services.is_stream_dirty(stream)
    services.publish(db, client, directory, stream.id)
    assert sorted(offer["offer_id"] for offer in client.streams[11]["offers"]) == [1, 2, 3]


def test_offer_deleted_in_keitaro_becomes_removed_on_fetch(setup):
    db, client, directory, campaign, stream = setup
    client.streams[11]["offers"] = [{"offer_id": 1, "share": 100, "state": "active"}]
    services.sync_campaign(db, client, directory, campaign)
    db.commit()
    assert shares(stream) == {1: (ACTIVE, 100), 2: (REMOVED, 0), 3: (REMOVED, 0)}
    services.bring_back(db, stream.id, 3)
    assert shares(stream)[3] == (ACTIVE, 50)


def test_pinned_share_survives_changes(setup):
    db, client, directory, campaign, stream = setup
    services.set_pin(db, stream.id, 1, True, 20)
    assert shares(stream) == {1: (ACTIVE, 20), 2: (ACTIVE, 40), 3: (ACTIVE, 40)}
    services.add_offer(db, directory, stream.id, 4)
    assert shares(stream)[1] == (ACTIVE, 20)
    assert sum(share for state, share in shares(stream).values()) == 100
    services.remove_offer(db, stream.id, 2)
    assert shares(stream) == {1: (ACTIVE, 20), 2: (REMOVED, 0), 3: (ACTIVE, 40), 4: (ACTIVE, 40)}


def test_pin_toggle_keeps_shares_and_stream_published(setup):
    db, client, directory, campaign, stream = setup
    services.set_pin(db, stream.id, 2, True, None)
    assert shares(stream) == {1: (ACTIVE, 34), 2: (ACTIVE, 33), 3: (ACTIVE, 33)}
    assert next(row for row in stream.offers if row.offer_id == 2).pinned
    assert not services.is_stream_dirty(stream)

    services.set_pin(db, stream.id, 2, False, None)
    assert shares(stream) == {1: (ACTIVE, 34), 2: (ACTIVE, 33), 3: (ACTIVE, 33)}
    assert not services.is_stream_dirty(stream)


def test_pinned_share_is_used_on_next_change(setup):
    db, client, directory, campaign, stream = setup
    services.set_pin(db, stream.id, 1, True, None)
    services.add_offer(db, directory, stream.id, 4)
    assert shares(stream) == {1: (ACTIVE, 34), 2: (ACTIVE, 22), 3: (ACTIVE, 22), 4: (ACTIVE, 22)}


def test_publish_rejects_wrong_total(setup):
    db, client, directory, campaign, stream = setup
    services.set_pin(db, stream.id, 1, True, 10)
    services.set_pin(db, stream.id, 2, True, 10)
    services.set_pin(db, stream.id, 3, True, 10)
    with pytest.raises(services.ServiceError):
        services.publish(db, client, directory, stream.id)


def test_make_alias():
    alias = services.make_alias("test_akio_Campaign 1")
    assert alias.startswith("test-akio-campaign-1-")
    assert len(alias.rsplit("-", 1)[1]) == 6


def test_parse_geos():
    assert services.parse_geos("mx, au ,RO") == ["MX", "AU", "RO"]
    with pytest.raises(services.ServiceError):
        services.parse_geos("Mexico")
