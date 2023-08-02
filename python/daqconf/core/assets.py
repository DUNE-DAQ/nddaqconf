
from os.path import exists,abspath,dirname

from .console import console


from daq_assettools.asset_file import AssetFile
from daq_assettools.asset_database import Database
from sqlite3 import OperationalError

def resolve_asset_file(data_file, verbose):
    from urllib.parse import urlparse, parse_qsl
    data_file_url = urlparse(data_file)

    if verbose:
        console.log(f"Checking asset URI {data_file_url}")

    if data_file_url.scheme == 'asset':
        asset_query = dict(parse_qsl(data_file_url.query))
        asset_db = Database('/cvmfs/dunedaq.opensciencegrid.org/assets/dunedaq-asset-db.sqlite')
        asset_query['status'] = 'valid'

        try:
            files = asset_db.get_files(asset_query)
            if not files:
                raise RuntimeError(f"Couldn\'t find a valid asset for the query {data_file_url.query}")

            elif len(files)>1:
                console.log(f"Found {len(files)} assets in {dirname(asset_db.database_file)}, taking the first one")

            if verbose:
                console.log(f"Found asset in {dirname(asset_db.database_file)}")

            root_dir = dirname(asset_db.database_file)
            return f'{root_dir}/{files[0]["path"]}/{files[0]["name"]}'

        except OperationalError:
            raise RuntimeError(f"Couldn\'t find the asset {data_file}")


    elif data_file_url.scheme == 'file':
        filename = abspath(data_file_url.netloc+data_file_url.path)

        if not exists(filename):
            raise RuntimeError(f'Cannot find the frames.bin file {filename}')

        if verbose:
            console.log(f"Found asset in {dirname(filename)}")

        return filename

    if data_file != '' and not exists(data_file):
        raise RuntimeError(f'Cannot find the frames.bin file {data_file}')

    if verbose:
        console.log(f"Found asset in {dirname(abspath(data_file))}")

    return abspath(data_file)
