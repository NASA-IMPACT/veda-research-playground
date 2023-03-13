import typer
from rich.table import Table
from rich.console import Console
from pick import pick
import veda_cli.applications.ecco as ecco

app = typer.Typer()

@app.command("list")
def list():
    console = Console()
    table = Table()

    table.add_column('Application Name', justify='left')
    table.add_column('Description', justify='left')
    table.add_column('Tags', justify='center')

    table.add_row('ECCO', 'Estimating the Circulation and Climate of the Ocean', 'OCEAN, CLIMATE')
    table.add_row('WRF', 'Weather Research & Forecasting Model', 'WEATHER, FORCASTING')

    console.print(table)
    

@app.command("info")
def info(application_name):
    print(f"Printing info for application", application_name)

@app.command("run")
def run():
    options = ["ECCO", "WRF" ]
    option, index = pick(options, "Select the application", indicator="=>")
    if option == 'ECCO':
        ecco.run_ecco()

