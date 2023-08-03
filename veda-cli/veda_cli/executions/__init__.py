import typer
from rich.table import Table
from rich.console import Console
from pysondb import db
import os
from rich import print
import boto3
import veda_cli.executions.ouput as op


app = typer.Typer()

app.add_typer(op.app, name="output")

def get_db():
    return db.getDb(os.path.join(os.path.expanduser('~'), ".veda", "db.json"))

@app.command("list")
def list_executions():
    console = Console()
    table = Table()

    table.add_column('Execution Id', justify='left')
    table.add_column('Application', justify='left')
    table.add_column('Runtime', justify='left')
    table.add_column('Created Time', justify='left')

    db_conn = get_db()
    executions = db_conn.getBy({"type":"Execution"})

    for execution in executions:
        table.add_row(execution['executionId'], execution['application'], execution['runtime'], execution['createdTime'])

    console.print(table)

@app.command("info")
def execution_info(executionid: str):
    db_conn = get_db()
    executions = db_conn.getBy({"type":"Execution", "executionId": executionid})
    print(executions)

@app.command("kill")
def kill_execution(executionid):
    db_conn = get_db()
    executions = db_conn.getBy({"type":"Execution", "executionId": executionid})
    if len(executions) > 0:
        for execution in executions:
            if execution['runtime'] == 'EC2':

                continue_termination = typer.confirm("This will terminate the EC2 instance " + execution['instanceId'] 
                    + ". Do you want to continue?", False)

                if continue_termination:
                    ec2_client = boto3.client(
                        'ec2', 
                        aws_access_key_id=execution['accessKey'], 
                        aws_secret_access_key=execution['secretKey'],
                        region_name=execution['region'])

                    ec2_client.terminate_instances(InstanceIds=[execution['instanceId']])
                    print("Terminated EC2 instance :", execution['instanceId'])
                    db_conn.deleteById(execution['id'])
