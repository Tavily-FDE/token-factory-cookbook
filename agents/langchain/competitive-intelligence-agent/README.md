# Competitive Intelligence Fact Ledger

A LangChain **Deep Agents** app for source-backed competitive intelligence, powered by an LLM served by [Nebius Token Factory](https://tokenfactory.nebius.com/) and web research via [Tavily](https://tavily.com/).

The app is intentionally split into two phases:

1. **Gather facts** — collect source packs, company claim ledgers, a verification queue, and a company-name to UUID registry.
2. **Generate brief** — use the persisted fact layer to generate a draft from a guidance prompt.

Facts and drafts are kept separate. Drafts should use only verified, copy-safe ledger claims.

## Why Deep Agents

Deep Agents provide the primitives this workflow needs:

- **Planning** via `write_todos`.
- **Virtual filesystem** via `write_file` / `read_file`, used as the boundary between fact collection and draft generation.
- **General-purpose subagent** via `task`, used to isolate large research or drafting objectives without creating rigid specialist subagents.
- **Context management** for long-running research flows.

This app overrides the default `general-purpose` subagent with a competitive-intelligence worker that can be instructed with objectives like pricing, product capabilities, security/compliance, positioning, benchmarks/latency, market momentum, or sentiment.

## Setup

```bash
cd agents/langchain/competitive-intelligence-agent
uv sync
cp env.example .env
```

Then edit `.env`:

```bash
NEBIUS_API_KEY=your-nebius-api-key
TAVILY_API_KEY=your-tavily-api-key
```

## Step 1: Gather Facts

```bash
uv run cli.py "Tavily vs Exa vs Parallel vs You.com vs Brave" --gather-facts
```

This writes a global company registry and one fact folder per company:

```text
output/
  companies.json
  companies/
    <company-uuid>/
      company.json
      sources.md
      facts.yaml
      verification-queue.md
      run-summary.md
```

If facts already exist, the command lists the existing files instead of rerunning research. Use `--force` to rebuild:

```bash
uv run cli.py "Tavily vs Exa vs Parallel" --gather-facts --force
```

## Step 2: Generate Brief

```bash
uv run cli.py "Tavily vs Exa vs Parallel" \
  --generate-brief "Write a Tavily-favored comparison page for AI agent builders. Be fair to competitors and use only verified claims."
```

This loads the persisted fact folders for the same scope and writes:

```text
output/
  briefs/
    <scope-slug>/
      generated-brief.md
      run-summary.md
```

Brief generation requires existing facts. It will fail fast if the fact layer has not been gathered first.

## Options

```bash
uv run cli.py "Tavily vs Exa" --gather-facts
uv run cli.py "Tavily vs Exa" --generate-brief "Write a neutral buyer comparison."
```

| Flag | Notes |
| --- | --- |
| `--gather-facts` | Collect or list persisted source packs and ledgers. |
| `--generate-brief TEXT` | Generate a brief from persisted facts using the guidance prompt. |
| `--force` | Rerun fact collection even when facts exist. |
| `--output PATH` | Artifact root. Defaults to `./output`. |
| `--model TEXT` | Tool-calling model served by Nebius Token Factory. |
| `--recursion-limit INT` | Bump for larger competitor sets. |

## Files

```text
agent.py         # Deep Agent setup, prompts, Tavily tools, general-purpose subagent
cli.py           # Two-step CLI, local artifact persistence, stream rendering
streamlit_app.py # Older UI surface; CLI is the primary path for the fact-ledger flow
```

## References

- LangChain Deep Agents — <https://docs.langchain.com/oss/python/deepagents/overview>
- Deep Agents subagents — <https://docs.langchain.com/oss/python/deepagents/subagents>
- Deep Agents filesystem — <https://docs.langchain.com/oss/python/deepagents/filesystem>
- LangChain Tavily — <https://docs.langchain.com/oss/python/integrations/tools/tavily_search>
- LangChain Nebius provider — <https://docs.langchain.com/oss/python/integrations/providers/nebius>
- Nebius Token Factory — <https://tokenfactory.nebius.com/>
- Tavily — <https://docs.tavily.com/>
