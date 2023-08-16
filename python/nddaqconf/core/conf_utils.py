# Set moo schema search path
from dunedaq.env import get_moo_model_path
import moo.io
moo.io.default_load_path = get_moo_model_path()

import urllib
from pathlib import Path
from copy import deepcopy
from collections import namedtuple, defaultdict
import json
from enum import Enum
from typing import Callable
from graphviz import Digraph
import networkx as nx
import moo.otypes
import copy as cp
moo.otypes.load_types('rcif/cmd.jsonnet')
moo.otypes.load_types('appfwk/cmd.jsonnet')
moo.otypes.load_types('appfwk/app.jsonnet')

moo.otypes.load_types('iomanager/connection.jsonnet')

from appfwk.utils import acmd, mcmd, mspec
import dunedaq.appfwk.app as appfwk  # AddressedCmd,
import dunedaq.rcif.cmd as rccmd  # AddressedCmd,
import dunedaq.iomanager.connection as conn

from nddaqconf.core.daqmodule import DAQModule

from .console import console

########################################################################
#
# Classes
#
########################################################################

# TODO: Understand whether extra_commands is actually needed. Seems like "resume" is already being sent to everyone?

# TODO: Make these all dataclasses

class Direction(Enum):
    IN = 1
    OUT = 2

class Endpoint:
    # def __init__(self, **kwargs):
    #     if kwargs['connection']:
    #         self.__init_with_nwmgr(**kwargs)
    #     else:
    #         self.__init_with_external_name(**kwargs)
    def __init__(self, external_name:str, data_type:str, internal_name:str, direction:Direction, is_pubsub=False, size_hint=1000, toposort=False, check_endpoints=True):
        self.external_name = external_name
        self.data_type = data_type
        self.internal_name = internal_name
        self.direction = direction
        self.is_pubsub = is_pubsub
        self.size_hint = size_hint
        self.toposort = toposort
        self.check_endpoints = check_endpoints

    def __repr__(self):
        return f"{'' if self.toposort else '!'}{self.external_name}/{self.internal_name}"
    # def __init_with_nwmgr(self, connection, internal_name):
    #     self.nwmgr_connection = connection
    #     self.internal_name = internal_name
    #     self.external_name = None
    #     self.direction = Direction.IN

class Queue:
    def __init__(self, push_module:str, pop_module:str, data_type:str, name:str = None, size=10, toposort=False):
        self.name = name
        self.data_type = data_type
        self.size = size
        self.push_modules = [push_module]
        self.pop_modules = [pop_module]
        self.toposort = toposort
        if self.name is None:
            self.name = push_module + "_to_" + pop_module

    def add_module_link(self, push_module, pop_module):
        if push_module not in self.push_modules:
            self.push_modules.append(push_module)
        if pop_module not in self.pop_modules:
            self.pop_modules.append(pop_module)

    def __repr__(self):
        return self.name

FragmentProducer = namedtuple('FragmentProducer', ['source_id', 'requests_in', 'fragments_out', 'queue_name', 'is_mlt_producer'])


Publisher = namedtuple(
    "Publisher", ['msg_type', 'msg_module_name', 'subscribers'])

Sender = namedtuple("Sender", ['msg_type', 'msg_module_name', 'receiver'])

########################################################################
#
# Functions
#
########################################################################

def replace_localhost_ip(uri):
    parsed = urllib.parse.urlparse(uri)
    return f'{parsed.scheme}://0.0.0.0:{parsed.port}'

