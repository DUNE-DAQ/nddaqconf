# testapp_noreadout_two_process.py

# This python configuration produces *two* json configuration files
# that together form a MiniDAQApp with the same functionality as
# MiniDAQApp v1, but in two processes. One process contains the
# TriggerDecisionEmulator, while the other process contains everything
# else.
#
# As with testapp_noreadout_confgen.py
# in this directory, no modules from the readout package are used: the
# fragments are provided by the FakeDataProd module from dfmodules

import math
# from rich.console import Console
from ..core.console import console
# Set moo schema search path
from dunedaq.env import get_moo_model_path
import moo.io
moo.io.default_load_path = get_moo_model_path()

# Load configuration types
import moo.otypes
# moo.otypes.load_types('rcif/cmd.jsonnet')
moo.otypes.load_types('hsilibs/hsireadout.jsonnet')
moo.otypes.load_types('hsilibs/hsicontroller.jsonnet')
moo.otypes.load_types('readoutlibs/readoutconfig.jsonnet')

# import dunedaq.rcif.cmd as rccmd # AddressedCmd, 
import dunedaq.hsilibs.hsireadout as hsir
import dunedaq.hsilibs.hsicontroller as hsic
import dunedaq.readoutlibs.readoutconfig as rconf

from ..core.app import App, ModuleGraph
from ..core.daqmodule import DAQModule
from ..core.conf_utils import Direction, Queue

#===============================================================================
def get_timing_hsi_app(
                detector,
                hsi,
                daq_common,
                source_id,
                timing_session_name,
                UHAL_LOG_LEVEL="notice",
                QUEUE_POP_WAIT_MS=10,
                LATENCY_BUFFER_SIZE=100000,
                DATA_REQUEST_TIMEOUT=1000,
                DEBUG=False):




    # Temp vars - remove
    CLOCK_SPEED_HZ = detector.clock_speed_hz
    DATA_RATE_SLOWDOWN_FACTOR = daq_common.data_rate_slowdown_factor
    RANDOM_TRIGGER_RATE_HZ = hsi.random_trigger_rate_hz
    CONTROL_HSI_HARDWARE=hsi.control_hsi_hw
    CONNECTIONS_FILE=hsi.hsi_hw_connections_file
    READOUT_PERIOD_US = hsi.hsi_readout_period
    HSI_DEVICE_NAME = hsi.hsi_device_name
    HARDWARE_STATE_RECOVERY_ENABLED = hsi.enable_hardware_state_recovery
    HSI_ENDPOINT_ADDRESS = hsi.hsi_endpoint_address
    HSI_ENDPOINT_PARTITION = hsi.hsi_endpoint_partition
    HSI_RE_MASK=hsi.hsi_re_mask
    HSI_FE_MASK=hsi.hsi_fe_mask
    HSI_INV_MASK=hsi.hsi_inv_mask
    HSI_SOURCE=hsi.hsi_source
    HSI_SOURCE_ID=source_id
    TIMING_SESSION=timing_session_name
    HOST=hsi.host_timing_hsi

    modules = {}

    ## TODO all the connections...
    modules = [DAQModule(name = "hsir",
                        plugin = "HSIReadout",
                        conf = hsir.ConfParams(connections_file=CONNECTIONS_FILE,
                                            readout_period=READOUT_PERIOD_US,
                                            hsi_device_name=HSI_DEVICE_NAME,
                                            uhal_log_level=UHAL_LOG_LEVEL))]
    
    modules += [DAQModule(name = f"hsi_datahandler",
                        plugin = "HSIDataLinkHandler",
                        conf = rconf.Conf(readoutmodelconf = rconf.ReadoutModelConf(source_queue_timeout_ms = QUEUE_POP_WAIT_MS,
                                                                                    source_id=HSI_SOURCE_ID,
                                                                                    send_partial_fragment_if_available = True),
                                             latencybufferconf = rconf.LatencyBufferConf(latency_buffer_size = LATENCY_BUFFER_SIZE,
                                                                                         source_id=HSI_SOURCE_ID),
                                             rawdataprocessorconf = rconf.RawDataProcessorConf(source_id=HSI_SOURCE_ID,
                                                                                               clock_speed_hz=(CLOCK_SPEED_HZ/DATA_RATE_SLOWDOWN_FACTOR)),
                                             requesthandlerconf= rconf.RequestHandlerConf(latency_buffer_size = LATENCY_BUFFER_SIZE,
                                                                                          pop_limit_pct = 0.8,
                                                                                          pop_size_pct = 0.1,
                                                                                          source_id=HSI_SOURCE_ID,
                                                                                          # output_file = f"output_{idx + MIN_LINK}.out",
                                                                                          request_timeout_ms = DATA_REQUEST_TIMEOUT,
                                                                                          warn_about_empty_buffer = False,
                                                                                          enable_raw_recording = False)
                                             ))]

    if CONTROL_HSI_HARDWARE:
        modules.extend( [
                        DAQModule(name="hsic",
                                plugin = "HSIController",
                                conf = hsic.ConfParams( device=HSI_DEVICE_NAME,
                                                        hardware_state_recovery_enabled=HARDWARE_STATE_RECOVERY_ENABLED,
                                                        timing_session_name=TIMING_SESSION,
                                                        clock_frequency=CLOCK_SPEED_HZ,
                                                        trigger_rate=RANDOM_TRIGGER_RATE_HZ,
                                                        address=HSI_ENDPOINT_ADDRESS,
                                                        partition=HSI_ENDPOINT_PARTITION,
                                                        rising_edge_mask=HSI_RE_MASK,
                                                        falling_edge_mask=HSI_FE_MASK,
                                                        invert_edge_mask=HSI_INV_MASK,
                                                        data_source=HSI_SOURCE),
                                # extra_commands = {"start": startpars}
                                ),
                        ] )
    
    queues = [Queue(f"hsir.output",f"hsi_datahandler.raw_input", "HSIFrame", f'hsi_link_0', 100000)]

    mgraph = ModuleGraph(modules, queues=queues)
    
    mgraph.add_fragment_producer(id = HSI_SOURCE_ID, subsystem = "HW_Signals_Interface",
                                         requests_in   = f"hsi_datahandler.request_input",
                                         fragments_out = f"hsi_datahandler.fragment_queue")
    mgraph.add_endpoint(f"timesync_timing_hsi", f"hsi_datahandler.timesync_output",  "TimeSync",  Direction.OUT, is_pubsub=True, toposort=False)

    
    if CONTROL_HSI_HARDWARE:
        mgraph.add_endpoint("timing_cmds", "hsic.timing_cmds", "TimingHwCmd", Direction.OUT, check_endpoints=False)
        mgraph.add_endpoint(HSI_DEVICE_NAME+"_info", "hsic."+HSI_DEVICE_NAME+"_info", "JSON", Direction.IN, is_pubsub=True, check_endpoints=False)

    mgraph.add_endpoint("hsievents", "hsir.hsievents", "HSIEvent",    Direction.OUT)
    
    # dummy subscriber
    mgraph.add_endpoint(None, None, data_type="TimeSync", inout=Direction.IN, is_pubsub=True)

    hsi_app = App(modulegraph=mgraph, host=HOST, name="HSIApp")
    
    return hsi_app
