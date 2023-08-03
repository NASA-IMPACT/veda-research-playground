import typer
from rich.table import Table
from rich.console import Console
from pysondb import db
import os
from rich import print
import boto3
from airavata_mft_cli import operations as ops
from typing import Optional


app = typer.Typer()

def get_db():
    return db.getDb(os.path.join(os.path.expanduser('~'), ".veda", "db.json"))

@app.command("list")
def list_outputs(executionid: str, prefix :Optional[str] = typer.Argument("")):
    db_conn = get_db()
    executions = db_conn.getBy({"type":"Execution", "executionId": executionid})
    ops.list(executions[0]["storageId"] + "/" + executions[0]["outputDir"] + "/" + prefix )
    #print(executions)


@app.command("download")
def download_outputs(executionid: str, output: str, destination: str ):
    db_conn = get_db()
    executions = db_conn.getBy({"type":"Execution", "executionId": executionid})
    ops.copy(executions[0]["storageId"] + "/" + executions[0]["outputDir"] + "/" + output, "local-agent/" + destination)
    #print(executions)