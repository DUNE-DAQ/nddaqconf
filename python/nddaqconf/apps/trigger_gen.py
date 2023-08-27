# Set moo schema search path
from dunedaq.env import get_moo_model_path
import moo.io
moo.io.default_load_path = get_moo_model_path()

# Load configuration types
import moo.otypes

moo.otypes.load_types('trigger/triggeractivitymaker.jsonnet')
moo.otypes.load_types('trigger/triggercandidatemaker.jsonnet')
moo.otypes.load_types('trigger/customtriggercandidatemaker.jsonnet')
moo.otypes.load_types('trigger/triggerzipper.jsonnet')
moo.otypes.load_types('trigger/moduleleveltrigger.jsonnet')
moo.otypes.load_types('trigger/timingtriggercandidatemaker.jsonnet')
moo.otypes.load_types('trigger/faketpcreatorheartbeatmaker.jsonnet')
moo.otypes.load_types('trigger/txbuffer.jsonnet')
moo.otypes.load_types('readoutlibs/readoutconfig.jsonnet')
moo.otypes.load_types('trigger/tpchannelfilter.jsonnet')

# Import new types
import dunedaq.trigger.triggeractivitymaker as tam
import dunedaq.trigger.triggercandidatemaker as tcm
import dunedaq.trigger.customtriggercandidatemaker as ctcm
import dunedaq.trigger.triggerzipper as tzip
import dunedaq.trigger.moduleleveltrigger as mlt
import dunedaq.trigger.timingtriggercandidatemaker as ttcm
import dunedaq.trigger.faketpcreatorheartbeatmaker as heartbeater
import dunedaq.trigger.txbufferconfig as bufferconf
import dunedaq.readoutlibs.readoutconfig as readoutconf
import dunedaq.trigger.tpchannelfilter as chfilter

from nddaqconf.core.app import App, ModuleGraph
from nddaqconf.core.daqmodule import DAQModule
from nddaqconf.core.conf_utils import Direction, Queue
from daqconf.core.sourceid import TAInfo, TPInfo, TCInfo

from trgdataformats import TriggerBits as trgbs

#FIXME maybe one day, triggeralgs will define schemas... for now allow a dictionary of 4byte int, 4byte floats, and strings
moo.otypes.make_type(schema='number', dtype='i4', name='temp_integer', path='temptypes')
moo.otypes.make_type(schema='number', dtype='f4', name='temp_float', path='temptypes')
moo.otypes.make_type(schema='string', name='temp_string', path='temptypes')
moo.otypes.make_type(schema='boolean', name='temp_boolean', path='temptypes')
def make_moo_record(conf_dict,name,path='temptypes'):
    fields = []
    for pname,pvalue in conf_dict.items():
        typename = None
        if type(pvalue) == int:
            typename = 'temptypes.temp_integer'
        elif type(pvalue) == float:
            typename = 'temptypes.temp_float'
        elif type(pvalue) == str:
            typename = 'temptypes.temp_string'
        elif type(pvalue) == bool:
            typename = 'temptypes.temp_boolean'
        else:
            raise Exception(f'Invalid config argument type: {type(pvalue)}')
        fields.append(dict(name=pname,item=typename))
    moo.otypes.make_type(schema='record', fields=fields, name=name, path=path)

#===============================================================================
def get_buffer_conf(source_id, data_request_timeout):
    return bufferconf.Conf(latencybufferconf = readoutconf.LatencyBufferConf(latency_buffer_size = 10_000_000,
                                                                             source_id = source_id),
                           requesthandlerconf = readoutconf.RequestHandlerConf(latency_buffer_size = 10_000_000,
                                                                               pop_limit_pct = 0.8,
                                                                               pop_size_pct = 0.1,
                                                                               source_id = source_id,
                                                                               det_id = 1,
                                                                               # output_file = f"output_{idx + MIN_LINK}.out",
                                                                               stream_buffer_size = 8388608,
                                                                               request_timeout_ms = data_request_timeout,
                                                                               warn_on_timeout = False,
                                                                               enable_raw_recording = False))

