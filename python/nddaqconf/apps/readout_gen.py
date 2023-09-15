# Set moo schema search path
from dunedaq.env import get_moo_model_path
import moo.io
moo.io.default_load_path = get_moo_model_path()

# Load configuration types
import moo.otypes

moo.otypes.load_types('readoutlibs/sourceemulatorconfig.jsonnet')
moo.otypes.load_types('readoutlibs/readoutconfig.jsonnet')
moo.otypes.load_types('lbrulibs/pacmancardreader.jsonnet')
moo.otypes.load_types('dfmodules/fakedataprod.jsonnet')

# Import new types
import dunedaq.readoutlibs.sourceemulatorconfig as sec
import dunedaq.readoutlibs.readoutconfig as rconf
import dunedaq.lbrulibs.pacmancardreader as pcr
import dunedaq.dfmodules.fakedataprod as fdp

from os import path
from pathlib import Path

from daqconf.core.conf_utils import Direction, Queue
from daqconf.core.sourceid import  SourceIDBroker
from daqconf.core.daqmodule import DAQModule
from daqconf.core.app import App, ModuleGraph
from daqconf.detreadoutmap import ReadoutUnitDescriptor, group_by_key
from daqconf.apps.readout_gen import ReadoutAppGenerator
from detdataformats import DetID


## Compute the frament types from detector infos
def compute_data_types(
        stream_entry
    ):
    det_str = DetID.subdetector_to_string(DetID.Subdetector(stream_entry.geo_id.det_id))

    if det_str == "NDLAr_TPC":
        fe_type = "pacman"
        fakedata_frag_type = "PACMAN"
        queue_frag_type = "PACMANFrame"
        fakedata_time_tick=None
        fakedata_frame_size=None       
    elif det_str == "NDLAr_PDS":
        fe_type = "mpd"
        fakedata_frag_type = "MPD"
        queue_frag_type = "MPDFrame"
        fakedata_time_tick=None
        fakedata_frame_size=None       
    else:
        raise ValueError(f"No match for {det_str}, {stream_entry.kind}")


    return fe_type, queue_frag_type, fakedata_frag_type, fakedata_time_tick, fakedata_frame_size


# Time to wait on pop()
QUEUE_POP_WAIT_MS = 10 # This affects stop time, as each link will wait this long before stop

class NDReadoutAppGenerator(ReadoutAppGenerator):

    dlh_plugin = "NDDataLinkHandler"

    def create_pacman_cardreader(
            self,
            RU_DESCRIPTOR # ReadoutUnitDescriptor
        ) -> tuple[list, list]:
        """
        Create a Pacman Cardeader 
        """

        FRONTEND_TYPE, _, _, _, _ = compute_data_types(RU_DESCRIPTOR.streams[0])
        reader_name = "pacman_reader" 
        if FRONTEND_TYPE == 'pacman':
            reader_name = "pacman_source"

        elif FRONTEND_TYPE == 'mpd':
            reader_name = "mpd_source"

        else:
            raise RuntimeError(f"PACMAN Cardreader for {FRONTEND_TYPE} not supported")

        modules = [DAQModule(
                    name=reader_name,
                    plugin="PacmanCardReader",   # should be changed after consulting at Core meeting on 30 Sept
                    conf=pcr.Conf(link_confs = [pcr.LinkConfiguration(Source_ID=stream.src_id)
                                        for stream in RU_DESCRIPTOR.streams],
                        zmq_receiver_timeout = 10000)
                )]

        # Queues
        queues = []
        for s in RU_DESCRIPTOR.streams:
            FRONTEND_TYPE, QUEUE_FRAGMENT_TYPE, _, _, _ = compute_data_types(s)
            queues.append(
                Queue(
                    f"{reader_name}.output_{s.src_id}",
                    f"datahandler_{s.src_id}.raw_input", QUEUE_FRAGMENT_TYPE,
                    f'{FRONTEND_TYPE}_stream_{s.src_id}', 100000
                )
            )

        return modules, queues


    def create_cardreader(self, RU_DESCRIPTOR, data_file_map):
        # Create the card readers
        cr_mods = []
        cr_queues = []
        cfg = self.ro_cfg
        
        # Create the card readers
        if cfg.use_fake_cards:
            fakecr_mods, fakecr_queues = self.create_fake_cardreader(
                DATA_FILES=data_file_map,
                RU_DESCRIPTOR=RU_DESCRIPTOR
            )
            cr_mods += fakecr_mods
            cr_queues += fakecr_queues
        else : 
            if RU_DESCRIPTOR.kind == 'eth' and RU_DESCRIPTOR.streams[0].parameters.protocol == "zmq":
            
                pac_mods, pac_queues = self.create_pacman_cardreader(
                    RU_DESCRIPTOR=RU_DESCRIPTOR
                )
                cr_mods += pac_mods
                cr_queues += pac_queues
            else:
                raise RuntimeError("Card reader could not be created.")

        return cr_mods, cr_queues
