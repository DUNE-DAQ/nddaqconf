// This is the configuration schema for nddaqconf_gen
//

local moo = import "moo.jsonnet";


local stypes = import "daqconf/types.jsonnet";
local types = moo.oschema.hier(stypes).dunedaq.daqconf.types;

local sboot = import "daqconf/bootgen.jsonnet";
local bootgen = moo.oschema.hier(sboot).dunedaq.daqconf.bootgen;

local sdetector = import "daqconf/detectorgen.jsonnet";
local detectorgen = moo.oschema.hier(sdetector).dunedaq.daqconf.detectorgen;

local sdaqcommon = import "daqconf/daqcommongen.jsonnet";
local daqcommongen = moo.oschema.hier(sdaqcommon).dunedaq.daqconf.daqcommongen;

local stiming = import "daqconf/timinggen.jsonnet";
local timinggen = moo.oschema.hier(stiming).dunedaq.daqconf.timinggen;

local shsi = import "daqconf/hsigen.jsonnet";
local hsigen = moo.oschema.hier(shsi).dunedaq.daqconf.hsigen;

local sreadout = import "nddaqconf/readoutgen.jsonnet";
local readoutgen = moo.oschema.hier(sreadout).dunedaq.nddaqconf.readoutgen;

local strigger = import "daqconf/triggergen.jsonnet";
local triggergen = moo.oschema.hier(strigger).dunedaq.daqconf.triggergen;

local sdataflow = import "daqconf/dataflowgen.jsonnet";
local dataflowgen = moo.oschema.hier(sdataflow).dunedaq.daqconf.dataflowgen;

local sdqm = import "daqconf/dqmgen.jsonnet";
local dqmgen = moo.oschema.hier(sdqm).dunedaq.daqconf.dqmgen;

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
    s.field('readout',     readoutgen.readout,    default=readoutgen.readout,      doc='Readout parameters'),
    s.field('timing',      timinggen.timing,     default=timinggen.timing,       doc='Timing parameters'),
    s.field('trigger',     triggergen.trigger,    default=triggergen.trigger,      doc='Trigger parameters')
  ]),

};

// Output a topologically sorted array.
stypes + sboot + sdetector + sdaqcommon + stiming + shsi + sreadout + strigger + sdataflow + sdqm + moo.oschema.sort_select(cs)
