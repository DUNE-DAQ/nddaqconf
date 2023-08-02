# Set moo schema search path
from dunedaq.env import get_moo_model_path
import moo.io
moo.io.default_load_path = get_moo_model_path()

# Load configuration types
import moo.otypes

moo.otypes.load_types('flxlibs/felixcardreader.jsonnet')
moo.otypes.load_types('readoutlibs/sourceemulatorconfig.jsonnet')
moo.otypes.load_types('readoutlibs/readoutconfig.jsonnet')
moo.otypes.load_types('dfmodules/fakedataprod.jsonnet')
moo.otypes.load_types("dpdklibs/nicreader.jsonnet")


# Import new types
import dunedaq.readoutlibs.sourceemulatorconfig as sec
import dunedaq.flxlibs.felixcardreader as flxcr
import dunedaq.readoutlibs.readoutconfig as rconf
import dunedaq.dfmodules.fakedataprod as fdp
import dunedaq.dpdklibs.nicreader as nrc

# from appfwk.utils import acmd, mcmd, mrccmd, mspec
from os import path
from pathlib import Path

from ..core.conf_utils import Direction, Queue
from ..core.sourceid import  SourceIDBroker
from ..core.daqmodule import DAQModule
from ..core.app import App, ModuleGraph
from ..detreadoutmap import ReadoutUnitDescriptor, group_by_key

# from detdataformats._daq_detdataformats_py import *
from detdataformats import DetID


## Compute the frament types from detector infos
def compute_data_types(
        stream_entry
    ):
    det_str = DetID.subdetector_to_string(DetID.Subdetector(stream_entry.geo_id.det_id))


    # Far detector types
    if (det_str in ("HD_TPC","VD_Bottom_TPC") and stream_entry.kind=='flx' ):
        fe_type = "wib2"
        queue_frag_type="WIB2Frame"
        fakedata_frag_type = "WIB"
        fakedata_time_tick=32
        fakedata_frame_size=472
    elif (det_str in ("HD_TPC","VD_Bottom_TPC") and stream_entry.kind=='eth' ):
        fe_type = "wibeth"
        queue_frag_type="WIBEthFrame"
        fakedata_frag_type = "WIBEth"
        fakedata_time_tick=2048
        fakedata_frame_size=7200
    elif det_str in ("HD_PDS", "VD_Cathode_PDS", "VD_Membrane_PDS") and stream_entry.parameters.mode == "var_rate":
        fe_type = "pds"
        fakedata_frag_type = "DAPHNE"
        queue_frag_type = "PDSFrame"
        fakedata_time_tick=None
        fakedata_frame_size=472
    elif det_str in ("HD_PDS", "VD_Cathode_PDS", "VD_Membrane_PDS") and  stream_entry.parameters.mode == "fix_rate":
        fe_type = "pds_stream"
        fakedata_frag_type = "DAPHNE"
        queue_frag_type = "PDSStreamFrame"
        fakedata_time_tick=None
        fakedata_frame_size=472
    elif det_str == "VD_Top_TPC":
        fe_type = "tde"
        fakedata_frag_type = "TDE_AMC"
        queue_frag_type = "TDEFrame"
        fakedata_time_tick=4472*32
        fakedata_frame_size=8972
    # 20-Jun-2023, KAB: quick fix to get FD-specific nightly build to run
    ## Near detector types
    #elif det_str == "NDLAr_TPC":
    #    fe_type = "pacman"
    #    fakedata_frag_type = "PACMAN"
    #    queue_frag_type = "PACMANFrame"
    #    fakedata_time_tick=None
    #    fakedata_frame_size=None       
    #elif det_str == "NDLAr_PDS":
    #    fe_type = "mpd"
    #    fakedata_frag_type = "MPD"
    #    queue_frag_type = "MPDFrame"
    #    fakedata_time_tick=None
    #    fakedata_frame_size=None       
    else:
        raise ValueError(f"No match for {det_str}, {stream_entry.kind}")


    return fe_type, queue_frag_type, fakedata_frag_type, fakedata_time_tick, fakedata_frame_size


