"""
Detector-Readout Stream MAP

BEWARE: Horrible things are done in this module, such that others don't have to suffer

Open questions:

- General vs specific validation (ETH, FLX) - delegate to spedific classes?
- Streams mapping to readout unit applications, consistency checks: delegate to a dedicated class?
"""
# Set moo schema search path
from dunedaq.env import get_moo_model_path
import moo.io
moo.io.default_load_path = get_moo_model_path()

moo.otypes.load_types('nddaqconf/detreadoutmap.jsonnet')
moo.otypes.load_types('hdf5libs/hdf5rawdatafile.jsonnet')

import dunedaq.nddaqconf.detreadoutmap as dromap
import dunedaq.hdf5libs.hdf5rawdatafile as hdf5rdf

import collections
import json
import pathlib
import copy
from itertools import groupby

from typing import Dict
from collections import namedtuple, defaultdict

import sys

from rich import print
from rich.table import Table


### Move to utility module
def group_by_key(coll, key):
    """
    """
    m = {}
    s = sorted(coll, key=key)
    for k, g in groupby(s, key):
        m[k] = list(g)
    return m


### HORROR!
thismodule = sys.modules[__name__]

# Turn moo object into named tuples
for c in [
    hdf5rdf.GeoID,
    dromap.DROStreamEntry,
    dromap.EthStreamParameters,
    dromap.FelixStreamParameters,
]: 
    c_ost = c.__dict__['_ost']
    c_name = c_ost['name']
    setattr(thismodule, c_name, namedtuple(c_name, [f['name'] for f in c_ost['fields']]))


class ReadoutUnitDescriptor:

    def __init__(self, host_name, iface, kind, det_id, streams):
        self.host_name = host_name
        self.iface = iface
        self.kind = kind
        self.det_id = det_id
        self.streams = streams

    @property
    def safe_host_name(self):
        return self.host_name.replace('-','')

    @property
    def label(self):
        return f"{self.safe_host_name}{self.kind}{self.iface}"
    
    @property
    def app_name(self):
        return f"ru{self.label}"


StreamKindTraits = namedtuple("StreamKindTraits", [
    'tuple_class',
    'moo_class',
    'host_label',
    'iflable'
] )

