// This is the configuration schema for daqconf_multiru_gen
//

local moo = import "moo.jsonnet";

local stypes = import "daqconf/types.jsonnet";
local types = moo.oschema.hier(stypes).dunedaq.daqconf.types;

local s = moo.oschema.schema("dunedaq.daqconf.dqmgen");
local nc = moo.oschema.numeric_constraints;

local cs = {
  monitoring_dest: s.enum(     "MonitoringDest", ["local", "cern", "pocket"]),
  dqm_channel_map: s.enum(     "DQMChannelMap", ['HD', 'VD', 'PD2HD', 'HDCB']),
  dqm_params:      s.sequence( "DQMParams",     types.count, doc="Parameters for DQM (fixme)"),

  dqm: s.record("dqm", [
    s.field('enable_dqm', types.flag, default=false, doc="Enable Data Quality Monitoring"),
    s.field('impl', self.monitoring_dest, default='local', doc="DQM destination (Kafka used for cern and pocket)"),
    s.field('cmap', self.dqm_channel_map, default='HD', doc="Which channel map to use for DQM"),
    s.field('host_dqm', types.hosts, default=['localhost'], doc='Host(s) to run the DQM app on'),
    s.field('raw_params', self.dqm_params, default=[60, 50], doc="Parameters that control the data sent for the raw display plot"),
    s.field('std_params', self.dqm_params, default=[10, 1000], doc="Parameters that control the data sent for the mean/rms plot"),
    s.field('rms_params', self.dqm_params, default=[0, 1000], doc="Parameters that control the data sent for the mean/rms plot"),
    s.field('fourier_channel_params', self.dqm_params, default=[0, 0], doc="Parameters that control the data sent for the fourier transform plot"),
    s.field('fourier_plane_params', self.dqm_params, default=[600, 1000], doc="Parameters that control the data sent for the summed fourier transform plot"),
    s.field('df_rate', types.count, default=10, doc='How many seconds between requests to DF for Trigger Records'),
    s.field('df_algs', types.string, default='raw std fourier_plane', doc='Algorithms to be run on Trigger Records from DF (use quotes)'),
    s.field('max_num_frames', types.count, default=32768, doc='Maximum number of frames to use in the algorithms'),
    s.field('kafka_address', types.string, default='', doc='kafka address used to send messages'),
    s.field('kafka_topic', types.string, default='DQM', doc='kafka topic used to send messages'),
  ]),
};

stypes + moo.oschema.sort_select(cs)
