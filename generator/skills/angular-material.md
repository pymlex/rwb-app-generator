# Angular Material interface

Use Angular 20.1.6 and its matching Material and CDK versions from the fixed package manifest.
Keep the standalone controller in app.ts, DTOs in app.types.ts, view in app.html and styles in app.css.
Templates bind only to actual exported controller members. Import every Material module used.
Use native semantic labels, meaningful button text, keyboard access and responsive spacing.
Implement loading, empty, success, validation-error, forbidden and transport-error states.
Determine the role with the actual authenticated /api/v1/me response, not token text.
Use HttpClient with the fixed interceptor. Keep access tokens out of bundled source and persistent assets.
Critical write retries reuse their existing idempotency key until input changes or the operation succeeds.
All controls call real endpoints. Do not substitute local arrays for persisted server business state.
Use compact responsive layouts. On narrow screens, stack sections without hiding required operations.
Polling must be bounded and disposed on component destruction. Timers need distinct demo-clock semantics.
Browser geolocation and PWA installation require a secure context such as localhost or HTTPS.

