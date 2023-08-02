from daqconf.core.daqmodule import DAQModule
from daqconf.core.conf_utils import Endpoint, Direction, FragmentProducer, Queue
from daqconf.core.sourceid import SourceID, ensure_subsystem
import networkx as nx
from typing import List, Dict

class ModuleGraph:
    """
    A set of modules and connections between them.

    modulegraph holds a dictionary of modules, with each module
    knowing its (outgoing) connections to other modules in the
    modulegraph.

    Connections to other modulegraphs are represented by
    `endpoints`. The endpoint's `external_name` is the "public" name
    of the connection, which other modulegraphs should use. The
    endpoint's `internal_name` specifies the particular module and
    sink/source name which the endpoint is connected to, which may be
    changed without affecting other applications.
    """

    def combine_queues(self, queues : List[Queue]):
        output_queues = []

        for q in queues:
            match = False
            for oq in output_queues:
                if oq.name == q.name:
                    match = True
                    for push_mod in q.push_modules:
                        if push_mod not in oq.push_modules:
                            oq.push_modules.append(push_mod)
                    for pop_mod in q.pop_modules:
                        if pop_mod not in oq.pop_modules:
                            oq.pop_modules.append(pop_mod)
                    break
            if not match:
                output_queues.append(q)

        return output_queues

    def __init__(self, modules:List[DAQModule]=None, endpoints:List[Endpoint]=None, fragment_producers:Dict[int, FragmentProducer]=None, queues: List[Queue]=None):
        self.modules=modules if modules else []
        self.endpoints=endpoints if endpoints else []
        self.fragment_producers = fragment_producers if fragment_producers else dict()
        self.queues = self.combine_queues(queues) if queues else []

    def __repr__(self):
        return f"modulegraph(modules={self.modules}, endpoints={self.endpoints}, fragment_producers={self.fragment_producers})"

    def __rich_repr__(self):
        yield "modules", self.modules
        yield "endpoints", self.endpoints
        yield "fragment_producers", self.fragment_producers

    def set_from_dict(self, module_dict):
        self.modules=module_dict

    def digraph(self):
        deps = nx.DiGraph()
        modules_set = set()

        for module in self.modules:
            if module.name in modules_set:
                raise RuntimeError(f"Module {module.name} appears twice in the ModuleGraph")
            deps.add_node(module.name, label=f"<<B>{module.name}</B><BR/>[{module.plugin}]>", shape='box', style='"rounded,filled"', fillcolor='lightskyblue1')
            modules_set.add(module.name)

        for queue in self.queues:
            for pop_mod in queue.pop_modules:
                for push_mod in queue.push_modules:
                    queue_start = push_mod.split(".")
                    if len(queue_start) != 2:
                        raise RuntimeError(f"Bad queue config!: {queue} output module must be specified as module.queue_name")
                    queue_end = pop_mod.split(".")
                    if len(queue_end) != 2:
                        raise RuntimeError(f"Bad queue config!: {queue} input module must be specified as module.queue_name")
                    deps.add_edge(queue_start[0], queue_end[0], label=queue.name)

        for endpoint in self.endpoints:
            if endpoint.internal_name is None:
                continue
            endpoint_internal_data = endpoint.internal_name.split(".")
            if len(endpoint_internal_data) != 2:
                raise RuntimeError(f'Bad endpoint!: {endpoint} internal_endpoint must be specified as module.queue_name')
            to_module = endpoint_internal_data[0]
            if to_module in modules_set:
                if endpoint.direction == Direction.IN:
                    deps.add_edge(endpoint.external_name, to_module, label=endpoint_internal_data[1], color='red', style='dashed')
                    deps.nodes[endpoint.external_name]['color'] = 'red'
                    deps.nodes[endpoint.external_name]['shape'] = 'box'
                else:
                    deps.add_edge(to_module, endpoint.external_name, label=endpoint_internal_data[1], color='blue', style='dashed')
                    deps.nodes[endpoint.external_name]['color'] = 'blue'
                    deps.nodes[endpoint.external_name]['shape'] = 'box'
            else:
                raise RuntimeError(f"Bad endpoint {endpoint}: internal connection which doesn't connect to any module! Available modules: {modules_set}")

        # finally the fragment producers
        for producer in self.fragment_producers.values():
            producer_request_in = producer.requests_in.split(".")
            if len(producer_request_in) != 2:
                raise RuntimeError(f"Bad fragment producer {producer}: request_in must be specified as module.queue_name")

            if producer_request_in[0] in modules_set:
                deps.add_edge("TriggerRecordBuilder", producer_request_in[0], label='requests', color='gold', style='dashed')
                deps.nodes["TriggerRecordBuilder"]['color'] = 'gold'
                deps.nodes["TriggerRecordBuilder"]['style'] = 'filled, dashed'
                deps.nodes["TriggerRecordBuilder"]['shape'] = 'oval'
                deps.nodes["TriggerRecordBuilder"]['label'] = 'from TRB'
            else:
                raise RuntimeError(f"Bad FragmentProducer {producer}: request_in doesn't connect to any module! Available modules: {modules_set}")

            producer_frag_out = producer.fragments_out.split(".")
            if len(producer_frag_out) != 2:
                raise RuntimeError(f"Bad fragment producer {producer}: fragments_out must be specified as module.queue_name")

            if producer_frag_out[0] in modules_set:
                deps.add_edge(producer_frag_out[0], "FragmentReceiver", label='fragments', color='orange', style='dashed, filled')
                deps.nodes["FragmentReceiver"]['color'] = 'orange'
                deps.nodes["FragmentReceiver"]['style'] = 'filled, dashed'
                deps.nodes["FragmentReceiver"]['shape'] = 'oval'
                deps.nodes["FragmentReceiver"]['label'] = 'to FR'

                
            else:
                raise RuntimeError(f"Bad FragmentProducer {producer}: fragments_out doesn't connect to any module! Available modules: {modules_set}")

        return deps

    def get_module(self, name):
        for mod in self.modules:
            if mod.name == name:
                return mod
        return None

    def reset_module(self, name, new_module):
        for i,mod in enumerate(self.modules):
            if mod.name == name:
                self.modules[i] = new_module
                return
        raise RuntimeError(f'Module {name} not found!')

    def reset_module_conf(self, name, new_conf):
        """Replace the configuration object of the module `name` with the new object `conf`"""
        # It would be nice to just modify the `conf` attribute of the
        # DAQModule object directly, but moo-derived objects work in a funny
        # way (returning a copy of the attribute, not returning a
        # reference to it), which means we have to copy and replace the
        # whole module
        for i,mod in enumerate(self.modules):
            if mod.name == name:
                old_module = self.modules[i]
                new_module = DAQModule(name=name,
                                       plugin=old_module.plugin,
                                       conf=new_conf)
                self.modules[i] = new_module
                return
        raise RuntimeError(f'Module {name} not found!')

    def module_names(self):
        return [n.name for n in self.modules]

    def module_list(self):
        return self.modules

    def add_module(self, name, **kwargs):
        if self.get_module(name):
            raise RuntimeError(f"Module of name {name} already exists in this modulegraph")
        mod=DAQModule(name=name, **kwargs)
        self.modules.append(mod)
        return mod

    def has_endpoint(self, external_name, internal_name):
        for endpoint in self.endpoints:
            if endpoint.external_name == external_name and endpoint.internal_name == internal_name:
                return True
        return False

    def add_endpoint(self, external_name:str, internal_name:str, data_type:str, inout:Direction, is_pubsub=False, toposort=False, check_endpoints=True):
        if not self.has_endpoint(external_name, internal_name):
            self.endpoints += [Endpoint(external_name, data_type, internal_name, inout, is_pubsub=is_pubsub, toposort=toposort, check_endpoints=check_endpoints)]
        else:
            raise KeyError(f"Endpoint {external_name} - {internal_name} already registered")
        
    def remove_endpoint(self, external_name):
        for i, endpoint in enumerate(self.endpoints):
            if endpoint.external_name == external_name:
                return self.endpoints.pop(i)
        
        raise KeyError(f"Failed to remove endpoint {external_name} - not found")

    def connect_modules(self, push_addr:str, pop_addr:str, data_type:str, queue_name:str = "", size_hint:int = 10, toposort = True):
        queue_start = push_addr.split(".")
        queue_end = pop_addr.split(".")
        if len(queue_start) < 2 or queue_start[0] not in self.module_names():
            raise RuntimeError(f"connect_modules called with invalid parameters. push_addr ({push_addr}) must be of form <module>.<internal name>, and the module must already be in the module graph!")

        if len(queue_end) < 2 or queue_end[0] not in self.module_names():
            raise RuntimeError(f"connect_modules called with invalid parameters. pop_addr ({pop_addr}) must be of form <module>.<internal name>, and the module must already be in the module graph!")

        if queue_name == "":
            self.queues.append(Queue(push_addr, pop_addr, data_type, push_addr + "_to_" + pop_addr, size_hint, toposort))
        else:
            existing_queue = False
            for queue in self.queues:
                if queue.name == queue_name:
                    queue.add_module_link(push_addr, pop_addr)
                    existing_queue = True
            if not existing_queue:
                self.queues.append(Queue(push_addr, pop_addr, data_type, queue_name, size_hint, toposort))

    def endpoint_names(self, inout=None):
        if inout is not None:
            return [ e[0] for e in self.endpoints.items() if e[1].inout==inout ]
        return self.endpoints.keys()

    def add_fragment_producer(self, subsystem, id, requests_in, fragments_out, is_mlt_producer=True):
        source_id = SourceID(ensure_subsystem(subsystem), id)
        if source_id in self.fragment_producers:
            raise ValueError(f"There is already a fragment producer for SourceID {source_id}")
        # Can't set queue_name here, because the queue names need to be unique system-wide,
        # but we're inside a particular app here. Instead, we create the queue names in readout_gen.generate,
        # where all of the fragment producers are known
        queue_name = None
        self.fragment_producers[source_id] = FragmentProducer(source_id, requests_in, fragments_out, queue_name, is_mlt_producer)

