# Project idea

Open Brain is persistent, searchable Markdown memory for coding agents. It stores a project's purpose, architecture, decisions, rules, and current state so a new agent can retrieve useful facts without relying on a long conversation history. A standalone local map lets people inspect the memory and its connections.

## Problem

Coding agents can spend tokens rereading files and rediscovering decisions between sessions. Context windows and automatic compaction can remove important project knowledge.

## Audience

Developers who use local coding agents and need project knowledge to survive across sessions and tools.

## Value proposition

Short, relevant CLI or MCP search backed by local CPU embeddings, with no LLM API. Source code stays in the repository; the Brain keeps durable reasons and decisions.
