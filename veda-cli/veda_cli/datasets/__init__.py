import typer
from rich.table import Table
from rich.console import Console
from pysondb import db
import os
from datetime import datetime
from airavata_mft_cli import operations as ops
from airavata_mft_cli import config as configcli
from airavata_mft_sdk import mft_client
from airavata_mft_sdk.scp import SCPCredential_pb2
from airavata_mft_sdk.scp import SCPStorage_pb2
from airavata_mft_sdk.common import StorageCommon_pb2
from airavata_mft_sdk.common import StorageCommon_pb2
from airavata_mft_sdk import MFTTransferApi_pb2
import time

app = typer.Typer()

def get_db():
    return db.getDb(os.path.join(os.path.expanduser('~'), ".veda", "ds.json"))

def get_exec_db():
    return db.getDb(os.path.join(os.path.expanduser('~'), ".veda", "db.json"))

@app.command("list")
def list_datasets():
    console = Console()
    table = Table()

    table.add_column('Dataset Name', justify='left')
    table.add_column('Description', justify='left')
    table.add_column('Tags', justify='left')

    table.add_row('ECCO-NASA-V4', 'NASA Hosted ECCO V4 Dataset', 'OCEAN, CLIMATE')

    db_conn = get_db()
    dss = db_conn.getBy({"type":"Dataset"})

    for ds in dss:
        table.add_row(ds["name"], "Replica available in storage " + ds["storageId"], 'CUSTOM')

    console.print(table)

@app.command("info")
def dataset_info(dataset_name):
    print("Printing dataset info")
    db_conn = get_db()
    datasets = db_conn.getBy({"type":"Dataset",  "name": dataset_name})
    for ds in datasets:
        print(ds)

def get_file_list(storage_id, root_dir):

    metadata_resp = ops.get_resource_metadata(storage_id + "/" + root_dir)

    file_metadata = metadata_resp.directory.files

    files = []
    for f in file_metadata:
        files.append(f.friendlyName)

    return files

@app.command("register")
def register_dataset(execution_id, dataset_name, dataset_path):
    print("Registring the dataset")

    db_conn = get_exec_db()
    executions = db_conn.getBy({"type":"Execution", "executionId": execution_id})
    execution = executions[0]
    storage_id = execution["storageId"]
    output_dir = execution["outputDir"]

    dataset_path = output_dir + "/" + dataset_path

    db_conn = get_db()
    db_conn.add({
        "type": "Dataset",
        "storageId": storage_id,
        "name": dataset_name, 
        "base_path": dataset_path, 
        "createdTime": datetime.now().strftime("%m/%d/%Y, %H:%M:%S"),
        "files": get_file_list(storage_id, dataset_path)})
    
def register_custom_dataset(execution_id, dataset_name, dataset_base_path, dataset_paths):
    print("Registring custom datasets")

    db_conn = get_exec_db()
    executions = db_conn.getBy({"type":"Execution", "executionId": execution_id})
    execution = executions[0]
    storage_id = execution["storageId"]

    db_conn = get_db()
    db_conn.add({
        "type": "Dataset",
        "storageId": storage_id,
        "name": dataset_name, 
        "base_path": dataset_base_path, 
        "createdTime": datetime.now().strftime("%m/%d/%Y, %H:%M:%S"),
        "files": dataset_paths})
    
@app.command("register-local")
def register_local_dataset(dataset_name, dataset_path):
    print("Registring the dataset")

    db_conn = get_db()
    db_conn.add({
        "type": "Dataset",
        "storageId": "local-agent",
        "name": dataset_name, 
        "base_path": dataset_path, 
        "createdTime": datetime.now().strftime("%m/%d/%Y, %H:%M:%S"),
        "files": get_file_list("local-agent", dataset_path)})
    
@app.command("copy")
def copy_dataset(dataset_name, target_storage):
    print("Publishing the Dataset to storage " + target_storage)
    db_conn = get_db()
    datasets = db_conn.getBy({"type":"Dataset",  "name": dataset_name})
    if len(datasets) > 0:
        ds = datasets[0]
        ops.copy(ds["storageId"] + "/" + ds["base_path"], target_storage + "/" + ds["name"] + "/")
        ds["storageId"] = target_storage
        db_conn.add(ds)

def get_dataset(dataset_name, destination_path):
    db_conn = get_db()
    datasets = db_conn.getBy({"type":"Dataset",  "name": dataset_name})
    if len(datasets) > 0:
        ds = datasets[0]
        endpoint_paths = []
        for f in ds['files']:
            endpoint_paths.append(MFTTransferApi_pb2.EndpointPaths(
                sourcePath = ds["base_path"] + "/" + f,
                destinationPath = destination_path + "/" + f))
            
        copy(ds["storageId"], "local-agent", endpoint_paths)

@app.command("delete")
def delete_dataset(dataset_name):
    db_conn = get_db()
    datasets = db_conn.getBy({"type":"Dataset",  "name": dataset_name})
    for ds in datasets:
        db_conn.deleteById(ds['id'])


def copy(source_storage_id, dest_storage_id, endpoint_paths):

  source_storage_id, source_secret_id = ops.fetch_storage_and_secret_ids(source_storage_id)
  dest_storage_id, dest_secret_id = ops.fetch_storage_and_secret_ids(dest_storage_id)

  ## TODO : Check agent availability and deploy cloud agents if required

  total_volume = 0

  transfer_request = ops.MFTTransferApi_pb2.TransferApiRequest(sourceStorageId = source_storage_id,
                                                           sourceSecretId = source_secret_id,
                                                           destinationStorageId = dest_storage_id,
                                                           destinationSecretId = dest_secret_id,
                                                           optimizeTransferPath = False)

  transfer_request.endpointPaths.extend(endpoint_paths)

  client = mft_client.MFTClient(transfer_api_port = configcli.transfer_api_port,
                                transfer_api_secured = configcli.transfer_api_secured,
                                resource_service_host = configcli.resource_service_host,
                                resource_service_port = configcli.resource_service_port,
                                resource_service_secured = configcli.resource_service_secured,
                                secret_service_host = configcli.secret_service_host,
                                secret_service_port = configcli.secret_service_port)

  transfer_resp = client.transfer_api.submitTransfer(transfer_request)

  transfer_id = transfer_resp.transferId

  state_request = MFTTransferApi_pb2.TransferStateApiRequest(transferId=transfer_id)

  ## TODO: This has to be optimized and avoid frequent polling of all transfer ids in each iteration
  ## Possible fix is to introduce a parent batch transfer id at the API level and fetch child trnasfer id
  # summaries in a single API call

  completed = 0
  failed = 0

  with typer.progressbar(length=100) as progress:

    while 1:
      state_resp = client.transfer_api.getTransferStateSummary(state_request)

      progress.update(int(state_resp.percentage * 100))
      if (state_resp.percentage == 1.0):
        completed = len(state_resp.completed)
        failed = len(state_resp.failed)
        break

      if (state_resp.state == "FAILED"):
        print("Transfer failed. Reason: " + state_resp.description)
        raise typer.Abort()
      time.sleep(1)

  print(f"Processed {completed + failed} files. Completed {completed}, Failed {failed}.")