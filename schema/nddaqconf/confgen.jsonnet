// This is the configuration schema for nddaqconf_gen
//

local moo = import "moo.jsonnet";


local stypes = import "nddaqconf/types.jsonnet";
local types = moo.oschema.hier(stypes).dunedaq.nddaqconf.types;

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

  nddaqconf_gen: s.record('nddaqconf_gen', [
    s.field('detector',    detectorgen.detector,   default=detectorgen.detector,     doc='Boot parameters'),
    s.field('daq_common',  daqcommongen.daq_common, default=daqcommongen.daq_common,   doc='DAQ common parameters'),
    s.field('boot',        bootgen.boot,    default=bootgen.boot,      doc='Boot parameters'),
    s.field('dataflow',    dataflowgen.dataflow,   default=dataflowgen.dataflow,     doc='Dataflow paramaters'),
    s.field('dqm',         dqmgen.dqm,        default=dqmgen.dqm,          doc='DQM parameters'),
    s.field('hsi',         hsigen.hsi,        default=hsigen.hsi,          doc='HSI parameters'),
    // 03-Jul-2023, KAB, ND
    //s.field('ctb_hsi',     self.ctb_hsi,    default=self.ctb_hsi,      doc='CTB parameters'),
    s.field('readout',     readoutgen.readout,    default=readoutgen.readout,      doc='Readout parameters'),
    s.field('timing',      timinggen.timing,     default=timinggen.timing,       doc='Timing parameters'),
    s.field('trigger',     triggergen.trigger,    default=triggergen.trigger,      doc='Trigger parameters')
    // s.field('dpdk_sender', self.dpdk_sender, default=self.dpdk_sender, doc='DPDK sender parameters'),
  ]),

};

// Output a topologically sorted array.
stypes + sboot + sdetector + sdaqcommon + stiming + shsi + sreadout + strigger + sdataflow + sdqm + moo.oschema.sort_select(cs)
