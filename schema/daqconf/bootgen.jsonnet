// This is the configuration schema for daqconf_multiru_gen
//

local moo = import "moo.jsonnet";

local stypes = import "daqconf/types.jsonnet";
local types = moo.oschema.hier(stypes).dunedaq.daqconf.types;

local s = moo.oschema.schema("dunedaq.daqconf.bootgen");
local nc = moo.oschema.numeric_constraints;

local cs = {
  monitoring_dest: s.enum(     "MonitoringDest", ["local", "cern", "pocket"]),
  pm_choice:       s.enum(     "PMChoice", ["k8s", "ssh"], doc="Process Manager choice: ssh or Kubernetes"),


  boot: s.record("boot", [
    // s.field( "op_env", self.string, default='swtest', doc="Operational environment - used for raw data filename prefix and HDF5 Attribute inside the files"),
    s.field( "base_command_port", types.port, default=3333, doc="Base port of application command endpoints"),

    # Obscure
    s.field( "capture_env_vars", types.strings, default=['TIMING_SHARE', 'DETCHANNELMAPS_SHARE'], doc="List of variables to capture from the environment"),
    s.field( "disable_trace", types.flag, false, doc="Do not enable TRACE (default TRACE_FILE is /tmp/trace_buffer_${HOSTNAME}_${USER})"),
    s.field( "opmon_impl", self.monitoring_dest, default='local', doc="Info collector service implementation to use"),
    s.field( "ers_impl", self.monitoring_dest, default='local', doc="ERS destination (Kafka used for cern and pocket)"),
    s.field( "pocket_url", types.host, default='127.0.0.1', doc="URL for connecting to Pocket services"),
    s.field( "process_manager", self.pm_choice, default="ssh", doc="Choice of process manager"),

    # K8S
    s.field( "k8s_image", types.string, default="dunedaq/c8-minimal", doc="Which docker image to use"),

    # Connectivity Service
    s.field( "use_connectivity_service", types.flag, default=true, doc="Whether to use the ConnectivityService to manage connections"),
    s.field( "start_connectivity_service", types.flag, default=true, doc="Whether to use the ConnectivityService to manage connections"),
    s.field( "connectivity_service_threads", types.count, default=2, doc="Number of threads for the gunicorn server that serves connection info"),
    s.field( "connectivity_service_host", types.host, default='localhost', doc="Hostname for the ConnectivityService"),
    s.field( "connectivity_service_port", types.port, default=15000, doc="Port for the ConnectivityService"),
    s.field( "connectivity_service_interval", types.count, default=1000, doc="Publish interval for the ConnectivityService")
    ]),
};


stypes + moo.oschema.sort_select(cs)
