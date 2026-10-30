# Evaluation procedure

## Preparation case

Generate the parking application from `examples/parking.md`. Use the supplied Saint Petersburg provider data as an integration fixture. The Moscow dataset must not be substituted for Saint Petersburg.

The provider contains WKT street geometries and integer prices in minor units. A street segment is not an official parking-zone boundary. Any matching radius must be documented in metres and treated as an assumption. A provider externalZoneId must not be labelled an official zone number without evidence.

Demonstrate route movement, entry, explicit session confirmation, end time, the ten-minute warning, departure, transition to another zone and persisted administrative history. A simulated clock must be visibly distinguished from real time.

## Hidden case

Use a new output directory and only the newly issued requirements. Keep the model fixed to qwen3.8-27b. Retain the original input, its digest, retrieval snapshot, structured requirements, API blueprint, generated source, model-call events and check reports. Do not seed a prepared parking solution into the hidden run.

The exported organiser clarification permits up to three generations. The implementation uses an initial attempt and at most two bounded repairs. Reasoning tokens, when returned by the API, are part of provider usage and must not be excluded from reporting.

## Evidence interpretation

`generated_unverified` means artifacts exist but required execution evidence is missing. `failed` means at least one executed check failed. `verified` requires all scheduled checks and the acceptance suite to pass. Individual FR links remain unverified until their named assertions and evidence are reviewed.

Scanner presence is not scanner success. Missing feeds, failed downloads and scanner process errors are failures. A dependency report must retain severity and package evidence. Generated documents must never replace raw execution evidence.
