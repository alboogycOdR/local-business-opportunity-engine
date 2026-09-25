# Sources and reference material

Accessed for the v0.1 blueprint on 2026-09-25.

## User-supplied repositories

### Google Maps Scraper Kit
https://github.com/Mahanaicoach/google-maps-scraper-kit

Role in architecture: experimental/high-volume discovery adapter. The repository wraps `gosom/google-maps-scraper`, exposes a local Docker/REST workflow, normalizes lead fields and includes rate-limit/responsible-use guidance.

### Google Maps Business Data Fetcher
https://github.com/deonna/google-maps-downloader

Role in architecture: enrichment reference. It uses Places API (New), parses Maps URLs, requests place data, transforms the response, analyzes a small review sample and emits JSON/Markdown.

## User-supplied workflow document

Google Doc: “How to Make Money With Websites (Without Leaving Your Job)”  
Document ID: `1KxwqVWCeDjZ8ZcA_pxqnaGQU3oQYnp9hcPi4vVqUZz4`

Role in architecture: commercial workflow reference — find no/weak website, collect information, generate a demo before outreach, then sell the outcome rather than an abstract promise.

## Official Google references

Places API (New) policies and attributions:  
https://developers.google.com/maps/documentation/places/web-service/policies

Place IDs and storage exception:  
https://developers.google.com/maps/documentation/places/web-service/place-id

Places API overview:  
https://developers.google.com/maps/documentation/places/web-service/overview

Google Maps Platform Terms:  
https://cloud.google.com/maps-platform/terms

Service Specific Terms:  
https://cloud.google.com/maps-platform/terms/maps-service-terms

Architecture implication: do not assume Places responses can be cached/rehosted indefinitely. Persist source-policy metadata, treat Place IDs as durable references, and handle photos/reviews/other Places content according to current attribution/storage terms.

## South African privacy/direct marketing reference

Information Regulator POPIA page:  
https://inforegulator.org.za/popia/

Protection of Personal Information Act 4 of 2013:  
https://www.gov.za/documents/protection-personal-information-act

Architecture implication: electronic direct marketing needs a consent-aware workflow. Public availability of a phone/email does not, by itself, become the system's authorization to send promotional messages. Maintain consent and suppression records and require human review during the pilot.

## Note

This package is a product/engineering blueprint, not legal advice. Terms and privacy rules can change; production launch should include a current policy/legal review for the jurisdictions and channels actually used.

