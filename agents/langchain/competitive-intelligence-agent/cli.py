"""CLI for the fact-ledger competitive-intelligence agent.

Two explicit steps:

    uv run cli.py "Tavily vs Exa vs Parallel" --gather-facts
    uv run cli.py "Tavily vs Exa" --generate-brief "Write a Tavily-favored comparison page"

Facts are persisted under the output directory by scope. Brief generation reads
those persisted facts and should not rediscover the web unless the user asks for
fresh verification.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import uuid
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Iterable

import typer
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, ToolMessage
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from agent import build_agent

_TODO_TOOL = "write_todos"
_TASK_TOOL = "task"
_WRITE_FILE_TOOL = "write_file"

_STATUS_ICON = {"pending": "○", "in_progress": "◐", "completed": "●"}
_STATUS_STYLE = {"pending": "dim", "in_progress": "yellow", "completed": "green"}

COMPANY_FACT_FILES = (
    "company.json",
    "sources.md",
    "facts.yaml",
    "verification-queue.md",
    "run-summary.md",
)


def _short(text: str, limit: int = 240) -> str:
    text = text.strip().replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:90] or "competitive-scope"


def _candidate_company_names(scope: str) -> list[str]:
    # Treat ordinary multi-word product names as one company. Split only on
    # explicit comparison/list separators.
    parts = re.split(r"\s+(?:vs|versus)\s+|\s*,\s*|\s*\+\s*|\s*/\s*", scope, flags=re.IGNORECASE)
    names = []
    for part in parts:
        name = part.strip(" \t\n\r:;|")
        if name and name.lower() not in {"compare", "comparison"}:
            names.append(name)
    return names or [scope.strip()]


def _format_args(args: dict[str, Any]) -> str:
    if not args:
        return ""
    parts = []
    for key, value in args.items():
        if isinstance(value, str):
            parts.append(f"{key}={json.dumps(_short(value, 80))}")
        elif isinstance(value, (list, dict)):
            parts.append(f"{key}={_short(json.dumps(value, default=str), 80)}")
        else:
            parts.append(f"{key}={value!r}")
    return ", ".join(parts)


def _namespace_prefix(ns: tuple[str, ...]) -> Text:
    if not ns:
        return Text("lead", style="bold cyan")
    parts = []
    for entry in ns:
        head = entry.split(":")
        parts.append(head[1] if len(head) >= 2 else entry)
    return Text(" → ".join(parts), style="bold magenta")


def _render_todos(console: Console, todos: list[dict[str, Any]]) -> None:
    lines = []
    for item in todos:
        status = item.get("status", "pending")
        icon = _STATUS_ICON.get(status, "?")
        style = _STATUS_STYLE.get(status, "white")
        lines.append(Text(f"  {icon} {item.get('content', '')}", style=style))
    body = Text("\n").join(lines) if lines else Text("(empty)", style="dim")
    console.print(Panel(body, title="📋 plan", border_style="blue", expand=False))


def _render_tool_call(console: Console, prefix: Text, name: str, args: dict[str, Any]) -> None:
    if name == _TODO_TOOL:
        console.print(prefix, Text("📝 plan updated", style="blue"))
        _render_todos(console, args.get("todos", []))
        return

    if name == _TASK_TOOL:
        console.print(
            prefix,
            Text("🤖 dispatch ", style="magenta"),
            Text(args.get("subagent_type", "?"), style="bold magenta"),
            Text(f"  «{_short(args.get('description', ''), 100)}»", style="dim"),
        )
        return

    if name == _WRITE_FILE_TOOL:
        path = args.get("file_path") or args.get("path") or "?"
        console.print(
            prefix,
            Text("💾 write_file ", style="green"),
            Text(path, style="bold green"),
            Text(f"  ({len(args.get('content', ''))} chars)", style="dim"),
        )
        return

    console.print(
        prefix,
        Text(f"🔧 {name}(", style="cyan"),
        Text(_format_args(args), style="cyan dim"),
        Text(")", style="cyan"),
    )


def _render_tool_result(console: Console, prefix: Text, msg: ToolMessage) -> None:
    name = getattr(msg, "name", "tool")
    content = msg.content if isinstance(msg.content, str) else json.dumps(msg.content, default=str)
    console.print(prefix, Text(f"   ↳ {name}: ", style="dim cyan"), Text(_short(content, 200), style="dim"))


def _render_ai_text(console: Console, prefix: Text, content: str) -> None:
    console.print(prefix, Text("💬 ", style="yellow"), Text(_short(content, 400), style="yellow"))


def render_stream(console: Console, events: Iterable[Any]) -> dict[str, Any]:
    files: dict[str, Any] = {}
    todos_snapshot: list[dict[str, Any]] = []

    for event in events:
        if isinstance(event, tuple) and len(event) == 2:
            namespace, update = event
        else:
            namespace, update = ((), event)
        prefix = _namespace_prefix(namespace)

        for _node_name, partial in update.items():
            if not isinstance(partial, dict):
                continue

            if isinstance(partial.get("files"), dict):
                files.update(partial["files"])
            if isinstance(partial.get("todos"), list):
                todos_snapshot = partial["todos"]

            for msg in partial.get("messages", []) or []:
                if isinstance(msg, AIMessage):
                    for call in getattr(msg, "tool_calls", []) or []:
                        _render_tool_call(console, prefix, call.get("name", "?"), call.get("args", {}) or {})
                    text = msg.content if isinstance(msg.content, str) else ""
                    if text.strip():
                        _render_ai_text(console, prefix, text)
                elif isinstance(msg, ToolMessage):
                    _render_tool_result(console, prefix, msg)

    return {"files": files, "todos": todos_snapshot}


app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Build competitor fact ledgers or generate briefs from existing ledgers.",
)


def _check_env(console: Console) -> None:
    missing = [k for k in ("NEBIUS_API_KEY", "TAVILY_API_KEY") if not os.getenv(k)]
    if missing:
        console.print(
            Panel(
                f"Missing environment variable(s): [bold red]{', '.join(missing)}[/].\n\n"
                "Copy [cyan]env.example[/] to [cyan].env[/] and fill in your keys, then re-run.",
                title="setup required",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)


def _file_content(entry: object) -> str | None:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        content = entry.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(content)
    return None


def _safe_output_parts(virtual_path: str) -> list[str]:
    pure = PurePosixPath("/" + virtual_path.lstrip("/"))
    parts = [part for part in pure.parts if part not in ("/", "", ".")]
    if any(part == ".." for part in parts):
        raise ValueError(f"Unsafe virtual path: {virtual_path}")
    return parts


def _mapped_output_path(
    root: Path,
    virtual_path: str,
    *,
    mode: str,
    scope_slug: str,
    scope_registry: dict[str, str],
) -> Path:
    parts = _safe_output_parts(virtual_path)
    if not parts:
        raise ValueError(f"Unsafe virtual path: {virtual_path}")

    if parts == ["companies.json"]:
        return root / "companies.json"

    if parts[0] == "companies" and len(parts) >= 2 and parts[1] in set(scope_registry.values()):
        return root.joinpath(*parts)

    if mode == "brief" and parts[0] == "briefs":
        return root.joinpath(*parts)

    raise ValueError(
        "Unexpected virtual output path "
        f"{virtual_path!r}. Write fact artifacts under /companies/<uuid>/ "
        "and brief artifacts under /briefs/<scope>/."
    )


def _persist_virtual_files(
    root: Path,
    files: dict[str, object],
    *,
    mode: str,
    scope_slug: str,
    scope_registry: dict[str, str],
) -> list[Path]:
    written: list[Path] = []
    for virtual_path, entry in sorted(files.items()):
        content = _file_content(entry)
        if content is None:
            continue
        if not virtual_path.startswith("/"):
            virtual_path = "/" + virtual_path
        if virtual_path.startswith("/large_tool_results/"):
            continue
        output_path = _mapped_output_path(
            root,
            virtual_path,
            mode=mode,
            scope_slug=scope_slug,
            scope_registry=scope_registry,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        written.append(output_path)
    return written


def _load_company_registry(output_dir: Path) -> dict[str, str]:
    path = output_dir / "companies.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if isinstance(v, str)}


def _registry_for_scope(scope: str, existing: dict[str, str] | None = None) -> dict[str, str]:
    registry = dict(existing or {})
    existing_by_lower = {name.lower(): name for name in registry}
    scoped: dict[str, str] = {}

    for name in _candidate_company_names(scope):
        existing = existing_by_lower.get(name.lower())
        if existing is None:
            scoped[name] = str(uuid.uuid5(uuid.NAMESPACE_URL, f"competitive-intel:{name.lower()}"))
        else:
            scoped[existing] = registry[existing]
    return scoped


def _merge_company_registry(output_dir: Path, scope: str) -> tuple[dict[str, str], Path]:
    registry = _load_company_registry(output_dir)
    existing_by_lower = {name.lower(): name for name in registry}

    for name in _candidate_company_names(scope):
        existing = existing_by_lower.get(name.lower())
        if existing is None:
            registry[name] = str(uuid.uuid5(uuid.NAMESPACE_URL, f"competitive-intel:{name.lower()}"))

    path = output_dir / "companies.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(registry.items())), indent=2) + "\n", encoding="utf-8")
    return _registry_for_scope(scope, registry), path


def _registry_file_data(registry: dict[str, str]) -> dict[str, dict[str, str]]:
    content = json.dumps(registry, indent=2) + "\n"
    return {"/companies.json": {"content": content, "encoding": "utf-8"}}


def _company_dirs(output_dir: Path, scope_registry: dict[str, str]) -> list[Path]:
    return [output_dir / "companies" / company_id for company_id in scope_registry.values()]


def _fact_files(output_dir: Path, scope_registry: dict[str, str]) -> list[Path]:
    paths: list[Path] = []
    registry_path = output_dir / "companies.json"
    if registry_path.exists():
        paths.append(registry_path)
    for company_dir in _company_dirs(output_dir, scope_registry):
        for name in COMPANY_FACT_FILES:
            path = company_dir / name
            if path.is_file():
                paths.append(path)
    return sorted(set(paths))


def _facts_exist(output_dir: Path, scope_registry: dict[str, str]) -> bool:
    return any((company_dir / "facts.yaml").exists() or (company_dir / "sources.md").exists() for company_dir in _company_dirs(output_dir, scope_registry))


def _missing_company_fact_files(output_dir: Path, scope_registry: dict[str, str]) -> list[Path]:
    missing: list[Path] = []
    for company_dir in _company_dirs(output_dir, scope_registry):
        for name in COMPANY_FACT_FILES:
            path = company_dir / name
            if not path.is_file():
                missing.append(path)
    return missing


def _load_fact_files(output_dir: Path, scope_registry: dict[str, str]) -> dict[str, dict[str, str]]:
    loaded: dict[str, dict[str, str]] = {}
    for path in _fact_files(output_dir, scope_registry):
        rel = path.relative_to(output_dir).as_posix()
        loaded["/" + rel] = {"content": path.read_text(encoding="utf-8"), "encoding": "utf-8"}
    return loaded


def _print_existing_facts(console: Console, output_dir: Path, scope_registry: dict[str, str]) -> None:
    files = _fact_files(output_dir, scope_registry)
    if not files:
        console.print("[yellow]No persisted fact files found.[/]")
        return

    console.print(Panel(f"[bold]Fact root:[/] {output_dir}", title="existing facts", border_style="green"))
    for path in files:
        console.print(f"[green]•[/] {path.relative_to(output_dir)}")

    for company_dir in _company_dirs(output_dir, scope_registry):
        summary = company_dir / "run-summary.md"
        if summary.exists():
            console.print(Rule(f"{company_dir.name} run summary", style="dim"))
            console.print(Markdown(summary.read_text(encoding="utf-8")))


def _company_folder_instructions(scope_registry: dict[str, str]) -> str:
    lines = ["COMPANY OUTPUT FOLDERS:"]
    for name, company_id in scope_registry.items():
        lines.append(f"- {name}: /companies/{company_id}")
    return "\n".join(lines)


def _run_agent(
    *,
    console: Console,
    mode: str,
    model: str,
    recursion_limit: int,
    user_request: str,
    initial_files: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    agent = build_agent(model_name=model, mode=mode)  # type: ignore[arg-type]
    input_state: dict[str, Any] = {"messages": [{"role": "user", "content": user_request}]}
    if initial_files:
        input_state["files"] = initial_files

    stream = agent.stream(
        input_state,
        config={"recursion_limit": recursion_limit},
        stream_mode="updates",
        subgraphs=True,
    )
    return render_stream(console, stream)


@app.command()
def main(
    scope: Annotated[
        str,
        typer.Argument(help='Company or comparison scope, e.g. "Tavily vs Exa vs Parallel".'),
    ],
    gather_facts: Annotated[
        bool,
        typer.Option("--gather-facts", help="Collect or list persisted fact ledgers for this scope."),
    ] = False,
    generate_brief: Annotated[
        str | None,
        typer.Option("--generate-brief", help="Generate a brief from persisted facts using this guidance prompt."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Rerun fact collection even if fact files already exist."),
    ] = False,
    model: Annotated[
        str,
        typer.Option("--model", "-m", help="Any tool-calling capable model served by Nebius Token Factory."),
    ] = "moonshotai/Kimi-K2.5",
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Directory for persisted fact and draft artifacts."),
    ] = Path("./output"),
    recursion_limit: Annotated[
        int,
        typer.Option(help="LangGraph recursion limit. Bump for larger scopes."),
    ] = 180,
) -> None:
    """Run exactly one phase: gather facts or generate a brief."""
    load_dotenv()
    console = Console()

    if gather_facts == bool(generate_brief):
        console.print(
            Panel(
                "Choose exactly one mode:\n\n"
                "[cyan]--gather-facts[/]\n"
                "[cyan]--generate-brief \"<guidance prompt>\"[/]",
                title="mode required",
                border_style="red",
            )
        )
        raise typer.Exit(code=2)

    _check_env(console)

    scope_slug = _slugify(scope)

    if gather_facts:
        scope_registry, registry_path = _merge_company_registry(output, scope)

        if _facts_exist(output, scope_registry) and not force:
            _print_existing_facts(console, output, scope_registry)
            return

        if force:
            for company_dir in _company_dirs(output, scope_registry):
                if company_dir.exists():
                    shutil.rmtree(company_dir)

        console.print(
            Panel(
                f"[bold]Scope:[/] {scope}\n"
                f"[bold]Mode:[/] gather facts\n"
                f"[bold]Output root:[/] {output}\n"
                f"[bold]Registry:[/] {registry_path}",
                title="source-backed fact collection",
                border_style="cyan",
            )
        )
        console.print(Rule("live agent activity", style="dim"))

        user_request = (
            "MODE: gather facts only.\n"
            f"SCOPE: {scope}\n\n"
            f"EXPLICIT COMPANIES TO RESEARCH: {', '.join(_candidate_company_names(scope))}\n"
            f"{_company_folder_instructions(scope_registry)}\n\n"
            "Do not discover or research additional competitors unless the scope explicitly asks for competitor discovery.\n\n"
            "Build persisted source packs, claim ledgers, a verification queue, and a run summary. "
            "Do not generate a marketing brief. Write company artifacts only under the UUID folders listed above: "
            "company.json, sources.md, facts.yaml, verification-queue.md, and run-summary.md. "
            "Keep /companies.json at the root as the global name-to-UUID registry. "
            "Do not stop after writing company.json; the run is incomplete until every listed company folder has all five files."
        )
        try:
            final = _run_agent(
                console=console,
                mode="facts",
                model=model,
                recursion_limit=recursion_limit,
                user_request=user_request,
                initial_files=_registry_file_data(_load_company_registry(output)),
            )
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted.[/]")
            sys.exit(130)

        written = _persist_virtual_files(
            output,
            final["files"],
            mode="facts",
            scope_slug=scope_slug,
            scope_registry=scope_registry,
        )
        if registry_path not in written:
            written.append(registry_path)
        console.print(Rule("artifacts", style="dim"))
        if not written:
            console.print(
                Panel(
                    f"No files were written by the agent. Virtual files seen: {list(final['files'].keys()) or '(none)'}",
                    title="no artifacts produced",
                    border_style="red",
                )
            )
            raise typer.Exit(code=2)
        for path in written:
            console.print(f"[green]✓[/] {path}")
        missing = _missing_company_fact_files(output, scope_registry)
        if missing:
            console.print(
                Panel(
                    "\n".join(str(path) for path in missing),
                    title="completing missing fact artifacts",
                    border_style="yellow",
                )
            )
            completion_request = (
                "MODE: gather facts completion pass.\n"
                f"SCOPE: {scope}\n\n"
                f"{_company_folder_instructions(scope_registry)}\n\n"
                "The broad research pass already created some company files. "
                "Read the existing /companies.json registry and each relevant /companies/<uuid>/ folder. "
                "Write only the missing required company artifacts listed below. "
                "Use existing sources.md first; use Tavily extract/search only when a needed fact is not present in the existing files. "
                "Do not write old root-level /sources, /ledgers, /verification-queue.md, or /run-summary.md paths.\n\n"
                "MISSING FILES:\n"
                + "\n".join(f"- /{path.relative_to(output).as_posix()}" for path in missing)
            )
            completion = _run_agent(
                console=console,
                mode="facts",
                model=model,
                recursion_limit=recursion_limit,
                user_request=completion_request,
                initial_files=_load_fact_files(output, scope_registry),
            )
            completion_written = _persist_virtual_files(
                output,
                completion["files"],
                mode="facts",
                scope_slug=scope_slug,
                scope_registry=scope_registry,
            )
            for path in completion_written:
                if path not in written:
                    written.append(path)
                    console.print(f"[green]✓[/] {path}")
            missing = _missing_company_fact_files(output, scope_registry)

        if missing:
            console.print(
                Panel(
                    "\n".join(str(path) for path in missing),
                    title="missing required fact artifacts",
                    border_style="red",
                )
            )
            raise typer.Exit(code=2)
        return

    assert generate_brief is not None
    scope_registry = _registry_for_scope(scope, _load_company_registry(output))
    if not _facts_exist(output, scope_registry):
        console.print(
            Panel(
                f"No persisted facts found for scope [bold]{scope}[/].\n\n"
                f"Run: [cyan]uv run cli.py {json.dumps(scope)} --gather-facts[/]",
                title="facts required",
                border_style="red",
            )
        )
        raise typer.Exit(code=2)

    fact_files = _load_fact_files(output, scope_registry)
    console.print(
        Panel(
            f"[bold]Scope:[/] {scope}\n"
            f"[bold]Mode:[/] generate brief\n"
            f"[bold]Facts:[/] {len(fact_files)} files loaded from {output}\n"
            f"[bold]Guidance:[/] {_short(generate_brief, 180)}",
            title="brief generation from facts",
            border_style="cyan",
        )
    )
    console.print(Rule("live agent activity", style="dim"))

    user_request = (
        "MODE: generate brief from existing fact files only.\n"
        f"SCOPE: {scope}\n"
        f"BRIEF OUTPUT FOLDER: /briefs/{scope_slug}\n"
        f"GUIDANCE PROMPT: {generate_brief}\n\n"
        "Read the existing /companies.json registry and relevant /companies/<uuid>/ fact folders. "
        "Generate the requested draft from verified, copy-safe facts only. "
        f"Write /briefs/{scope_slug}/generated-brief.md and /briefs/{scope_slug}/run-summary.md."
    )

    try:
        final = _run_agent(
            console=console,
            mode="brief",
            model=model,
            recursion_limit=recursion_limit,
            user_request=user_request,
            initial_files=fact_files,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/]")
        sys.exit(130)

    written = _persist_virtual_files(
        output,
        final["files"],
        mode="brief",
        scope_slug=scope_slug,
        scope_registry=scope_registry,
    )
    console.print(Rule("artifacts", style="dim"))
    for path in written:
        console.print(f"[green]✓[/] {path}")

    draft = output / "briefs" / scope_slug / "generated-brief.md"
    if draft.exists():
        console.print(Rule("draft", style="dim"))
        console.print(Markdown(draft.read_text(encoding="utf-8")))


if __name__ == "__main__":
    app()
