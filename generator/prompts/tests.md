Generate exactly tests/test_acceptance.py using Python unittest and stdlib urllib.request,
urllib.error, json, os, uuid and datetime. No third-party dependencies, comments or shell execution.
Read BASE_URL default http://frontend:8080 and ADMIN_TOKEN and DRIVER_TOKEN from environment.
Run against the supplied actual backend contract. Implement at least 10 independent tests.
Name tests test_FR_001_behaviour using the real requirement identifiers. Do not invent identifiers.
Cover complete successful workflows, persistence by rereading state, input rejection, unauthorized
requests, driver forbidden from admin endpoints, duplicate critical requests, event history and relevant
state-transition boundaries. For a geospatial scenario include entering a zone, leaving, switching,
out-of-range coordinates and 10-minute warning using the backend's explicit demo clock controls.
Use unique record IDs per test or isolate fixtures without depending on execution order.
Include a helper returning (status, parsed body) for BOTH HTTP success and HTTPError responses.
No network retry loops hiding failures. Do not loosen assertions to make incorrect behaviour pass.
Test business requirements, not just health checks. Show exact expected JSON field names.
Test data must be consistent with seeded fixtures in Domain.Initialise. Avoid external API dependencies.
