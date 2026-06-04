import typer

app = typer.Typer(help="CBDB import and normalization tools for FigureChain.")


@app.callback()
def main() -> None:
    """FigureChain data import command line interface."""
