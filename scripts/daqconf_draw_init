#!/usr/bin/env python



import logging
from rich import print
import networkx as nx

import click
import json

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-i', '--interactive', is_flag=True, default=False)
@click.argument('file_path', type=click.Path(exists=True))
def cli(interactive: bool, file_path: str):
    
    with open(file_path) as f:
        init_data = json.load(f)
    
    print(init_data)

    # Ensure it's an init conf
    g = nx.DiGraph()

    conn_map = {}
    for m in init_data['modules']:
        g.add_node(m['inst'], label=f"<<B>{m['inst']}</B><BR/>[{m['plugin']}]>", shape='box', style='"rounded,filled"', fillcolor='lightskyblue1')
        for cr in m['data']['conn_refs']:
            print(cr)
            # conn_map.setdefault(cr['uid'], {}).setdefault(cr['dir'], []).append(m['inst'])
            conn_map.setdefault(cr['uid'], []).append(m['inst'])

    print(conn_map)

    # for c in init_data['connections']:
    #     c_uid = c['uid']
    #     c_uri = c['uri']
    #     c_service_type = c['service_type']
    #     if c_uid in conn_map:

    #         if c_service_type in ['kNetReceiver', 'kSubscriber']:
    #             g.add_node(c_uid, label=f"<<B>{c_uid}</B><BR/>[{c_uri}]>", shape='box', color='red')
    #             # if c_uid in conn_map:
    #             for i in conn_map[c_uid]['kInput']:
    #                 g.add_edge(c_uid, i, color='red', style='dashed')

    #         elif c_service_type in ['kNetSender', 'kPublisher']:
    #             g.add_node(c_uid, label=f"<<B>{c_uid}</B><BR/>[{c_uri}]>", shape='box', color='blue')
    #             # if c_uid in conn_map:
    #             for o in conn_map[c_uid]['kOutput']:
    #                 g.add_edge(o, c_uid, color='blue', style='dashed')
    #         elif c_service_type == 'kQueue':
    #             for o in conn_map[c_uid]['kOutput']:
    #                 for i in conn_map[c_uid]['kInput']:
    #                     # g.add_edge(o, i, label=c_uid)
    #                     g.add_edge(o, i)



        
        
        # for m in init_data['modules']:

    nx.drawing.nx_pydot.write_dot(g, 'pippo.dot')



if __name__ == '__main__':
    from rich.logging import RichHandler

    logging.basicConfig(
        level="DEBUG",
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)]
    )

    cli()