###
# DPDK Card Reader creator
###
class NICReceiverBuilder:

    # FIXME: workaround to avoid lcore to be set to 0
    # To be reviewd
    lcore_offset = 1

    def __init__(self, rudesc : ReadoutUnitDescriptor):
        self.desc = rudesc


    def streams_by_host(self):

        iface_map = group_by_key(self.desc.streams, lambda s: s.parameters.rx_host)

        return iface_map    

    def streams_by_rxiface(self):
        """Group streams by interface

        Returns:
            dict: A map of streams with the same destination ip, mac and host
        """

        iface_map = group_by_key(self.desc.streams, lambda s: (s.parameters.rx_ip, s.parameters.rx_mac, s.parameters.rx_host))

        return iface_map

    def streams_by_rxiface_and_tx_endpoint(self):

        s_by_if = self.streams_by_rxiface()
        m = {}
        for k,v in s_by_if.items():
            m[k] = group_by_key(v, lambda s: (s.parameters.tx_ip, s.parameters.tx_mac, s.parameters.tx_host))
            
        return m
    
    # def streams_by_ru(self):
    #     m = group_by_key(self.desc.streams, lambda s: (getattr(s.parameters, self.desc._host_label_map[s.kind]), getattr(s.parameters, self.desc._iflabel_map[s.kind]), s.kind, s.geo_id.det_id))
    #     return m

    def build_conf(self, eal_arg_list, lcores_id_set):


        streams_by_if_and_tx = self.streams_by_rxiface_and_tx_endpoint()

        ifcfgs = []
        for (rx_ip, rx_mac, _),txs in streams_by_if_and_tx.items():
            srcs = []
            # Sid is used for the "Source.id". What is it?

            # Transmitters are sorted by tx ip address.
            # This is not good for understanding what is what, so we sort them by minimum
            # src_id
            txs_sorted_by_src = sorted(txs.items(), key=lambda x: min(x[1], key=lambda y: y.src_id))

            for sid,((tx_ip,_,_),streams) in enumerate(txs_sorted_by_src):
                ssm = nrc.SrcStreamsMapping([
                        nrc.StreamMap(source_id=s.src_id, stream_id=s.geo_id.stream_id)
                        for s in streams
                    ])
                geo_id = streams[0].geo_id
                si = nrc.SrcGeoInfo(
                    det_id=geo_id.det_id,
                    crate_id=geo_id.crate_id,
                    slot_id=geo_id.slot_id
                )

                srcs.append(
                    nrc.Source(
                        id=sid, # FIXME what is this ID?
                        ip_addr=tx_ip,
                        lcore=lcores_id_set[sid % len(lcores_id_set)],
                        rx_q=sid,
                        src_info=si,
                        src_streams_mapping=ssm
                    )
                )
            ifcfgs.append(
                nrc.Interface(
                    ip_addr=rx_ip,
                    mac_addr=rx_mac,
                    expected_sources=srcs,
                    stats_reporting_cfg=nrc.StatsReporting()
                )
            )         


        conf = nrc.Conf(
            ifaces = ifcfgs,
            eal_arg_list=eal_arg_list
        )

        return conf
    

# Time to wait on pop()
QUEUE_POP_WAIT_MS = 10 # This affects stop time, as each link will wait this long before stop


