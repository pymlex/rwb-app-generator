The smoke check uses the real application and backend. It verifies token sign-in,
a visible list loaded from the API, a successful mutation rendered in the UI,
and a visible server error after repeating the mutation with an invalid token.
It never mocks the API, skips unsupported steps, or saves browser traces with tokens.

The default locators use accessible English labels and simple forms. For a domain
with a dialog, multiple lists or constrained fields, set `E2E_SCENARIO` to a JSON
object in the invoking environment. Selectors are Playwright CSS selectors:

```json
{"tokenInput":"#token","signIn":"#login","list":"#items","openCreate":"#new-item","create":"#save-item","fields":{"#name":"$unique","#quantity":"2"},"createdText":"$unique","error":"[role=alert]"}
```

`$unique` is replaced per run in text values. Field values can also specify UI
operations: `{"select":"item-id"}` for a native select, `{"option":"Display text"}`
for a Material select, `{"check":true}` for a checkbox, or `{"click":true}`.
These operations use the real controls and do not inject data into application state. Configure actual domain-valid values and selectors
from the generated UI. A missing element, failed mutation, absent rendered result,
or absent server error fails the check and is recorded in `reports/e2e.json`.
Use `openCreate` when each mutation needs a fresh dialog. Workflows with multiple
steps need a domain-specific scenario; the smoke reports any unmet step as failed.
