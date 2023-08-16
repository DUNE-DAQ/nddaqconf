// This is the configuration schema for nddaqconf_multiru_gen
//

local moo = import "moo.jsonnet";

local stypes = import "nddaqconf/types.jsonnet";
local types = moo.oschema.hier(stypes).dunedaq.nddaqconf.types;

local s = moo.oschema.schema("dunedaq.nddaqconf.triggergen");
local nc = moo.oschema.numeric_constraints;
// A temporary schema construction context.
local cs = {
  tc_type:         s.number(   "TCType",        "i4", nc(minimum=0, maximum=9), doc="Number representing TC type. Currently ranging from 0 to 9"),
  tc_types:        s.sequence( "TCTypes",       self.tc_type, doc="List of TC types"),
  tc_interval:     s.number(   "TCInterval",    "i8", nc(minimum=1, maximum=30000000000), doc="The intervals between TCs that are inserted into MLT by CTCM, in clock ticks"),
  tc_intervals:    s.sequence( "TCIntervals",   self.tc_interval, doc="List of TC intervals used by CTCM"),
  readout_time:    s.number(   "ROTime",        "i8", doc="A readout time in ticks"),
  bitword:	   s.string(   "Bitword",       doc="A string representing the TC type name, to be set in the trigger bitword."),
  bitword_list:    s.sequence( "BitwordList",   self.bitword, doc="A sequence of bitword (TC type bits) forming a bitword."),
  bitwords:        s.sequence( "Bitwords",      self.bitword_list, doc="List of bitwords to use when forming trigger decisions in MLT" ),

  trigger_algo_config: s.record("trigger_algo_config", [
    s.field("prescale", types.count, default=100),
    s.field("window_length", types.count, default=10000),
    s.field("adjacency_threshold", types.count, default=6),
    s.field("adj_tolerance", types.count, default=4),
    s.field("trigger_on_adc", types.flag, default=false),
    s.field("trigger_on_n_channels", types.flag, default=false),
    s.field("trigger_on_adjacency", types.flag, default=true),
    s.field("adc_threshold", types.count, default=10000),
    s.field("n_channels_threshold", types.count, default=8),
    s.field("print_tp_info", types.flag, default=false),
  ]),

  c0_readout: s.record("c0_readout", [
    s.field("candidate_type", self.tc_type,      default=0,     doc="The TC type, 0=Unknown"),
    s.field("time_before",    self.readout_time, default=1000, doc="Time to readout before TC time [ticks]"),
    s.field("time_after",     self.readout_time, default=1001, doc="Time to readout after TC time [ticks]"),
  ]),
  c1_readout: s.record("c1_readout", [
    s.field("candidate_type", self.tc_type,      default=1,     doc="The TC type, 1=Timing"),
    s.field("time_before",    self.readout_time, default=1000, doc="Time to readout before TC time [ticks]"),
    s.field("time_after",     self.readout_time, default=1001, doc="Time to readout after TC time [ticks]"),
  ]),
  c2_readout: s.record("c2_readout", [
    s.field("candidate_type", self.tc_type,      default=2,     doc="The TC type, 2=TPCLowE"),
    s.field("time_before",    self.readout_time, default=1000, doc="Time to readout before TC time [ticks]"),
    s.field("time_after",     self.readout_time, default=1001, doc="Time to readout after TC time [ticks]"),
  ]),
  c3_readout: s.record("c3_readout", [
    s.field("candidate_type", self.tc_type,      default=3,     doc="The TC type, 3=Supernova"),
    s.field("time_before",    self.readout_time, default=1000, doc="Time to readout before TC time [ticks]"),
    s.field("time_after",     self.readout_time, default=1001, doc="Time to readout after TC time [ticks]"),
  ]),
  c4_readout: s.record("c4_readout", [
    s.field("candidate_type", self.tc_type,      default=4,     doc="The TC type, 4=Random"),
    s.field("time_before",    self.readout_time, default=1000, doc="Time to readout before TC time [ticks]"),
    s.field("time_after",     self.readout_time, default=1001, doc="Time to readout after TC time [ticks]"),
  ]),
  c5_readout: s.record("c5_readout", [
    s.field("candidate_type", self.tc_type,      default=5,     doc="The TC type, 5=Prescale"),
    s.field("time_before",    self.readout_time, default=1000, doc="Time to readout before TC time [ticks]"),
    s.field("time_after",     self.readout_time, default=1001, doc="Time to readout after TC time [ticks]"),
  ]),
  c6_readout: s.record("c6_readout", [
    s.field("candidate_type", self.tc_type,      default=6,     doc="The TC type, 6=ADCSimpleWindow"),
    s.field("time_before",    self.readout_time, default=1000, doc="Time to readout before TC time [ticks]"),
    s.field("time_after",     self.readout_time, default=1001, doc="Time to readout after TC time [ticks]"),
  ]),
  c7_readout: s.record("c7_readout", [
    s.field("candidate_type", self.tc_type,      default=7,     doc="The TC type, 7=HorizontalMuon"),
    s.field("time_before",    self.readout_time, default=1000, doc="Time to readout before TC time [ticks]"),
    s.field("time_after",     self.readout_time, default=1001, doc="Time to readout after TC time [ticks]"),
  ]),
  c8_readout: s.record("c8_readout", [
    s.field("candidate_type", self.tc_type,      default=8,     doc="The TC type, 8=MichelElectron"),
    s.field("time_before",    self.readout_time, default=1000, doc="Time to readout before TC time [ticks]"),
    s.field("time_after",     self.readout_time, default=1001, doc="Time to readout after TC time [ticks]"),
  ]),
  c9_readout: s.record("c9_readout", [
    s.field("candidate_type", self.tc_type,      default=9,     doc="The TC type, 9=LowEnergyEvent"),
    s.field("time_before",    self.readout_time, default=1000, doc="Time to readout before TC time [ticks]"),
    s.field("time_after",     self.readout_time, default=1001, doc="Time to readout after TC time [ticks]"),
  ]),

  tc_readout_map: s.record("tc_readout_map", [
    s.field("c0", self.c0_readout, default=self.c0_readout, doc="TC readout for TC type 0"),
    s.field("c1", self.c1_readout, default=self.c1_readout, doc="TC readout for TC type 1"),
    s.field("c2", self.c2_readout, default=self.c2_readout, doc="TC readout for TC type 2"),
    s.field("c3", self.c3_readout, default=self.c3_readout, doc="TC readout for TC type 3"),
    s.field("c4", self.c4_readout, default=self.c4_readout, doc="TC readout for TC type 4"),
    s.field("c5", self.c5_readout, default=self.c5_readout, doc="TC readout for TC type 5"),
    s.field("c6", self.c6_readout, default=self.c6_readout, doc="TC readout for TC type 6"),
    s.field("c7", self.c7_readout, default=self.c7_readout, doc="TC readout for TC type 7"),
    s.field("c8", self.c8_readout, default=self.c8_readout, doc="TC readout for TC type 8"),
    s.field("c9", self.c9_readout, default=self.c9_readout, doc="TC readout for TC type 9"),
  ]),

  trigger: s.record("trigger",[
    // s.field( "trigger_rate_hz", types.rate, default=1.0, doc='Fake HSI only: rate at which fake HSIEvents are sent. 0 - disable HSIEvent generation. Former -t'),
    s.field( "trigger_window_before_ticks",types.count, default=1000, doc="Trigger window before marker. Former -b"),
    s.field( "trigger_window_after_ticks", types.count, default=1000, doc="Trigger window after marker. Former -a"),
    s.field( "host_trigger", types.host, default='localhost', doc='Host to run the trigger app on'),
    // s.field( "host_tpw", types.host, default='localhost', doc='Host to run the TPWriter app on'),
    # trigger options
    s.field( "completeness_tolerance", types.count, default=1, doc="Maximum number of inactive queues we will tolerate."),
    s.field( "tolerate_incompleteness", types.flag, default=false, doc="Flag to tell trigger to tolerate inactive queues."),
    s.field( "ttcm_s1", types.count,default=1, doc="Timing trigger candidate maker accepted HSI signal ID 1"),
    s.field( "ttcm_s2", types.count, default=2, doc="Timing trigger candidate maker accepted HSI signal ID 2"),
    s.field( "trigger_activity_plugin", types.string, default='TriggerActivityMakerPrescalePlugin', doc="Trigger activity algorithm plugin"),
    s.field( "trigger_activity_config", self.trigger_algo_config, default=self.trigger_algo_config,doc="Trigger activity algorithm config (string containing python dictionary)"),
    s.field( "trigger_candidate_plugin", types.string, default='TriggerCandidateMakerPrescalePlugin', doc="Trigger candidate algorithm plugin"),
    s.field( "trigger_candidate_config", self.trigger_algo_config, default=self.trigger_algo_config, doc="Trigger candidate algorithm config (string containing python dictionary)"),
    s.field( "hsi_trigger_type_passthrough", types.flag, default=false, doc="Option to override trigger type in the MLT"),
    // s.field( "enable_tpset_writing", types.flag, default=false, doc="Enable the writing of TPs to disk (only works with enable_tpg or enable_firmware_tpg)"),
    // s.field( "tpset_output_path", types.path,default='.', doc="Output directory for TPSet stream files"),
    // s.field( "tpset_output_file_size",types.count, default=4*1024*1024*1024, doc="The size threshold when TPSet stream files are closed (in bytes)"),
    // s.field( "tpg_channel_map", self.tpg_channel_map, default="ProtoDUNESP1ChannelMap", doc="Channel map for TPG"),
    s.field( "mlt_merge_overlapping_tcs", types.flag, default=true, doc="Option to turn off merging of overlapping TCs when forming TDs in MLT"),
    s.field( "mlt_buffer_timeout", types.count, default=100, doc="Timeout (buffer) to wait for new overlapping TCs before sending TD"),
    s.field( "mlt_send_timed_out_tds", types.flag, default=true, doc="Option to drop TD if TC comes out of timeout window"),
    s.field( "mlt_max_td_length_ms", types.count, default=1000, doc="Maximum allowed time length [ms] for a readout window of a single TD"),
    s.field( "mlt_ignore_tc", self.tc_types, default=[], doc="Optional list of TC types to be ignored in MLT"),
    s.field( "mlt_use_readout_map", types.flag, default=false, doc="Option to use custom readout map in MLT"),
    s.field( "mlt_td_readout_map", self.tc_readout_map, default=self.tc_readout_map, doc="The readout windows assigned to TDs in MLT, based on TC type."),
    s.field( "mlt_use_bitwords", types.flag, default=false, doc="Option to use bitwords (ie trigger types, coincidences) when forming trigger decisions in MLT" ),
    s.field( "mlt_trigger_bitwords", self.bitwords, default=[], doc="Optional dictionary of bitwords to use when forming trigger decisions in MLT" ),    
    s.field( "use_custom_maker", types.flag, default=false, doc="Option to use a Custom Trigger Candidate Maker (plugin)"),
    s.field( "ctcm_trigger_types", self.tc_types, default=[4], doc="Optional list of TC types to be used by the Custom Trigger Candidate Maker (plugin)"),
    s.field( "ctcm_trigger_intervals", self.tc_intervals, default=[10000000], doc="Optional list of intervals (clock ticks) for the TC types to be used by the Custom Trigger Candidate Maker (plugin)"),
  ]),

};

stypes + moo.oschema.sort_select(cs)
