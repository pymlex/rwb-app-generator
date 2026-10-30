Extract a precise system analysis from business_requirements. Assign FR-001 onwards.
Every source_quote MUST be an exact nonempty substring of business_requirements, preserving punctuation.
Acceptance criteria must be independently testable and include rejected operations and boundary conditions.
Cover all requested behaviours, roles, data ownership, persistence, state transitions and integrations.
Separate assumptions from customer statements. Use PWA as the allowed mobile implementation.
Ask blocking questions only for decisions that cannot safely be assumed and would change security,
scope or financial behaviour. Do not ask about branding, libraries or deployment ports.
No real payment processing: use an official external link and explicit confirmation of paid sessions.
Domain specifics must derive from the supplied business requirements, not prior examples.
Use the retrieved corporate regulations to define analysis completeness.
