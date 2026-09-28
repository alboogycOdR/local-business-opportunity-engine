# Incident runbook

If `/ready` fails, inspect PostgreSQL/Redis and `/v1/system/status`. If migrations are behind, back up first and run the migration runner. If an export is missing, verify writable roots and rerun the relevant operator export. If a safety boundary is suspected, stop the workflow, preserve logs, confirm `system_delivery_count=0`, and escalate before changing code.
