# Agent instructions

## Purpose and boundary

This is an independent, public personal GeoAI / Location Intelligence lab linked to a personal blog. Use only publicly obtainable data and public sources.

- **会社GeoAI（非公開）→ geoai-open-lab（個人公開）は禁止。** Do not access, reference, copy, or import company repositories, private code, internal documents, prompts, configuration, proprietary logic or know-how, or nonpublic/commercial data such as ロケスマDATA. Do not explore sibling company projects for context.
- **geoai-open-lab（公開）→ 会社GeoAIの参照・業務利用は可。** Company projects may reference this repository's public code, findings, documentation, and blog posts, subject to applicable licenses. This does not authorize importing company assets here.

## Public safety

- Never commit raw/downloaded data, credentials, API keys, tokens, passwords, cookies, `.env`, databases, or caches. Do not force-add ignored files.
- Publish acquisition code and reproducible instructions rather than datasets. Store generated artifacts under ignored project-local `data/` (raw downloads in `data/raw/`, caches in `data/cache/`).
- Before using a new source, document its license, attribution, redistribution conditions, official source, and review date in `docs/`. Public availability alone is not redistribution permission.
- Record release ID/version, snapshot date, retrieval date (UTC), source URLs, AOI, filters, command, and environment. Pin releases rather than relying on `latest`; include checksums where available. Never put credentials or signed URLs in provenance.
- Committed samples must be small and explicitly redistributable, with documented permission and attribution. Use a dedicated `samples/` directory only after this review.
- Notebooks must have all outputs cleared and execution counts reset before commit. Inspect metadata, attachments, and embedded data too.
- Before **every `git add` and `git commit`**, inspect status, candidate paths, sizes, and contents for raw data, secrets, and large files. Before commit, review the staged diff and staged file list. Investigate any file over 1 MiB; this is not permission to commit smaller data or secrets.
- Repository code and original documentation use Apache-2.0. External data retain their own licenses; Apache-2.0 does not relicense them.

## Development

Keep the structure small. Use Python 3.11+ and `uv sync --locked`; commit `uv.lock` when dependencies change. Add dependencies only when needed. Start with Foursquare Open Source Places inspection via DuckDB / Python; do not prebuild the later pipeline.

Read `docs/data-policy.md` before adding a data source or publishing results. Do not add automations, cloud resources, or downloaded datasets merely to scaffold the project.
