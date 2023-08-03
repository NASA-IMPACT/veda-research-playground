import boto3
from botocore.exceptions import ClientError
import os
import string
import random
import stat
import paramiko
import socket
import time
import typer
from pysondb import db
from datetime import datetime
from rich import print
from airavata_mft_cli import config as configcli
from airavata_mft_sdk import mft_client
from airavata_mft_sdk.scp import SCPCredential_pb2
from airavata_mft_sdk.scp import SCPStorage_pb2
from airavata_mft_sdk.common import StorageCommon_pb2

def get_db():
    return db.getDb(os.path.join(os.path.expanduser('~'), ".veda", "db.json"))

def register_execution_endpoint(storage_name, private_key, user_name, host_name, port):
    client = mft_client.MFTClient(transfer_api_port = configcli.transfer_api_port,
                                    transfer_api_secured = configcli.transfer_api_secured,
                                    resource_service_host = configcli.resource_service_host,
                                    resource_service_port = configcli.resource_service_port,
                                    resource_service_secured = configcli.resource_service_secured,
                                    secret_service_host = configcli.secret_service_host,
                                    secret_service_port = configcli.secret_service_port)
    
    secret_create_req = SCPCredential_pb2.SCPSecretCreateRequest(privateKey=private_key, 
                                                                 user=user_name)
    created_secret = client.scp_secret_api.createSCPSecret(secret_create_req)

    scp_storage_create_req = SCPStorage_pb2.SCPStorageCreateRequest(
        host=host_name, port=port, name=storage_name)
    
    created_storage = client.scp_storage_api.createSCPStorage(scp_storage_create_req)

    secret_for_storage_req = StorageCommon_pb2.SecretForStorage(storageId = created_storage.storageId,
                                       secretId = created_secret.secretId,
                                       storageType = StorageCommon_pb2.StorageType.SCP)

    client.common_api.registerSecretForStorage(secret_for_storage_req)

    return created_storage.storageId


    
def describe_vpcs(tag, tag_values, max_items, ec2_client):
    """
    Describes one or more VPCs.
    """
    try:
        # creating paginator object for describe_vpcs() method
        paginator = ec2_client.get_paginator('describe_vpcs')
        # creating a PageIterator from the paginator
        response_iterator = paginator.paginate(
            Filters=[{
                'Name': f'tag:{tag}',
                'Values': tag_values
            }],
            PaginationConfig={'MaxItems': max_items})
        full_result = response_iterator.build_full_result()
        vpc_list = []
        for page in full_result['Vpcs']:
            vpc_list.append(page)
    except ClientError:
        print('Could not describe VPCs.')
        raise
    else:
        return vpc_list

def describe_sgs(tag, tag_values, max_items, ec2_client):
    """
    Describes one or more security groups.
    """
    try:
        # creating paginator object for describe_vpcs() method
        paginator = ec2_client.get_paginator('describe_security_groups')
        # creating a PageIterator from the paginator
        response_iterator = paginator.paginate(
            Filters=[{
                'Name': f'tag:{tag}',
                'Values': tag_values
            }],
            PaginationConfig={'MaxItems': max_items})
        full_result = response_iterator.build_full_result()
        sg_list = []
        for page in full_result['SecurityGroups']:
            sg_list.append(page)
    except ClientError:
        print('Could not describe SecurityGroups.')
        raise
    else:
        return sg_list

def describe_subnets(tag, tag_values, max_items, ec2_client):
    """
    Describes one or more subnets.
    """
    try:
        # creating paginator object for describe_vpcs() method
        paginator = ec2_client.get_paginator('describe_subnets')
        # creating a PageIterator from the paginator
        response_iterator = paginator.paginate(
            Filters=[{
                'Name': f'tag:{tag}',
                'Values': tag_values
            }],
            PaginationConfig={'MaxItems': max_items})
        full_result = response_iterator.build_full_result()
        subnets = []
        for page in full_result['Subnets']:
            subnets.append(page)
    except ClientError:
        print('Could not describe Subnets.')
        raise
    else:
        return subnets


def wait_for_ssh(host, ssh_timeout: float = 60.0):
    start_time = time.perf_counter()
    while True:
        try:
            with socket.create_connection((host, 22), timeout=ssh_timeout):
                break
        except OSError as ex:
            time.sleep(0.1)
            if time.perf_counter() - start_time >= ssh_timeout:
                raise TimeoutError('Connection timed out') from ex

