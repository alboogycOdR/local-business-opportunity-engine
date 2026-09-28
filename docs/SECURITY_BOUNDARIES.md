# Security boundaries

LBOE does not send messages or sync inboxes/CRMs. Audit URLs retain SSRF
protection. Preview links validate hashed, expiring tokens and never expose raw
filesystem paths. Internal auth is optional for local development and required
for controlled deployment. Do not put credentials in logs, exports, or pages.
