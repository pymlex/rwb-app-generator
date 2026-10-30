Fix the concrete failed checks without changing requirements, API semantics or weakening tests.
Return complete replacement files only for affected files among backend/Domain.cs,
backend/migrations/002_domain.sql, frontend/src/app.ts and tests/test_acceptance.py.
Compiler errors should be fixed at their actual source. Test failures must be traced to the contract.
Keep valid existing behaviour. Never remove authorization, validation, transactions or assertions.
Do not claim checks passed. Do not modify infrastructure or dependency versions.
