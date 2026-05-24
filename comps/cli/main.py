"""Typer CLI. --json is the difference between a CLI that lives in users'
shells and one that doesn't — pipe-ability is the whole point.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from comps.cli import history
from comps.cli.format import fmt_mult, fmt_usd, truncate
from comps.core.logging import configure

app = typer.Typer(
    help="comps — financial deal comparables search.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _print_results(query: str, results: list[dict]) -> None:
    t = Table(title=f"Comps for: {query}", show_lines=False, header_style="bold")
    t.add_column("#", justify="right", style="dim", width=3)
    t.add_column("Target")
    t.add_column("Buyer")
    t.add_column("Yr", justify="right")
    t.add_column("Rev", justify="right")
    t.add_column("EV", justify="right")
    t.add_column("EV/Rev", justify="right")
    t.add_column("EV/EBITDA", justify="right")
    t.add_column("Score", justify="right")
    t.add_column("Thesis")
    for i, r in enumerate(results, 1):
        t.add_row(
            str(i),
            r.get("target") or "—",
            r.get("buyer") or "—",
            str(r.get("year") or "—"),
            fmt_usd(r.get("revenue")),
            fmt_usd(r.get("ev_usd")),
            fmt_mult(r.get("ev_revenue_mult")),
            fmt_mult(r.get("ev_ebitda_mult")),
            f"{r.get('score') or 0:.2f}",
            truncate(r.get("thesis"), 60),
        )
    console.print(t)


async def _do_search(query: str, limit: int) -> list[dict]:
    # Local in-process search to avoid mandating a running API for the CLI.
    from comps.search.service import _search_core

    results = await _search_core(query, limit)
    return [r.model_dump() for r in results]


@app.command()
def search(
    query: str = typer.Argument(..., help="Natural-language search."),
    limit: int = typer.Option(10, "--limit", "-n"),
    json_out: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Search for deal comps."""
    configure()
    results = asyncio.run(_do_search(query, limit))
    history.save(query, results)
    if json_out:
        typer.echo(json.dumps(results, default=str))
        return
    if not results:
        console.print("[yellow]No results.[/yellow]")
        return
    _print_results(query, results)