#===============================================================================
### Function that converts trigger word strings to trigger word integers given TC type. Uses functions from trgdataformats.
def get_trigger_bitwords(bitwords):
    # create bitwords flags
    final_bit_flags = []
    for bitword in bitwords:
        tmp_bits = []
        for bit_name in bitword:
            bit_value = trgbs.string_to_fragment_type_value(bit_name)
            if bit_value == 0:
                raise RuntimeError(f'One (or more) of provided MLT trigger bitwords is unknown! Please recheck the names...')
            else:
                tmp_bits.append(bit_value)
        final_bit_flags.append(tmp_bits)
 
    return final_bit_flags
    
#===============================================================================
def get_trigger_app(
        trigger,
        detector,
        daq_common,
        tp_infos,
        trigger_data_request_timeout,
        USE_HSI_INPUT = True,
        USE_CHANNEL_FILTER: bool = True,
        DEBUG=False
    ):

    # Temp variables, To cleanup
    DATA_RATE_SLOWDOWN_FACTOR = daq_common.data_rate_slowdown_factor
    CLOCK_SPEED_HZ = detector.clock_speed_hz
    TP_CONFIG = tp_infos
    TOLERATE_INCOMPLETENESS=trigger.tolerate_incompleteness
    COMPLETENESS_TOLERANCE=trigger.completeness_tolerance
    ACTIVITY_PLUGIN = trigger.trigger_activity_plugin
    ACTIVITY_CONFIG = trigger.trigger_activity_config
    CANDIDATE_PLUGIN = trigger.trigger_candidate_plugin
    CANDIDATE_CONFIG = trigger.trigger_candidate_config
    TTCM_S1=trigger.ttcm_s1
    TTCM_S2=trigger.ttcm_s2
    TRIGGER_WINDOW_BEFORE_TICKS = trigger.trigger_window_before_ticks
    TRIGGER_WINDOW_AFTER_TICKS = trigger.trigger_window_after_ticks
    HSI_TRIGGER_TYPE_PASSTHROUGH = trigger.hsi_trigger_type_passthrough
    MLT_MERGE_OVERLAPPING_TCS = trigger.mlt_merge_overlapping_tcs
    MLT_BUFFER_TIMEOUT = trigger.mlt_buffer_timeout
    MLT_MAX_TD_LENGTH_MS = trigger.mlt_max_td_length_ms
    MLT_SEND_TIMED_OUT_TDS = trigger.mlt_send_timed_out_tds
    MLT_IGNORE_TC = trigger.mlt_ignore_tc
    MLT_USE_READOUT_MAP = trigger.mlt_use_readout_map
    MLT_READOUT_MAP = trigger.mlt_td_readout_map
    MLT_USE_BITWORDS = trigger.mlt_use_bitwords
    MLT_TRIGGER_BITWORDS = trigger.mlt_trigger_bitwords
    USE_CUSTOM_MAKER = trigger.use_custom_maker
    CTCM_TYPES = trigger.ctcm_trigger_types
    CTCM_INTERVAL = trigger.ctcm_trigger_intervals
    CHANNEL_MAP_NAME = detector.tpc_channel_map
    DATA_REQUEST_TIMEOUT=trigger_data_request_timeout
    HOST=trigger.host_trigger
    
    # Generate schema for the maker plugins on the fly in the temptypes module
    make_moo_record(ACTIVITY_CONFIG , 'ActivityConf' , 'temptypes')
    make_moo_record(CANDIDATE_CONFIG, 'CandidateConf', 'temptypes')
    import temptypes

    # How many clock ticks are there in a _wall clock_ second?
    ticks_per_wall_clock_s = CLOCK_SPEED_HZ / DATA_RATE_SLOWDOWN_FACTOR
    
    # Converting certain parameters to ticks instead of ms
    max_td_length_ticks = MLT_MAX_TD_LENGTH_MS * CLOCK_SPEED_HZ / 1000
    
    modules = []
    
    TP_SOURCE_IDS = {}
    TA_SOURCE_IDS = {}
    TC_SOURCE_ID = {}

    for trigger_sid,conf in TP_CONFIG.items():
        if isinstance(conf, TAInfo):
            TA_SOURCE_IDS[conf.region_id] = {"source_id": trigger_sid, "conf": conf}
        elif isinstance(conf, TCInfo):
            TC_SOURCE_ID = {"source_id": trigger_sid, "conf": conf}
        elif isinstance(conf, TPInfo):
            TP_SOURCE_IDS[trigger_sid] = conf
        
    # We always have a TC buffer even when there are no TPs, because we want to put the timing TC in the output file
    modules += [DAQModule(name = 'tc_buf',
                          plugin = 'TCBuffer',
                          conf = get_buffer_conf(TC_SOURCE_ID["source_id"], DATA_REQUEST_TIMEOUT))]
    if USE_HSI_INPUT:
        modules += [DAQModule(name = 'tctee_ttcm',
                         plugin = 'TCTee')]

    
    if len(TP_SOURCE_IDS) > 0:        
        config_tcm =  tcm.Conf(candidate_maker=CANDIDATE_PLUGIN,
                               candidate_maker_config=temptypes.CandidateConf(**CANDIDATE_CONFIG))

        # (PAR 2022-06-09) The max_latency_ms here should be kept
        # larger than the corresponding value in the upstream
        # TPZippers. See comment below for more details
        modules += [DAQModule(name = 'tazipper',
                              plugin = 'TAZipper',
                              conf = tzip.ConfParams(cardinality=len(TA_SOURCE_IDS),
                                                     max_latency_ms=1000,
                                                     element_id=TC_SOURCE_ID["source_id"])),
                    DAQModule(name = 'tcm',
                              plugin = 'TriggerCandidateMaker',
                              conf = config_tcm),

                    DAQModule(name = 'tctee_chain',
                              plugin = 'TCTee'),
                    ]

        # Make one heartbeatmaker per link
        for tp_sid in TP_SOURCE_IDS:
            link_id = f'tplink{tp_sid}'

            if USE_CHANNEL_FILTER:
                modules += [DAQModule(name = f'channelfilter_{link_id}',
                                      plugin = 'TPChannelFilter',
                                      conf = chfilter.Conf(channel_map_name=CHANNEL_MAP_NAME,
                                                           keep_collection=True,
                                                           keep_induction=True))]
            modules += [DAQModule(name = f'tpsettee_{link_id}',
                                  plugin = 'TPSetTee'),
#                        DAQModule(name = f'heartbeatmaker_{link_id}',
#                                  plugin = 'FakeTPCreatorHeartbeatMaker',
#                                  conf = heartbeater.Conf(heartbeat_interval=ticks_per_wall_clock_s//100))]
                       ]
            # 1 buffer per TPG channel
            modules += [DAQModule(name = f'buf_{link_id}',
                                  plugin = 'TPBuffer',
                                  conf = bufferconf.Conf(latencybufferconf = readoutconf.LatencyBufferConf(latency_buffer_size = 1_000_000,
                                                                                                           source_id = tp_sid),
                                                         requesthandlerconf = readoutconf.RequestHandlerConf(latency_buffer_size = 1_000_000,
                                                                                                             pop_limit_pct = 0.8,
                                                                                                             pop_size_pct = 0.1,
                                                                                                             source_id = tp_sid,
                                                                                                             det_id = 1,
                                                                                                             # output_file = f"output_{idx + MIN_LINK}.out",
                                                                                                             stream_buffer_size = 8388608,
                                                                                                             request_timeout_ms = DATA_REQUEST_TIMEOUT,
                                                                                                             enable_raw_recording = False)))]

        for region_id, ta_conf in TA_SOURCE_IDS.items():
                # (PAR 2022-06-09) The max_latency_ms here should be
                # kept smaller than the corresponding value in the
                # downstream TAZipper. The reason is to avoid tardy
                # sets at run stop, which are caused as follows:
                #
                # 1. The TPZipper receives its last input TPSets from
                # multiple links. In general, the last time received
                # from each link will be different (because the
                # upstream readout senders don't all stop
                # simultaneously). So there will be sets on one link
                # that don't have time-matched sets on the other
                # links. TPZipper sends these unmatched sets out after
                # TPZipper's max_latency_ms milliseconds have passed,
                # so these sets are delayed by
                # "tpzipper.max_latency_ms"
                #
                # 2. Meanwhile, the TAZipper has also stopped
                # receiving data from all but one of the readout units
                # (which are stopped sequentially), and so is in a
                # similar situation. Once tazipper.max_latency_ms has
                # passed, it sends out the sets from the remaining
                # live input, and "catches up" with the current time
                #
                # So, if tpzipper.max_latency_ms >
                # tazipper.max_latency_ms, the TA inputs made from the
                # delayed TPSets will certainly arrive at the TAZipper
                # after it has caught up to the current time, and be
                # tardy. If the tpzipper.max_latency_ms ==
                # tazipper.max_latency_ms, then depending on scheduler
                # delays etc, the delayed TPSets's TAs _may_ arrive at
                # the TAZipper tardily. With tpzipper.max_latency_ms <
                # tazipper.max_latency_ms, everything should be fine.
                modules += [
                            #DAQModule(name = f'zip_{region_id}',
                            #          plugin = 'TPZipper',
                            #                  conf = tzip.ConfParams(cardinality=len(TP_SOURCE_IDS)/len(TA_SOURCE_IDS),
                            #                                         max_latency_ms=100,
                            #                                         element_id=ta_conf["source_id"],
                            #                                         # Need to find out where to specify these"
                            #                                         tolerate_incompleteness=TOLERATE_INCOMPLETENESS,
                            #                                         completeness_tolerance=COMPLETENESS_TOLERANCE)),
                                    
                            DAQModule(name = f'tam_{region_id}',
                                      plugin = 'TriggerActivityMaker',
                                      conf = tam.Conf(activity_maker=ACTIVITY_PLUGIN,
                                                      geoid_element=region_id,  # 2022-02-02 PL: Same comment as above
                                                      window_time=10000,  # GLM: TO BE REMOVED 
                                                      buffer_time=10*ticks_per_wall_clock_s//1000, # 10 wall-clock ms
                                                      activity_maker_config=temptypes.ActivityConf(**ACTIVITY_CONFIG))),

                            DAQModule(name = f'tasettee_region_{region_id}',
                                      plugin = "TASetTee"),
                            
                            DAQModule(name = f'ta_buf_region_{region_id}',
                                      plugin = 'TABuffer',
                                      # PAR 2022-04-20 Not sure what to set the element id to so it doesn't collide with the region/element used by TP buffers. Make it some big number that shouldn't already be used by the TP buffer
                                      conf = bufferconf.Conf(latencybufferconf = readoutconf.LatencyBufferConf(latency_buffer_size = 100_000,
                                                                                                               source_id = ta_conf["source_id"]),
                                                             requesthandlerconf = readoutconf.RequestHandlerConf(latency_buffer_size = 100_000,
                                                                                                                 pop_limit_pct = 0.8,
                                                                                                                 pop_size_pct = 0.1,
                                                                                                                 source_id = ta_conf["source_id"],
                                                                                                                 det_id = 1,
                                                                                                                 # output_file = f"output_{idx + MIN_LINK}.out",
                                                                                                                 stream_buffer_size = 8388608,
                                                                                                                 request_timeout_ms = DATA_REQUEST_TIMEOUT,
                                                                                                                 enable_raw_recording = False)))]

        
    if USE_HSI_INPUT:
        modules += [DAQModule(name = 'ttcm',
                          plugin = 'TimingTriggerCandidateMaker',
                          conf=ttcm.Conf(s0=ttcm.map_t(signal_type=0,
                                                       time_before=TRIGGER_WINDOW_BEFORE_TICKS,
                                                       time_after=TRIGGER_WINDOW_AFTER_TICKS),
                                         s1=ttcm.map_t(signal_type=TTCM_S1,
                                                       time_before=TRIGGER_WINDOW_BEFORE_TICKS,
                                                       time_after=TRIGGER_WINDOW_AFTER_TICKS),
                                         s2=ttcm.map_t(signal_type=TTCM_S2,
                                                       time_before=TRIGGER_WINDOW_BEFORE_TICKS,
                                                       time_after=TRIGGER_WINDOW_AFTER_TICKS),
                     hsi_trigger_type_passthrough=HSI_TRIGGER_TYPE_PASSTHROUGH))]

    if USE_CUSTOM_MAKER:
        if (len(CTCM_TYPES) != len(CTCM_INTERVAL)):
            raise RuntimeError(f'CTCM requires same size of types and intervals!')
        modules += [DAQModule(name = 'ctcm',
                       plugin = 'CustomTriggerCandidateMaker',
                       conf=ctcm.Conf(trigger_types=CTCM_TYPES,
                       trigger_intervals=CTCM_INTERVAL,
                       clock_frequency_hz=CLOCK_SPEED_HZ,
                       timestamp_method="kSystemClock"))]

    ### get trigger bitwords for mlt
    MLT_TRIGGER_FLAGS = get_trigger_bitwords(MLT_TRIGGER_BITWORDS)
    
    # We need to populate the list of links based on the fragment
    # producers available in the system. This is a bit of a
    # chicken-and-egg problem, because the trigger app itself creates
    # fragment producers (see below). Eventually when the MLT is its
    # own process, this problem will probably go away, but for now, we
    # leave the list of links here blank, and replace it in
    # util.connect_fragment_producers
    modules += [DAQModule(name = 'mlt',
                          plugin = 'ModuleLevelTrigger',
                          conf=mlt.ConfParams(links=[],  # To be updated later - see comment above
                                              hsi_trigger_type_passthrough=HSI_TRIGGER_TYPE_PASSTHROUGH,
                                              merge_overlapping_tcs=MLT_MERGE_OVERLAPPING_TCS,
                                              buffer_timeout=MLT_BUFFER_TIMEOUT,
                                              td_out_of_timeout=MLT_SEND_TIMED_OUT_TDS,
                                              ignore_tc=MLT_IGNORE_TC,
                                              td_readout_limit=max_td_length_ticks,
                                              use_readout_map=MLT_USE_READOUT_MAP,
                                              td_readout_map=MLT_READOUT_MAP,
					      use_bitwords=MLT_USE_BITWORDS,
					      trigger_bitwords=MLT_TRIGGER_FLAGS))]

    mgraph = ModuleGraph(modules)

    if USE_HSI_INPUT:
        mgraph.connect_modules("ttcm.output",         "tctee_ttcm.input",             "TriggerCandidate", "ttcm_input", size_hint=1000)
        mgraph.connect_modules("tctee_ttcm.output1",  "mlt.trigger_candidate_input", "TriggerCandidate","tcs_to_mlt", size_hint=1000)
        mgraph.connect_modules("tctee_ttcm.output2",  "tc_buf.tc_source",             "TriggerCandidate","tcs_to_buf", size_hint=1000)
        mgraph.add_endpoint("hsievents", "ttcm.hsi_input", "HSIEvent", Direction.IN)

    if USE_CUSTOM_MAKER:
        mgraph.connect_modules("ctcm.trigger_candidate_sink", "mlt.trigger_candidate_source", "TriggerCandidate", "tcs_to_mlt", size_hint=1000)

    if len(TP_SOURCE_IDS) > 0:
        mgraph.connect_modules("tazipper.output", "tcm.input", data_type="TASet", size_hint=1000)

        for tp_sid,tp_conf in TP_SOURCE_IDS.items():
            link_id = f'tplink{tp_sid}'
            if USE_CHANNEL_FILTER:
                mgraph.connect_modules(f'channelfilter_{link_id}.tpset_sink', f'tpsettee_{link_id}.input', data_type="TPSet", size_hint=1000)

            #mgraph.connect_modules(f'tpsettee_{link_id}.output1', f'heartbeatmaker_{link_id}.tpset_source', data_type="TPSet", size_hint=1000)
            mgraph.connect_modules(f'tpsettee_{link_id}.output1', f'tam_{tp_conf.region_id}.input', data_type="TPSet", size_hint=1000)
            mgraph.connect_modules(f'tpsettee_{link_id}.output2', f'buf_{link_id}.tpset_source',data_type="TPSet", size_hint=1000)

            #mgraph.connect_modules(f'heartbeatmaker_{link_id}.tpset_sink', f"zip_{tp_conf.region_id}.input","TPSet", f"{tp_conf.region_id}_tpset_q", size_hint=1000)

        #for region_id in TA_SOURCE_IDS.keys():
        #    mgraph.connect_modules(f'zip_{region_id}.output', f'tam_{region_id}.input', "TPSet", size_hint=1000)
        # Use connect_modules to connect up the Tees to the buffers/MLT,
        # as manually adding Queues doesn't give the desired behaviour
        mgraph.connect_modules("tcm.output",          "tctee_chain.input",           "TriggerCandidate", "chain_input", size_hint=1000)
        mgraph.connect_modules("tctee_chain.output1", "mlt.trigger_candidate_input","TriggerCandidate", "tcs_to_mlt",  size_hint=1000)
        mgraph.connect_modules("tctee_chain.output2", "tc_buf.tc_source",             "TriggerCandidate","tcs_to_buf",  size_hint=1000)


        for region_id in TA_SOURCE_IDS.keys():
            mgraph.connect_modules(f'tam_{region_id}.output',              f'tasettee_region_{region_id}.input',     data_type="TASet", size_hint=1000)
            mgraph.connect_modules(f'tasettee_region_{region_id}.output1', f'tazipper.input', queue_name="tas_to_tazipper",     data_type="TASet", size_hint=1000)
            mgraph.connect_modules(f'tasettee_region_{region_id}.output2', f'ta_buf_region_{region_id}.taset_source',data_type="TASet", size_hint=1000)

    mgraph.add_endpoint("td_to_dfo", "mlt.td_output", "TriggerDecision", Direction.OUT, toposort=True)
    mgraph.add_endpoint("df_busy_signal", "mlt.dfo_inhibit_input", "TriggerInhibit", Direction.IN)

    mgraph.add_fragment_producer(id=TC_SOURCE_ID["source_id"], subsystem="Trigger",
                                 requests_in="tc_buf.data_request_source",
                                 fragments_out="tc_buf.fragment_sink")

    if len(TP_SOURCE_IDS) > 0:
        for tp_sid,tp_conf in TP_SOURCE_IDS.items():
                # 1 buffer per link
                link_id=f"tplink{tp_sid}"
                buf_name=f'buf_{link_id}'
                ru_sid = f'tplink{tp_conf.tp_ru_sid}'
              
                if USE_CHANNEL_FILTER:
                    mgraph.add_endpoint(f"tpsets_{ru_sid}", f"channelfilter_{link_id}.tpset_source", "TPSet", Direction.IN, is_pubsub=True)
                else:
                    mgraph.add_endpoint(f"tpsets_{ru_sid}", f'tpsettee_{link_id}.input', "TPSet",            Direction.IN, is_pubsub=True)
                    

                mgraph.add_fragment_producer(id=tp_sid, subsystem="Trigger",
                                             requests_in=f"{buf_name}.data_request_source",
                                             fragments_out=f"{buf_name}.fragment_sink")

        for region_id, ta_conf in TA_SOURCE_IDS.items():
            buf_name = f'ta_buf_region_{region_id}'
            mgraph.add_fragment_producer(id=ta_conf["source_id"], subsystem="Trigger",
                                         requests_in=f"{buf_name}.data_request_source",
                                         fragments_out=f"{buf_name}.fragment_sink")


    trigger_app = App(modulegraph=mgraph, host=HOST, name='TriggerApp')
    
    return trigger_app

