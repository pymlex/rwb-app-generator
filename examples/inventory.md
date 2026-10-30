# Equipment checkout

An internal IT team lends equipment to employees. The administrator registers equipment with a unique asset tag, a name, a serial number and a condition. Employees browse available equipment and request a loan. An administrator approves or rejects a request. Equipment cannot have two active loans. The borrower confirms return and the administrator records its condition before it becomes available again.

The administrator sees all assets, requests, current loans and overdue loans. Employees see only their own requests and loans. Each state transition must appear in an audit history. Repeated approval requests with the same idempotency key must not create a second loan. Invalid transitions must be rejected without changing stored state.

The system provides a responsive web interface with a mobile view. Store all operational data persistently. Include seed equipment, API documentation, automated acceptance tests, containers and deployment instructions. Do not integrate payments or external inventory systems.
