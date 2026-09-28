# Security boundaries

LBOE does not send messages or sync inboxes/CRMs. Audit URLs retain SSRF
protection. Preview links validate hashed, expiring tokens and never expose raw
filesystem paths. Internal auth is optional for local development and required
for controlled deployment. Do not put credentials in logs, exports, or pages.

Additional v1 boundaries: LBOE does not process payments, create contracts or
e-signatures, store credentials, purchase domains, deploy websites automatically,
or export raw preview tokens/scraper payloads. Auth and storage status endpoints
redact secrets. Operator-entered contact, approval, and CRM records are
explicitly assertions rather than externally verified facts.
