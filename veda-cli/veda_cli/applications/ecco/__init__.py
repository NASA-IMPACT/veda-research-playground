from pick import pick
import typer
import veda_cli.applications.ecco.ecco_app as ecco_app

    
def run_ecco():
    options = ["Amazon EC2", "Jetstream 2" ]
    server_option, index = pick(options, "Where Do you want to run ECCO Application?", indicator="=>")

    options = ['ECCO-NASA-V4 : NASA Hosted ECCO V4 Dataset', 'Custom']
    option, index = pick(options, "Which dataset do you want to use?", indicator="=>")

    execution_name = typer.prompt("Execution Name")

    customize = typer.confirm("Do want to customize model parameters?", True)

    ecco_configs = {}
    if customize:
        ecco_configs['time_step'] = typer.prompt("Time Step (S)", 3600) 
        ecco_configs['total_time_steps'] = typer.prompt("Total Time (S)", 227903) 
        ecco_configs['gravity'] = typer.prompt("Gravity", 9.81)
        ecco_configs['rhonil']=typer.prompt("Rhonil", 1029)

    if server_option == 'Amazon EC2':
        ecco_app.run_ecco_on_ec2(execution_name, ecco_configs)
    elif server_option == 'Jetstream 2':
        ecco_app.run_ecco_on_jetstream2(execution_name, ecco_configs)
    else:
        print("Error: Unknow server selection")