class ReadoutAppGenerator:
    """Utility class to generate readout applications"""

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
            flx_card_override = ex['felix_card_id']
        except KeyError:
            numa_id = cfg.numa_config['default_id']
            latency_numa = cfg.numa_config['default_latency_numa_aware']
            latency_preallocate = cfg.numa_config['default_latency_preallocation']
            flx_card_override = -1
        return (numa_id, latency_numa, latency_preallocate, flx_card_override)

    def get_lcore_config(self, RU_DESCRIPTOR):
        cfg = self.ro_cfg
        try:
            ex = self.lcores_excpt[(RU_DESCRIPTOR.host_name, RU_DESCRIPTOR.iface)]
            lcore_id_set = ex['lcore_id_set']
        except KeyError:
            lcore_id_set = cfg.dpdk_lcores_config['default_lcore_id_set']

        
        return list(dict.fromkeys(lcore_id_set))


    ###
    # Fake Card Reader creator
    ###
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
                clock_speed_hz=self.det_cfg.clock_speed_hz,
                queue_timeout_ms = QUEUE_POP_WAIT_MS
                )


        modules = [DAQModule(name = "fake_source",
                                plugin = "FDFakeCardReader",
                                conf = conf)]
        # queues = [
        #     Queue(
        #         f"fake_source.output_{s.src_id}",
        #         f"datahandler_{s.src_id}.raw_input",
        #         QUEUE_FRAGMENT_TYPE,
        #         f'{FRONTEND_TYPE}_link_{s.src_id}', 100000
        #     ) for s in RU_DESCRIPTOR.streams
        # ]
        
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


    ###
    # FELIX Card Reader creator
    ###
    def create_felix_cardreader(
            self,
            # FRONTEND_TYPE: str,
            # QUEUE_FRAGMENT_TYPE: str,
            CARD_ID_OVERRIDE: int,
            NUMA_ID: int,
            RU_DESCRIPTOR # ReadoutUnitDescriptor
        ) -> tuple[list, list]:
        """
        Create a FELIX Card Reader (and reader->DHL Queues?)

        [CR]->queues
        """
        links_slr0 = []
        links_slr1 = []
        strms_slr0 = []
        strms_slr1 = []
        for stream in RU_DESCRIPTOR.streams:
            if stream.parameters.slr == 0:
                links_slr0.append(stream.parameters.link)
                strms_slr0.append(stream)
            if stream.parameters.slr == 1:
                links_slr1.append(stream.parameters.link)
                strms_slr1.append(stream)

        links_slr0.sort()
        links_slr1.sort()

        card_id = RU_DESCRIPTOR.iface if CARD_ID_OVERRIDE == -1 else CARD_ID_OVERRIDE

        modules = []
        queues = []
        if len(links_slr0) > 0:
            modules += [DAQModule(name = 'flxcard_0',
                            plugin = 'FelixCardReader',
                            conf = flxcr.Conf(card_id = card_id,
                                                logical_unit = 0,
                                                dma_id = 0,
                                                chunk_trailer_size = 32,
                                                dma_block_size_kb = 4,
                                                dma_memory_size_gb = 4,
                                                numa_id = NUMA_ID,
                                                links_enabled = links_slr0
                                            )
                        )]
        
        if len(links_slr1) > 0:
            modules += [DAQModule(name = "flxcard_1",
                                plugin = "FelixCardReader",
                                conf = flxcr.Conf(card_id = card_id,
                                                    logical_unit = 1,
                                                    dma_id = 0,
                                                    chunk_trailer_size = 32,
                                                    dma_block_size_kb = 4,
                                                    dma_memory_size_gb = 4,
                                                    numa_id = NUMA_ID,
                                                    links_enabled = links_slr1
                                                )
                        )]
        
        # # Queues for card reader 1
        # queues += [
        #     Queue(
        #         f'flxcard_0.output_{idx}',
        #         f"datahandler_{idx}.raw_input",
        #         QUEUE_FRAGMENT_TYPE,
        #         f'{FRONTEND_TYPE}_link_{idx}',
        #         100000 
        #     ) for idx in strms_slr0
        # ]
        # # Queues for card reader 2
        # queues += [
        #     Queue(
        #         f'flxcard_1.output_{idx}',
        #         f"datahandler_{idx}.raw_input",
        #         QUEUE_FRAGMENT_TYPE,
        #         f'{FRONTEND_TYPE}_link_{idx}',
        #         100000 
        #     ) for idx in strms_slr1
        # ]
    
        # Queues for card reader 1
        for s in strms_slr0:
            FRONTEND_TYPE, QUEUE_FRAGMENT_TYPE, _, _, _ = compute_data_types(s)
            queues.append(
                Queue(
                    f'flxcard_0.output_{s.src_id}',
                    f"datahandler_{s.src_id}.raw_input",
                    QUEUE_FRAGMENT_TYPE,
                    f'{FRONTEND_TYPE}_link_{s.src_id}',
                    100000 
                )
            )
        # Queues for card reader 2
        for s in strms_slr1:
            FRONTEND_TYPE, QUEUE_FRAGMENT_TYPE, _, _, _ = compute_data_types(s)
            queues.append(
                Queue(
                    f'flxcard_1.output_{s.src_id}',
                    f"datahandler_{s.src_id}.raw_input",
                    QUEUE_FRAGMENT_TYPE,
                    f'{FRONTEND_TYPE}_link_{s.src_id}',
                    100000 
                )
            )


        return modules, queues


    def create_dpdk_cardreader(
            self,
            # FRONTEND_TYPE: str,
            # QUEUE_FRAGMENT_TYPE: str,
            RU_DESCRIPTOR # ReadoutUnitDescriptor
        ) -> tuple[list, list]:
        """
        Create a DPDK Card Reader (and reader->DHL Queues?)

        [CR]->queues
        """

        cfg = self.ro_cfg

        eth_ru_bldr = NICReceiverBuilder(RU_DESCRIPTOR)

        nic_reader_name = f"nic_reader_{RU_DESCRIPTOR.iface}"

        lcores_id_set = self.get_lcore_config(RU_DESCRIPTOR)

        modules = [DAQModule(
                    name=nic_reader_name,
                    plugin="NICReceiver",
                    conf=eth_ru_bldr.build_conf(
                        eal_arg_list=cfg.dpdk_eal_args,
                        lcores_id_set=lcores_id_set
                        ),
                )]

        # Queues
        # queues = [
        #     Queue(
        #         f"{nic_reader_name}.output_{stream.src_id}",
        #         f"datahandler_{stream.src_id}.raw_input", QUEUE_FRAGMENT_TYPE,
        #         f'{FRONTEND_TYPE}_stream_{stream.src_id}', 100000
        #     ) 
        #     for stream in RU_DESCRIPTOR.streams
        # ]
        
        queues = []
        for stream in RU_DESCRIPTOR.streams:
            FRONTEND_TYPE, QUEUE_FRAGMENT_TYPE, _, _, _ = compute_data_types(stream)
            queues.append(
                Queue(
                    f"{nic_reader_name}.output_{stream.src_id}",
                    f"datahandler_{stream.src_id}.raw_input",
                    QUEUE_FRAGMENT_TYPE,
                    f'{FRONTEND_TYPE}_stream_{stream.src_id}', 100000
                )
            )

        return modules, queues
    

