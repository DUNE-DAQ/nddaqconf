
# Set moo schema search path
from dunedaq.env import get_moo_model_path
import moo.io
moo.io.default_load_path = get_moo_model_path()

# Load configuration types
import moo.otypes
moo.otypes.load_types('rcif/cmd.jsonnet')
moo.otypes.load_types('appfwk/cmd.jsonnet')
moo.otypes.load_types('appfwk/app.jsonnet')

moo.otypes.load_types('dfmodules/tpstreamwriter.jsonnet')
moo.otypes.load_types('dfmodules/hdf5datastore.jsonnet')

# Import new types
import dunedaq.dfmodules.tpstreamwriter as tpsw
import dunedaq.hdf5libs.hdf5filelayout as h5fl
import dunedaq.dfmodules.hdf5datastore as hdf5ds

from daqconf.core.app import App, ModuleGraph
from daqconf.core.daqmodule import DAQModule
from daqconf.core.conf_utils import Direction

# Time to wait on pop()
QUEUE_POP_WAIT_MS = 100

def get_tpwriter_app(
        detector,
        dataflow,
        daq_common,
        app_name,
        file_label,
        source_id,
        SRC_GEO_ID_MAP,
        DEBUG=False
    ):
    """Generate the json configuration for the readout and DF process"""

    # Temp vars
    OUTPUT_PATH = dataflow.tpset_output_path
    APP_NAME = app_name
    OPERATIONAL_ENVIRONMENT = detector.op_env
    MAX_FILE_SIZE = dataflow.tpset_output_file_size
    DATA_RATE_SLOWDOWN_FACTOR = daq_common.data_rate_slowdown_factor
    CLOCK_SPEED_HZ = detector.clock_speed_hz
    SOURCE_IDX=source_id
    HOST=dataflow.host_tpw

    ONE_SECOND_INTERVAL_TICKS = CLOCK_SPEED_HZ / DATA_RATE_SLOWDOWN_FACTOR

    modules = []

    modules += [DAQModule(name = 'tpswriter',
                          plugin = "TPStreamWriter",
                          conf = tpsw.ConfParams(tp_accumulation_interval_ticks=ONE_SECOND_INTERVAL_TICKS,
                              source_id=SOURCE_IDX,
                              data_store_parameters=hdf5ds.ConfParams(
                              name="tp_stream_writer",
                              operational_environment = OPERATIONAL_ENVIRONMENT,
                              directory_path = OUTPUT_PATH,
                              max_file_size_bytes = MAX_FILE_SIZE,
                              disable_unique_filename_suffix = False,
                              srcid_geoid_map=SRC_GEO_ID_MAP,
                              filename_parameters = hdf5ds.FileNameParams(
                                  overall_prefix = "tpstream",
                                  digits_for_run_number = 6,
                                  file_index_prefix = "",
                                  digits_for_file_index = 4,
                                  writer_identifier = f"{APP_NAME}_tpswriter"),
                              file_layout_parameters = h5fl.FileLayoutParams(
                                  record_name_prefix= "TimeSlice",
                                  record_header_dataset_name = "TimeSliceHeader",
                                  digits_for_record_number = 6,
                                  digits_for_sequence_number = 0,
                                  path_param_list = h5fl.PathParamList(
                                      [h5fl.PathParams(detector_group_type="Detector_Readout",
                                                       detector_group_name="TPC",
                                                       element_name_prefix="Link")])))))]

    mgraph=ModuleGraph(modules)

    mgraph.add_endpoint(".*", f"tpswriter.tpset_source", "TPSet", Direction.IN, is_pubsub=True)

    tpw_app = App(modulegraph=mgraph, host=HOST)

    tpw_app.mounted_dirs += [{
        'name': 'raw-data',
        'physical_location':OUTPUT_PATH,
        'in_pod_location':OUTPUT_PATH,
        'read_only': False
    }]

    return tpw_app
