# Competitive Intelligence Fact Ledger

A LangChain **Deep Agents** app for source-backed competitive intelligence, powered by provider-aware LangChain chat models and web research via [Tavily](https://tavily.com/).

The app is intentionally split into two phases:

1. **Gather facts** — collect source packs, company claim ledgers, a verification queue, and a company-name to UUID registry.
2. **Write assets** — use the persisted fact layer to generate markdown assets from a guidance prompt.

Facts and drafts are kept separate. Drafts should use only verified, copy-safe ledger claims.

## Why Deep Agents

Deep Agents provide the primitives this workflow needs:

- **Planning** via `write_todos`.
- **Virtual filesystem** via `write_file` / `read_file`, used as the boundary between fact collection and writer generation.
- **General-purpose subagent** via `task`, used to isolate large research or drafting objectives without creating rigid specialist subagents.
- **Context management** for long-running research flows.

This app uses separate fact and writer agents. Each keeps one objective-driven `general-purpose` subagent and loads app-local skills on demand.

## Setup

```bash
cd agents/langchain/competitive-intelligence-agent
uv sync
cp env.example .env
```

Then edit `.env`:

```bash
NEBIUS_API_KEY=your-nebius-api-key
OPENAI_API_KEY=your-openai-api-key
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
```

If facts already exist, the command lists the existing files instead of rerunning research. Use `--force` to rebuild:

```bash
uv run cli.py "Tavily vs Exa vs Parallel" --gather-facts --force
```

## Step 2: Write Asset

```bash
uv run cli.py "Tavily vs Exa vs Parallel" \
  --write "Create a Tavily-favored comparison page for AI agent builders. Be fair to competitors and use only verified claims."
```

This loads the persisted fact folders for the same scope and writes:

```text
output/
  drafts/
    <scope-slug>/
      draft.md
      claims-used.md
      avoided-claims.md
```

Writer generation requires existing facts. It will fail fast if the fact layer has not been gathered first.

## Options

```bash
uv run cli.py "Tavily vs Exa" --gather-facts
uv run cli.py "Tavily vs Exa" --write "Write a neutral buyer comparison."
```

| Flag | Notes |
| --- | --- |
| `--gather-facts` | Collect or list persisted source packs and ledgers. |
| `--write TEXT` | Generate a markdown asset from persisted facts using the guidance prompt. |
| `--force` | Rerun fact collection even when facts exist. |
| `--output PATH` | Artifact root. Defaults to `./output`. |
| `--model TEXT` | Coordinator model spec. Use `openai:<model>` or `nebius:<model>`; bare names use Nebius. Defaults to `moonshotai/Kimi-K2.6`. |
| `--subagent-model TEXT` | General-purpose subagent model spec. Defaults to `openai:gpt-4.1`. Use `nebius:<model>` to route subagents through Nebius. |
| `--recursion-limit INT` | Bump for larger competitor sets. |

## Files

```text
fact_agent.py    # Fact-gathering Deep Agent wrapper, Tavily tools, skills, general-purpose subagent
writer_agent.py  # Writer Deep Agent wrapper for ledger-grounded markdown assets
agent.py         # Legacy mixed agent kept for reference; not used by the CLI runtime
schemas.py       # Lightweight Pydantic models for source packs, claim candidates, and writer outputs
cli.py           # Two-step CLI, local artifact persistence, stream rendering
skills/          # App-local fact and writer playbooks loaded through Deep Agents skills
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
