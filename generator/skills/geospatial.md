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

For LINESTRING and MULTILINESTRING zones, use ST_DWithin on geography with a configurable
lane-distance threshold in metres. A default of 15 metres is an explicit approximation assumption,
not a measured lane width or an authoritative boundary. Preserve the source line geometry.
For POLYGON and MULTIPOLYGON zones, use ST_Covers for interior and boundary points. Apply a
separate configurable GPS-noise threshold in metres with ST_DWithin on geography for nearby
outside points, marking those matches approximate. Document the threshold and its assumption.
For GEOMETRYCOLLECTION, use ST_CollectionExtract(geometry, 2) for linear components and
ST_CollectionExtract(geometry, 3) for polygon components, applying the respective rules to each.
Ignore empty extracted components. Never cast an unfiltered mixed collection to geography.
If several zones match, choose the nearest by ST_Distance on geography in metres, with a stable
source identifier as tie-breaker. Return the selected source geometry and approximation metadata.
Acceptance tests must cover a curbside point near a line, points inside and outside the configured
line threshold, a multiline, polygon interior and boundary, GPS noise, mixed and empty collections,
and overlapping candidates where the nearest zone wins. Derive coordinates from valid fixtures.

