import json
import os
import sys
from os.path import exists, join

from .console import console

def write_metadata_file(json_dir, generator, config_file):
    console.log("Generating metadata file")

    # Backwards compatibility
    if isinstance(json_dir, str):
        from pathlib import Path
        json_dir = Path(json_dir)

    with open(join(json_dir / f"{generator}.info"), 'w') as f:
        daqconf_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

        # build info file is one directory up from the main script (daqconf vs. daqconf/bin)
        buildinfo_file=join(os.path.dirname(daqconf_dir), "daqconf_build_info.json")
        buildinfo = {}
        #console.log(f"Buildinfo file is {buildinfo_file}")
        if exists(buildinfo_file):
            with open(buildinfo_file, 'r') as ff:
                try:
                    #console.log(f"Reading buildinfo file {buildinfo_file}")
                    buildinfo = json.load(ff)
                except json.decoder.JSONDecodeError as e:
                    console.log(f"Error reading buildinfo file {buildinfo_file}: {e}")

        daqconf_info = {
            "command_line": ' '.join(sys.argv),
            "daqconf_exe_dir": daqconf_dir,
            "build_info": buildinfo,
            "config_file": config_file
        }
        json.dump(daqconf_info, f, indent=4, sort_keys=True)


def write_config_file(json_dir, json_output_file, data):
    console.log(f'Saving metadata {json_output_file}')
    # Backwards compatibility
    if isinstance(json_dir, str):
        from pathlib import Path
        json_dir = Path(json_dir)

    path = json_dir/'config'
    out_file = json_output_file.split("/")[-1]
    console.log(f'Saving metadata to {path}/{out_file}')

    os.mkdir(path)

    with open(join(path/json_output_file), 'w') as f:
        json.dump(data.pod(), f, indent=4, sort_keys=True)
