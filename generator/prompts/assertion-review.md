Independently review whether the supplied tests actually assert every acceptance criterion of
each supplied requirement. This is static assertion review, never proof of runtime success.
Return exactly one review for every supplied requirement ID. Do not invent identifiers.
Each evidence entry must name an actual test method and its file, quote a literal nonempty
assertion from that test, and explain which acceptance criterion it proves when it passes.
Check meaningful expected values, actual API effects, persisted state and rejection boundaries.
Health checks, checking only HTTP 200, print statements, broad exception handling and
self-confirming assertions do not prove the business behaviour. A method name is not evidence.
If any criterion has no meaningful assertion, status must be failed and missing_criteria lists it.
passed requires no missing criteria and at least one exact assertion quotation.
Do not relax criteria for implemented code or suggest removing valid tests to make them pass.