def create_ssh_connection(user, ip, key_file):
    print("Waiting for SSH to come up")
    wait_for_ssh(host=ip)
    print("Port 22 is open. Trying to SSH into the vm")
    ssh = paramiko.SSHClient()
    k = paramiko.RSAKey.from_private_key_file(key_file)
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=ip, username=user, pkey=k)
    return ssh

def init_local():
    
    veda_aws_credentials = os.path.join(os.path.expanduser('~'), ".veda", "credentials", "aws")
    if not os.path.exists(veda_aws_credentials):
        os.makedirs(veda_aws_credentials)

    veda_ssh_credentials = os.path.join(os.path.expanduser('~'), ".veda", "credentials", "ssh")
    if not os.path.exists(veda_ssh_credentials):
        os.makedirs(veda_ssh_credentials)
    
def run_ecco_on_ec2(execution_name, ecco_configs):
    print("Running the ECCO simulation on EC2")

    init_local()

    access_key = typer.prompt("AWS Access Key Id", hide_input=True)
    secret_key = typer.prompt("AWS Secret Access Key", hide_input=True)

    region = "us-west-2"
    ecco_ami = 'ami-01b3a8d8f90f3fd3c'
    instance_size = 'c5.24xlarge'
    vpc_name = 'veda_ecco_vpc'
    security_group_name = 'veda_ecco_sg'
    subnet_name = 'veda_ecco_subnet'
    route_table_name = 'veda_ecco_rt'
    internet_gateway_name = 'veda_ecco_ig'
    instance_name = 'VEDA ECCO Run'

    ec2_client = boto3.client(
        'ec2', 
        aws_access_key_id=access_key, 
        aws_secret_access_key=secret_key,
        region_name=region)

    key_files = os.listdir(os.path.join(os.path.expanduser('~'), ".veda", "credentials", "ssh"))
    all_keys = ec2_client.describe_key_pairs()['KeyPairs']
    available_keys = []
    for k in all_keys:
        if k['KeyName'] in key_files:
            available_keys.append(k['KeyName'])

    if len(available_keys) == 0:

        key_name = 'ecco_key_' + ''.join(random.choices(string.ascii_lowercase +
                                string.digits, k=5))

        keypair = ec2_client.create_key_pair(KeyName=key_name)
        key_path = os.path.join(os.path.expanduser('~'), ".veda", "credentials", "ssh", key_name)
        with open(key_path, "w") as key_file:
            key_file.write(keypair['KeyMaterial'])

        os.chmod(key_path, stat.S_IRUSR);

        print("Created key : ", key_name)
    else:
        key_name = available_keys[0]
        print("Reusing existing key : ", key_name)

    vpcs = describe_vpcs("Name", [vpc_name], 1, ec2_client)

    
    if len(vpcs) == 0:
        print("Creating VPC for ECCO VEDA")
        vpc = ec2_client.create_vpc(CidrBlock='172.16.0.0/16')
        vpc_id = vpc['Vpc']['VpcId']

        ec2_client.create_tags(Resources=[vpc_id], Tags=[{"Key": "Name", "Value": vpc_name}])

        print("Waiting until the VPC is available")
        waiter = ec2_client.get_waiter('vpc_available')
        waiter.wait(VpcIds=[vpc_id])

    else:
        vpc = vpcs[0]
        vpc_id = vpc['VpcId']
        print("Reusing existing vpc : " + vpc_name)

    subnets = describe_subnets("Name", [subnet_name], 1, ec2_client)

    if len(subnets) == 0:

        route_table = ec2_client.create_route_table(VpcId=vpc_id)
        internet_gateway = ec2_client.create_internet_gateway()

        route_table_id = route_table['RouteTable']['RouteTableId']
        ec2_client.create_tags(Resources=[route_table_id], Tags=[{"Key": "Name", "Value": route_table_name}])

        internet_gateway_id = internet_gateway['InternetGateway']['InternetGatewayId']
        ec2_client.create_tags(Resources=[internet_gateway_id], Tags=[{"Key": "Name", "Value": internet_gateway_name}])

        #print(route_table)
        #print(internet_gateway)

        response = ec2_client.attach_internet_gateway(
            InternetGatewayId=internet_gateway_id,
            VpcId=vpc_id
        )

        ec2_client.create_route(
            DestinationCidrBlock='0.0.0.0/0',
            GatewayId=internet_gateway_id,
            RouteTableId=route_table_id,
        )

        subnet = ec2_client.create_subnet(CidrBlock = '172.16.2.0/24', VpcId= vpc_id)
        subnet_id = subnet['Subnet']['SubnetId']
        ec2_client.create_tags(Resources=[subnet_id], Tags=[{"Key": "Name", "Value": subnet_name}])

        route_table = boto3.resource('ec2', aws_access_key_id=access_key, aws_secret_access_key=secret_key, region_name=region).RouteTable(route_table_id)
        route_table.associate_with_subnet(SubnetId=subnet_id)


    else:
        print("Reusing existing subnet")
        subnet_id = subnets[0]['SubnetId']

    sgs = describe_sgs("Name", [security_group_name], 1, ec2_client)
    
    if len(sgs) == 0:
        secrity_group = ec2_client.create_security_group(GroupName=security_group_name,
                                            Description=security_group_name,
                                            VpcId=vpc_id)

        security_group_id = secrity_group['GroupId']

        ec2_client.create_tags(Resources=[security_group_id], Tags=[{"Key": "Name", "Value": security_group_name}])

        sg_ingress = ec2_client.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[
                {'IpProtocol': 'tcp',
                'FromPort': 22,
                'ToPort': 22,
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
            ])
        
        print(secrity_group)
    else:
        print("Using existing security group : " + security_group_name)
        security_group_id = sgs[0]['GroupId']

    print("Security group id ", security_group_id)
    
    instances = ec2_client.run_instances(
        ImageId=ecco_ami,
        MinCount=1,
        MaxCount=1,
        InstanceType=instance_size,
        KeyName=key_name,
        NetworkInterfaces=[{'SubnetId': subnet_id,'Groups': [security_group_id], 'AssociatePublicIpAddress': True, 'DeleteOnTermination': True, 'DeviceIndex': 0}]
    )

    instance_id = instances['Instances'][0]['InstanceId']

    print("Instance id " + instance_id)

    ec2_client.create_tags(Resources=[instance_id], Tags=[{"Key": "Name", "Value": instance_name}])

    print("Waiting until the instance " + instance_id + " is up and running")
    waiter = ec2_client.get_waiter('instance_running')
    waiter.wait(InstanceIds=[instance_id])
    print('Instance is running')

    public_ip = ec2_client.describe_instances(InstanceIds=[instance_id])['Reservations'][0]['Instances'][0]['PublicIpAddress']
    print("You can log in to the ECCO running instance using following SSH command")
    local_key_file = os.path.join(os.path.expanduser('~'), ".veda", "credentials", "ssh", key_name)
    print('[bold red]ssh -i ' + local_key_file + ' ubuntu@' + public_ip + '[/bold red]')
    ssh = create_ssh_connection('ubuntu', public_ip, local_key_file)

    ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command("cd /home/ubuntu/MITgcm/ECCOV4/release4/run; nohup mpirun -np 96 ./mitgcmuv >> mpi.out 2>&1 &")
    stdout = ssh_stdout.readlines()

    with open(local_key_file, 'r') as key_file:
        private_key = key_file.read()

    storage_id = register_execution_endpoint(execution_name + " storage",  private_key, "ubuntu", public_ip, 22)

    execution_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
    db_conn = get_db()
    db_conn.add({
        "type": "Execution", 
        "runtime": "EC2", 
        "application": "ECCO", 
        "executionId": execution_id, 
        "createdTime": datetime.now().strftime("%m/%d/%Y, %H:%M:%S"),
        "instanceId": instance_id,
        "publicIp": public_ip,
        "loginUser": "ubuntu",
        "accessKey":access_key,
        "secretKey": secret_key,
        "region": region,
        "keyPath": local_key_file,
        "storageId": storage_id,
        "outputDir": "/home/ubuntu/MITgcm/ECCOV4/release4/run/diags"})

    print("[bold blue]Started the ECCO Model run. Execution Id: " + execution_id + "[/bold blue]")


def run_ecco_on_jetstream2(execution_name, ecco_configs):
    print("Running the ECCO simulation on Jetstream 2")
    print("This is not yet supported...")
    

