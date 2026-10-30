# Qwen request budgeting

## Observed environment

All application generation calls use the organiser VM and the organiser Qwen endpoint. The model ID is qwen3.8-27b. The proxy OpenAPI document identifies LiteLLM 1.105.2. The error response gives a token limit of 30000 and a minute reset timestamp.

## Failed frontend request

The original request contained 80050 characters across the system and user messages. Its output cap was 14000. A character-based input estimate of 20013 and the output reservation totalled about 34013. The proxy returned HTTP 429 while reporting all 30000 tokens remaining.

This is consistent with a request that cannot fit an empty rate-limit window. Waiting for a reset cannot make that same request admissible.

The previous backend request had 59029 input characters, an estimated reservation of about 28758 and an output cap of 14000. It was accepted. The model reported 14036 input tokens and 7295 output tokens. These observed results distinguish the admission estimate from actual model usage.

## Two different estimates

The same proxy exposes `/utils/token_counter`. It returned 16968 for the backend request and 21388 for the frontend request, explicitly marking both as `local_estimate` with `openai_tokenizer`. Those are not measured Qwen prompt-token counts.

The public [LiteLLM limiter implementation](https://github.com/BerriAI/litellm/blob/main/litellm/proxy/hooks/parallel_request_limiter_v3.py) estimates text input from character count with a divisor of four and adds the explicit output cap for TPM reservation. That algorithm explains the accepted backend and rejected frontend requests. The deployed proxy source was not available for a byte-for-byte comparison.

## Implemented policy

- Retain original requirements and corporate regulations for analysis, then use the structured analysis and API blueprint for implementation stages.
- Do not send the full frontend source to backend acceptance-test generation.
- Split system documentation and handover documentation into separate bounded artifact batches.
- Use stage-specific output caps.
- Check both the proxy-style TPM reservation and the token counter's context estimate, retaining a configurable margin of 512 tokens.
- Reject contexts that leave insufficient room for a complete artifact before a generation request is sent.
- Do not retry a rejection when the full window is free or the reservation exceeds its limit.
- For a temporary shortage, use Retry-After or the server reset timestamp and server Date header. Unclassified failures stop with evidence.

Settings are RWB_TPM_LIMIT, RWB_CONTEXT_LIMIT, RWB_TOKEN_MARGIN and RWB_MAX_OUTPUT_TOKENS. Model usage and request-admission estimates are recorded separately.
