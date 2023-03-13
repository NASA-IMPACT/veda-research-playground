import typer
from rich.table import Table
from rich.console import Console

app = typer.Typer()

@app.command("list")
def list():
    console = Console()
    table = Table()

    table.add_column('Dataset Name', justify='left')
    table.add_column('Description', justify='left')
    table.add_column('Tags', justify='left')

    table.add_row('ECCO-NASA-V4', 'NASA Hosted ECCO V4 Dataset', 'OCEAN, CLIMATE')

    console.print(table)

@app.command("info")
def info(dataset_name):
    print("Printing dataset info")