def make_module_deps(app, system_connections, verbose=False):
    """
    Given a list of `module` objects, produce a dictionary giving
    the dependencies between them. A dependency is any connection between
    modules. Connections whose upstream ends begin with a '!' are not
    considered dependencies, to allow us to break cycles in the DAG.

    Returns a networkx DiGraph object where nodes are module names
    """

    deps = nx.DiGraph()
    for module in app.modulegraph.modules:
        deps.add_node(module.name)

        for endpoint in app.modulegraph.endpoints:
            if endpoint.internal_name is None or endpoint.direction != Direction.IN:
                continue
            mod_name, q_name = endpoint.internal_name.split(".")
            if module.name != mod_name:
                continue

            for other_endpoint in app.modulegraph.endpoints:
                if other_endpoint.internal_name is None:
                    continue
                if other_endpoint.external_name == endpoint.external_name and other_endpoint.internal_name != endpoint.internal_name and other_endpoint.direction != Direction.IN:
                    other_mod, other_q = other_endpoint.internal_name.split(".")
                    if verbose: console.log(f"Adding generated dependency edge {other_mod} -> {mod_name}")
                    deps.add_edge(other_mod, mod_name)


    for queue in app.modulegraph.queues:
        if not queue.toposort:
            continue
        for push_addr in queue.push_modules:
            for pop_addr in queue.pop_modules:
                push_mod, push_name = push_addr.split(".", maxsplit=1)
                pop_mod, pop_name = pop_addr.split(".", maxsplit=1)
                if verbose: console.log(f"Adding queue dependency edge {push_mod} -> {pop_mod}")
                deps.add_edge(push_mod, pop_mod)



    return deps


def make_app_deps(the_system, forced_deps=[], verbose=False):
    """
    Produce a dictionary giving
    the dependencies between a set of applications, given their connections.

    Returns a networkx DiGraph object where nodes are app names
    """

    deps = the_system.make_digraph(for_toposort=True)

    for from_app,to_app in forced_deps:
        deps.add_edge(from_app, to_app, label="FORCED DEPENDENCY", color="green")

    if verbose:
        console.log("Writing app deps to make_app_deps.dot")
        nx.drawing.nx_pydot.write_dot(deps, "make_app_deps.dot")

    return deps

def add_one_command_data(command_data, command, default_params, app):
    """Add the command data for one command in one app to the command_data object. The modules to be sent the command are listed in `module_order`. If the module has an entry in its extra_commands dictionary for this command, then that entry is used as the parameters to pass to the command, otherwise the `default_params` object is passed"""
    mod_and_params=[("", default_params)]
    # for module in module_order:
    #     extra_commands = app.modulegraph.get_module(module).extra_commands
    #     if command in extra_commands:
    #         mod_and_params.append((module, extra_commands[command]))
    #     else:
    #         mod_and_params.append((module, default_params))

    command_data[command] = acmd(mod_and_params)

def make_queue_connection(the_system, app, endpoint_name, data_type, in_apps, out_apps, size, verbose):
    conn_id = conn.ConnectionId(uid=endpoint_name, data_type=data_type)
    if len(in_apps) == 1 and len(out_apps) == 1:
        if verbose:
            console.log(f"Queue {endpoint_name}, SPSC Queue (data_type={data_type}, size={size})")
        the_system.queues[app] += [conn.QueueConfig(id=conn_id, queue_type="kFollySPSCQueue", capacity=size)]
    else:
        if verbose:
            console.log(f"Queue {endpoint_name}, MPMC Queue (data_type={data_type}, size={size})")
        the_system.queues[app] += [conn.QueueConfig(id=conn_id, queue_type="kFollyMPMCQueue", capacity=size)]

def make_network_connection(the_system, endpoint_name, data_type, in_apps, out_apps, verbose, use_k8s=False, use_connectivity_service=True):
    if verbose:
        console.log(f"Connection {endpoint_name}, Network")
    if len(in_apps) > 1:
        raise ValueError(f"Connection with name {endpoint_name} has multiple receivers, which is unsupported for a network connection!")

    port = the_system.next_unassigned_port() if not use_connectivity_service or use_k8s else '*'
    address_sender = f'tcp://{{{in_apps[0]}}}:{port}' if not use_k8s else f'tcp://{in_apps[0]}:{port}'
    conn_id = conn.ConnectionId(uid=endpoint_name, data_type=data_type)
    the_system.connections[in_apps[0]] += [conn.Connection(id=conn_id, connection_type="kSendRecv", uri=address_sender)]
    if not use_connectivity_service:
        for app in set(out_apps):
            the_system.connections[app] += [conn.Connection(id=conn_id, connection_type="kSendRecv", uri=address_sender)]

