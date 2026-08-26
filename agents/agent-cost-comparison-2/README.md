# Agent Cost Comparison 2

Benchmarks Nebius-hosted models on a small data-analysis task, run as a
[deepagents](https://github.com/langchain-ai/deepagents) filesystem agent with
no shell/code-execution tool, and compares cost, tokens, latency, and
correctness across models.

## Task

The agent is given a workspace with sales/product data (`data-1/input/`) and must:

1. Compare Q1 vs Q2 revenue by region.
2. Find the region with the largest revenue decline and the dollar amount.
3. Find the product that contributed most to that decline.
4. Write `/output/result.json` and `/output/summary.md`.

The agent has to do all reasoning and arithmetic itself over file contents —
there's no code-execution tool available.

## Models compared

Configured in `MODELS` in `agent_cost_comparison_1.py`:

- `nvidia/Nemotron-3-Ultra-550b-a55b`
- `nvidia/nemotron-3-super-120b-a12b`
- `nvidia/Nemotron-3_5-Lightning`

## Setup

```bash
uv sync
```

Set `NEBIUS_API_KEY` in a `.env` file (see `load_dotenv()` in
`agent_cost_comparison_1.py`).

## Run

```bash
uv run agent_cost_comparison_1.py
```

Each model gets its own workspace under `benchmarks/<model>/` (input copied
in, output written to `output/`), validated against `data-1/expected.json`. A final
comparison table is printed across all models, sorted by cost ascending.

## Files

- `agent_cost_comparison_1.py` — runs each model against the task and scores it.
- `utils.py` — workspace setup, usage/cost collection, validation, printing.
- `data-1/input/` — source data copied into each model's workspace.
- `data-1/expected.json` — ground-truth answer used for scoring.
- `benchmarks/` — per-model run artifacts (gitignored).
