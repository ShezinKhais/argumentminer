"""ArgumentMiner CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from argumentminer.segmenter import ArgumentSegmenter
from argumentminer.fallacy import FallacyDetector
from argumentminer.graph import build_graph
from argumentminer.visualiser import render_text_tree, render_html

app     = typer.Typer(name="argumentminer", add_completion=False)
console = Console()


@app.command("mine")
def mine(
    text: str   = typer.Argument(None, help="Text to analyse (or use --file)"),
    file: Path  = typer.Option(None, "--file", "-f", help="Read text from file"),
    html_out: Path = typer.Option(None, "--html", help="Save HTML graph"),
    json_out: Path = typer.Option(None, "--json", help="Save JSON output"),
    no_fallacies: bool = typer.Option(False, "--no-fallacies"),
):
    """Segment text into argument units, build a graph, and detect fallacies."""
    if file:
        text = file.read_text(encoding="utf-8")
    if not text:
        console.print("[red]Provide text as argument or with --file[/red]")
        raise typer.Exit(1)

    segmenter = ArgumentSegmenter()
    detector  = FallacyDetector()

    segments  = segmenter.segment(text)
    graph     = build_graph(segments)

    console.print("\n[bold]Argument Structure:[/bold]")
    console.print(render_text_tree(graph))

    # Keyed by unit so the HTML report can mark a match on the unit it fired on
    # rather than filing it in a list of its own.
    unit_fallacies = None if no_fallacies else {
        node.id: detector.detect_unique(node.segment.text) for node in graph.nodes
    }

    if not no_fallacies:
        fallacies = detector.detect_unique(text)
        if fallacies:
            table = Table(title="Detected Fallacies")
            table.add_column("Fallacy")
            table.add_column("Matched Text")
            table.add_column("Confidence")
            for f in fallacies:
                table.add_row(f.name, f.matched_text, f"{f.confidence:.0%}")
            console.print(table)
        else:
            console.print("[green]No obvious fallacies detected.[/green]")

    if html_out:
        render_html(
            graph,
            title="ArgumentMiner Analysis",
            output_path=html_out,
            fallacies=unit_fallacies,
            source=str(file) if file else "text passed on the command line",
        )
        console.print(f"HTML saved -> {html_out}")

    if json_out:
        data = {
            "segments": [{"text": s.text, "type": s.type,
                           "confidence": s.confidence} for s in segments],
            "graph": graph.to_dict(),
        }
        json_out.write_text(json.dumps(data, indent=2))
        console.print(f"JSON saved -> {json_out}")


@app.command("fallacies")
def fallacies(
    text: str  = typer.Argument(None, help="Text to scan (or use --file)"),
    file: Path = typer.Option(None, "--file", "-f", help="Read text from file"),
):
    """List the logical fallacies detected in the text, without building a graph."""
    if file:
        text = file.read_text(encoding="utf-8")
    if not text:
        console.print("[red]Provide text as argument or with --file[/red]")
        raise typer.Exit(1)

    detected = FallacyDetector().detect_unique(text)
    if not detected:
        console.print("[green]No obvious fallacies detected.[/green]")
        return
    table = Table(title="Detected Fallacies")
    table.add_column("Fallacy")
    table.add_column("Matched Text")
    table.add_column("Confidence")
    for f in detected:
        table.add_row(f.name, f.matched_text, f"{f.confidence:.0%}")
    console.print(table)


if __name__ == "__main__":
    app()
