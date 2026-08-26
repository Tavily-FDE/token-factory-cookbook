
import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_nebius import ChatNebius
from langgraph.checkpoint.memory import InMemorySaver
from utils import (
    collect_usage,
    create_workspace,
    print_comparison,
    print_metrics,
    print_summary,
    print_validation,
    validate_result,
)

load_dotenv()


# ============================================================
# Configuration
# ============================================================

parser = argparse.ArgumentParser()
parser.add_argument(
    "--data-dir",
    default="data-1",
    help="data suite directory under the script's parent (default: data-1)",
)
ARGS = parser.parse_args()

DATA_SUITE_DIR = Path(__file__).parent / ARGS.data_dir
BENCHMARK_ROOT = Path(__file__).parent / "benchmarks"
INPUT_DATA_DIR = DATA_SUITE_DIR / "input"
OUTPUT_DATA_DIR = "output"
EXPECTED_PATH = DATA_SUITE_DIR / "expected.json"

NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY")

TASK = (
    "Inspect the input files in the workspace, then write the analysis results to "
    "/output/result.json and /output/summary.md as described in your instructions."
)

EXPECTED = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))


MODELS = [
    {
        "model_id": "nvidia/Nemotron-3-Ultra-550b-a55b",
        "input_price_per_1m": 1.00,
        "output_price_per_1m": 3.00,
    },
    {
        "model_id": "nvidia/nemotron-3-super-120b-a12b",
        "input_price_per_1m": 0.30,
        "output_price_per_1m": 0.90,
    },
    {
        "model_id": "nvidia/Nemotron-3_5-Lightning",
        "input_price_per_1m": 0.06,
        "output_price_per_1m": 0.24,
    },
    # {
    #     "model_id": "moonshotai/Kimi-K3",
    #     "input_price_per_1m": 3.00,
    #     "output_price_per_1m": 15.00,
    # },
]

SYSTEM_PROMPT = """
You are a data analysis agent.

You have access to a workspace containing input files.

Your task is to:

1. Inspect the available files.
2. Compare Q1 and Q2 revenue by region.
3. Determine which region had the largest revenue change by magnitude — \
whether that change is an increase or a decrease.
4. Calculate the dollar amount of that change (later period minus earlier \
period: positive for an increase, negative for a decrease).
5. Determine which product contributed most to that change in that region.
6. Verify your calculations before producing the final answer.

You have no shell or code-execution tool. Perform all comparisons and
arithmetic yourself by reasoning over the file contents you read.

You MUST create:

/output/result.json
/output/summary.md

result.json MUST have exactly this structure:

{
  "region": "string",
  "change": number,
  "primary_product": "string"
}

"change" is the region's revenue change (later period minus earlier
period): positive for an increase, negative for a decrease.

summary.md MUST contain:

# Sales Analysis

- Region with the largest revenue change
- Dollar amount of that change (signed)
- Product that contributed most to the change

## Executive Summary

Then provide exactly three concise bullet points.

Do not guess.
Base your answer only on the files in the workspace.
"""


# ============================================================
# Run one model
# ============================================================

def run_model(model_config):
    name = model_config["model_id"]

    print()
    print("=" * 72)
    print(f"Running model: {name}")
    print("=" * 72)

    workspace = create_workspace(
        run_dir=BENCHMARK_ROOT,
        model=name,
        input_data_dir=INPUT_DATA_DIR,
        output_data_dir=OUTPUT_DATA_DIR,
    )

    # --------------------------------------------------------
    # Nebius LangChain adapter
    # --------------------------------------------------------

    model = ChatNebius(
        model=model_config["model_id"],
        api_key=NEBIUS_API_KEY,
        temperature=0,
    )

    # --------------------------------------------------------
    # Deep Agent backend
    #
    # FilesystemBackend has no shell/code-execution tool, so the
    # agent is confined to the file tools (ls/read/write/edit/glob/
    # grep), which are jailed to `workspace` under virtual_mode.
    # --------------------------------------------------------

    backend = FilesystemBackend(
        root_dir=workspace,
        virtual_mode=True,
    )

    # --------------------------------------------------------
    # Deep Agent
    # --------------------------------------------------------

    agent = create_deep_agent(
        model=model,
        backend=backend,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=InMemorySaver(),
    )

    # --------------------------------------------------------
    # Execute benchmark
    # --------------------------------------------------------

    run_config = {"configurable": {"thread_id": name}}

    start = time.perf_counter()

    try:

        response = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": TASK,
                    }
                ]
            },
            config=run_config,
        )

        error = None

    except Exception as exc:

        # Recover whatever messages were checkpointed before the crash, so
        # tokens/cost already billed for this run aren't reported as zero.
        state = agent.get_state(run_config)

        response = {
            "messages": state.values.get("messages", [])
        }

        error = str(exc)

    elapsed = time.perf_counter() - start

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    usage = collect_usage(
        response.get("messages", [])
    )

    validation = validate_result(workspace, EXPECTED)

    input_cost = (
        usage["input_tokens"]
        / 1_000_000
        * model_config["input_price_per_1m"]
    )

    output_cost = (
        usage["output_tokens"]
        / 1_000_000
        * model_config["output_price_per_1m"]
    )

    total_cost = input_cost + output_cost

    return {
        "model_id": name,

        "success": validation["success"],
        "score": validation["score"],
        "all_checks_score": validation["all_checks_score"],

        "checks": validation["checks"],
        "actual": validation["actual"],

        "turns": usage["turns"],
        "tool_calls": usage["tool_calls"],
        "tool_usage": usage["tool_usage"],

        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],

        "total_tokens": (
            usage["input_tokens"]
            + usage["output_tokens"]
        ),

        "latency_seconds": elapsed,

        "cost": total_cost,

        "workspace": workspace,

        "error": error,
    }


# ============================================================
# Main
# ============================================================

def main():

    BENCHMARK_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print("=" * 72)
    print(f"Data suite: {ARGS.data_dir}")
    print(f"  input:    {ARGS.data_dir}/input")
    print(f"  expected: {ARGS.data_dir}/expected.json")
    print("=" * 72)

    results = []

    for model_config in MODELS:

        result = run_model(
            model_config
        )

        results.append(result)

        print_validation(result)
        print_metrics(result)
        print_summary(result)

    print_comparison(results)


if __name__ == "__main__":
    main()