from nddaqconf.core.conf_utils import Direction
import networkx as nx

class System:
    """
    A full DAQ system consisting of multiple applications and the
    connections between them. The `apps` member is a dictionary from
    application name to app object. Endpoints are specified
    as strings like app_name.endpoint_name.

    An explicit mapping from upstream endpoint name to zeromq
    connection string may be specified, but typical usage is to not
    specify this, and leave the mapping to be automatically generated.

    The same is true for application start order.
    """

    def __init__(self, apps=None, connections=None, app_start_order=None,
                 first_port=12345, queues=None):
        self.apps=apps if apps else dict()
        self.connections = connections if connections else dict()
        self.queues = queues if queues else dict()
        self.app_start_order = app_start_order
        self._next_port = first_port
        self.digraph = None

    def __rich_repr__(self):
        yield "apps", self.apps
        yield "connections", self.connections
        yield "queues", self.queues
        yield "app_connections", self.app_connections
        yield "app_start_order", self.app_start_order

    def get_fragment_producers(self):
        """Get a list of all the fragment producers in the system"""
        all_producers = []
        all_geoids = set()
        for app in self.apps.values():
            producers = app.modulegraph.fragment_producers
            for producer in producers.values():
                if producer.source_id in all_geoids:
                    raise ValueError(f"SourceID {producer.source_id} has multiple fragment producers")
                all_geoids.add(producer.source_id)
                all_producers.append(producer)
        return all_producers

    def make_digraph(self, for_toposort=False):
        deps = nx.MultiDiGraph()

        for app_name in self.apps.keys():
            deps.add_node(app_name)

        for from_app_n, from_app in self.apps.items():
            for from_ep in from_app.modulegraph.endpoints:
                if from_ep.direction == Direction.OUT:
                    for to_app_n, to_app in self.apps.items():
                        for to_ep in to_app.modulegraph.endpoints:
                            if to_ep.direction == Direction.IN:
                                if from_ep.external_name == to_ep.external_name:
                                    color="red"
                                    if from_ep.toposort or to_ep.toposort:
                                        color="blue"
                                    elif for_toposort:
                                        continue
                                    deps.add_edge(from_app_n, to_app_n, label=to_ep.external_name, color=color)


        return deps


    def export(self, filename):
        self.digraph = self.make_digraph()
        nx.drawing.nx_pydot.write_dot(self.digraph, filename)

    def next_unassigned_port(self):
        self._next_port += 1
        return self._next_port
