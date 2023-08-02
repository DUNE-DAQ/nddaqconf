#!/usr/bin/env python

import click
from rich import print

from dunedaq.env import get_moo_model_path
import moo.io

@click.command()
@click.argument("schema_name")
def cli(schema_name):
    moo.io.default_load_path = get_moo_model_path()
    x = moo.otypes.load_types(schema_name)
    print(x)

if __name__ == '__main__':
    cli()
