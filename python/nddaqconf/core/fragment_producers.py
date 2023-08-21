# Set moo schema search path
from dunedaq.env import get_moo_model_path
import moo.io
moo.io.default_load_path = get_moo_model_path()

import moo.otypes

moo.otypes.load_types('trigger/moduleleveltrigger.jsonnet')
moo.otypes.load_types('dfmodules/triggerrecordbuilder.jsonnet')

import dunedaq.trigger.moduleleveltrigger as mlt
import dunedaq.dfmodules.triggerrecordbuilder as trb

from nddaqconf.core.conf_utils import Direction
from nddaqconf.core.sourceid import source_id_raw_str, ensure_subsystem_string
from .console import console

def set_mlt_links(the_system, mlt_app_name="trigger", verbose=False):
    """
    The MLT needs to know the full list of fragment producers in the
    system so it can populate the TriggerDecisions it creates. This
    function gets all the fragment producers in the system and adds their
    GeoIDs to the MLT's config. It assumes that the ModuleLevelTrigger
    lives in an application with name `mlt_app_name` and has the name
    "mlt".
    """
    mlt_links = []
    for producer in the_system.get_fragment_producers():
        if producer.is_mlt_producer:
            source_id = producer.source_id
            mlt_links.append( mlt.SourceID(subsystem=ensure_subsystem_string(source_id.subsystem), element=source_id.id) )
    if verbose:
        console.log(f"Adding {len(mlt_links)} links to mlt.links: {mlt_links}")
    mgraph = the_system.apps[mlt_app_name].modulegraph
    old_mlt_conf = mgraph.get_module("mlt").conf
    mgraph.reset_module_conf("mlt", mlt.ConfParams(links=mlt_links, 
                                                   hsi_trigger_type_passthrough=old_mlt_conf.hsi_trigger_type_passthrough,
                                                   merge_overlapping_tcs=old_mlt_conf.merge_overlapping_tcs,
						   buffer_timeout=old_mlt_conf.buffer_timeout,
                                                   td_out_of_timeout=old_mlt_conf.td_out_of_timeout,
                                                   td_readout_limit=old_mlt_conf.td_readout_limit,
                                                   ignore_tc=old_mlt_conf.ignore_tc,
                                                   use_readout_map=old_mlt_conf.use_readout_map,
                                                   td_readout_map=old_mlt_conf.td_readout_map,
						   use_bitwords=old_mlt_conf.use_bitwords,
						   trigger_bitwords=old_mlt_conf.trigger_bitwords))

def remove_mlt_link(the_system, source_id, mlt_app_name="trigger"):
    """
    Remove the given source_id (which should be a dict with keys "system", "region", "element") from the list of links to request data from in the MLT.
    """
    mgraph = the_system.apps[mlt_app_name].modulegraph
    old_mlt_conf = mgraph.get_module("mlt").conf
    mlt_links = old_mlt_conf.links
    if source_id not in mlt_links:
        raise ValueError(f"SourceID {source_id} not in MLT links list")
    mlt_links.remove(source_id)
    mgraph.reset_module_conf("mlt", mlt.ConfParams(links=mlt_links, 
                                                   hsi_trigger_type_passthrough=old_mlt_conf.hsi_trigger_type_passthrough,
                                                   merge_overlapping_tcs=old_mlt_conf.merge_overlapping_tcs,
                                                   buffer_timeout=old_mlt_conf.buffer_timeout,
                                                   td_out_of_timeout=old_mlt_conf.td_out_of_timeout,
                                                   td_readout_limit=old_mlt_conf.td_readout_limit,
                                                   ignore_tc=old_mlt_conf.ignore_tc,
                                                   use_readout_map=old_mlt_conf.use_readout_map,
                                                   td_readout_map=old_mlt_conf.td_readout_map,
                                                   use_bitwords=old_mlt_conf.use_bitwords,
                                                   trigger_bitwords=old_mlt_conf.trigger_bitwords))
 
def connect_fragment_producers(app_name, the_system, verbose=False):
    """Connect the data request and fragment sending queues from all of
       the fragment producers in the app with name `app_name` to the
       appropriate endpoints of the dataflow app."""
    if verbose:
        console.log(f"Connecting fragment producers in {app_name}")

    app = the_system.apps[app_name]
    producers = app.modulegraph.fragment_producers

    # Nothing to do if there are no fragment producers. Return now so we don't create unneeded RequestReceiver and FragmentSender
    if len(producers) == 0:
        return
    
    # Create fragment sender. We can do this before looping over the
    # producers because it doesn't need any settings from them
#    app.modulegraph.add_module("fragment_sender",
#                               plugin = "FragmentSender",
#                               conf = None)

    # For each producer, we:
    # 1. Add it to the SourceID -> queue name map that is used in RequestReceiver
    # 2. Connect the relevant RequestReceiver output queue to the request input queue of the fragment producer
    # 3. Connect the fragment output queue of the producer module to the FragmentSender
    

    for producer in producers.values():
        queue_inst = f"data_requests_for_{source_id_raw_str(producer.source_id)}"
        # Connect request receiver to TRB output in DF app
        app.modulegraph.add_endpoint(queue_inst,
                                 internal_name = producer.requests_in, 
                                 data_type = "DataRequest",
                                 inout = Direction.IN)
        
                               
                               
    trb_apps = [ (name,app) for (name,app) in the_system.apps.items() if "TriggerRecordBuilder" in [n.plugin for n in app.modulegraph.module_list()] ]

    for trb_app_name, trb_app_conf in trb_apps:
        fragment_connection_name = f"fragments_to_{trb_app_name}"
        app.modulegraph.add_endpoint(fragment_connection_name, None, "Fragment", Direction.OUT)
        df_mgraph = trb_app_conf.modulegraph
        trb_module_name = [n.name for n in df_mgraph.module_list() if n.plugin == "TriggerRecordBuilder"][0]
        for producer in producers.values():
            queue_inst = f"data_requests_for_{source_id_raw_str(producer.source_id)}"
            df_mgraph.add_endpoint(queue_inst, f"{trb_module_name}.request_output_{source_id_raw_str(producer.source_id)}", "DataRequest", Direction.OUT)
            
                          

def connect_all_fragment_producers(the_system, dataflow_name="dataflow", verbose=False):
    """
    Connect all fragment producers in the system to the appropriate
    queues in the dataflow app.
    """
    for name, app in the_system.apps.items():
        if name==dataflow_name:
            continue
        connect_fragment_producers(name, the_system, verbose)
        
    trb_apps = [ (name,app) for (name,app) in the_system.apps.items() if "TriggerRecordBuilder" in [n.plugin for n in app.modulegraph.module_list()] ]
    
    for trb_app_name, trb_app_conf in trb_apps:
        fragment_connection_name = f"fragments_to_{trb_app_name}"
        df_mgraph = trb_app_conf.modulegraph
        trb_module_name = [n.name for n in df_mgraph.module_list() if n.plugin == "TriggerRecordBuilder"][0]
        df_mgraph.add_endpoint(fragment_connection_name, f"{trb_module_name}.data_fragment_all", "Fragment", Direction.IN, toposort=True)

        # Add the new source_id-to-connections map to the
        # TriggerRecordBuilder.
        old_trb_conf = df_mgraph.get_module(trb_module_name).conf
        df_mgraph.reset_module_conf(trb_module_name, trb.ConfParams(general_queue_timeout=old_trb_conf.general_queue_timeout,
                                                               source_id = old_trb_conf.source_id,
                                                          max_time_window = old_trb_conf.max_time_window,
                                                          trigger_record_timeout_ms = old_trb_conf.trigger_record_timeout_ms))