def make_system_connections(the_system, verbose=False, use_k8s=False, use_connectivity_service=True):
    """Given a system with defined apps and endpoints, create the
    set of connections that satisfy the endpoints.

    If an endpoint's ID only exists for one application, a queue will
    be used.

    If an endpoint's ID exists for multiple applications, a network connection
    will be created, unless the inputs and outputs are exactly paired between
    those applications. (Each application in the set of applications that has
    that endpoint has exactly one input and one output with that endpoint name)

    If a queue connection has a single producer and single consumer, it will use FollySPSC,
    otherwise FollyMPMC will be used.


    """

    uids = []
    endpoint_map = defaultdict(list)
    topic_map = defaultdict(list)

    for app in the_system.apps:
      the_system.connections[app] = []
      the_system.queues[app] = []
      for queue in the_system.apps[app].modulegraph.queues:
            make_queue_connection(the_system, app, queue.name, queue.data_type, queue.push_modules, queue.pop_modules, queue.size, verbose)
      for endpoint in the_system.apps[app].modulegraph.endpoints:
        if not endpoint.is_pubsub:
            if verbose:
                console.log(f"Adding endpoint {endpoint.external_name}, app {app}, direction {endpoint.direction}")
            endpoint_map[endpoint.external_name] += [{"app": app, "endpoint": endpoint}]
            uids.append(endpoint.external_name)
        else:
            if verbose:
                console.log(f"Getting topics for endpoint {endpoint.external_name}, app {app}, direction {endpoint.direction}")
            topic_map[endpoint.data_type] += [{"app": app, "endpoint": endpoint}]

    for topic in topic_map.keys():
        if topic in uids:
            raise ValueError(f"Name {topic} is both an endpoint external name and a data_type")

    for endpoint_name,endpoints in endpoint_map.items():
        if verbose:
            console.log(f"Processing {endpoint_name} with defined endpoints {endpoints}")
        first_app = endpoints[0]["app"]
        check_endpoints = endpoints[0]["endpoint"].check_endpoints
        in_apps = []
        out_apps = []
        size = 0
        data_type = endpoints[0]["endpoint"].data_type
        for endpoint in endpoints:
            direction = endpoint['endpoint'].direction
            if direction == Direction.IN:
                in_apps += [endpoint["app"]]
            else:
                out_apps += [endpoint["app"]]
            if endpoint['endpoint'].size_hint > size:
                size = endpoint['endpoint'].size_hint

        if len(in_apps) == 0 and check_endpoints:
            raise ValueError(f"Connection with name {endpoint_name} has no consumers!")
        if len(out_apps) == 0 and check_endpoints:
            raise ValueError(f"Connection with name {endpoint_name} has no producers!")

        if not check_endpoints:
            if len(in_apps) > 0:
                make_network_connection(the_system, endpoint_name, data_type, in_apps, out_apps, verbose, use_k8s=use_k8s, use_connectivity_service=use_connectivity_service)
        elif all(first_app == elem["app"] for elem in endpoints):
            make_queue_connection(the_system, first_app, endpoint_name, data_type, in_apps, out_apps, size, verbose)
        elif len(in_apps) == len(out_apps):
            paired_exactly = False
            if len(set(in_apps)) == len(in_apps) and len(set(out_apps)) == len(out_apps):
                paired_exactly = True
                for in_app in in_apps:
                    if(out_apps.count(in_app) != 1):
                        paired_exactly = False
                        break

                if paired_exactly:
                    for in_app in in_apps:
                        for app_endpoint in the_system.apps[in_app].modulegraph.endpoints:
                            if app_endpoint.external_name == endpoint_name:
                                app_endpoint.external_name = f"{in_app}.{endpoint_name}"
                        make_queue_connection(the_system,in_app, f"{in_app}.{endpoint_name}", data_type, [in_app], [in_app], size, verbose)

            if paired_exactly == False:
                make_network_connection(the_system, endpoint_name, data_type, in_apps, out_apps, verbose, use_k8s=use_k8s, use_connectivity_service=use_connectivity_service)

        else:
            make_network_connection(the_system, endpoint_name, data_type, in_apps, out_apps, verbose, use_k8s=use_k8s, use_connectivity_service=use_connectivity_service)

    pubsub_connectionids = {}
    for topic, endpoints in topic_map.items():
        if verbose:
            console.log(f"Processing {topic} with defined endpoints {endpoints}")

        publishers = []
        subscribers = [] # Only really care about the topics from here
        publisher_uids = {}
        topic_connectionuids = []
        check_endpoints = endpoints[0]["endpoint"].check_endpoints

        for endpoint in endpoints:
            direction = endpoint['endpoint'].direction
            if direction == Direction.IN:
                subscribers += [endpoint["app"]]
            else:
                publishers += [endpoint["app"]]
                if endpoint['endpoint'].external_name not in pubsub_connectionids:
                    port = the_system.next_unassigned_port() if not use_connectivity_service or use_k8s else '*'
                    address = f'tcp://{{{endpoint["app"]}}}:{port}' if not use_k8s else f'tcp://{endpoint["app"]}:{port}'
                    conn_id =conn.ConnectionId( uid=endpoint['endpoint'].external_name, data_type=endpoint['endpoint'].data_type)
                    pubsub_connectionids[endpoint['endpoint'].external_name] = conn.Connection(id=conn_id,
                        connection_type="kPubSub",
                        uri=address
                    )
                topic_connectionuids += [endpoint['endpoint'].external_name]
                if endpoint['app'] not in publisher_uids.keys(): publisher_uids[endpoint["app"]] = []
                publisher_uids[endpoint["app"]] += [endpoint['endpoint'].external_name]

        if len(subscribers) == 0 and check_endpoints:
            raise ValueError(f"Data Type {topic} has no subscribers!")
        if len(publishers) == 0 and check_endpoints:
            raise ValueError(f"Data Type {topic} has no publishers!")

        for publisher in publishers:
            publisher_connections = [c.id['uid'] for c in the_system.connections[publisher]]
            for connid in publisher_uids[publisher]:
                if connid not in publisher_connections:
                    conn_copy = cp.deepcopy(pubsub_connectionids[connid])
                    conn_copy.uri = conn_copy.uri
                    the_system.connections[publisher] += [conn_copy]
        if not use_connectivity_service:
            for subscriber in subscribers:
                subscriber_connections = [c.id['uid'] for c in the_system.connections[subscriber]]
                for connid in topic_connectionuids:
                    if connid not in subscriber_connections:
                        conn_copy = cp.deepcopy(pubsub_connectionids[connid])
                        the_system.connections[subscriber] += [conn_copy]

