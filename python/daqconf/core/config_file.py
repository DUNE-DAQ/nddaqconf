import os
import math
import sys
import glob
# from rich.console import Console
from collections import defaultdict
from os.path import exists, join
import json
from pathlib import Path
from . console import console

# Set moo schema search path
from dunedaq.env import get_moo_model_path
import moo.io
moo.io.default_load_path = get_moo_model_path()


# Load configuration types
import moo.otypes
import moo.oschema


class ConfigSet:

 
    def get(self,conf):
        if conf in self.confs:
            return self.confs[conf]
        else:
            myconf = self.base_config
            for pname, pval in self.full_input[conf]:
                myconf[pname] = pval
            return myconf

    def create_all_configs(self):
        for cname, pars in self.full_input.items():
            if(cname==self.base_name): continue
            self.confs[cname] = dict(self.base_config)
            for pname, pval in pars.items():
                self.confs[cname][pname] = pval
                
    def get_all_configs(self):
        return self.confs

    def list_all_configs(self):
        print(self.confs.keys())

    def __init__(self,conf_file,base_name='common'):

        self.base_name = base_name
        with open(conf_file,"r+") as f:
            self.full_input = json.load(f)

        try:
            self.base_config = self.full_input[self.base_name]
        except KeyError as e:
            print(f"No '{self.base_name}' config in {conf_file}.")
            raise e

        self.confs = {self.base_name: self.base_config}
        self.create_all_configs()


def _strict_recursive_update(dico1, dico2):
    for k, v in dico2.items():
        if not k in dico1:
            raise RuntimeError(f'\'{k}\' key is unknown, available keys are: {list(dico1.keys())}')

        if isinstance(v, dict):
            if v != {}:
                try:
                    dico1[k] = _strict_recursive_update(dico1.get(k, {}), v)
                except Exception as e:
                    raise RuntimeError(f'Couldn\'t update the dictionary of keys: {list(dico1.keys())} with dictionary \'{k}\'\nError: {e}')
            else:
                continue
        else:
            dico1[k] = v
    return dico1


def parse_json(filename, schemed_object):
    console.log(f"Parsing config json file {filename}")

    filepath = Path(filename)
    # basepath = filepath.parent

    # First pass, load the main json file
    with open(filepath, 'r') as f:
        try:
            new_parameters = json.load(f)
        except Exception as e:
            raise RuntimeError(f"Couldn't parse {filepath}, error: {str(e)}")
        
    # second pass, look for references
    subkeys = [ k for k,v in schemed_object.pod().items() if isinstance(v,dict) ]
    for k in new_parameters:
        # look for keys that are associated to dicts in the schemed_obj but here are strings
        v = new_parameters[k]

        if isinstance(v,str) and k in subkeys:
        
            # It's a string! It's a reference! Try loading it
            subfile_path = Path(os.path.expandvars(v)).expanduser()
            if not subfile_path.is_absolute():
                subfile_path = filepath.parent / subfile_path
            if not subfile_path.exists():
                raise RuntimeError(f'Cannot find the file {v} ({subfile_path})')
        
            console.log(f"Detected subconfiguration for {k} {v} - loading {subfile_path}")
            with open(subfile_path, 'r') as f:
                try:
                    new_subpars = json.load(f)
                except Exception as e:
                    raise RuntimeError(f"Couldn't parse {subfile_path}, error: {str(e)}")
                new_parameters[k] = new_subpars
            
        elif '<defaults>' in v:
            cname = k
            pars = v['<defaults>']
            scname = pars['config_name']
            scfile = pars['config_file'] if 'config_file' in pars else f'{cname}_configs.json'
            scbase = pars['config_base'] if 'config_base' in pars else 'common'


            scfile = Path(os.path.expandvars(scfile)).expanduser()
            if not scfile.is_absolute():
                scfile = filepath.parent / scfile

            if not scfile.exists():
                raise RuntimeError(f'Cannot find the file {v} ({scfile})')

            scset = ConfigSet(scfile,scbase)
            new_parameters[k] = scset.get(scname)

    try:
        # Validate the heck out of this but that doesn't change the object itself (ARG)
        _strict_recursive_update(schemed_object.pod(), new_parameters)
        # now its validated, update the object with moo
        schemed_object.update(new_parameters)
    except Exception as e:
        raise RuntimeError(f'Couldn\'t update the object {schemed_object} with the file {filename},\nError: {e}')

    return schemed_object


def parse_config_file(filename, configurer_conf):
    from os.path import exists, splitext

    if filename is None:
        ## if we didn't provide any file, make sure the schema is valid, and return the default version of it
        configurer_conf.pod()
        return configurer_conf, None

    if exists(filename):
        _, extension = splitext(filename)
        if  ".json" == extension:
            return parse_json(filename, configurer_conf), filename
        elif ".ini" == extension:
            raise RuntimeError(f'.ini configuration are not supported anymore, convert it to json')
            # return parse_ini(filename, configurer_conf), filename

    raise RuntimeError(f'Configuration {filename} doesn\'t exist')


def helptree(ost, prefix=''):
    if 'doc' in ost.keys():
        output = f"{prefix}{ost['name']}: {ost['doc']}"
    else:
        output = f"{prefix}{ost['name']}:"
    for field in ost['fields']:

        if type(field['default']) is dict:
            output += "\n" + helptree(field["default"], prefix + "    ")
        else:
            docstr = ""
            if 'doc' in field.keys():
                docstr = f": {field['doc']}"
            output += f"\n{prefix}    {field['name']} (Default: {field['default']}){docstr}"
    return "\b\n"+output

def generate_cli_from_schema(schema_file, schema_object_name, *args): ## doh
    def add_decorator(function):
        moo.otypes.load_types(schema_file)
        import importlib
        module_name = schema_file.replace('.jsonnet', '').replace('/', '.')
        config_module = importlib.import_module(f'dunedaq.{module_name}')
        schema_object = getattr(config_module, schema_object_name)
        extra_schemas = []
        for obj_name in args:
            if '.' in obj_name:
                i = obj_name.rfind('.')
                ex_module_name, ex_schema_object_name = obj_name[:i], obj_name[i+1:]
                extra_module = importlib.import_module(f'dunedaq.{ex_module_name}')
                extra_schemas += [getattr(extra_module, ex_schema_object_name)()]
            else:
                # extra_schemas = [getattr(config_module, obj)() for obj in args]
                extra_schemas = [getattr(config_module, obj_name)()]

        def configure(ctx, param, filename):
            return parse_config_file(filename, schema_object())

        import click

        hlp = helptree(schema_object().ost)
        for extra_schema in extra_schemas:
            hlp+="\n\n\n"+helptree(extra_schema.ost)

        return click.option(
            '-c', '--config',
            type         = click.Path(dir_okay=False),
            default      = None,
            callback     = configure,
            help         = hlp,
            show_default = True,
        )(function)
    return add_decorator
