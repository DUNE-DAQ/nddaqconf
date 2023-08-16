# Set moo schema search path
from dunedaq.env import get_moo_model_path
import moo.io

moo.io.default_load_path = get_moo_model_path()

# Load configuration types
import moo.otypes

moo.otypes.load_types("dpdklibs/nicsender.jsonnet")

# Import new types
import dunedaq.dpdklibs.nicsender as nsc

from nddaqconf.core.app import App, ModuleGraph
from nddaqconf.core.daqmodule import DAQModule
from nddaqconf.core.conf_utils import Endpoint, Direction, Queue

# Time to waait on pop()
QUEUE_POP_WAIT_MS = 100


def get_dpdk_sender_app(
        HOST='localhost',
        NUMBER_OF_CORES=2,
        NUMBER_OF_IPS_PER_CORE=2,
        BASE_SOURCE_IP='10.73.139.',
        DESTINATION_IP='10.73.139.17',
        DESTINATION_MAC='EC:0D:9A:8E:BA:10',
        FRONTEND_TYPE='tde',
        RATE=None,
        TIME_TICK_DIFFERENCE=1000,
        EAL_ARGS='',
        DEBUG=False,
):

    modules = []
    queues = []

    last_ip = 100

    core_maps = []
    for core in range(NUMBER_OF_CORES):
        ips = []
        for ip in range(NUMBER_OF_IPS_PER_CORE):
            src_ip = f'{BASE_SOURCE_IP}{last_ip + core * NUMBER_OF_IPS_PER_CORE + ip}'
            ips.append(src_ip)
        core_maps.append(nsc.Core(lcore_id=core+1, src_ips=ips))

    modules += [DAQModule(name="nic_sender", plugin="NICSender",
                          conf=nsc.Conf(
                              eal_arg_list=EAL_ARGS,
                              frontend_type='tde',
                              number_of_cores=NUMBER_OF_CORES,
                              number_of_ips_per_core=NUMBER_OF_IPS_PER_CORE,
                              burst_size=1,
                              rate=1,
                              core_list=core_maps,
                              time_tick_difference=TIME_TICK_DIFFERENCE,
                          )
        )]

    mgraph = ModuleGraph(modules, queues=queues)

    dpdk_app = App(modulegraph=mgraph, host=HOST, name="dpdk_sender")
    return dpdk_app
