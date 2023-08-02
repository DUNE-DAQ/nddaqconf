// This is the configuration schema for daqconf_multiru_gen
//

local moo = import "moo.jsonnet";

local stypes = import "daqconf/types.jsonnet";
local types = moo.oschema.hier(stypes).dunedaq.daqconf.types;

local s = moo.oschema.schema("dunedaq.daqconf.timinggen");
local nc = moo.oschema.numeric_constraints;

local cs = {

  timing: s.record("timing", [
    s.field( "timing_session_name", types.string, default="", doc="Name of the global timing session to use, for timing commands"),
    s.field( "host_tprtc", types.host, default='localhost', doc='Host to run the timing partition controller app on'),
    # timing hw partition options
    s.field( "control_timing_partition", types.flag, default=false, doc='Flag to control whether we are controlling timing partition in master hardware'),
    s.field( "timing_partition_master_device_name", types.string, default="", doc='Timing partition master hardware device name'),
    s.field( "timing_partition_id", types.count, default=0, doc='Timing partition id'),
    s.field( "timing_partition_trigger_mask", types.count, default=255, doc='Timing partition trigger mask'),
    s.field( "timing_partition_rate_control_enabled", types.flag, default=false, doc='Timing partition rate control enabled'),
    s.field( "timing_partition_spill_gate_enabled", types.flag, default=false, doc='Timing partition spill gate enabled'),
  ]),
};


stypes + moo.oschema.sort_select(cs)