#    def create_pacman_cardreader(
#            self,
#            FRONTEND_TYPE: str,
#            QUEUE_FRAGMENT_TYPE: str,
#            RU_DESCRIPTOR # ReadoutUnitDescriptor
#        ) -> tuple[list, list]:
#        """
#        Create a Pacman Cardeader 
#        """
#
#        reader_name = "nd_reader" 
#        if FRONTEND_TYPE == 'pacman':
#            reader_name = "pacman_source"
#
#        elif FRONTEND_TYPE == 'mpd':
#            reader_name = "mpd_source"
#
#        else:
#            raise RuntimeError(f"Pacman Cardreader for {FRONTEND_TYPE} not supported")
#
#        modules = [DAQModule(
#                    name=reader_name,
#                    plugin="PacmanCardReader",
#                    conf=pcr.Conf(link_confs = [pcr.LinkConfiguration(Source_ID=stream.src_id)
#                                        for stream in RU_DESCRIPTOR.streams],
#                        zmq_receiver_timeout = 10000)
#                )]
#        
#        # Queues
#        queues = [
#            Queue(
#                f"{reader_name}.output_{stream.src_id}",
#                f"datahandler_{stream.src_id}.raw_input", QUEUE_FRAGMENT_TYPE,
#                f'{FRONTEND_TYPE}_stream_{stream.src_id}', 100000
#            ) 
#            for stream in RU_DESCRIPTOR.streams
#        ]
#
        return modules, queues





    ###
    # Create detector datalink handlers
    ###
    def create_det_dhl(
            self,
            # LATENCY_BUFFER_SIZE: int,
            LATENCY_BUFFER_NUMA_AWARE: int,
            LATENCY_BUFFER_ALLOCATION_MODE: int,
            NUMA_ID: int,
            SEND_PARTIAL_FRAGMENTS: bool,
            # RAW_RECORDING_OUTPUT_DIR: str,
            DATA_REQUEST_TIMEOUT: int,
            # FRAGMENT_SEND_TIMEOUT: int,
            # RAW_RECORDING_ENABLED: bool,
            RU_DESCRIPTOR, # ReadoutUnitDescriptor
            # EMULATOR_MODE : bool
    
        ) -> tuple[list, list]:

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
                        plugin = "FDDataLinkHandler", 
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
    # Enable processing in DHLs
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

        
        # Create the TP link handler
        modules = [
        DAQModule(name = f"tp_datahandler_{tpset_sid}",
                    plugin = "FDDataLinkHandler",
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
            # print(dlh)

            # extract source ids
            dro_sid = dlh.conf.readoutmodelconf['source_id']
            # tp_sid = dlh.conf.rawdataprocessorconf.tpset_sourceid

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

        numa_id, latency_numa, latency_preallocate, card_override = self.get_numa_cfg(RU_DESCRIPTOR)
        cfg = self.ro_cfg
        TPG_ENABLED = cfg.enable_tpg
        DATA_FILES = data_file_map
        DATA_REQUEST_TIMEOUT=data_timeout_requests

        # FRONTEND_TYPE, QUEUE_FRAGMENT_TYPE, _, _, _ = compute_data_types(RU_DESCRIPTOR.det_id, self.det_cfg.clock_speed_hz, RU_DESCRIPTOR.kind)
        
        # TPG is automatically disabled for non wib2 frontends
        # TPG_ENABLED = TPG_ENABLED and (FRONTEND_TYPE=='wib2' or FRONTEND_TYPE=='wibeth')
        TPG_ENABLED = TPG_ENABLED and (RU_DESCRIPTOR.det_id == DetID.Subdetector.kHD_TPC.value)
        
        modules = []
        queues = []


        # Create the card readers
        cr_mods = []
        cr_queues = []


        # Create the card readers
        if cfg.use_fake_cards:
            fakecr_mods, fakecr_queues = self.create_fake_cardreader(
                # FRONTEND_TYPE=FRONTEND_TYPE,
                # QUEUE_FRAGMENT_TYPE=QUEUE_FRAGMENT_TYPE,
                DATA_FILES=DATA_FILES,
                RU_DESCRIPTOR=RU_DESCRIPTOR
            )
            cr_mods += fakecr_mods
            cr_queues += fakecr_queues
        else:
            if RU_DESCRIPTOR.kind == 'flx':
                flx_mods, flx_queues = self.create_felix_cardreader(
                    # FRONTEND_TYPE=FRONTEND_TYPE,
                    # QUEUE_FRAGMENT_TYPE=QUEUE_FRAGMENT_TYPE,
                    CARD_ID_OVERRIDE=card_override,
                    NUMA_ID=numa_id,
                    RU_DESCRIPTOR=RU_DESCRIPTOR
                )
                cr_mods += flx_mods
                cr_queues += flx_queues

            elif RU_DESCRIPTOR.kind == 'eth' and RU_DESCRIPTOR.streams[0].parameters.protocol == "udp":
                dpdk_mods, dpdk_queues = self.create_dpdk_cardreader(
                    # FRONTEND_TYPE=FRONTEND_TYPE,
                    # QUEUE_FRAGMENT_TYPE=QUEUE_FRAGMENT_TYPE,
                    RU_DESCRIPTOR=RU_DESCRIPTOR
                )
                cr_mods += dpdk_mods
                cr_queues += dpdk_queues

#            elif RU_DESCRIPTOR.kind == 'eth' and RU_DESCRIPTOR.streams[0].parameters.protocol == "zmq":
#
#                pac_mods, pac_queues = self.create_pacman_cardreader(
#                    FRONTEND_TYPE=FRONTEND_TYPE,
#                    QUEUE_FRAGMENT_TYPE=QUEUE_FRAGMENT_TYPE,
#                    RU_DESCRIPTOR=RU_DESCRIPTOR
#                )
#                cr_mods += pac_mods
#                cr_queues += pac_queues

        modules += cr_mods
        queues += cr_queues

        # Create the data-link handlers
        dlhs_mods, _ = self.create_det_dhl(
            # LATENCY_BUFFER_SIZE=cfg.latency_buffer_size,
            LATENCY_BUFFER_NUMA_AWARE=latency_numa,
            LATENCY_BUFFER_ALLOCATION_MODE=latency_preallocate,
            NUMA_ID=numa_id,
            SEND_PARTIAL_FRAGMENTS=False,
            DATA_REQUEST_TIMEOUT=DATA_REQUEST_TIMEOUT,
            RU_DESCRIPTOR=RU_DESCRIPTOR,

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


        # Kubernetes-specific extensions
        if RU_DESCRIPTOR.kind == 'flx':
            c = card_override if card_override != -1 else RU_DESCRIPTOR.iface
            readout_app.resources = {
                f"felix.cern/flx{c}-data": "1", # requesting FLX{c}
                # "memory": f"{}Gi" # yes bro
            }

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