def make_app_command_data(system, app, appkey, verbose=False, use_k8s=False, use_connectivity_service=True, connectivity_service_interval=1000):
    """Given an App instance, create the 'command data' suitable for
    feeding to nanorc. The needed queues are inferred from from
    connections between modules, as are the start and stop order of the
    modules

    TODO: This should probably be split up into separate stages of
    inferring/creating the queues (which can be part of validation)
    and actually making the command data objects for nanorc.

    """
    if '_' in appkey:
        raise RuntimeError(f'Application "{appkey}" is invalid, it shouldn\'t contain the character "_". Change its name.')


    if verbose:
        console.log(f"Making app command data for {app.name}")


    command_data = {}

    if len(system.connections) == 0 and len(system.queues) == 0:
        make_system_connections(system, verbose, use_k8s=use_k8s, use_connectivity_service=use_connectivity_service)

    module_deps = make_module_deps(app, system.connections[appkey], verbose)
    if verbose:
        console.log(f"inter-module dependencies are: {module_deps}")

    # stop_order = list(nx.algorithms.dag.topological_sort(module_deps))
    # start_order = stop_order[::-1]

    # if verbose:
        # console.log(f"Inferred module start order is {start_order}")
        # console.log(f"Inferred module stop order is {stop_order}")

    app_connrefs = defaultdict(list)
    for endpoint in app.modulegraph.endpoints:
        if endpoint.internal_name is None:
            continue
        module, name = endpoint.internal_name.split(".")
        if verbose:
            console.log(f"module, name= {module}, {name}, endpoint.external_name={endpoint.external_name}, endpoint.direction={endpoint.direction}")
        app_connrefs[module] += [appfwk.ConnectionReference(name=name, uid=endpoint.external_name)]

    for queue in app.modulegraph.queues:
        queue_uid = queue.name
        for push_mod in queue.push_modules:
            module, name = push_mod.split(".", maxsplit=1)
            app_connrefs[module] += [appfwk.ConnectionReference(name=name, uid=queue_uid)]
        for pop_mod in queue.pop_modules:
            module, name = pop_mod.split(".", maxsplit=1)
            app_connrefs[module] += [appfwk.ConnectionReference(name=name, uid=queue_uid)]

    if verbose:
        console.log(f"Creating mod_specs for {[ (mod.name, mod.plugin) for mod in app.modulegraph.modules ]}")
    mod_specs = [ mspec(mod.name, mod.plugin, app_connrefs[mod.name]) for mod in app.modulegraph.modules ]

    # Fill in the "standard" command entries in the command_data structure
    command_data['init'] = appfwk.Init(modules=mod_specs,
                                       connections=system.connections[appkey],
                                       queues=system.queues[appkey],
                                       use_connectivity_service=use_connectivity_service,
                                       connectivity_service_interval_ms=connectivity_service_interval)

    # TODO: Conf ordering
    command_data['conf'] = acmd([
        (mod.name, mod.conf) for mod in app.modulegraph.modules
    ])

    startpars = rccmd.StartParams(run=1, disable_data_storage=False)
    # resumepars = rccmd.ResumeParams()

    add_one_command_data(command_data, "start",            startpars,  app)
    add_one_command_data(command_data, "stop",             None,       app)
    add_one_command_data(command_data, "prestop1",         None,       app)
    add_one_command_data(command_data, "prestop2",         None,       app)
    add_one_command_data(command_data, "disable_triggers", None,       app)
    add_one_command_data(command_data, "enable_triggers",  None,       app)
    add_one_command_data(command_data, "scrap",            None,       app)
    # add_one_command_data(command_data, "resume",           resumepars, app)
    # add_one_command_data(command_data, "pause",            None,       app)

    # TODO: handle modules' `extra_commands`, including "record"

    return command_data

