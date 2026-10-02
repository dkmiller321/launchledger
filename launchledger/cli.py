"""`ll`: seed, drift, eval and report commands.

By default the CLI reaches /systems/* in-process (no server needed). Pass --systems-url to
point it at a running server instead.
"""

import json
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(no_args_is_help=True, add_completion=False)
drift_app = typer.Typer(no_args_is_help=True)
eval_app = typer.Typer(no_args_is_help=True)
dw_app = typer.Typer(no_args_is_help=True)
demo_app = typer.Typer(no_args_is_help=True)
report_app = typer.Typer(no_args_is_help=True)
app.add_typer(drift_app, name="drift", help="Drift baseline, checks and injection.")
app.add_typer(eval_app, name="eval", help="Golden-case evals.")
app.add_typer(dw_app, name="dw", help="Data-warehouse rollups.")
app.add_typer(demo_app, name="demo", help="Demo data.")
app.add_typer(report_app, name="report", help="Leadership reports.")

SystemsUrl = Annotated[str | None, typer.Option(help="Use a running server's /systems.")]


def _connect(systems_url: str | None) -> None:
    import httpx

    from launchledger.systems.client import use_client_factory

    if systems_url:
        use_client_factory(lambda: httpx.Client(base_url=systems_url, timeout=15))
        return
    from starlette.testclient import TestClient

    from launchledger.main import app as asgi_app

    use_client_factory(lambda: TestClient(asgi_app, base_url="http://testserver"))


@app.command()
def seed(if_empty: Annotated[bool, typer.Option("--if-empty")] = False) -> None:
    """Load the deterministic seed into the system schemas."""
    from launchledger.ops import seed_systems

    done = seed_systems(if_empty=if_empty)
    typer.echo("seeded" if done else "already seeded; skipped")


@drift_app.command("baseline")
def drift_baseline(
    if_empty: Annotated[bool, typer.Option("--if-empty")] = False, systems_url: SystemsUrl = None
) -> None:
    """Capture value-distribution baselines from clean data."""
    from launchledger.contracts.monitor import capture_baselines, has_baselines

    _connect(systems_url)
    if if_empty and has_baselines():
        typer.echo("baselines exist; skipped")
        return
    capture_baselines()
    typer.echo("baselines captured")


@drift_app.command("check")
def drift_check(systems_url: SystemsUrl = None) -> None:
    """Run one drift-monitor pass."""
    from launchledger.contracts.monitor import check_now

    _connect(systems_url)
    found = check_now()
    typer.echo(f"{found} problem(s) found")


@drift_app.command("enable")
def drift_enable(scenario: str) -> None:
    from launchledger.drift.state import set_scenario

    set_scenario(scenario, True)
    typer.echo(f"{scenario} enabled")


@drift_app.command("disable")
def drift_disable(scenario: str) -> None:
    from launchledger.drift.state import set_scenario

    set_scenario(scenario, False)
    typer.echo(f"{scenario} disabled")


@eval_app.command("run")
def eval_run(
    model: Annotated[str, typer.Option(help="'mock' or an OpenRouter slug")] = "mock",
    workflow: Annotated[list[str] | None, typer.Option(help="W1..W12; repeatable")] = None,
    drift: Annotated[str | None, typer.Option(help="Run with a drift scenario injected")] = None,
    json_out: Annotated[Path | None, typer.Option(help="Write the JSON report here")] = None,
    systems_url: SystemsUrl = None,
) -> None:
    """Run the golden cases, print a summary, and exit 1 if the gate fails."""
    from launchledger.evals.runner import create_eval_run, execute_eval_run, gate_failures

    _connect(systems_url)
    eval_id = create_eval_run(model, drift)
    report = execute_eval_run(eval_id, model, workflow, drift)
    out = json_out or Path("eval-reports") / f"eval-{eval_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    typer.echo(f"eval run {eval_id} | model {model}" + (f" | drift {drift}" if drift else ""))
    for name, c in sorted(report["per_workflow"].items()):
        typer.echo(f"  {name:<20} {c['passed']}/{c['total']}")
    for case in report["cases"]:
        if not case["passed"]:
            typer.echo(f"  {case['case_id']}: {case['outcome']}: {'; '.join(case['diff'])}")
    typer.echo(
        f"passed {report['passed']}/{report['total']} | declined {report['declined']} | "
        f"wrong {report['wrong']}"
    )
    typer.echo(
        f"tokens {report['tokens']} | estimated cost ${report['cost_usd']:.4f} | "
        f"p95 latency {report['latency_ms_p95']} ms"
    )
    typer.echo(f"report: {out}")
    problems = gate_failures(report)
    for p in problems:
        typer.echo(f"GATE FAILED: {p}")
    raise typer.Exit(1 if problems else 0)


@dw_app.command("rebuild")
def dw_rebuild() -> None:
    """Recompute the data-warehouse rollups from ERP and MES."""
    from launchledger.clock import today
    from launchledger.db.session import session_scope
    from launchledger.systems.dw import rebuild_dw

    with session_scope() as s:
        rebuild_dw(s, today())
    typer.echo("data warehouse rebuilt")


if __name__ == "__main__":
    app()
