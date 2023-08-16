// This is the configuration schema for nddaqconf_multiru_gen
//

local moo = import "moo.jsonnet";


local stypes = import "nddaqconf/types.jsonnet";
local types = moo.oschema.hier(stypes).dunedaq.nddaqconf.types;

local sctb = import "ctbmodules/ctbmodule.jsonnet";
local ctbmodule = moo.oschema.hier(sctb).dunedaq.ctbmodules.ctbmodule;

local sboot = import "nddaqconf/bootgen.jsonnet";
local bootgen = moo.oschema.hier(sboot).dunedaq.nddaqconf.bootgen;

local sdetector = import "nddaqconf/detectorgen.jsonnet";
local detectorgen = moo.oschema.hier(sdetector).dunedaq.nddaqconf.detectorgen;

local sdaqcommon = import "nddaqconf/daqcommongen.jsonnet";
local daqcommongen = moo.oschema.hier(sdaqcommon).dunedaq.nddaqconf.daqcommongen;

local stiming = import "nddaqconf/timinggen.jsonnet";
local timinggen = moo.oschema.hier(stiming).dunedaq.nddaqconf.timinggen;

local shsi = import "nddaqconf/hsigen.jsonnet";
local hsigen = moo.oschema.hier(shsi).dunedaq.nddaqconf.hsigen;

local sreadout = import "nddaqconf/readoutgen.jsonnet";
local readoutgen = moo.oschema.hier(sreadout).dunedaq.nddaqconf.readoutgen;

local strigger = import "nddaqconf/triggergen.jsonnet";
local triggergen = moo.oschema.hier(strigger).dunedaq.nddaqconf.triggergen;

local sdataflow = import "nddaqconf/dataflowgen.jsonnet";
local dataflowgen = moo.oschema.hier(sdataflow).dunedaq.nddaqconf.dataflowgen;

local sdqm = import "nddaqconf/dqmgen.jsonnet";
local dqmgen = moo.oschema.hier(sdqm).dunedaq.nddaqconf.dqmgen;

local s = moo.oschema.schema("dunedaq.nddaqconf.confgen");
local nc = moo.oschema.numeric_constraints;
// A temporary schema construction context.

local cs = {
  // port:            s.number(   "Port", "i4", doc="A TCP/IP port number"),
  // freq:            s.number(   "Frequency", "u4", doc="A frequency"),
  // rate:            s.number(   "Rate", "f8", doc="A rate as a double"),
  // count:           s.number(   "count", "i8", doc="A count of things"),
  // three_choice:    s.number(   "threechoice", "i8", nc(minimum=0, exclusiveMaximum=3), doc="A choice between 0, 1, or 2"),
  // flag:            s.boolean(  "Flag", doc="Parameter that can be used to enable or disable functionality"),
  // monitoring_dest: s.enum(     "MonitoringDest", ["local", "cern", "pocket"]),
  // path:            s.string(   "Path", doc="Location on a filesystem"),
  // paths:           s.sequence( "Paths",         self.path, doc="Multiple paths"),
  // host:            s.string(   "Host",          moo.re.dnshost, doc="A hostname"),
  // hosts:           s.sequence( "Hosts",         self.host, "Multiple hosts"),
  // string:          s.string(   "Str",           doc="Generic string"),
  // strings:         s.sequence( "Strings",  self.string, doc="List of strings"),

  // tpg_channel_map: s.enum(     "TPGChannelMap", ["VDColdboxChannelMap", "ProtoDUNESP1ChannelMap", "PD2HDChannelMap", "HDColdboxChannelMap"]),
  // dqm_channel_map: s.enum(     "DQMChannelMap", ['HD', 'VD', 'PD2HD', 'HDCB']),
  // dqm_params:      s.sequence( "DQMParams",     self.count, doc="Parameters for DQM (fixme)"),
  // tc_types:        s.sequence( "TCTypes",       self.count, doc="List of TC types"),
  // tc_type:         s.number(   "TCType",        "i4", nc(minimum=0, maximum=9), doc="Number representing TC type. Currently ranging from 0 to 9"),
  // tc_interval:     s.number(   "TCInterval",    "i8", nc(minimum=1, maximum=30000000000), doc="The intervals between TCs that are inserted into MLT by CTCM, in clock ticks"),
  // tc_intervals:    s.sequence( "TCIntervals",   self.tc_interval, doc="List of TC intervals used by CTCM"),
  // readout_time:    s.number(   "ROTime",        "i8", doc="A readout time in ticks"),
  // channel_list:    s.sequence( "ChannelList",   self.count, doc="List of offline channels to be masked out from the TPHandler"),
  // tpg_algo_choice: s.enum(     "TPGAlgoChoice", ["SimpleThreshold", "AbsRS"], doc="Trigger algorithm choice"),
  // pm_choice:       s.enum(     "PMChoice", ["k8s", "ssh"], doc="Process Manager choice: ssh or Kubernetes"),
  // rte_choice:      s.enum(     "RTEChoice", ["auto", "release", "devarea"], doc="Kubernetes DAQ application RTE choice"),
  

  ctb_hsi: s.record("ctb_hsi", [
    # ctb options
    s.field( "use_ctb_hsi", types.flag, default=false, doc='Flag to control whether CTB HSI config is generated. Default is false'),
    s.field( "host_ctb_hsi", types.host, default='localhost', doc='Host to run the HSI app on'),
    s.field( "hlt_triggers", ctbmodule.Hlt_trigger_seq, []),
    s.field( "beam_llt_triggers", ctbmodule.Llt_mask_trigger_seq, []),
    s.field( "crt_llt_triggers", ctbmodule.Llt_count_trigger_seq, []),
    s.field( "pds_llt_triggers", ctbmodule.Llt_count_trigger_seq, []),
    s.field( "fake_trig_1", ctbmodule.Randomtrigger, ctbmodule.Randomtrigger),
    s.field( "fake_trig_2", ctbmodule.Randomtrigger, ctbmodule.Randomtrigger)
  ]),


  nddaqconf_multiru_gen: s.record('nddaqconf_multiru_gen', [
    s.field('detector',    detectorgen.detector,   default=detectorgen.detector,     doc='Boot parameters'),
    s.field('daq_common',  daqcommongen.daq_common, default=daqcommongen.daq_common,   doc='DAQ common parameters'),
    s.field('boot',        bootgen.boot,    default=bootgen.boot,      doc='Boot parameters'),
    s.field('dataflow',    dataflowgen.dataflow,   default=dataflowgen.dataflow,     doc='Dataflow paramaters'),
    s.field('dqm',         dqmgen.dqm,        default=dqmgen.dqm,          doc='DQM parameters'),
    s.field('hsi',         hsigen.hsi,        default=hsigen.hsi,          doc='HSI parameters'),
    s.field('ctb_hsi',     self.ctb_hsi,    default=self.ctb_hsi,      doc='CTB parameters'),
    s.field('readout',     readoutgen.readout,    default=readoutgen.readout,      doc='Readout parameters'),
    s.field('timing',      timinggen.timing,     default=timinggen.timing,       doc='Timing parameters'),
    s.field('trigger',     triggergen.trigger,    default=triggergen.trigger,      doc='Trigger parameters')
    // s.field('dpdk_sender', self.dpdk_sender, default=self.dpdk_sender, doc='DPDK sender parameters'),
  ]),

};

// Output a topologically sorted array.
stypes + sboot + sdetector + sdaqcommon + stiming + shsi + sreadout + strigger + sdataflow + sdqm + sctb + moo.oschema.sort_select(cs)