@app.command("similar-to")
def similar_to(
    deal_id: int = typer.Argument(..., help="Deal id to seed similarity."),
    limit: int = typer.Option(10, "--limit", "-n"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Find deals similar to an existing deal."""
    configure()

    async def _run() -> list[dict]:
        from comps.db import queries

        deal = await queries.fetch_deal(deal_id)
        if not deal:
            raise typer.BadParameter(f"deal {deal_id} not found")
        seed = deal.get("thesis") or deal.get("target_name") or ""
        if not seed:
            raise typer.BadParameter(f"deal {deal_id} has no thesis text")
        return await _do_search(seed, limit + 1)

    results = asyncio.run(_run())
    results = [r for r in results if r.get("deal_id") != deal_id][:limit]
    history.save(f"similar-to {deal_id}", results)
    if json_out:
        typer.echo(json.dumps(results, default=str))
        return
    _print_results(f"similar to deal #{deal_id}", results)


@app.command()
def show(rank: int = typer.Argument(..., help="Rank from last search.")) -> None:
    """Full deal card for the rank-N result of the last search."""
    last = history.last()
    if not last:
        console.print("[red]No previous search in this session.[/red]")
        raise typer.Exit(1)
    _, results = last
    if rank < 1 or rank > len(results):
        console.print(f"[red]Rank {rank} out of range (1..{len(results)}).[/red]")
        raise typer.Exit(1)
    r = results[rank - 1]
    body = (
        f"[bold]{r.get('target') or '—'}[/bold]   "
        f"deal_id={r.get('deal_id')}   "
        f"year={r.get('year') or '—'}\n"
        f"Buyer:   {r.get('buyer') or '—'}\n"
        f"Sector:  {r.get('sector_gics') or '—'} ({r.get('region') or '—'})\n"
        f"Revenue: {fmt_usd(r.get('revenue'))}     "
        f"EV: {fmt_usd(r.get('ev_usd'))}\n"
        f"EV/Rev:  {fmt_mult(r.get('ev_revenue_mult'))}   "
        f"EV/EBITDA: {fmt_mult(r.get('ev_ebitda_mult'))}\n\n"
        f"{r.get('thesis') or '—'}"
    )
    console.print(Panel(body, title=f"#{rank}"))


@app.command()
def why(
    a: int = typer.Argument(..., help="First rank from last search."),
    b: int = typer.Argument(..., help="Second rank from last search."),
) -> None:
    """Side-by-side comparability for two ranks from the last search."""
    last = history.last()
    if not last:
        console.print("[red]No previous search in this session.[/red]")
        raise typer.Exit(1)
    _, results = last
    if not (1 <= a <= len(results) and 1 <= b <= len(results)):
        console.print(f"[red]Rank out of range (1..{len(results)}).[/red]")
        raise typer.Exit(1)
    ra, rb = results[a - 1], results[b - 1]
    t = Table(title=f"#{a} vs #{b}", show_lines=False)
    t.add_column("")
    t.add_column(ra.get("target") or "—")
    t.add_column(rb.get("target") or "—")
    rows = [
        ("Year", ra.get("year"), rb.get("year")),
        ("Buyer", ra.get("buyer"), rb.get("buyer")),
        ("Sector", ra.get("sector_gics"), rb.get("sector_gics")),
        ("Region", ra.get("region"), rb.get("region")),
        ("Revenue", fmt_usd(ra.get("revenue")), fmt_usd(rb.get("revenue"))),
        ("EV", fmt_usd(ra.get("ev_usd")), fmt_usd(rb.get("ev_usd"))),
        ("EV/Rev", fmt_mult(ra.get("ev_revenue_mult")), fmt_mult(rb.get("ev_revenue_mult"))),
        ("EV/EBITDA", fmt_mult(ra.get("ev_ebitda_mult")), fmt_mult(rb.get("ev_ebitda_mult"))),
    ]
    for label, av, bv in rows:
        t.add_row(label, str(av) if av is not None else "—", str(bv) if bv is not None else "—")
    console.print(t)
    console.print(Panel(ra.get("thesis") or "—", title=f"#{a} thesis", border_style="cyan"))
    console.print(Panel(rb.get("thesis") or "—", title=f"#{b} thesis", border_style="magenta"))


@app.command()
def ingest(
    paths: list[str] = typer.Argument(..., help="Document URIs or local paths."),
    kind: str = typer.Option("other", help="10-K, S-1, press, memo, CIM, other."),
    enqueue: bool = typer.Option(
        True,
        "--enqueue/--inline",
        help="Push to the worker queue, or run inline in this process.",
    ),
) -> None:
    """Ingest one or more documents."""
    configure()
    if enqueue:
        from comps.ingest.pipeline import enqueue as enqueue_fn

        asyncio.run(enqueue_fn(paths, kind))
        console.print(f"[green]Enqueued {len(paths)} document(s).[/green]")
        return

    from comps.ingest.pipeline import ingest_one

    async def _run() -> None:
        for p in paths:
            try:
                out = await ingest_one({}, p, kind)
                console.print(f"[green]ok[/green] {p} -> deal {out['deal_id']}")
            except Exception as e:
                console.print(f"[red]err[/red] {p}: {e}")

    asyncio.run(_run())


@app.command()
def migrate() -> None:
    """Apply all pending Postgres migrations."""
    from comps.db.migrate import run

    asyncio.run(run())
    console.print("[green]Migrations applied.[/green]")


@app.command(name="eval")
def eval_cmd(
    out: Path | None = typer.Option(None, "--out", help="Write report JSON here."),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Run the eval harness against the live system."""
    configure()
    from comps.eval.run import evaluate_default

    report = asyncio.run(evaluate_default())
    payload = report.model_dump()
    if out:
        out.write_text(json.dumps(payload, indent=2, default=str))
    if json_out:
        typer.echo(json.dumps(payload, default=str))
        return
    console.print(
        f"[bold]eval[/bold]  nDCG@10={report.mean_ndcg:.3f}  recall@20={report.mean_recall:.3f}  "
        f"(n={len(report.rows)})"
    )


if __name__ == "__main__":
    app()
