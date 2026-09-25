# integrations/maps-scraper

Sprint 2 provides a thin `MapsScraperAdapter` in `integrations/maps_scraper`.
It talks to a separately running Mahanaicoach/google-maps-scraper-kit service;
the upstream scraper is not copied into this repository or the core domain.

Start the local scraper separately at `http://localhost:8080`, then enable it
deliberately in `.env`:

```text
LBOE_FEATURE_MAPS_SCRAPER=true
LBOE_DISCOVERY_KILL_SWITCH=false
LBOE_MAPS_SCRAPER_URL=http://localhost:8080
LBOE_DISCOVERY_MAX_CONCURRENCY=1
LBOE_DISCOVERY_TIMEOUT_SECONDS=300
```

The adapter submits one conservative job at a time through `POST /api/v1/jobs`,
polls `GET /api/v1/jobs/{id}`, and downloads the lean CSV result from
`GET /api/v1/jobs/{id}/download`. It stores only normalized discovery fields and
provenance; raw provider payloads are never persisted. The kill switch or a
disabled feature flag fails closed. Treat scraped data as leads requiring review,
not as permission for outreach.
