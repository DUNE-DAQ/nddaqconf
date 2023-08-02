#!/usr/bin/env python
import json

# Set moo schema search path
from dunedaq.env import get_moo_model_path
import moo.io
moo.io.default_load_path = get_moo_model_path()

moo.otypes.load_types('daqconf/detreadoutmap.jsonnet')
moo.otypes.load_types('hdf5libs/hdf5rawdatafile.jsonnet')

import dunedaq.daqconf.detreadoutmap as drom
import dunedaq.hdf5libs.hdf5rawdatafile as hdf5rdf


from rich import print

e_f = drom.DROStreamEntry(
    src_id = 0,
    geo_id=hdf5rdf.GeoID(det_id=3, crate_id=1, slot_id=0, stream_id=0), 
    kind="flx", 
    parameters=drom.FelixStreamParameters(host = 'np04-srv-028')
)
print(f"FELIX link {e_f.pod()}")

e_e0 = drom.DROStreamEntry(
    src_id = 1,
    geo_id=hdf5rdf.GeoID(det_id=3, crate_id=3, slot_id=0, stream_id=64),
    kind="eth",
    parameters=drom.EthStreamParameters(rx_host = 'np04-srv-029', tx_host='np04-wib-501')
)
print(f"Eth link {e_e0.pod()}")

e_e1 = drom.DROStreamEntry(
    src_id = 2, 
    geo_id=hdf5rdf.GeoID(det_id=3, crate_id=3, slot_id=0, stream_id=65),
    kind="eth",
    parameters=drom.EthStreamParameters(rx_host = 'np04-srv-029', tx_host='np04-wib-501')
)
print(f"Eth link {e_e1.pod()}")

e_e2 = drom.DROStreamEntry(
    src_id = 3,
    geo_id=hdf5rdf.GeoID(det_id=3, crate_id=3, slot_id=0, stream_id=66),
    kind="eth",
    parameters=drom.EthStreamParameters(rx_host = 'np04-srv-029', tx_host='np04-wib-501')
)
print(f"Eth link {e_e2.pod()}")


dro_links = []
for e in [e_f, e_e0, e_e1, e_e2]:
    e_dict = e.pod()
    i = e_dict.pop('parameters')
    d = drom.DROStreamEntry(**(e_dict))
    print(d.kind)
    if d.kind == "flx":
        d.parameters = drom.FelixStreamParameters(**i)
    elif d.kind == "eth":
        d.parameters = drom.EthStreamParameters(**i)
    dro_links.append(d)

dlmap = drom.DROStreamMap(dro_links)
m = dlmap.pod()
print(m)

with open("test_dro_map.json",'w') as f:
    json.dump(m, f, indent=4)

