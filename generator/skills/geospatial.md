# Geospatial data

Read the supplied reference_data profile before designing an importer or query.
Use actual collection paths, nullability, provider IDs, field names and original coordinate systems.
Preserve the source payload or every source field alongside normalised indexed fields.
Use ST_GeomFromText with SRID 4326 for WKT supplied in longitude and latitude.
LINESTRING and MULTILINESTRING features are linear observations, not authoritative area boundaries.
GEOMETRYCOLLECTION and EMPTY values need explicit handling. Never fabricate replacement polygons.
Match linear features with ST_DWithin on geography using a documented configurable distance in metres.
Add a GiST geography expression index matching the distance query expression.
Never compare metre thresholds with geometry coordinates in degrees. Geography buffers use metres.
Use ST_Covers for authoritative polygon boundaries when actual polygon data is available.
Return original geometries and an explicit approximation indicator to the UI.
GPS input needs finite coordinates, range checks, monotonic timestamps, ownership and stale detection.
Source tariff values retain their published units. Do not guess units from a field name.
Render real source geometry and recorded routes, fit their actual bounds, and label uncertainty.
Derive demonstration route coordinates from actual valid source features. Do not assume that
arbitrary fixture coordinates lie inside an imported zone. Ignore empty geometries for matching.

