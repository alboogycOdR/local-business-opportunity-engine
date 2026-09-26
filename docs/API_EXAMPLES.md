# API Examples

Examples use synthetic values only. Set a shell variable first:

```powershell
$base = "http://127.0.0.1:8000"
```

## Health and readiness

```powershell
Invoke-RestMethod "$base/health"
Invoke-RestMethod "$base/ready"
```

## Campaign and import

```powershell
$campaign = Invoke-RestMethod "$base/v1/campaigns" -Method Post -ContentType 'application/json' -Body (@{name='Synthetic Salon Pilot'; vertical='hair_salon'; geography='Cape Town'} | ConvertTo-Json)
$campaignId = $campaign.id
$import = Invoke-RestMethod "$base/v1/campaigns/$campaignId/import" -Method Post -ContentType 'application/json' -Body (@{format='json'; records=@(@{display_name='Synthetic Demo Salon'; category='hair salon'; locality='Cape Town'; address_text='Synthetic Cape Town'})} | ConvertTo-Json)
$businessId = $import.successes[0].business_id
```

## Discovery

```powershell
Invoke-RestMethod "$base/v1/campaigns/$campaignId/discover" -Method Post -ContentType 'application/json' -Body (@{queries=@('hair salons'); geography='Cape Town'; latitude=-33.9249; longitude=18.4241; max_results=5; idempotency_key='synthetic-discovery-1'} | ConvertTo-Json)
```

## Audit, score, brief, and demo

```powershell
Invoke-RestMethod "$base/v1/businesses/$businessId/audit" -Method Post -ContentType 'application/json' -Body (@{idempotency_key='synthetic-audit-1'} | ConvertTo-Json)
Invoke-RestMethod "$base/v1/businesses/$businessId/score" -Method Post -ContentType 'application/json' -Body (@{idempotency_key='synthetic-score-1'} | ConvertTo-Json)
Invoke-RestMethod "$base/v1/businesses/$businessId/brief" -Method Post -ContentType 'application/json' -Body (@{idempotency_key='synthetic-brief-1'} | ConvertTo-Json)
Invoke-RestMethod "$base/v1/businesses/$businessId/demo" -Method Post -ContentType 'application/json' -Body (@{idempotency_key='synthetic-demo-1'} | ConvertTo-Json)
```

## Review, draft, readiness, manual log, and CRM

Use the IDs returned by the previous calls. Review checklist values must be
explicitly passed by the operator. The manual log endpoint only records an
operator assertion and never sends a message.

```powershell
Invoke-RestMethod "$base/v1/demos/$demoId/review" -Method Post -ContentType 'application/json' -Body (@{decision='approve'; reviewer='operator'; checklist=@()} | ConvertTo-Json)
Invoke-RestMethod "$base/v1/businesses/$businessId/outreach-draft" -Method Post -ContentType 'application/json' -Body (@{idempotency_key='synthetic-draft-1'} | ConvertTo-Json)
Invoke-RestMethod "$base/v1/businesses/$businessId/outreach-readiness" -Method Post -ContentType 'application/json' -Body (@{outreach_draft_package_id=$packageId; decision='approve_for_manual_outreach'; reviewer='operator'; selected_channels=@('email'); consent_basis_type='public_business_contact_for_manual_outreach'; consent_basis_notes='Synthetic operator review.'} | ConvertTo-Json)
Invoke-RestMethod "$base/v1/businesses/$businessId/outreach-log" -Method Post -ContentType 'application/json' -Body (@{outreach_draft_package_id=$packageId; outreach_draft_message_id=$messageId; channel='email'; operator='operator'; sent_at=(Get-Date).ToUniversalTime().ToString('o'); notes='Manual log only; no system delivery.'} | ConvertTo-Json)
Invoke-RestMethod "$base/v1/businesses/$businessId/crm-event" -Method Post -ContentType 'application/json' -Body (@{event_type='reply_received'; channel='email'; operator='operator'; occurred_at=(Get-Date).ToUniversalTime().ToString('o'); summary='Synthetic reply recorded.'} | ConvertTo-Json)
```

## Reporting

```powershell
Invoke-RestMethod "$base/v1/reports/pilot?include_details=true"
Invoke-RestMethod "$base/v1/campaigns/$campaignId/reports/pilot"
```
