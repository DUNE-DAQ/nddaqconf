#!/usr/bin/env python



import click
import json
import requests
from pathlib import Path
from os import environ as env
from rich import print

host = 'np04-srv-023'
port = '31011'

# # http://np04-srv-023:31011/listVersions?name=thea-k8s-test


@click.group()
def cli():
    pass


@cli.command('list')
def list_configs():
    uri = f'http://{host}:{port}/listConfigs'
    print(uri)
    r = requests.get(uri)
    if (r.status_code != 200):
        click.Errors("Failed to read the configurations list from db")

    res = r.json()
    for c in sorted(res['configs']):
        print(c)

@cli.command('versions')
@click.argument('config_name')
def config_versions(config_name):
    uri = f'http://{host}:{port}/listVersions?name={config_name}'
    print(uri)
    r = requests.get(uri)
    if (r.status_code != 200):
        click.Errors("Failed to read the configurations list from db")

    res = r.json()
    for v in res['versions']:
        print(v)
    
@cli.command('dump')
@click.argument('config_name')
@click.option('-v', '--version', type=int, default=None)
@click.option('-w', '--write', is_flag=True, default=False)
@click.option('-o', '--output', default=None)
def config_versions(config_name, version, write, output):

    if not version is None:
        uri = f'http://{host}:{port}/retrieveVersion?name={config_name}&version={version}'
    else:
        uri = f'http://{host}:{port}/retrieveLast?name={config_name}'

    print(uri)
    r = requests.get(uri)
    if (r.status_code != 200):
        click.Errors("Failed to read the configurations list from db")

    res = r.json()
    print(res)

    if write:
        outname = output if not output is None else f"{config_name}_v{version}.json"
        with open(outname, "w") as outfile:
            json.dump(
                res, 
                outfile,
                sort_keys=True,
                indent=4,
            )

if __name__ == '__main__':
    cli()

