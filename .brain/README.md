# Local Second Brain

Project context lives in `project/` and `knowledge/` Markdown. Run `brain index` after manual edits, `brain search` to retrieve context, and `brain remember` to record durable decisions. `index/brain.db` is a rebuildable local SQLite + sqlite-vec index. Embeddings use the public `intfloat/multilingual-e5-small` model on CPU; run `brain model download` once. `AGENT_BRAIN.md` explains when agents should search and update memory. See the repository README and `docs/INSTALLATION.md` for installation and MCP configuration.

Open `map.html` in a browser to inspect this project's memories, links, and approximate stored text size. It updates after indexing and remembering; run `brain map` to refresh it manually. This generated local file is ignored by Git.