def data_request_endpoint_name(producer):
    return f"data_request_{geoid_raw_str(producer.geoid)}"

def resolve_endpoint(app, external_name, inout, verbose=False):
    """
    Resolve an `external` endpoint name to the corresponding internal "module.sinksource"
    """
    if external_name in app.modulegraph.endpoints:
        e=app.modulegraph.endpoints[external_name]
        if e.direction==inout:
            if verbose:
                console.log(f"Endpoint {external_name} resolves to {e.internal_name}")
            return e.internal_name
        else:
            raise KeyError(f"Endpoint {external_name} has direction {e.direction}, but requested direction was {inout}")
    else:
        raise KeyError(f"Endpoint {external_name} not found")

def make_unique_name(base, module_list):
    module_names = [ mod.name for mod in module_list ]
    suffix=0
    while f"{base}_{suffix}" in module_names:
        suffix+=1
    assert f"{base}_{suffix}" not in module_names

    return f"{base}_{suffix}"


def data_network_translation(hosts:dict, control_to_data_network:Callable[[str],str]=None) -> dict:
    hosts_data = {}
    if not control_to_data_network:
        hosts_data = cp.deepcopy(hosts)
    else:
        for app, hostname in hosts.items():
            hosts_data[app] = control_to_data_network(hostname)
    return hosts_data

def update_with_ssh_boot_data (
        boot_data:dict,
        apps: list,
        base_command_port: int=3333,
        verbose=False,
        control_to_data_network = None
):
    """
    Update boot_data to create the final the boot.json file
    """

    apps_desc = {}
    hosts = {}
    current_port = base_command_port

    for name, app in apps.items():
        apps_desc[name] = {
            "exec": "daq_application_ssh",
            "host": name,
            "port": current_port,
        }
        current_port+=1
        hosts[name] = app.host

    boot_data.update({
        "apps": apps_desc,
        "hosts-ctrl": hosts,
        'hosts-data': data_network_translation(hosts, control_to_data_network)
    })



def add_k8s_app_boot_data(
        boot_data: dict,
        apps: list,
        image: str,
        boot_order: list,
        base_command_port: int=3333,
        verbose=False,
        control_to_data_network = None):
    """
    Generate the dictionary that will become the boot.json file
    """
    if control_to_data_network:
        raise RuntimeError('Don\'t know how to use data network with k8s!!')

    apps_desc = {}
    for name, app in apps.items():
        apps_desc[name] = {
            "exec": 'daq_application_k8s',
            "node-selection": app.node_selection,
            "port": base_command_port,
            "mounted_dirs": app.mounted_dirs,
            "resources": app.resources,
            "affinity": app.pod_affinity,
            "anti-affinity": app.pod_anti_affinity,
        }


    boot_data.update({"apps": apps_desc})
    boot_data.update({"order": boot_order})
    # if 'rte_script' in boot_data:
    #     boot_data['exec']['daq_application_k8s']['cmd'] = ['daq_application']
    # else:
    #     boot_data['exec']['daq_application_k8s']['cmd'] = ['/dunedaq/run/app-entrypoint.sh']
    boot_data["exec"]["daq_application_k8s"]["image"] = image