class DetReadoutMapService:
    """Detector - Readout Link mapping"""

    _traits_map = {
        'flx': StreamKindTraits(FelixStreamParameters, dromap.FelixStreamParameters, 'host', 'card'),
        'eth': StreamKindTraits(EthStreamParameters, dromap.EthStreamParameters, 'rx_host', 'rx_iface'),
    }

    @classmethod
    def _get_host_label(cls, kind: str) -> str:
        return cls._traits_map[kind].host_label

    @classmethod
    def _get_iflabel(cls, kind: str) -> str:
        return cls._traits_map[kind].iflable
    
    @classmethod
    def _get_moo_class(cls, kind: str) -> str:
        return cls._traits_map[kind].moo_class
    

    @classmethod
    def _get_tuple_class(cls, kind: str) -> str:
        return cls._traits_map[kind].tuple_class
    

    def __init__(self):
        self._map = {}


    def load(self, map_path: str, merge: bool = False, offset: int = 0) -> None:
        
        map_fp = pathlib.Path(map_path)

        # Opening JSON file
        with open(map_fp) as f:
        
            # returns JSON object as 
            # a dictionary
            data = json.load(f)

        self._validate_json(data)
        

        streams = self._build_streams(data)

        print(f"Offset = {offset}")
        if offset:
            streams = [s._replace(src_id = s.src_id + offset) for s in streams]

        if merge:
            src_id_max = max(self.get())+1 if self.get() else 0
            new_src_id_min = min([s.src_id for s in streams])
            shifted_streams = []

            if src_id_max > new_src_id_min:
                print(f"WARNING: source id overlap detected, loaded source ids will be shifted by {src_id_max - new_src_id_min}")
                for s in streams:
                    shifted_streams.append(s._replace(src_id = s.src_id - new_src_id_min + src_id_max))
                streams = shifted_streams
            streams = self.streams + streams

        self._validate_streams(streams)
        self._validate_eth(streams)
        self._validate_rohosts(streams)


        self._map = {s.src_id:s for s in streams}
    
    @classmethod
    def _validate_json(cls, data) -> None:

        # Make a copy to work locally
        data = copy.deepcopy(data)

        dro_links = []
        
        for e in data:

            info = e.pop('parameters')

            dro_en = dromap.DROStreamEntry(**e)
            
            moo_t = cls._get_moo_class(dro_en.kind)
            dro_en.parameters = moo_t(**info)

            dro_links.append(dro_en)

        dlmap = dromap.DROStreamMap(dro_links)
        _ = dlmap.pod()

    
    @classmethod
    def _build_streams(cls, data) -> None:
        """Build a list of stream entries"""

        streams = []
        for s in data:

            tuple_t = cls._get_tuple_class(s['kind'])
            parameters = tuple_t(**s['parameters'])

            s.update({
                'parameters':parameters,
                'geo_id':GeoID(**s['geo_id'])
            })
            en = DROStreamEntry(**s)
            streams.append(en)
        return streams
    
    def _validate_streams(self, streams):
        """Validates the list of stream entries"""

        src_id_list = [s.src_id for s in streams]
        geo_id_list = [s.geo_id for s in streams]

        # Ensure source id uniqueness
        dups_src_ids = [item for item, count in collections.Counter(src_id_list).items() if count > 1]
        if len(dups_src_ids):
            raise ValueError(f"Found duplicated source ids : {', '.join([str(i) for i in sorted(dups_src_ids)])}")
        
        # Ensure geo id uniqueness
        dups_geo_ids = [item for item, count in collections.Counter(geo_id_list).items() if count > 1]
        if len(dups_geo_ids):
            raise ValueError(f"Found duplicated geo ids : {', '.join([str(i) for i in dups_geo_ids])}")
        
        
    def _validate_rohosts(self, streams):
        # Check RU consistency, i.e. only one kind type per readout host
        host_label_map = {
            'flx': 'host',
            'eth': 'rx_host',
        }

        kind_m = defaultdict(set)
        det_id_m = defaultdict(set)
        for en in streams:
            ro_host = getattr(en.parameters, host_label_map[en.kind])
            kind_m[ro_host].add(en.kind)
            det_id_m[ro_host].add(en.geo_id.det_id)

        multi_kind_hosts = {k:v for k,v in kind_m.items() if len(v) > 1}
        if multi_kind_hosts:
            raise ValueError(f"Readout hosts with streams of different kinds are not supported. Found {multi_kind_hosts}")

        multi_det_hosts = {k:v for k,v in det_id_m.items() if len(v) > 1}
        if multi_det_hosts:
            raise ValueError(f"Readout hosts with streams from different detectors are not supported. Found {multi_det_hosts}")
    
    # FIXME: Dedicated Ethernet Validator class?
    def _validate_eth(self, streams):
        """
        Apply rules:
        - ip and mac pairing is strict (one-to-one)
        - a mac can only belong to a single host
        """


        rx_mac_to_host = defaultdict(set)
        rx_mac_to_ip = defaultdict(set)
        rx_mac_to_iface = defaultdict(set)
        rx_ip_to_mac = defaultdict(set)

        tx_mac_to_host = defaultdict(set)
        tx_mac_to_ip = defaultdict(set)
        tx_ip_to_mac = defaultdict(set)

        for s in streams:
            if s.kind != 'eth':
                continue
            
            rx_mac_to_host[s.parameters.rx_mac].add(s.parameters.rx_host)
            rx_mac_to_ip[s.parameters.rx_mac].add(s.parameters.rx_ip)
            rx_mac_to_iface[s.parameters.rx_mac].add(s.parameters.rx_iface)
            rx_ip_to_mac[s.parameters.rx_ip].add(s.parameters.rx_mac)

            tx_mac_to_ip[s.parameters.tx_mac].add(s.parameters.tx_ip)
            tx_ip_to_mac[s.parameters.tx_ip].add(s.parameters.tx_mac)
            tx_mac_to_host[s.parameters.tx_mac].add(s.parameters.tx_host)


        dup_rx_hosts = { k:v for k,v in rx_mac_to_host.items() if len(v) > 1}
        dup_rx_macs = { k:v for k,v in rx_mac_to_ip.items() if len(v) > 1}
        dup_rx_iface = { k:v for k,v in rx_mac_to_iface.items() if len(v) > 1}
        dup_rx_ips = { k:v for k,v in rx_ip_to_mac.items() if len(v) > 1}

        dup_tx_hosts = { k:v for k,v in tx_mac_to_host.items() if len(v) > 1}
        dup_tx_macs = { k:v for k,v in tx_mac_to_ip.items() if len(v) > 1}
        dup_tx_ips = { k:v for k,v in tx_ip_to_mac.items() if len(v) > 1}
        

        errors = []
        if dup_rx_hosts:
            errors.append(f"Many rx hosts associated to the same rx mac {dup_rx_hosts}")
        if dup_rx_macs:
            errors.append(f"Many rx ips associated to the same rx mac {dup_rx_macs}")
        if dup_rx_iface:
            errors.append(f"Many rx interfaces associated to the same rx mac {dup_rx_iface}")
        if dup_rx_ips:
            errors.append(f"Many rx macs associated to the same rx ips {dup_rx_ips}")


        if dup_tx_hosts:
            errors.append(f"Many tx hosts associated to the same tx mac {dup_tx_hosts}")
        if dup_tx_macs:
            errors.append(f"Many tx macs associated to the same tx ips {dup_tx_macs}")
        if dup_tx_ips:
            errors.append(f"Many tx ips associated to the same tx mac {dup_tx_ips}")

        # FIXME : Create a dedicated exception
        if errors:
            nl = r'\n'
            raise RuntimeError(f"Ethernet streams validation failed: {nl.join(errors)}")

    @property
    def streams(self):
        return list(self._map.values())


    def get(self):
        return self._map


    def group_by_host(self) -> Dict:
        """Group streams by host

        Returns:
            Dict: readout host -> streams map
        """
        m = {}

        for s in self._map.values():
            m.setdefault(getattr(s.parameters, self._get_host_label[s.kind]),[]).append(s)

        return m


    # FIXME: This implements a readout-specific view on the stream map. Does it belong here?
    def get_ru_descriptors(self) -> Dict:
        
        m = defaultdict(list)
        for s in self.streams:
            ru_host = getattr(s.parameters, self._get_host_label(s.kind))
            ru_iface = getattr(s.parameters, self._get_iflabel(s.kind))
            m[(ru_host, ru_iface, s.kind, s.geo_id.det_id)].append(s)

        # Repackage as a map of ReadoutUnitDescriptors
        rud_map = {}
        for (ru_host, ru_iface, kind, det_id),streams in m.items():
            d = ReadoutUnitDescriptor(ru_host, ru_iface, kind, det_id, streams)
            rud_map[d.app_name] = d

        return rud_map


    def get_by_kind(self, kind: str) -> Dict:
        """Get the stream map by stream kind

        Args:
            kind (str): _description_

        Returns:
            Dict: _description_
        """
        return {
            k:v for k,v in self._map.items()
            if v.kind == kind
        }


    def get_src_ids(self) -> list:
        """Get the list of source ids in the map

        Returns:
            list: list of source ids
        """
        return list(self._map)


    def get_geo_ids(self) -> list:
        """Return the list of GeoIDs in the map

        Returns:
            list: list of geo ids
        """
        return [v.geo_id for v in self.streams]


    def get_src_geo_map(self):
        """Build the SrcGeoID map for HDF5RawDataFile"""
        return hdf5rdf.SrcIDGeoIDMap([
            hdf5rdf.SrcIDGeoIDEntry(
                src_id=s,
                geo_id=hdf5rdf.GeoID(**(en.geo_id._asdict()))
            ) for s,en in self._map.items()
        ])


    def as_table(self):
        """Export the table as a rich table"""
        m = self._map

        t = Table()
        t.add_column('src_id', style='blue')
        for f in GeoID._fields:
            t.add_column(f)
        t.add_column('kind')
        for f in FelixStreamParameters._fields:
            t.add_column(f"flx_{f}", style='cyan')
        for f in EthStreamParameters._fields:
            t.add_column(f"eth_{f}", style='magenta')

        for s,en in sorted(m.items(), key=lambda x: x[0]):

            row = [str(s)]+[str(x) for x in en.geo_id]+[en.kind]

            if en.kind == "flx":
                infos = [str(x) for x in en.parameters]
                pads = ['-']*(len(t.columns)-len(row)-len(infos))
                row += infos + pads

            elif en.kind == "eth":
                infos = [str(x) for x in en.parameters]
                pads = ['-']*(len(t.columns)-len(row)-len(infos))
                row += pads + infos
                
            t.add_row(*row)
        
        return t
    

    def as_json(self):
        """Convert the map into a moo-json object"""
        m = self._map

        dro_seq = []
        for _,en in m.items():

            dro_en = dromap.DROStreamEntry()
            dro_en.src_id = en.src_id
            dro_en.kind = en.kind
            dro_en.geo_id = hdf5rdf.GeoID(**(en.geo_id._asdict()))

            moo_t = self._get_moo_class(en.kind)
            dro_en.parameters = moo_t(**(en.parameters._asdict()))

            dro_seq.append(dro_en)

        dlmap = dromap.DROStreamMap(dro_seq)
        return dlmap.pod()
    

    def remove_srcid(self, srcid):
        """Remove a source ID"""
        return self._map.pop(srcid)


    def add_srcid(self, src_id, geo_id, kind, **kwargs):
        """Add a new source id"""

        if src_id in self._map:
            raise KeyError(f"Source ID {src_id} is already present in the map")
        
        if geo_id in self.get_geo_ids():
            raise KeyError(f"Geo ID {geo_id} is already present in the map")


        tuple_t = self._get_tuple_class(kind)
        moo_t = self._get_moo_class(kind)

        parameters = tuple_t(**(moo_t(**kwargs).pod()))


        s = DROStreamEntry(src_id=src_id, geo_id=geo_id, kind=kind, parameters=parameters)
        stream_list = list(self.streams)+[s]
        self._validate_streams(stream_list)
        self._validate_eth(stream_list)
        self._validate_rohosts(stream_list)
        self._map[src_id] = s
    