# Frontend/BFF request dependency map

| Surface | Requests | Required for first render | Parallel | Deferred | Failure boundary |
| --- | --- | --- | --- | --- | --- |
| Dashboard/studio | Recent threads, archive preview, brand-kit summary | No | Yes | Archive and brand-kit previews | Each preview keeps the shell usable |
| Chat thread | Thread metadata, resume state, state snapshot, messages | Thread ID is required | Yes, with one pre-resolved auth context | No | Optional metadata and messages degrade independently |
| Archive | Archive projection list | No | Not applicable | Yes | Cached/local creatives remain visible |
| Result | GenerationJob status projection | Yes | Not applicable | Full result detail waits for terminal state | Existing generation failure surface |
| Settings/brand kit | Current brand kit | No | Not applicable | Yes | Settings shell remains usable |

The chat restore boundary resolves authentication once, then starts its four independent projection requests concurrently. It does not fetch full GenerationJob detail for list/status views and does not add open-domain routing internals to public payloads.
