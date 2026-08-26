import json
import shutil
from pathlib import Path


def create_workspace(
    run_dir: Path,
    model: str,
    input_data_dir: Path,
    output_data_dir: str = "output",
) -> Path:
    workspace = run_dir / model.replace("/", "__")

    if workspace.exists():
        shutil.rmtree(workspace)

    shutil.copytree(input_data_dir, workspace / "input")

    (workspace / output_data_dir).mkdir(parents=True)

    return workspace


def collect_usage(messages):
    input_tokens = 0
    output_tokens = 0
    tool_calls = 0
    turns = 0
    tool_usage = {}

    for message in messages:
        usage = getattr(message, "usage_metadata", None)

        if usage:
            input_tokens += usage.get("input_tokens", 0)
            output_tokens += usage.get("output_tokens", 0)

        if getattr(message, "type", None) == "ai":
            turns += 1

        calls = getattr(message, "tool_calls", None)

        if calls:
            tool_calls += len(calls)

            for call in calls:
                tool_name = call.get("name", "unknown")
                tool_usage[tool_name] = tool_usage.get(tool_name, 0) + 1

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "tool_calls": tool_calls,
        "turns": turns,
        "tool_usage": tool_usage,
    }


def validate_result(workspace: Path, expected: dict):
    result_path = workspace / "output" / "result.json"
    summary_path = workspace / "output" / "summary.md"

    checks = {
        "result_created": result_path.exists(),
        "summary_created": summary_path.exists(),
    }

    actual = None

    if result_path.exists():
        try:
            actual = json.loads(
                result_path.read_text(encoding="utf-8")
            )

            checks["valid_json"] = True

            checks["region"] = (
                str(actual.get("region", "")).lower()
                == expected["region"]
            )

            checks["decline"] = (
                actual.get("decline")
                == expected["decline"]
            )

            checks["primary_product"] = (
                str(actual.get("primary_product", "")).lower()
                == expected["primary_product"]
            )

        except Exception:
            checks["valid_json"] = False
            checks["region"] = False
            checks["decline"] = False
            checks["primary_product"] = False

    else:
        checks["valid_json"] = False
        checks["region"] = False
        checks["decline"] = False
        checks["primary_product"] = False

    if summary_path.exists():
        summary = summary_path.read_text(
            encoding="utf-8"
        ).strip()
        checks["summary_nonempty"] = len(summary) > 50
    else:
        checks["summary_nonempty"] = False

    correctness_checks = [
        checks["region"],
        checks["decline"],
        checks["primary_product"],
    ]

    score = sum(correctness_checks) / len(correctness_checks)
    success = all(correctness_checks)
    all_checks_score = sum(checks.values()) / len(checks)

    return {
        "success": success,
        "score": score,
        "all_checks_score": all_checks_score,
        "checks": checks,
        "actual": actual,
    }


def print_validation(result):
    print("\nValidation")

    name_width = max(len(name) for name in result["checks"]) + 1

    for name, passed in result["checks"].items():
        status = "PASS" if passed else "FAIL"
        print(f"  {name:<{name_width}} {status}")

    print(f"\n  Score:      {result['score']:.0%}")
    print(f"  Robustness: {result['all_checks_score']:.0%}")


def print_metrics(result):
    print("\nMetrics")

    tool_usage = (
        ", ".join(
            f"{name}={count}"
            for name, count in sorted(result["tool_usage"].items())
        )
        or "none"
    )

    rows = [
        ("Agent turns:", str(result["turns"])),
        ("Tool calls:", str(result["tool_calls"])),
        ("Tool usage:", tool_usage),
        ("Input tokens:", f"{result['input_tokens']:,}"),
        ("Output tokens:", f"{result['output_tokens']:,}"),
        ("Total tokens:", f"{result['total_tokens']:,}"),
        ("E2E latency:", f"{result['latency_seconds']:.2f}s"),
        ("Estimated cost:", f"${result['cost']:.6f}"),
    ]

    if result["error"]:
        rows.append(("Error:", result["error"]))

    label_width = max(len(label) for label, _ in rows) + 1

    for label, value in rows:
        print(f"  {label:<{label_width}}{value}")


def print_summary(result):
    summary_path = (
        result["workspace"]
        / "output"
        / "summary.md"
    )

    print()
    print("Final Summary")
    print("-" * 72)

    if summary_path.exists():
        print(
            summary_path.read_text(
                encoding="utf-8"
            ).strip()
        )
    else:
        print("summary.md was not created.")

    print("-" * 72)


def print_comparison(results):
    headers = [
        "Model",
        "Success",
        "Score",
        "Turns",
        "Calls",
        "In Tok",
        "Out Tok",
        "Tot Tok",
        "Time",
        "Cost ▲",
    ]

    ordered = sorted(results, key=lambda result: result["cost"])

    rows = [
        [
            result["model_id"],
            "YES" if result["success"] else "NO",
            f"{result['score']:.0%}",
            str(result["turns"]),
            str(result["tool_calls"]),
            f"{result['input_tokens']:,}",
            f"{result['output_tokens']:,}",
            f"{result['total_tokens']:,}",
            f"{result['latency_seconds']:.2f}s",
            f"${result['cost']:.6f}",
        ]
        for result in ordered
    ]

    widths = [
        max([len(headers[i])] + [len(row[i]) for row in rows])
        for i in range(len(headers))
    ]

    def format_row(cells):
        padded = (cell.ljust(widths[i]) for i, cell in enumerate(cells))
        return "| " + " | ".join(padded) + " |"

    print()
    print("MODEL COMPARISON")
    print()
    print(format_row(headers))
    print("|" + "|".join("-" * (width + 2) for width in widths) + "|")

    for row in rows:
        print(format_row(row))
