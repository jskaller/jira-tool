0037:
- Fix NOT NULL error for reports.filters_json by:
  * Adding filters_json to ORM model (default "{}")
  * Auto-migrating column (TEXT NOT NULL DEFAULT '{}') if missing
  * Backfilling empty/NULL values
  * Writing filters_json on report creation with the request filters
