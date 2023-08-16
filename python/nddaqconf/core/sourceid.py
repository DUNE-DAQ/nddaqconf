# Set moo schema search path
from dunedaq.env import get_moo_model_path
import moo.io
moo.io.default_load_path = get_moo_model_path()
from rich.console import Console
from enum import Enum
from collections import namedtuple, defaultdict

from .console import console


from daqdataformats import SourceID
from detchannelmaps import *

TAID = namedtuple('TAID', ['detector', 'crate'])
TPID = namedtuple('TPID', ['detector', 'crate'])
#FWTPID = namedtuple('FWTPID', ['host', 'card', 'slr'])
#FWTPOUTID = namedtuple('FWTPOUTID', ['host', 'card', 'fwtpid'])

class TPInfo:
    def __init__(self):
        self.region_id = 0
        self.tp_ru_sid = 0
        self.link_count = 0

class TAInfo:
    def __init__(self):
        self.region_id = 0
        self.link_count = 0

class TCInfo:
    def __init__(self):
        self.ru_count = 0

class SourceIDBroker:


    def __init__(self):
        self.sourceid_map = {}
        self.debug: bool = False

    def get_next_source_id(self, subsystem, start_id = 0):
        while self.source_id_exists(subsystem, start_id):
            start_id += 1
        if self.debug: console.log(f"Returning {start_id} from get_next_source_id for subsystem {subsystem}")
        return start_id

    def get_all_source_ids(self, subsystem):
        if subsystem in self.sourceid_map:
            if self.debug: console.log(f"Returning {len(self.sourceid_map[subsystem])} SourceIDs for subsystem {subsystem}")
            return self.sourceid_map[subsystem]

        if self.debug: console.log(f"Subsystem {subsystem} not in sourceid_map")
        return {}

    def source_id_exists(self, subsystem, sid):
        if subsystem in self.sourceid_map:
            return sid in self.sourceid_map[subsystem]
        return False

    def register_source_id(self, subsystem, sid, info):
        if self.debug: console.log(f"Going to register Source ID {sid} for Subsystem {subsystem} with info object {info}")
        if not subsystem in self.sourceid_map:
            self.sourceid_map[subsystem] = {}
        if not self.source_id_exists(subsystem, sid):
            self.sourceid_map[subsystem][sid] = info
        else:
            raise ValueError(f"SourceID {sid} already exists for Subsystem {subsystem}!")

    # def _register_readout_source_ids(self, dro_configs):
    #     if self.debug: console.log(f"Generating Detector_Readout Source IDs, dro_configs are {dro_configs}")
    #     # fw_tp_ids = []
    #     max_sid = -1
    #     for dro_config in dro_configs:
    #         # slr_0 = False
    #         # slr_1 = False
    #         for link in dro_config.links:
    #             if not self.source_id_exists("Detector_Readout", link.dro_source_id):
    #                 self.register_source_id("Detector_Readout", link.dro_source_id, [link])
    #             else:
    #                 self.sourceid_map["Detector_Readout"][link.dro_source_id].append(link)
    #             # if tp_mode == TPGenMode.FWTPG:
    #             #     if max_sid < link.dro_source_id:
    #             #         max_sid = link.dro_source_id
    #             #     if link.dro_slr == 0 and slr_0 == False: x
    #             #         slr_0 = True
    #             #         # fw_tp_ids.append(FWTPID(dro_config.host, dro_config.card, 0))
    #             #     if link.dro_slr == 1 and slr_1 == False: 
    #             #         slr_1 = True
    #             #         # fw_tp_ids.append(FWTPID(dro_config.host, dro_config.card, 1))
    #         # if self.debug: console.log(f"found slr0: {slr_0}, found slr1: {slr_1}")
    #     # fwsid = []
    #     # if tp_mode == TPGenMode.FWTPG:
    #     #     for fw_tp_id in fw_tp_ids:
    #     #         sid = self.get_next_source_id("Detector_Readout", max_sid)
    #     #         fwsid.append(sid)
    #     #         if self.debug: console.log(f"Adding Detector_Readout SourceID {sid} for FW TP ID {fw_tp_id}")
    #     #         self.register_source_id("Detector_Readout", sid, fw_tp_id)
    #     #     for i in range(len(fwsid)):
    #     #         sid = self.get_next_source_id("Detector_Readout", max_sid)
    #     #         tp_out_id = FWTPOUTID(fw_tp_ids[i].host, fw_tp_ids[i].card, fwsid[i])
    #     #         if self.debug: console.log(f"Adding Detector_Readout SourceID {sid} for FW TP OUT ID {tp_out_id}")
    #     #         self.register_source_id("Detector_Readout", sid, tp_out_id)

    def register_readout_source_ids(self, dro_streams):
        if self.debug: console.log(f"Registering {len(dro_streams)} Detector-Readout Source IDs ")
        for stream in dro_streams:
            if not self.source_id_exists("Detector_Readout", stream.src_id):
                self.register_source_id("Detector_Readout", stream.src_id, [stream])
            else:
                self.sourceid_map["Detector_Readout"][stream.src_id].append(stream)


    # def _generate_trigger_source_ids(self, dro_configs, tp_mode: bool):
    #     tc_info = TCInfo()
    #     ta_infos = {}
    #     # fw_tp_infos = {}
    #     # dro_sids = self.get_all_source_ids("Detector_Readout")

    #     if self.debug: console.log(f"Generating Trigger Source IDs, tp_mode is {tp_mode}, dro_configs are {dro_configs}")

    #     for dro_config in dro_configs:
    #         dro_sends_data = False
    #         for link in dro_config.links:
    #             # if link.det_id != 3: continue # Only HD_TPC for now
    #             dro_sends_data = True
    #             taid = TAID(link.det_id, link.det_crate)
    #             if taid not in ta_infos:
    #                 ta_infos[taid] = TAInfo()
    #                 ta_infos[taid].region_id = link.det_crate
    #                 ta_infos[taid].link_count = 1
    #             else:
    #                 ta_infos[taid].link_count += 1
                    
    #             # if tp_mode == TPGenMode.FWTPG:
    #             #     fw_tp_id = FWTPID(dro_config.host, dro_config.card, link.dro_slr)
    #             #     if fw_tp_id not in fw_tp_infos:
    #             #         fwtp_link = TPInfo(link)
    #             #         fwtpid_found = False
    #             #         for fwsid,fwid in dro_sids.items():
    #             #             if isinstance(fwid, FWTPID) and fwid == fw_tp_id:
    #             #                 if fwtpid_found == True:
    #             #                     raise ValueError(f"Multiple matches found for firmware TP ID {fw_tp_id}")
    #             #                 fwtp_link.dro_source_id = fwsid
    #             #                 fwtpid_found = True
    #             #         if fwtpid_found == False:
    #             #             raise ValueError(f"No match found for firmware TP ID {fw_tp_id}")
    #             #         sid = self.get_next_source_id("Trigger")
    #             #         if self.debug: console.log(f"Adding Trigger SourceID {sid} for FW TP ID {fw_tp_id}")
    #             #         self.register_source_id("Trigger", sid, fwtp_link)
    #             #         fw_tp_infos[fw_tp_id] = fwtp_link
    #             # elif tp_mode == TPGenMode.SWTPG:
    #             if tp_mode:
    #                 sid = self.get_next_source_id("Trigger")
    #                 self.register_source_id("Trigger", sid, TPInfo(link))
    #         if dro_sends_data:
    #             tc_info.ru_count += 1

    #     for ta_info in ta_infos.values():
    #         self.register_source_id("Trigger", self.get_next_source_id("Trigger"), ta_info)
    #     self.register_source_id("Trigger", self.get_next_source_id("Trigger"), tc_info)


    def generate_trigger_source_ids(self, ru_descrs, tp_mode: bool):
        tc_info = TCInfo()
        ta_infos = {}
        tp_infos = {}
        # dro_sids = self.get_all_source_ids("Detector_Readout")

        if self.debug: console.log(f"Registering Trigger Source IDs, tp_mode is {tp_mode}, dro_configs are {ru_descrs}")

        for ru_name, ru_desc in ru_descrs.items():
            det_id = ru_desc.det_id
            crate_id = ru_desc.streams[0].geo_id.crate_id

            if tp_mode:
                tp_ru_sid = self.get_next_source_id("Trigger")
                self.register_source_id("Trigger", tp_ru_sid, ru_desc),

                tpid = TPID(det_id, crate_id)
                tp_infos[tpid] = TPInfo()
                tp_infos[tpid].region_id = crate_id
                tp_infos[tpid].tp_ru_sid = tp_ru_sid
                tp_infos[tpid].link_count = 1

                taid = TAID(det_id, crate_id)
                ta_infos[taid] = TAInfo()
                ta_infos[taid].region_id = crate_id
                ta_infos[taid].link_count = 1

            tc_info.ru_count += 1

        for tp_info in tp_infos.values():
            tpsid = self.get_next_source_id("Trigger")
            if self.debug: console.log(f"Registering Trigger TP Source IDs {tpsid} for region {tp_info.region_id}")
            self.register_source_id("Trigger", tpsid, tp_info)
        for ta_info in ta_infos.values():
            tasid = self.get_next_source_id("Trigger")
            if self.debug: console.log(f"Registering Trigger TA Source IDs {tasid} for region {ta_info.region_id}")
            self.register_source_id("Trigger", tasid, ta_info)
        self.register_source_id("Trigger", self.get_next_source_id("Trigger"), tc_info)


# def get_tpg_mode(enable_fw_tpg, enable_tpg):
#     if enable_fw_tpg and enable_tpg:
#         raise ValueError("Cannot enable both FW and SW TPG!")
#     if enable_fw_tpg:
#         return TPGenMode.FWTPG
#     if enable_tpg:
#         return TPGenMode.SWTPG

#     return TPGenMode.DISABLED
                

def source_id_raw_str(source_id: SourceID):
    """Get a string representation of a SourceID suitable for using in queue names"""
    return source_id.to_string()

def ensure_subsystem_string(subsystem):
    if isinstance(subsystem, str):
        return subsystem
    
    return SourceID.subsystem_to_string(SourceID.Subsystem(subsystem))

def ensure_subsystem(subsystem):
    if isinstance(subsystem, str):
        return SourceID.string_to_subsystem(subsystem)

    return SourceID.Subsystem(subsystem)