def resolve_localhost(host):
    if host == 'localhost' or host[:4] == '127.':
        import socket
        return socket.gethostname()
    return host

def generate_boot(
        boot_conf,
        system,
        verbose=False,
        control_to_data_network = None) -> dict:
    """
    Generate the dictionary that will become the boot.json file
    """

    info_svc_uri_map = {
        'cern':  "kafka://monkafka.cern.ch:30092/opmon",
        'pocket':  f"kafka://{boot_conf.pocket_url}:30092/opmon",
        'local': "file://info_{APP_NAME}_{APP_PORT}.json"
    }

    ers_settings=dict()

    if boot_conf.ers_impl == 'cern':
        use_kafka = True
        ers_settings["INFO"] =    "erstrace,throttle,lstdout,erskafka(monkafka.cern.ch:30092)"
        ers_settings["WARNING"] = "erstrace,throttle,lstdout,erskafka(monkafka.cern.ch:30092)"
        ers_settings["ERROR"] =   "erstrace,throttle,lstdout,erskafka(monkafka.cern.ch:30092)"
        ers_settings["FATAL"] =   "erstrace,lstdout,erskafka(monkafka.cern.ch:30092)"
    elif boot_conf.ers_impl == 'pocket':
        use_kafka = True
        ers_settings["INFO"] =    "erstrace,throttle,lstdout,erskafka(" + boot_conf.pocket_url + ":30092)"
        ers_settings["WARNING"] = "erstrace,throttle,lstdout,erskafka(" + boot_conf.pocket_url + ":30092)"
        ers_settings["ERROR"] =   "erstrace,throttle,lstdout,erskafka(" + boot_conf.pocket_url + ":30092)"
        ers_settings["FATAL"] =   "erstrace,lstdout,erskafka(" + boot_conf.pocket_url + ":30092)"
    elif boot_conf.ers_impl == 'local':
        use_kafka = False
        ers_settings["INFO"] =    "erstrace,throttle,lstdout"
        ers_settings["WARNING"] = "erstrace,throttle,lstdout"
        ers_settings["ERROR"] =   "erstrace,throttle,lstdout"
        ers_settings["FATAL"] =   "erstrace,lstdout"
    else:
        raise ValueError(f"Unknown boot_conf.ers_impl value {boot_conf.ers_impl}")

    info_svc_uri = info_svc_uri_map[boot_conf.opmon_impl]

    daq_app_exec_name = f"daq_application_{boot_conf.process_manager}"

    capture_paths = [
        'PATH',
        'LD_LIBRARY_PATH',
        'CET_PLUGIN_PATH',
        'DUNEDAQ_SHARE_PATH'
    ]

    app_env = {
                "TRACE_FILE": "getenv:/tmp/trace_buffer_{APP_HOST}_{DUNEDAQ_PARTITION}",
                "CMD_FAC": "rest://localhost:{APP_PORT}",
                "CONNECTION_SERVER": resolve_localhost(boot_conf.connectivity_service_host),
                "CONNECTION_PORT": f"{boot_conf.connectivity_service_port}",
                "INFO_SVC": info_svc_uri,
            }

    app_env.update({
        p:'getenv' for p in capture_paths
    })

    app_env.update({
        v:'getenv' for v in boot_conf.capture_env_vars
    })



    daq_app_specs = {
        daq_app_exec_name : {
            "comment": "Application profile using PATH variables (lower start time)",
            "env": app_env,
            "cmd":"daq_application",
            "args": [
                "--name",
                "{APP_NAME}",
                "-c",
                "{CMD_FAC}",
                "-i",
                "{INFO_SVC}",
                "--configurationService",
                "{CONF_LOC}"
            ]
        }
    }

    boot = {
        "env": {
            "DUNEDAQ_ERS_VERBOSITY_LEVEL": "getenv:1",
            "DUNEDAQ_ERS_INFO": ers_settings["INFO"],
            "DUNEDAQ_ERS_WARNING": ers_settings["WARNING"],
            "DUNEDAQ_ERS_ERROR": ers_settings["ERROR"],
            "DUNEDAQ_ERS_FATAL": ers_settings["FATAL"],
            "DUNEDAQ_ERS_DEBUG_LEVEL": "getenv_ifset",
        },
        "response_listener": {
            "port": 56789
        },
        "external_connections": [],
        "exec": daq_app_specs
    }

    if use_kafka:
        boot["env"]["DUNEDAQ_ERS_STREAM_LIBS"] = "erskafka"

    if boot_conf.disable_trace:
        del boot["exec"][daq_app_exec_name]["env"]["TRACE_FILE"]
    boot['rte_script'] = get_rte_script()
    # match boot_conf.k8s_rte:
    #     case 'auto':
    #         if (release_or_dev() == 'rel'):
    #             boot['rte_script'] = get_rte_script()

    #     case 'release':
    #         boot['rte_script'] = get_rte_script()

    #     case 'devarea':
    #         pass



    if boot_conf.process_manager == 'ssh':
        for app in system.apps.values():
            app.host = resolve_localhost(app.host)

        update_with_ssh_boot_data(
            boot_data = boot,
            apps = system.apps,
            base_command_port = boot_conf.base_command_port,
            verbose = verbose,
            control_to_data_network = control_to_data_network,
        )
    elif boot_conf.process_manager == 'k8s':
        # ARGGGGG (MASSIVE WARNING SIGN HERE)
        ruapps    = [app for app in system.apps.keys() if app[:2] == 'ru']
        dfapps    = [app for app in system.apps.keys() if app[:2] == 'df']
        otherapps = [app for app in system.apps.keys() if not app in ruapps + dfapps]
        boot_order = ruapps + dfapps + otherapps

        add_k8s_app_boot_data(
            boot_data = boot,
            apps = system.apps,
            boot_order = boot_order,
            image = boot_conf.k8s_image,
            base_command_port = boot_conf.base_command_port,
            verbose = verbose,
            control_to_data_network = control_to_data_network,
        )
    else:
        raise ValueError(f"Unknown boot_conf.process_manager value {boot_conf.process_manager}")


    if boot_conf.start_connectivity_service:
        if boot_conf.process_manager == 'k8s':
            raise RuntimeError(
                'Starting connectivity service only supported with ssh')

        # CONNECTION_PORT will be updatd by nanorc remove this entry
        daq_app_specs[daq_app_exec_name]["env"].pop("CONNECTION_PORT")
        consvc={
            "connectionservice": {
                "exec": "consvc_ssh",
                "host": "connectionservice",
                "port": boot_conf.connectivity_service_port,
                "update-env": {
                    "CONNECTION_PORT": "{APP_PORT}"
                }
            }
        }
        consvc_exec={
            "consvc_ssh": {
                "args": [
                    "--bind=0.0.0.0:{APP_PORT}",
                    "--workers=1",
                    "--worker-class=gthread",
                    f"--threads={boot_conf.connectivity_service_threads}",
                    "--timeout=0",
                    "--pid={APP_NAME}_{APP_PORT}.pid",
                    "connection-service.connection-flask:app"
                ],
                "cmd": "gunicorn",
                "env": {
                    "CONNECTION_FLASK_DEBUG": "getenv:2",
                    "PATH": "getenv",
                    "PYTHONPATH": "getenv"
                }
            }
        }
        if not "services" in boot:
            boot["services"]={}
        boot["services"].update(consvc)
        boot["exec"].update(consvc_exec)
        boot_conf.connectivity_service_host = resolve_localhost(boot_conf.connectivity_service_host)
        boot["hosts-ctrl"].update({"connectionservice":
                                   boot_conf.connectivity_service_host})
    return boot


