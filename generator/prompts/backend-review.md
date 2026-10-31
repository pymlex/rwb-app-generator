Independently review the actual generated backend against ALL source requirements and contracts.
This is a static review, never a claim that runtime tests passed. Read all supplied files.
Return concrete defects with exact nonempty source quotations from the named generated file.
Every source_quote must occur literally in that file, ignoring only whitespace differences.
Check compile evidence, ownership, matching seeded identities, stable seed IDs, JSON casing,
all real workflows, real geospatial queries, source data import, event histories, reminders,
idempotency and database-level concurrency protections, transactions, authorization and demo clock.
Read-only methods must return persisted data. Mutations must update persisted state and emit events.
Reject dead controls and methods returning success without their promised side effects.
Reject line containment used as a polygon geofence. Reject random duplicate startup seeds.
Reject init-only record property assignments. Reject default case-sensitive JSON deserialisation
for camelCase persisted DTOs. OwnerSubject is string and must match the Actor subject.
Do not demand real external payment access, enterprise OAuth or Kotlin: the case permits provider
adapters and PWA. Do not invent requirements. Cite only valid FR identifiers from analysis.
Severity critical or high means downstream generation must stop for correction.
passes_static_review is true only when there are no critical or high defects.
