# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 AquaeAtrae
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import click

from .models import CodeplugOptions, NAME_LENGTHS
from .parsers import parser_for
from .parsers.pdf_parser import PdfParser
from .writers import writer_for
from .writers.chirp_writer import ChirpWriter
from .writers.review_writer import ReviewWriter


def _collect_channels(
    input_files: Sequence[Path],
    options: CodeplugOptions,
    ocr: bool = False,
) -> list:
    from .parsers.pdf_parser import PdfParser

    channels = []
    location = options.start_location

    for path in input_files:
        if path.suffix.lower() == ".pdf":
            p = PdfParser(options, ocr=ocr)
        else:
            p = parser_for(path, options)

        for ch in p.parse(path):
            ch.location = location
            location += 1
            channels.append(ch)

    return channels


@click.group()
def main() -> None:
    """Parse ICS-217A forms and generate radio codeplugs."""


@main.command()
@click.argument("input_files", nargs=-1, required=True,
                type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", default=None, type=click.Path(path_type=Path),
              help="Output file (default: <stem>_review.csv or combined_review.csv).")
@click.option("--start-location", default=0, show_default=True,
              help="First CHIRP memory slot number.")
@click.option("--skip-digital", is_flag=True, default=False,
              help="Omit digital (DMR/P25) channels.")
@click.option("--ocr", is_flag=True, default=False,
              help="Enable OCR fallback for scanned PDFs (requires [ocr] extra).")
def parse(
    input_files: tuple[Path, ...],
    output: Path | None,
    start_location: int,
    skip_digital: bool,
    ocr: bool,
) -> None:
    """Parse one or more input files into a Review CSV."""
    options = CodeplugOptions(start_location=start_location, skip_digital=skip_digital)
    channels = _collect_channels(list(input_files), options, ocr=ocr)

    if output is None:
        if len(input_files) == 1:
            output = input_files[0].with_name(input_files[0].stem + "_review.csv")
        else:
            output = Path("combined_review.csv")

    ReviewWriter(options).write(channels, output)
    click.echo(f"Wrote {len(channels)} channels -> {output}")


@main.command()
@click.argument("review_csv", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", default=None, type=click.Path(path_type=Path),
              help="Output CHIRP CSV (default: <stem>_chirp.csv).")
@click.option("--name-len", default=8, show_default=True,
              type=click.Choice([str(n) for n in NAME_LENGTHS]),
              help="Which Name_N column to use as the CHIRP Name field.")
def finalize(review_csv: Path, output: Path | None, name_len: str) -> None:
    """Strip review columns from a Review CSV and write final CHIRP CSV."""
    options = CodeplugOptions(name_len=int(name_len))
    if output is None:
        output = review_csv.with_name(review_csv.stem.removesuffix("_review") + "_chirp.csv")
    ChirpWriter(options).finalize_from_review(review_csv, output)
    click.echo(f"Finalized -> {output}")


@main.command()
@click.argument("input_files", nargs=-1, required=True,
                type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", default=None, type=click.Path(path_type=Path),
              help="Output CHIRP CSV (default: stdout).")
@click.option("--name-len", default=8, show_default=True,
              type=click.Choice([str(n) for n in NAME_LENGTHS]),
              help="Max channel name length.")
@click.option("--start-location", default=0, show_default=True)
@click.option("--skip-digital", is_flag=True, default=False)
@click.option("--ocr", is_flag=True, default=False)
def convert(
    input_files: tuple[Path, ...],
    output: Path | None,
    name_len: str,
    start_location: int,
    skip_digital: bool,
    ocr: bool,
) -> None:
    """One-shot: parse input(s) and write final CHIRP CSV without a review step."""
    options = CodeplugOptions(
        name_len=int(name_len),
        start_location=start_location,
        skip_digital=skip_digital,
    )
    channels = _collect_channels(list(input_files), options, ocr=ocr)
    dest = output
    result = ChirpWriter(options).write(channels, dest)
    if result:
        click.echo(result, nl=False)
    else:
        click.echo(f"Wrote {len(channels)} channels -> {output}")


@main.command()
@click.option("-o", "--output", default=None, type=click.Path(path_type=Path),
              help="Output Review CSV (default: manual_review.csv).")
def enter(output: Path | None) -> None:
    """Interactively enter channel data and write a Review CSV."""
    from .parsers.manual_parser import ManualParser

    options = CodeplugOptions()
    channels = list(ManualParser(options).parse())
    if not channels:
        click.echo("No channels entered.")
        return
    dest = output or Path("manual_review.csv")
    ReviewWriter(options).write(channels, dest)
    click.echo(f"Wrote {len(channels)} channels -> {dest}")