def set_strict_anti_affinity(apps, dont_run_with_me):
    for app in apps:
        app.pod_anti_affinity += [{
            "app": dont_run_with_me,
            "strict": True
        }]

def set_strict_affinity(apps, run_with_me):
    for app in apps:
        app.pod_affinity += [{
            "app":run_with_me,
            "strict": True
        }]

def set_loose_anti_affinity(apps, dont_run_with_me_if_u_can):
    for app in apps:
        app.pod_anti_affinity += [{
            "app": dont_run_with_me_if_u_can,
            "strict": False
        }]

def set_loose_affinity(apps, run_with_me_if_u_can):
    for app in apps:
        app.pod_affinity += [{
            "app": run_with_me_if_u_can,
            "strict": False
        }]


cmd_set = ["init", "conf"]


def make_app_json(app_name, app_command_data, data_dir, verbose=False):
    """Make the json files for a single application"""

    # Backwards compatibility
    if isinstance(data_dir, str):
        data_dir = Path(data_dir)

    if verbose:
        console.log(f"make_app_json for app {app_name}")
    for c in cmd_set:
        with open(data_dir / f'{app_name}_{c}.json', 'w') as f:
            json.dump(app_command_data[c].pod(), f, indent=4, sort_keys=True)

def make_system_command_datas(boot_conf:dict, the_system, forced_deps=[], verbose:bool=False, control_to_data_network:Callable[[str],str]=None) -> dict:
    """Generate the dictionary of commands and their data for the entire system"""

    # if the_system.app_start_order is None:
    #     app_deps = make_app_deps(the_system, forced_deps, verbose)
    # the_system.app_start_order = list(nx.algorithms.dag.topological_sort(app_deps))

    system_command_datas=dict()

    for c in cmd_set:
        console.log(f"Generating system {c} command")
        cfg = {
            "apps": {app_name: f'data/{app_name}_{c}' for app_name in the_system.apps.keys()}
        }
        system_command_datas[c]=cfg

        if verbose:
            console.log(cfg)

    console.log(f"Generating boot json file")
    system_command_datas['boot'] = generate_boot(
        boot_conf = boot_conf,
        system = the_system,
        verbose = verbose,
        control_to_data_network=control_to_data_network
    )

    return system_command_datas