class App:
    """
    A single daq_application in a system, consisting of a modulegraph
    and a hostname on which to run
    """

    def __init__(self, modulegraph=None, host="localhost", name="__app"):
        if modulegraph:
            # hopefully that crashes if something is wrong!
            self.digraph = modulegraph.digraph()
            self.digraph.name = name

        self.modulegraph = modulegraph if modulegraph else ModuleGraph()
        self.name = name

        self.host = host # ssh

        # rest here are K8s specifics
        self.node_selection = [{ # k8s (NB: self.host is ignored for k8s)
            "strict": True,
            "kubernetes.io/hostname": [host],
            # ... can be used to select a node (or a collection of node). All the terms here are ANDed
            # this means if you add a field here, there has to be a pod which satisfies ALL the requirements at the same time
        }] if host != 'localhost' else [] # if you add another entry in the node_selection list, the requirement are ORed, so any node that satisfies a requirement is good
        self.mounted_dirs = []
        self.resources = {}
        self.pod_affinity = []
        self.pod_anti_affinity = []

    def reset_graph(self):
        if self.modulegraph:
            self.digraph = self.modulegraph.digraph()

    def export(self, filename):
        if not self.digraph:
            raise RuntimeError("Cannot export a app which doesn't have a valid digraph")
        nx.drawing.nx_pydot.write_dot(self.digraph, filename)
