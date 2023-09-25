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


###
# Create Fake dataproducers Application
###
def create_fake_readout_app(
    RU_DESCRIPTOR,
    CLOCK_SPEED_HZ
) -> App:
    """
    """
    modules = []
    queues = []

    # _, _, fakedata_fragment_type, fakedata_time_tick, fakedata_frame_size = compute_data_types(RU_DESCRIPTOR.det_id, CLOCK_SPEED_HZ, RU_DESCRIPTOR.kind)

    for stream in RU_DESCRIPTOR.streams:
        _, _, fakedata_fragment_type, fakedata_time_tick, fakedata_frame_size = compute_data_types(stream)

        modules += [DAQModule(name = f"fakedataprod_{stream.src_id}",
                                plugin='FakeDataProd',
                                conf = fdp.ConfParams(
                                system_type = "Detector_Readout",
                                source_id = stream.src_id,
                                time_tick_diff = fakedata_time_tick,
                                frame_size = fakedata_frame_size,
                                response_delay = 0,
                                fragment_type = fakedata_fragment_type,
                                ))]

    mgraph = ModuleGraph(modules, queues=queues)

    for stream in RU_DESCRIPTOR.streams:
        # Add fragment producers for fake data. This call is necessary to create the RequestReceiver instance, but we don't need the generated FragmentSender or its queues...
        mgraph.add_fragment_producer(id = stream.src_id, subsystem = "Detector_Readout",
                                        requests_in   = f"fakedataprod_{stream.src_id}.data_request_input_queue",
                                        fragments_out = f"fakedataprod_{stream.src_id}.fragment_queue")
        mgraph.add_endpoint(f"timesync_ru{RU_DESCRIPTOR.label}_{stream.src_id}", f"fakedataprod_{stream.src_id}.timesync_output",    "TimeSync",   Direction.OUT, is_pubsub=True, toposort=False)

    # Create the application
    readout_app = App(mgraph, host=RU_DESCRIPTOR.host_name)

    # All done
    return readout_app


# Time to wait on pop()
QUEUE_POP_WAIT_MS = 10 # This affects stop time, as each link will wait this long before stop

class NDReadoutAppGenerator(ReadoutAppGenerator):

    dlh_plugin = "NDDataLinkHandler"

    def create_fake_cardreader(
        self,
        # FRONTEND_TYPE: str,
        # QUEUE_FRAGMENT_TYPE: str,
        DATA_FILES: dict,
        RU_DESCRIPTOR # ReadoutUnitDescriptor

    ) -> tuple[list, list]:
        """
        Create a FAKE Card reader module
        """
        cfg = self.ro_cfg

        conf = sec.Conf(
                link_confs = [
                    sec.LinkConfiguration(
                        source_id=s.src_id,
                            crate_id = s.geo_id.crate_id,
                            slot_id = s.geo_id.slot_id,
                            link_id = s.geo_id.stream_id,
                            slowdown=self.daq_cfg.data_rate_slowdown_factor,
                            queue_name=f"output_{s.src_id}",
                            data_filename = DATA_FILES[s.geo_id.det_id] if s.geo_id.det_id in DATA_FILES.keys() else cfg.default_data_file,
                            emu_frame_error_rate=0
                        ) for s in RU_DESCRIPTOR.streams],
                use_now_as_first_data_time=cfg.emulated_data_times_start_with_now,
                generate_periodic_adc_pattern = cfg.generate_periodic_adc_pattern,  
                TP_rate_per_ch = cfg.emulated_TP_rate_per_ch,  
                clock_speed_hz=self.det_cfg.clock_speed_hz,
                queue_timeout_ms = QUEUE_POP_WAIT_MS
                )


        modules = [DAQModule(name = "fake_source",
                                plugin = "NDFakeCardReader",
                                conf = conf)]
      
        queues = []
        for s in RU_DESCRIPTOR.streams:
            FRONTEND_TYPE, QUEUE_FRAGMENT_TYPE, _, _, _ = compute_data_types(s)
            queues.append(
                Queue(
                    f"fake_source.output_{s.src_id}",
                    f"datahandler_{s.src_id}.raw_input",
                    QUEUE_FRAGMENT_TYPE,
                    f'{FRONTEND_TYPE}_link_{s.src_id}', 100000
                )
            )

        return modules, queues

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
