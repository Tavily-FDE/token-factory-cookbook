"""CLI for the fact-ledger competitive-intelligence agent.

Two explicit steps, run one company at a time in the fact phase:

    uv run cli.py "Tavily" --gather-facts
    uv run cli.py "Tavily vs Exa" --write "Write a Tavily-favored comparison page"

Facts are persisted under the output directory by scope. Brief generation reads
those persisted facts and does not rediscover the web.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import uuid
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Iterable

import typer
import yaml
from deepagents.backends import CompositeBackend, FilesystemBackend
from deepagents.middleware.filesystem import FilesystemPermission
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, ToolMessage
from pydantic import ValidationError
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from fact_agent import build_fact_agent
from model_factory import model_provider
from schemas import ClaimCandidate
from writer_agent import build_writer_agent

DEFAULT_COORDINATOR_MODEL = "zai-org/GLM-5.2"
DEFAULT_SUBAGENT_MODEL = "moonshotai/Kimi-K2.6"
DEFAULT_LEDGER_WRITER_MODEL = "openai:gpt-5.4"

_TODO_TOOL = "write_todos"
_TASK_TOOL = "task"
_WRITE_FILE_TOOL = "write_file"
_SKILLS_ROOT = Path(__file__).parent / "skills"

_STATUS_ICON = {"pending": "○", "in_progress": "◐", "completed": "●"}
_STATUS_STYLE = {"pending": "dim", "in_progress": "yellow", "completed": "green"}

COMPANY_FACT_FILES = (
    "company.json",
    "sources.md",
    "facts.yaml",
    "verification-queue.md",
)

WRITER_FILES = (
    "draft.md",
    "claims-used.md",
    "avoided-claims.md",
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
    help="Build competitor fact ledgers or write markdown assets from existing ledgers.",
)


def _check_env(console: Console, *, mode: str, model_specs: list[str]) -> None:
    required = set()
    if mode == "facts":
        required.add("TAVILY_API_KEY")

    for model_spec in model_specs:
        provider = model_provider(model_spec)
        if provider == "nebius":
            required.add("NEBIUS_API_KEY")
        elif provider == "openai":
            required.add("OPENAI_API_KEY")

    missing = sorted(k for k in required if not os.getenv(k))
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


def _company_scaffold(name: str, company_id: str, scope: str) -> dict[str, Any]:
    return {
        "uuid": company_id,
        "name": name,
        "scope": scope,
        "research_status": "initialized",
        "date_researched": date.today().isoformat(),
    }


def _write_company_scaffolds(output_dir: Path, scope: str, scope_registry: dict[str, str]) -> list[Path]:
    written: list[Path] = []
    for name, company_id in scope_registry.items():
        path = output_dir / "companies" / company_id / "company.json"
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_company_scaffold(name, company_id, scope), indent=2) + "\n", encoding="utf-8")
        written.append(path)
    return written


def _company_dirs(output_dir: Path, scope_registry: dict[str, str]) -> list[Path]:
    return [output_dir / "companies" / company_id for company_id in scope_registry.values()]


def _research_files(company_dir: Path) -> list[Path]:
    research_dir = company_dir / "research"
    if not research_dir.is_dir():
        return []
    return sorted(research_dir.glob("*.md"))


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
        paths.extend(_research_files(company_dir))
    return sorted(set(paths))


def _facts_complete_for_company(company_dir: Path) -> bool:
    if not (company_dir / "facts.yaml").is_file():
        return False
    if not (company_dir / "sources.md").is_file():
        return False
    if not _research_files(company_dir):
        return False
    return True


def _facts_exist(output_dir: Path, scope_registry: dict[str, str]) -> bool:
    return all(_facts_complete_for_company(c) for c in _company_dirs(output_dir, scope_registry))


def _company_research_complete(company_dir: Path) -> bool:
    """Research phase done — explorer + researchers, synthesis pending.

    True when the explorer artifact (`research/source_pack.md`) exists and at
    least one additional `research/*.md` topic file from a researcher exists.
    Used to detect the resume case where expensive crawling is already on disk
    but `facts.yaml` / `sources.md` synthesis did not complete.
    """
    if not (company_dir / "research" / "source_pack.md").is_file():
        return False
    other_topic_files = [p for p in _research_files(company_dir) if p.name != "source_pack.md"]
    return bool(other_topic_files)


def _company_needs_synthesis_only(company_dir: Path) -> bool:
    """Research on disk, but at least one synthesis artifact missing."""
    if not _company_research_complete(company_dir):
        return False
    return any(
        not (company_dir / name).is_file()
        for name in ("sources.md", "facts.yaml", "verification-queue.md")
    )


def _missing_company_fact_files(output_dir: Path, scope_registry: dict[str, str]) -> list[Path]:
    missing: list[Path] = []
    for company_dir in _company_dirs(output_dir, scope_registry):
        for name in COMPANY_FACT_FILES:
            path = company_dir / name
            if not path.is_file():
                missing.append(path)
        # Variable-named research artifacts are produced by subagents; require
        # at least one under research/, but do not pin specific filenames.
        if not _research_files(company_dir):
            missing.append(company_dir / "research" / "source_pack.md")
    return missing


def _missing_writer_files(output_dir: Path, scope_slug: str) -> list[Path]:
    draft_dir = output_dir / "drafts" / scope_slug
    return [draft_dir / name for name in WRITER_FILES if not (draft_dir / name).is_file()]


def _writer_files(output_dir: Path, scope_slug: str) -> list[Path]:
    draft_dir = output_dir / "drafts" / scope_slug
    return sorted(draft_dir / name for name in WRITER_FILES if (draft_dir / name).is_file())


def _load_fact_files(output_dir: Path, scope_registry: dict[str, str]) -> dict[str, dict[str, str]]:
    loaded: dict[str, dict[str, str]] = {}
    for path in _fact_files(output_dir, scope_registry):
        rel = path.relative_to(output_dir).as_posix()
        loaded["/" + rel] = {"content": path.read_text(encoding="utf-8"), "encoding": "utf-8"}
    return loaded


def _validate_fact_virtual_files(
    files: dict[str, object],
    scope_registry: dict[str, str],
) -> list[str]:
    warnings: list[str] = []
    allowed_company_ids = set(scope_registry.values())

    for virtual_path, entry in sorted(files.items()):
        content = _file_content(entry)
        if content is None:
            continue
        if not virtual_path.startswith("/"):
            virtual_path = "/" + virtual_path

        parts = _safe_output_parts(virtual_path)
        if (
            len(parts) == 3
            and parts[0] == "companies"
            and parts[1] in allowed_company_ids
            and parts[2] == "facts.yaml"
        ):
            try:
                parsed = yaml.safe_load(content) or []
            except yaml.YAMLError as exc:
                warnings.append(f"{virtual_path}: invalid YAML ({exc})")
                continue

            if not isinstance(parsed, list):
                warnings.append(f"{virtual_path}: expected a list of claim records")
                continue

            for index, item in enumerate(parsed, start=1):
                if not isinstance(item, dict):
                    warnings.append(f"{virtual_path}: claim {index} is not a mapping")
                    continue
                try:
                    ClaimCandidate.model_validate(item)
                except ValidationError as exc:
                    first_error = exc.errors()[0]
                    field = ".".join(str(part) for part in first_error.get("loc", ())) or "record"
                    warnings.append(f"{virtual_path}: claim {index} invalid at {field}: {first_error.get('msg')}")

    return warnings


def _print_existing_facts(console: Console, output_dir: Path, scope_registry: dict[str, str]) -> None:
    files = _fact_files(output_dir, scope_registry)
    if not files:
        console.print("[yellow]No persisted fact files found.[/]")
        return

    console.print(Panel(f"[bold]Fact root:[/] {output_dir}", title="existing facts", border_style="green"))
    for path in files:
        console.print(f"[green]•[/] {path.relative_to(output_dir)}")


def _build_backend(output_dir: Path) -> CompositeBackend:
    output_dir.mkdir(parents=True, exist_ok=True)
    return CompositeBackend(
        default=FilesystemBackend(root_dir=output_dir.resolve(), virtual_mode=True),
        routes={
            "/skills/facts/": FilesystemBackend(root_dir=(_SKILLS_ROOT / "facts").resolve(), virtual_mode=True),
            "/skills/writers/": FilesystemBackend(root_dir=(_SKILLS_ROOT / "writers").resolve(), virtual_mode=True),
        },
    )


def _filesystem_permissions() -> list[FilesystemPermission]:
    return [
        FilesystemPermission(["read"], ["/", "/companies.json", "/companies", "/companies/**", "/drafts", "/drafts/**"]),
        FilesystemPermission(["read"], ["/skills", "/skills/**"]),
        FilesystemPermission(["read", "write"], ["/large_tool_results", "/large_tool_results/**"]),
        FilesystemPermission(["write"], ["/companies", "/companies/**", "/drafts", "/drafts/**"]),
        FilesystemPermission(["write"], ["/companies.json", "/skills", "/skills/**"], mode="deny"),
        FilesystemPermission(["read", "write"], ["/**"], mode="deny"),
    ]


def _run_agent(
    *,
    console: Console,
    mode: str,
    model: str,
    subagent_model: str | None,
    explorer_model: str | None = None,
    researcher_model: str | None = None,
    ledger_writer_model: str | None = None,
    recursion_limit: int,
    user_request: str,
    output_dir: Path,
) -> dict[str, Any]:
    backend = _build_backend(output_dir)
    permissions = _filesystem_permissions()
    if mode == "facts":
        agent = build_fact_agent(
            model_name=model,
            explorer_model_name=explorer_model or subagent_model,
            researcher_model_name=researcher_model or subagent_model,
            ledger_writer_model_name=ledger_writer_model or subagent_model,
            backend=backend,
            permissions=permissions,
        )
    elif mode == "write":
        agent = build_writer_agent(
            model_name=model,
            subagent_model_name=subagent_model,
            backend=backend,
            permissions=permissions,
        )
    else:
        raise ValueError(f"Unknown agent mode: {mode}")
    input_state: dict[str, Any] = {"messages": [{"role": "user", "content": user_request}]}

    stream = agent.stream(
        input_state,
        config={"recursion_limit": recursion_limit},
        stream_mode="updates",
        subgraphs=True,
    )
    return render_stream(console, stream)


def _gather_facts_user_request(scope: str, company_name: str, company_uuid: str) -> str:
    return (
        "MODE: gather facts only.\n"
        f"SCOPE: {scope}\n"
        f"COMPANY: {company_name}\n"
        f"COMPANY FOLDER: /companies/{company_uuid}\n\n"
        "Do not discover or research additional competitors. "
        "Do not rewrite /companies.json. "
        "Do not write marketing copy."
    )


def _synthesize_facts_user_request(scope: str, company_name: str, company_uuid: str, output_dir: Path) -> str:
    """Resume request: research already on disk, only synthesize final artifacts.

    Tells the coordinator to skip explorer/researchers and dispatch the
    `ledger-writer` directly with the list of existing `research/*.md` files
    to read. Salvages expensive crawl output when synthesis did not complete.
    """
    research_dir = output_dir / "companies" / company_uuid / "research"
    research_files = sorted(p.name for p in _research_files(research_dir.parent))
    file_list = "\n".join(f"- /companies/{company_uuid}/research/{name}" for name in research_files)
    return (
        "MODE: synthesize facts only (resume).\n"
        f"SCOPE: {scope}\n"
        f"COMPANY: {company_name}\n"
        f"COMPANY FOLDER: /companies/{company_uuid}\n\n"
        "Research phase is already complete. The following research files exist "
        "on disk and must NOT be regenerated, overwritten, or deleted:\n"
        f"{file_list}\n\n"
        "Do not dispatch the `explorer` subagent. Do not dispatch `researcher` "
        "subagents. Do not browse, search, extract, map, or crawl. Do not "
        "rewrite /companies.json or /companies/<uuid>/company.json. Do not "
        "write marketing copy.\n\n"
        "Dispatch the `ledger-writer` subagent exactly once. Pass it the "
        f"company name ({company_name}), the UUID folder "
        f"(/companies/{company_uuid}), and the full list of research files "
        "above. The ledger-writer reads those files plus "
        "/skills/facts/claim-ledger-builder/SKILL.md and "
        "/skills/facts/claim-safety-review/SKILL.md, then writes "
        f"/companies/{company_uuid}/sources.md, "
        f"/companies/{company_uuid}/facts.yaml, "
        f"/companies/{company_uuid}/verification-queue.md with `write_file`."
    )


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
    write: Annotated[
        str | None,
        typer.Option("--write", help="Write a markdown asset from persisted facts using this guidance prompt."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Rerun fact collection even if fact files already exist."),
    ] = False,
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Coordinator model spec. Use openai:<model> or nebius:<model>; bare names use Nebius.",
        ),
    ] = DEFAULT_COORDINATOR_MODEL,
    subagent_model: Annotated[
        str | None,
        typer.Option(
            "--subagent-model",
            help=(
                "Default subagent model spec (applies to explorer, researcher, "
                "and ledger-writer unless overridden). Use openai:<model> or "
                f"nebius:<model>. Defaults to {DEFAULT_SUBAGENT_MODEL}."
            ),
        ),
    ] = DEFAULT_SUBAGENT_MODEL,
    explorer_model: Annotated[
        str | None,
        typer.Option(
            "--explorer-model",
            help="Explorer subagent model spec. Defaults to --subagent-model.",
        ),
    ] = None,
    researcher_model: Annotated[
        str | None,
        typer.Option(
            "--researcher-model",
            help="Researcher subagent model spec. Defaults to --subagent-model.",
        ),
    ] = None,
    ledger_writer_model: Annotated[
        str | None,
        typer.Option(
            "--ledger-writer-model",
            help=(
                "Ledger-writer subagent model spec. Defaults to --subagent-model. "
                "Point this at a strong long-context model for reliable "
                "synthesis of research/*.md into facts.yaml."
            ),
        ),
    ] = DEFAULT_LEDGER_WRITER_MODEL,
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Directory for persisted fact and draft artifacts."),
    ] = Path("./output"),
    recursion_limit: Annotated[
        int,
        typer.Option(help="LangGraph recursion limit. Bump for larger scopes."),
    ] = 180,
) -> None:
    """Run exactly one phase: gather facts or write from existing facts."""
    load_dotenv()
    console = Console()

    if gather_facts == bool(write):
        console.print(
            Panel(
                "Choose exactly one mode:\n\n"
                "[cyan]--gather-facts[/]\n"
                "[cyan]--write \"<guidance prompt>\"[/]",
                title="mode required",
                border_style="red",
            )
        )
        raise typer.Exit(code=2)

    mode = "facts" if gather_facts else "write"
    # Collect every model spec actually in play so _check_env validates all
    # provider keys at once (e.g. mixing openai ledger-writer with nebius
    # coordinator requires both OPENAI_API_KEY and NEBIUS_API_KEY).
    model_specs = [model, subagent_model]
    if mode == "facts":
        model_specs.extend(m for m in (explorer_model, researcher_model, ledger_writer_model) if m)
    _check_env(console, mode=mode, model_specs=[m for m in model_specs if m])

    scope_slug = _slugify(scope)

    if gather_facts:
        scope_registry, registry_path = _merge_company_registry(output, scope)

        if _facts_exist(output, scope_registry) and not force:
            _print_existing_facts(console, output, scope_registry)
            return

        if force:
            # `--force` is an explicit full rebuild: wipe the whole company
            # folder (research + synthesis). Do not wipe partial state without
            # `--force` — the resume path below salvages on-disk research.
            for company_dir in _company_dirs(output, scope_registry):
                if company_dir.exists():
                    shutil.rmtree(company_dir)

        scaffold_paths = _write_company_scaffolds(output, scope, scope_registry)

        # Resolve effective per-subagent models for display + dispatch.
        explorer_m = explorer_model or subagent_model
        researcher_m = researcher_model or subagent_model
        ledger_writer_m = ledger_writer_model or subagent_model

        console.print(
            Panel(
                f"[bold]Scope:[/] {scope}\n"
                f"[bold]Mode:[/] gather facts\n"
                f"[bold]Output root:[/] {output}\n"
                f"[bold]Registry:[/] {registry_path}\n"
                f"[bold]Coordinator:[/] {model}\n"
                f"[bold]Explorer:[/] {explorer_m}\n"
                f"[bold]Researcher:[/] {researcher_m}\n"
                f"[bold]Ledger-writer:[/] {ledger_writer_m}",
                title="source-backed fact collection",
                border_style="cyan",
            )
        )

        last_stream_files: dict[str, Any] = {}
        for company_name, company_uuid in scope_registry.items():
            company_dir = output / "companies" / company_uuid
            if not force and _company_needs_synthesis_only(company_dir):
                resume_request = _synthesize_facts_user_request(scope, company_name, company_uuid, output)
                console.print(Rule(f"company: {company_name} ({company_uuid}) — resume synthesis only", style="yellow"))
                try:
                    result = _run_agent(
                        console=console,
                        mode="facts",
                        model=model,
                        subagent_model=subagent_model,
                        explorer_model=explorer_model,
                        researcher_model=researcher_model,
                        ledger_writer_model=ledger_writer_model,
                        recursion_limit=recursion_limit,
                        user_request=resume_request,
                        output_dir=output,
                    )
                except KeyboardInterrupt:
                    console.print("\n[yellow]Interrupted.[/]")
                    sys.exit(130)
                last_stream_files = result.get("files", {})
                continue

            console.print(Rule(f"company: {company_name} ({company_uuid})", style="cyan"))
            try:
                result = _run_agent(
                    console=console,
                    mode="facts",
                    model=model,
                    subagent_model=subagent_model,
                    explorer_model=explorer_model,
                    researcher_model=researcher_model,
                    ledger_writer_model=ledger_writer_model,
                    recursion_limit=recursion_limit,
                    user_request=_gather_facts_user_request(scope, company_name, company_uuid),
                    output_dir=output,
                )
            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted.[/]")
                sys.exit(130)
            last_stream_files = result.get("files", {})

        validation_warnings = _validate_fact_virtual_files(_load_fact_files(output, scope_registry), scope_registry)
        if validation_warnings:
            console.print(
                Panel(
                    "\n".join(validation_warnings),
                    title="fact validation warnings",
                    border_style="yellow",
                )
            )

        written = _fact_files(output, scope_registry)
        for path in scaffold_paths:
            if path not in written:
                written.append(path)
        console.print(Rule("artifacts", style="dim"))
        if not written:
            console.print(
                Panel(
                    f"No files were written by the agent. Virtual files seen: {list(last_stream_files.keys()) or '(none)'}",
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
                    "\n".join(str(path) for path in missing)
                    + "\n\nRe-run without --force to resume synthesis from existing research; "
                    "use --force only for a full rebuild (wipes research).",
                    title="missing fact artifacts (non-fatal)",
                    border_style="yellow",
                )
            )
        return

    assert write is not None
    scope_registry = _registry_for_scope(scope, _load_company_registry(output))
    if not _facts_exist(output, scope_registry):
        console.print(
            Panel(
                f"No complete facts found for scope [bold]{scope}[/].\n\n"
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
            f"[bold]Mode:[/] write from facts\n"
            f"[bold]Facts:[/] {len(fact_files)} files loaded from {output}\n"
            f"[bold]Guidance:[/] {_short(write, 180)}",
            title="writer generation from facts",
            border_style="cyan",
        )
    )
    console.print(Rule("live agent activity", style="dim"))

    user_request = (
        "MODE: write markdown asset from existing fact files only.\n"
        f"SCOPE: {scope}\n"
        f"WRITER OUTPUT FOLDER: /drafts/{scope_slug}\n"
        f"GUIDANCE PROMPT: {write}\n\n"
        "Read the existing /companies.json registry and relevant /companies/<uuid>/ fact folders. "
        "Generate the requested markdown asset from verified, copy-safe facts only. "
        "Do not browse or perform fresh verification; if new verification is needed, note that the fact layer must be refreshed. "
        f"Write /drafts/{scope_slug}/draft.md, /drafts/{scope_slug}/claims-used.md, "
        f"and /drafts/{scope_slug}/avoided-claims.md."
    )

    try:
        final = _run_agent(
            console=console,
            mode="write",
            model=model,
            subagent_model=subagent_model,
            recursion_limit=recursion_limit,
            user_request=user_request,
            output_dir=output,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/]")
        sys.exit(130)

    written = _writer_files(output, scope_slug)
    console.print(Rule("artifacts", style="dim"))
    if not written:
        console.print(
            Panel(
                f"No draft files were written by the agent. Virtual files seen: {list(final['files'].keys()) or '(none)'}",
                title="no draft artifacts produced",
                border_style="red",
            )
        )
        raise typer.Exit(code=2)
    for path in written:
        console.print(f"[green]✓[/] {path}")

    missing = _missing_writer_files(output, scope_slug)
    if missing:
        console.print(
            Panel(
                "\n".join(str(path) for path in missing),
                title="missing required writer artifacts",
                border_style="red",
            )
        )
        raise typer.Exit(code=2)

    draft = output / "drafts" / scope_slug / "draft.md"
    if draft.exists():
        console.print(Rule("draft", style="dim"))
        console.print(Markdown(draft.read_text(encoding="utf-8")))


if __name__ == "__main__":
    app()