def write_json_files(app_command_datas, system_command_datas, json_dir, verbose=False):
    """Write the per-application and whole-system command data as json files in `json_dir`
    """

    # Backwards compatibility
    if isinstance(json_dir, str):
        json_dir = Path(json_dir)

    console.rule("JSON file creation")

    data_dir = json_dir / 'data'
    data_dir.mkdir(parents=True, exist_ok=True)

    # Apps
    for app_name, command_data in app_command_datas.items():
        make_app_json(app_name, command_data, data_dir, verbose)

    # System commands
    for cmd, cfg in system_command_datas.items():
        data_file = json_dir / f'{cmd}.json'
        with open(data_file, 'w') as f:
            json.dump(cfg, f, indent=4, sort_keys=True)
        console.log(f"- {data_file} generated")

    console.log(f"System configuration generated in directory '{json_dir}'")


def get_version():
    from os import getenv
    version = getenv("DUNE_DAQ_BASE_RELEASE")
    if not version:
        raise RuntimeError('Utils: dunedaq version not in the variable env DUNE_DAQ_BASE_RELEASE! Exit nanorc and\nexport DUNE_DAQ_BASE_RELEASE=dunedaq-vX.XX.XX\n')
    return version

def get_releases_dir():
    from os import getenv
    releases_dir = getenv("SPACK_RELEASES_DIR")
    if not releases_dir:
        raise RuntimeError('Utils: cannot get env SPACK_RELEASES_DIR! Exit nanorc and\nrun dbt-workarea-env or dbt-setup-release.')
    return releases_dir

def release_or_dev():
    from os import getenv
    is_release = getenv("DBT_SETUP_RELEASE_SCRIPT_SOURCED")
    if is_release:
        console.log('Using a release')
        return 'rel'
    is_devenv = getenv("DBT_WORKAREA_ENV_SCRIPT_SOURCED")
    if is_devenv:
        console.log('Using a development area')
        return 'dev'
    return 'rel'

def get_rte_script():
    from os import path,getenv
    script = ''
    if release_or_dev() == 'rel':
        ver = get_version()
        releases_dir = get_releases_dir()
        script = path.join(releases_dir, ver, 'daq_app_rte.sh')

    else:
        dbt_install_dir = getenv('DBT_INSTALL_DIR')
        script = path.join(dbt_install_dir, 'daq_app_rte.sh')

    if not path.exists(script):
        raise RuntimeError(f'Couldn\'t understand where to find the rte script tentative: {script}')
    return script
