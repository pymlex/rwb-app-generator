Act as the engineering lead. Partition the supplied IDomainService method names into small,
cohesive work packages for backend agents. Assign every method exactly once. Do not invent methods.
The first package must contain only Initialise. Each other package has at most three methods.
For each package select the actual FR identifiers and blueprint endpoint paths needed to implement
those methods. Include cross-cutting criteria such as ownership, persistence and events when relevant.
Do not assign every requirement to every package. The worker receives complete typed DTO and SQL
contracts separately, so it needs the focused business criteria and endpoint semantics for its task.
Keep related mutations and their reads together when possible. Explain each package's purpose.
This is a work plan, not application code or evidence that implementation passed.
