# Collaboration

Team TLE develops this repository jointly. Git history identifies individual contributors. No document should claim sole ownership of the project.

## Branches

Use `main` as the release baseline. Keep unfinished work on feature branches. Codex branches use `codex/<topic>`. Other contributors may use `feature/<topic>` or `fix/<topic>`.

Fetch before starting work. Keep each pull request focused on one reviewable change. Use draft pull requests for incomplete implementations so other contributors can see ownership and status. Avoid simultaneous edits to the same generator module or prompt. Reconcile changes from `main` before marking a pull request ready.

Do not force-push shared branches or rewrite `main` history. Publish corrections as new commits. Resolve review feedback and passing checks before merging. Branch protection is not currently enforced by this document.

## Verification

Run generator tests and lint on the organiser VM. Generated application changes also require a Docker build and relevant acceptance tests. Report missing checks as unverified. Do not replace failing assertions with weaker tests or record scanner errors as passes.

Every application-generation call must originate from the organiser VM and use the issued API endpoint with qwen3.8-27b. Do not substitute another LLM provider or model. Preserve required target-stack versions and the organisers' documented PWA allowance.

## Source materials and credentials

Do not commit original PDF files, chat exports, access instructions, passwords, API keys, `.env` files or private keys. Derived system-analysis rules, requirements, architecture and other generated artifacts may be versioned. Check staged files before pushing.

Keep the original documents and credentials outside Git. Use environment variables for the organiser API key and generated application credentials. Do not include secrets in screenshots, logs, issue bodies or pull-request descriptions.

## Releases

Use versioned tags on `main` only after a clean organiser-VM deployment and the required demonstration scenarios have passed. Retain build, acceptance, security and resource-usage evidence with the release. Record known limitations and explicit assumptions. Never label a preparation scaffold or an unverified generated application as a completed release.
