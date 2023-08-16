// This is the configuration schema for nddaqconf_multiru_gen
//

local moo = import "moo.jsonnet";

local stypes = import "nddaqconf/types.jsonnet";
local types = moo.oschema.hier(stypes).dunedaq.nddaqconf.types;

local s = moo.oschema.schema("dunedaq.nddaqconf.hsigen");
local nc = moo.oschema.numeric_constraints;

local cs = {

  hsi: s.record("hsi", [
    s.field( "random_trigger_rate_hz", types.rate, default=1.0, doc='Fake HSI only: rate at which fake HSIEvents are sent. 0 - disable HSIEvent generation. Former -t'),
    # timing hsi options
    s.field( "use_timing_hsi", types.flag, default=false, doc='Flag to control whether real hardware timing HSI config is generated. Default is false'),
    s.field( "host_timing_hsi", types.host, default='localhost', doc='Host to run the HSI app on'),
    s.field( "hsi_hw_connections_file", types.path, default="${TIMING_SHARE}/config/etc/connections.xml", doc='Real timing hardware only: path to hardware connections file'),
    s.field( "enable_hardware_state_recovery", types.flag, default=true, doc="Enable (or not) hardware state recovery"),
    s.field( "hsi_device_name", types.string, default="", doc='Real HSI hardware only: device name of HSI hw'),
    s.field( "hsi_readout_period", types.count, default=1e3, doc='Real HSI hardware only: Period between HSI hardware polling [us]'),
    s.field( "control_hsi_hw", types.flag, default=false, doc='Flag to control whether we are controlling hsi hardware'),
    s.field( "hsi_endpoint_address", types.count, default=1, doc='Timing address of HSI endpoint'),
    s.field( "hsi_endpoint_partition", types.count, default=0, doc='Timing partition of HSI endpoint'),
    s.field( "hsi_re_mask",types.count, default=0, doc='Rising-edge trigger mask'),
    s.field( "hsi_fe_mask", types.count, default=0, doc='Falling-edge trigger mask'),
    s.field( "hsi_inv_mask",types.count, default=0, doc='Invert-edge mask'),
    s.field( "hsi_source",types.count, default=1, doc='HSI signal source; 0 - hardware, 1 - emulation (trigger timestamp bits)'),
    # fake hsi options
    s.field( "use_fake_hsi", types.flag, default=true, doc='Flag to control whether fake or real hardware HSI config is generated. Default is true'),
    s.field( "host_fake_hsi", types.host, default='localhost', doc='Host to run the HSI app on'),
    s.field( "hsi_device_id", types.count, default=0, doc='Fake HSI only: device ID of fake HSIEvents'),
    s.field( "mean_hsi_signal_multiplicity", types.count, default=1, doc='Fake HSI only: rate of individual HSI signals in emulation mode 1'),
    s.field( "hsi_signal_emulation_mode", types.count, default=0, doc='Fake HSI only: HSI signal emulation mode'),
    s.field( "enabled_hsi_signals", types.count, default=1, doc='Fake HSI only: bit mask of enabled fake HSI signals')
  ]),

};


stypes + moo.oschema.sort_select(cs)
