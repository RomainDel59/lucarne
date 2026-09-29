# Contributing

Thank you for improving Lucarne.

## Ground rules

- Keep repository content, code, comments, logs, and documentation in English.
- Keep English as the source UI language and update French translations for user-visible changes.
- Preserve user isolation in every query and file operation.
- Avoid unbounded YouTube requests. Collection work must remain batched and sequential.
- Add tests for behavior changes and security boundaries.
- Do not add analytics, advertisements, tracking pixels, or YouTube account requirements.

## Checks

Run before opening a pull request:

```sh
ruff check src tests
pytest
docker build -t lucarne:test .
```

Keep changes focused and explain any storage or API compatibility impact in the pull request.

