Generate exactly frontend/src/app.ts and frontend/src/app.types.ts.
App.ts exports a standalone Angular App component with selector app-root,
templateUrl './app.html', styleUrl './app.css'. Do not include an inline template or styles.
Implement all state, API calls and event handlers needed by the supplied business requirements.
Define camelCase TypeScript DTOs in app.types.ts matching ACTUAL backend DTOs and responses.
Use Angular 20.1.6, HttpClient, CommonModule, FormsModule, signals or fields, and Angular Material.
Import all of these Material modules so the subsequent view can use them:
MatButtonModule, MatCardModule, MatFormFieldModule, MatInputModule, MatSelectModule,
MatTabsModule, MatChipsModule, MatProgressSpinnerModule, MatToolbarModule, MatCheckboxModule,
MatTooltipModule. Only use components from those modules. No icon font, router or map library.
Implement token sign-in using sessionStorage access_token and GET /api/v1/me to determine actual
role. The shared HttpClient interceptor adds the token. Never infer role from token contents.
Expose token, role, loading, error and success states and signIn/signOut methods.
Admins can inspect all data. Drivers only see owned data. Never rely solely on frontend filtering.
All controls must call actual endpoints. Critical writes use a UUID Idempotency-Key header.
Reuse the key when retrying the same operation. Regenerate it only after success or changed input.
Include startup loading, manual refresh, and bounded polling only where it serves the scenario.
If geospatial, expose real geometry paths, route paths and vehicle marker positions for SVG rendering.
Fit the viewport to relevant zone/route data and preserve aspect ratio. Do not fabricate map outlines.
Support browser geolocation and its permission failure, and distinct admin-controlled demo steps.
Expose countdown, domain events, official payment link and confirmed-session controls as required.
Use all exact service paths and field names from the actual supplied backend, not a guessed contract.
The HTML will be generated separately and must be able to bind to this component's public API.
Keep the controller compact. No HTML, CSS, TODOs, fake data, empty handlers or comments.
