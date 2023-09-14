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


class ReadoutAppGenerator:
    """Utility class to generate readout applications"""
    
    dlh_plugin = None

    def __init__(self, readout_cfg, det_cfg, daq_cfg):

        self.ro_cfg = readout_cfg
        self.det_cfg = det_cfg
        self.daq_cfg = daq_cfg

        numa_excpt = {}
        for ex in self.ro_cfg.numa_config['exceptions']:
            numa_excpt[(ex['host'], ex['card'])] = ex
        self.numa_excpt = numa_excpt

        lcores_excpt = {}
        for ex in self.ro_cfg.dpdk_lcores_config['exceptions']:
            lcores_excpt[(ex['host'], ex['iface'])] = ex
        self.lcores_excpt = lcores_excpt


    def get_numa_cfg(self, RU_DESCRIPTOR):

        cfg = self.ro_cfg
        try:
            ex = self.numa_excpt[(RU_DESCRIPTOR.host_name, RU_DESCRIPTOR.iface)]
            numa_id = ex['numa_id']
            latency_numa = ex['latency_buffer_numa_aware']
            latency_preallocate = ex['latency_buffer_preallocation']
        except KeyError:
            numa_id = cfg.numa_config['default_id']
            latency_numa = cfg.numa_config['default_latency_numa_aware']
            latency_preallocate = cfg.numa_config['default_latency_preallocation']
        return (numa_id, latency_numa, latency_preallocate)

    def get_lcore_config(self, RU_DESCRIPTOR):
        cfg = self.ro_cfg
        try:
            ex = self.lcores_excpt[(RU_DESCRIPTOR.host_name, RU_DESCRIPTOR.iface)]
            lcore_id_set = ex['lcore_id_set']
        except KeyError:
            lcore_id_set = cfg.dpdk_lcores_config['default_lcore_id_set']

        
        return list(dict.fromkeys(lcore_id_set))

    def create_cardreader(self, RU_DESCRIPTOR, data_file_map):

        raise NotImplementedError("create_cardreader must be implemented in detived classes!")

        return [],[]
    
    ###
    # Create detector datalink handlers
    ###
    def create_det_dhl(
            self,
            LATENCY_BUFFER_NUMA_AWARE: int,
            LATENCY_BUFFER_ALLOCATION_MODE: int,
            NUMA_ID: int,
            SEND_PARTIAL_FRAGMENTS: bool,
            DATA_REQUEST_TIMEOUT: int,
            RU_DESCRIPTOR # ReadoutUnitDescriptor
        ) -> tuple[list, list]:

        if self.dlh_plugin is None:
            raise NotImplementedError("DataLinkHandler plugin must be specified in derived classses!")

        cfg = self.ro_cfg

        # defaults hardcoded values
        default_latency_buffer_alignment_size = 4096
        default_pop_limit_pct = 0.8
        default_pop_size_pct = 0.1
        default_stream_buffer_size = 8388608


        modules = []
        for stream in RU_DESCRIPTOR.streams:
            geo_id = stream.geo_id
            modules += [DAQModule(
                        name = f"datahandler_{stream.src_id}",
                        plugin = self.dlh_plugin, 
                        conf = rconf.Conf(
                            readoutmodelconf= rconf.ReadoutModelConf(
                                source_queue_timeout_ms= QUEUE_POP_WAIT_MS,
                                # fake_trigger_flag=0, # default
                                source_id =  stream.src_id,
                                send_partial_fragment_if_available = SEND_PARTIAL_FRAGMENTS
                            ),
                            latencybufferconf= rconf.LatencyBufferConf(
                                latency_buffer_alignment_size = default_latency_buffer_alignment_size,
                                latency_buffer_size = cfg.latency_buffer_size,
                                source_id =  stream.src_id,
                                latency_buffer_numa_aware = LATENCY_BUFFER_NUMA_AWARE,
                                latency_buffer_numa_node = NUMA_ID,
                                latency_buffer_preallocation = LATENCY_BUFFER_ALLOCATION_MODE,
                                latency_buffer_intrinsic_allocator = LATENCY_BUFFER_ALLOCATION_MODE,
                            ),
                            rawdataprocessorconf= rconf.RawDataProcessorConf(
                                emulator_mode = cfg.emulator_mode,
                                crate_id = geo_id.crate_id, 
                                slot_id = geo_id.slot_id, 
                                link_id = geo_id.stream_id
                            ),
                            requesthandlerconf= rconf.RequestHandlerConf(
                                latency_buffer_size = cfg.latency_buffer_size,
                                pop_limit_pct = default_pop_limit_pct,
                                pop_size_pct = default_pop_size_pct,
                                source_id = stream.src_id,
                                det_id = RU_DESCRIPTOR.det_id,
                                output_file = path.join(cfg.raw_recording_output_dir, f"output_{RU_DESCRIPTOR.label}_{stream.src_id}.out"),
                                stream_buffer_size = default_stream_buffer_size,
                                request_timeout_ms = DATA_REQUEST_TIMEOUT,
                                fragment_send_timeout_ms = cfg.fragment_send_timeout_ms,
                                enable_raw_recording = cfg.enable_raw_recording,
                            ))
                    )]
        queues = []
        return modules, queues


    ###
    # Enable processing in DLHs
    ###
    def add_tp_processing(
            self,
            dlh_list: list,
            TPG_CHANNEL_MAP: str,
        ) -> list:

        cfg = self.ro_cfg

        modules = []

        # defaults hardcoded values
        default_error_counter_threshold=100
        default_error_reset_freq=10000


        # Loop over datalink handlers to re-define the data processor configuration
        for dlh in dlh_list:

            # Recover the raw data link source id
            # MOOOOOO
            dro_sid = dlh.conf.readoutmodelconf["source_id"]
            geo_cid = dlh.conf.rawdataprocessorconf["crate_id"]
            geo_sid = dlh.conf.rawdataprocessorconf["slot_id"]
            geo_lid = dlh.conf.rawdataprocessorconf["link_id"]
            # Re-create the module with an extended configuration
            modules += [DAQModule(
                name = dlh.name,
                plugin = dlh.plugin,
                conf = rconf.Conf(
                    readoutmodelconf = dlh.conf.readoutmodelconf,
                    latencybufferconf = dlh.conf.latencybufferconf,
                    requesthandlerconf = dlh.conf.requesthandlerconf,
                    rawdataprocessorconf= rconf.RawDataProcessorConf(
                        source_id = dro_sid,
                        crate_id = geo_cid,
                        slot_id = geo_sid,
                        link_id = geo_lid,
                        enable_tpg = True,
                        tpg_threshold = cfg.tpg_threshold,
                        tpg_algorithm = cfg.tpg_algorithm,
                        tpg_channel_mask = cfg.tpg_channel_mask,
                        channel_map_name = TPG_CHANNEL_MAP,
                        emulator_mode = cfg.emulator_mode,
                        clock_speed_hz = (self.det_cfg.clock_speed_hz / self.daq_cfg.data_rate_slowdown_factor),
                        error_counter_threshold=default_error_counter_threshold,
                        error_reset_freq=default_error_reset_freq
                    ),
                )
            )]
            
        return modules

    ###
    # Create TP data link handlers
    ###
    def create_tp_dlhs(
        self,    
        dlh_list: list,
        DATA_REQUEST_TIMEOUT: int, # To Check
        FRAGMENT_SEND_TIMEOUT: int, # To Check
        tpset_sid: int,
        )-> tuple[list, list]:
        
        default_pop_limit_pct = 0.8
        default_pop_size_pct = 0.1
        default_stream_buffer_size = 8388608
        default_latency_buffer_size = 4000000
        default_detid = 1

        if self.dlh_plugin is None:
            raise NotImplementedError("DataLinkHandler plugin must be specified in derived classses!")

        # Create the TP link handler
        modules = [
        DAQModule(name = f"tp_datahandler_{tpset_sid}",
                    plugin = self.dlh_plugin,
                    conf = rconf.Conf(
                                readoutmodelconf = rconf.ReadoutModelConf(
                                    source_queue_timeout_ms = QUEUE_POP_WAIT_MS,
                                    source_id = tpset_sid
                                ),
                                latencybufferconf = rconf.LatencyBufferConf(
                                    latency_buffer_size = default_latency_buffer_size,
                                    source_id =  tpset_sid
                                ),
                                rawdataprocessorconf = rconf.RawDataProcessorConf(enable_tpg = False),
                                requesthandlerconf= rconf.RequestHandlerConf(
                                    latency_buffer_size = default_latency_buffer_size,
                                    pop_limit_pct = default_pop_limit_pct,
                                    pop_size_pct = default_pop_size_pct,
                                    source_id = tpset_sid,
                                    det_id = default_detid,
                                    stream_buffer_size = default_stream_buffer_size,
                                    request_timeout_ms = DATA_REQUEST_TIMEOUT,
                                    fragment_send_timeout_ms = FRAGMENT_SEND_TIMEOUT,
                                    enable_raw_recording = False
                                )
                            )
                    )
                ]
        
        queues = []
        for dlh in dlh_list:
            # Attach to the detector DLH's tp_out connector
            queues += [
                Queue(
                    f"{dlh.name}.tp_out",
                    f"tp_datahandler_{tpset_sid}.raw_input",
                    "TriggerPrimitive",
                    f"tp_link_{tpset_sid}",1000000 
                    )
                ]

        return modules, queues

    ###
    # Add detector endpoints and fragment producers
    ###
    def add_dro_eps_and_fps(
            self,
            mgraph: ModuleGraph,
            dlh_list: list,
            RUIDX: str,
        ) -> None: 
        """Adds detector readout endpoints and fragment producers"""
        for dlh in dlh_list:
            # extract source ids
            dro_sid = dlh.conf.readoutmodelconf['source_id']

            mgraph.add_fragment_producer(
                id = dro_sid, 
                subsystem = "Detector_Readout",
                requests_in   = f"datahandler_{dro_sid}.request_input",
                fragments_out = f"datahandler_{dro_sid}.fragment_queue"
            )
            mgraph.add_endpoint(
                f"timesync_ru{RUIDX}_{dro_sid}",
                f"datahandler_{dro_sid}.timesync_output",
                "TimeSync",   Direction.OUT,
                is_pubsub=True,
                toposort=False
            )



    ###
    # Add tpg endpoints and fragment producers
    ###
    def add_tpg_eps_and_fps(
            self,
            mgraph: ModuleGraph,
            tpg_dlh_list: list,
            RUIDX: str,  
        ) -> None: 
        """Adds detector readout endpoints and fragment producers"""

        for dlh in tpg_dlh_list:

            # extract source ids
            tpset_sid = dlh.conf.readoutmodelconf['source_id']

            # Add enpointis with this source id for timesync and TPSets
            mgraph.add_endpoint(
                f"timesync_tp_dlh_ru{RUIDX}_{tpset_sid}",
                f"tp_datahandler_{tpset_sid}.timesync_output",
                "TimeSync",
                Direction.OUT,
                is_pubsub=True
            )

            mgraph.add_endpoint(
                    f"tpsets_tplink{tpset_sid}",
                    f"tp_datahandler_{tpset_sid}.tpset_out",
                    "TPSet",
                    Direction.OUT,
                    is_pubsub=True
                )

            # Add Fragment producer with this source id
            mgraph.add_fragment_producer(
                id = tpset_sid, subsystem = "Trigger",
                requests_in   = f"tp_datahandler_{tpset_sid}.request_input",
                fragments_out = f"tp_datahandler_{tpset_sid}.fragment_queue"
            )
        

    def generate(
            self,
            RU_DESCRIPTOR, 
            SOURCEID_BROKER,
            data_file_map,
            data_timeout_requests,
            ):
        """Generate the readout applicaton

        Args:
            RU_DESCRIPTOR (ReadoutUnitDescriptor): A readout unit descriptor object
            SOURCEID_BROKER (SourceIDBroker): The source ID brocker
            data_file_map (dict): Map of pattern files to application
            data_timeout_requests (int): Data timeout request

        Raises:
            RuntimeError: _description_

        Returns:
            _type_: _description_
        """
        numa_id, latency_numa, latency_preallocate = self.get_numa_cfg(RU_DESCRIPTOR)
        cfg = self.ro_cfg
        TPG_ENABLED = cfg.enable_tpg
        DATA_FILES = data_file_map
        DATA_REQUEST_TIMEOUT=data_timeout_requests
        
        modules = []
        queues = []


        # Create the card readers
        cr_mods = []
        cr_queues = []

        cr_mods, cr_queues = self.create_cardreader(
            RU_DESCRIPTOR=RU_DESCRIPTOR,
            data_file_map=data_file_map
        )

        modules += cr_mods
        queues += cr_queues

        # Create the data-link handlers
        dlhs_mods, _ = self.create_det_dhl(
            LATENCY_BUFFER_NUMA_AWARE=latency_numa,
            LATENCY_BUFFER_ALLOCATION_MODE=latency_preallocate,
            NUMA_ID=numa_id,
            SEND_PARTIAL_FRAGMENTS=False,
            DATA_REQUEST_TIMEOUT=DATA_REQUEST_TIMEOUT,
            RU_DESCRIPTOR=RU_DESCRIPTOR
        )

        # Configure the TP processing if requrested
        if TPG_ENABLED:
            dlhs_mods = self.add_tp_processing(
            dlh_list=dlhs_mods,
            TPG_CHANNEL_MAP=self.det_cfg.tpc_channel_map,
            )

        modules += dlhs_mods

        # Add the TP datalink handlers
        if TPG_ENABLED:
            tps = { k:v for k,v in SOURCEID_BROKER.get_all_source_ids("Trigger").items() if isinstance(v, ReadoutUnitDescriptor ) and v==RU_DESCRIPTOR}
            if len(tps) != 1:
                raise RuntimeError(f"Could not retrieve unique element from source id map {tps}")

            tpg_mods, tpg_queues = self.create_tp_dlhs(
                dlh_list=dlhs_mods,
                DATA_REQUEST_TIMEOUT=DATA_REQUEST_TIMEOUT,
                FRAGMENT_SEND_TIMEOUT=cfg.fragment_send_timeout_ms,
                tpset_sid = next(iter(tps))
            )
            modules += tpg_mods
            queues += tpg_queues

        # Create the Module graphs
        mgraph = ModuleGraph(modules, queues=queues)

        # Add endpoints and frame producers to DRO data handlers
        self.add_dro_eps_and_fps(
            mgraph=mgraph,
            dlh_list=dlhs_mods,
            RUIDX=RU_DESCRIPTOR.label
        )

        if TPG_ENABLED:
            # Add endpoints and frame producers to TP data handlers
            self.add_tpg_eps_and_fps(
                mgraph=mgraph,
                tpg_dlh_list=tpg_mods,
                RUIDX=RU_DESCRIPTOR.label
            )

        # Create the application
        readout_app = App(mgraph, host=RU_DESCRIPTOR.host_name)

        dir_names = set()

        cvmfs = Path('/cvmfs')
        ddf_path = Path(cfg.default_data_file)
        if not cvmfs in ddf_path.parents:
            dir_names.add(ddf_path.parent)

        for file in data_file_map.values():
            f = Path(file)
            if not cvmfs in f.parents:
                dir_names.add(f.parent)

        for dir_idx, dir_name in enumerate(dir_names):
            readout_app.mounted_dirs += [{
                'name': f'data-file-{dir_idx}',
                'physical_location': dir_name,
                'in_pod_location':   dir_name,
                'read_only': True,
            }]

        # All done
        return readout_app
    


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

        if RU_DESCRIPTOR.kind == 'eth' and RU_DESCRIPTOR.streams[0].parameters.protocol == "zmq":
            
            pac_mods, pac_queues = self.create_pacman_cardreader(
                RU_DESCRIPTOR=RU_DESCRIPTOR
            )
            cr_mods += pac_mods
            cr_queues += pac_queues
        else:
            raise RuntimeError("Card reader could not be created.")

        return cr_mods, cr_queues

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
