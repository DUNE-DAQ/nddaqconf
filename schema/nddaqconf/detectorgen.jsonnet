// This is the configuration schema for nddaqconf_gen
//

local moo = import "moo.jsonnet";

local stypes = import "nddaqconf/types.jsonnet";
local types = moo.oschema.hier(stypes).dunedaq.nddaqconf.types;

local s = moo.oschema.schema("dunedaq.nddaqconf.detectorgen");
local nc = moo.oschema.numeric_constraints;
// A temporary schema construction context.
local cs = {

  tpc_channel_map: s.enum("TPCChannelMap", ["VDColdboxChannelMap", "ProtoDUNESP1ChannelMap", "PD2HDChannelMap", "HDColdboxChannelMap"]),

  detector :  s.record("detector", [
    s.field( "op_env", types.string, default='swtest', doc="Operational environment - used for HDF5 Attribute inside the files"),
    s.field( "clock_speed_hz", types.freq, default=62500000),
    s.field( "tpc_channel_map", self.tpc_channel_map, default="PD2HDChannelMap", doc="Channel map for TPG"),
  ], doc="Global common settings"),


};

stypes + moo.oschema.sort_select(cs)
