Generate exactly frontend/src/app.ts exporting class App with selector app-root.
Use a standalone Angular 20.1.6 component, inline template and inline styles, Angular Material UI Kit.
Do not modify other files. Do not import files that do not exist. Imports available: Angular common,
forms, core, material, rxjs. No router package or external map library is installed.
The supplied backend/Domain.cs is the actual contract: match paths and all field names exactly.
Provide both an admin workspace and a mobile driver view if required, with responsive navigation.
Use a deliberately designed enterprise interface: dark navy sidebar, restrained blue accent, pale
canvas, clear spacing, data-rich cards, status chips, tables and a mobile bottom action area.
Use Material components for fields, actions, tabs, cards and progress. Import every used Material module.
Do not use ligature mat-icon because the icon font is not installed. Use text or inline SVG icons.
Include an access token sign-in form, stored in sessionStorage key access_token. Never embed tokens.
The HttpClient interceptor adds the bearer token automatically. Clear data on sign-out.
UI must load actual backend data, submit actual mutations and display server errors accessibly.
Cover loading, empty, invalid-input, forbidden and unavailable-backend states. No fake metrics.
For geographic scenarios, draw actual zone boundaries or segments and the actual route in a responsive
SVG map with a legend, coordinate labels, accessible title and current vehicle marker. Do not depend
on third-party tile servers. Show raw GPS and zone uncertainty when relevant. Support browser
geolocation with permission rejection feedback and a separate clearly labelled demo route control.
Include controls to exercise the full acceptance scenario. Do not expose admin controls in driver mode.
Use Angular @if and @for blocks with track expressions, signals or component fields, HttpClient.
Use async subscription error handlers and show human-readable feedback. Avoid getters creating
side effects. PWA shell and responsive global styles are already configured.
Use English copy and no emoji. No comments, fake data in UI, TODOs, placeholders or dead buttons.
