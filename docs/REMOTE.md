# Optional linked-service integration

The standalone workflow in the [README](../README.md) stores and searches local
project memory without a server or account. This repository also contains an
HTTP client for a separate, compatible Brain service. The service itself is not
included or started by installing Open Brain. The local stability audit does not
validate a live remote deployment.

## Before linking

Use this path only if you already have the service URL, access to a project on
that service and any required credentials. The client defaults to
`http://localhost:8020`; it does not discover or provision a hosted service.
This is optional integration support, not a required installation step.

Linking changes the project's read/write path: it prefers the service, maintains
a local Markdown mirror on sync and queues writes when the service is unreachable.
Project data is sent to the selected service. The offline/local-only behavior
described in the README applies to **unlinked** projects.

## Commands

Replace the URL and project slug with the ones supplied by your service operator:

```bash
brain link my-project --url https://your-brain-service.example
brain sync
brain context --task "Explain the retry policy"
```

`--create` asks the service to create a missing project. `--push-local` explicitly
uploads existing local memories during linking; linking without that flag does
not upload them. These actions need the service's corresponding permissions.
Run `brain link --help` before selecting those options.

The HTTP client supports `BRAIN_URL` and `BRAIN_API_TOKEN`. Linked-project
operations use `.brain/credentials.json` when present; otherwise the environment
token is used. This repository does not provide a login command. Obtain credentials
through your service's documented setup, keep them out of Git, and add
`.brain/credentials.json` to your project's ignore rules if using that file.
`brain init` does not add that credentials path to `.gitignore` automatically.

## Offline and sync behavior

- Reads fall back to the local mirror when the service is unreachable; they may
  be stale. Local semantic searches need the cached embedding model and an index.
- Offline writes are queued in `.brain/outbox.jsonl`. A queued write is not an
  immediate update to the local mirror.
- `brain sync` sends queued writes, exports current records to Markdown, refreshes
  `.brain/BRAIN.md` and attempts local indexing. There is no background sync daemon.
- Authentication/HTTP rejections are distinct from an unreachable service; they
  are not silently treated as successful offline writes. During outbox flushing,
  rejected writes are recorded in `.brain/history/outbox-rejected.jsonl` instead
  of retried indefinitely.
- `brain unlink` removes the remote binding. The existing local mirror remains;
  queued writes are not automatically sent by unlinking.

Inspect pending/rejected writes before assuming they reached the service. Keep
`.brain/outbox.jsonl`, credentials and other service-specific private data out of
public commits. Review the mirror too before sharing canonical Markdown.

## Implementation reference

`src/second_brain/remote.py` implements the HTTP client, local/remote backends,
offline outbox and mirror export. `src/second_brain/cli.py` implements link/sync;
the MCP server selects its backend from the project's configuration. A compatible
service must implement the expected `/v1/projects/...` and knowledge endpoints.
The code also exposes service-dependent commands such as `kb`, `projects` and
`cost`; their appearance in `brain --help` does not mean a service is installed.
