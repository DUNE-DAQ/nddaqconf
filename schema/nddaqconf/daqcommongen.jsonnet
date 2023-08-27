// This is the configuration schema for nddaqconf_gen
//

local moo = import "moo.jsonnet";

local stypes = import "nddaqconf/types.jsonnet";
local types = moo.oschema.hier(stypes).dunedaq.nddaqconf.types;

local s = moo.oschema.schema("dunedaq.nddaqconf.daqcommongen");
local nc = moo.oschema.numeric_constraints;
// A temporary schema construction context.
local cs = {

  daq_common :  s.record("daq_common", [
    s.field( "data_request_timeout_ms", types.count, default=1000, doc="The baseline data request timeout that will be used by modules in the Readout and Trigger subsystems (i.e. any module that produces data fragments). Downstream timeouts, such as the trigger-record-building timeout, are derived from this."),
    s.field( "use_data_network", types.flag, default = false, doc="Whether to use the data network (Won't work with k8s)"),
    s.field( "data_rate_slowdown_factor",types.count, default=1, doc="Factor by which to suppress data generation. Former -s"),
  ], doc="Common daq_common settings"),

};

stypes + moo.oschema.sort_select(cs)
