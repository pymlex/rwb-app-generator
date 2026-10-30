Fix the concrete failed checks without changing requirements, API semantics or weakening tests.
Return a complete replacement only for the exact output_path assigned in the task.
Use the supplied contract and the other files only as dependencies.
Compiler errors should be fixed at their actual source. Test failures must be traced to the contract.
Keep valid existing behaviour. Never remove authorization, validation, transactions or assertions.
Do not claim checks passed. Do not modify infrastructure or dependency versions.
