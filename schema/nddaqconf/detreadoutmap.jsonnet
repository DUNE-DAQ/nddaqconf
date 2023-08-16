// This is the configuration schema for nddaqconf_multiru_gen
//

local moo = import "moo.jsonnet";

local s_hdf5rdf = import "hdf5libs/hdf5rawdatafile.jsonnet";
local hdf5rdf = moo.oschema.hier(s_hdf5rdf).dunedaq.hdf5libs.hdf5rawdatafile;

local s = moo.oschema.schema("dunedaq.nddaqconf.detreadoutmap");
local nc = moo.oschema.numeric_constraints;

// A temporary schema construction context.
local cs = {
    short:  s.number("Short", "u2", doc="A short Unsigned number"),
    long:   s.number("Long", "u8", doc="A link identifier"),
    size:   s.number("Size", "u8", doc="A count of very many things"),
    freq:   s.number("Frequency", "u4", doc="A frequency"),
    count:  s.number("Count", "i8", doc="A count of things"),
    flag:   s.boolean("Flag", doc="Parameter that can be used to enable or disable functionality"),
    string: s.string("Str", doc="Generic string"),
    host:   s.string("Host", pattern=moo.re.dnshost, doc="Generic string"),
    ipv4:   s.string("ipv4", pattern=moo.re.ipv4, doc="ipv4 string"),
    mac:    s.string("mac", pattern="^[a-fA-F0-9]{2}(:[a-fA-F0-9]{2}){5}$", doc="mac string"),
    kind:   s.enum("StreamKind", ["eth", "flx"]),
    mode:   s.enum("StreamMode", ["fix_rate", "var_rate"]),
    flx_protocol: s.enum("FlxProtocol", ["full", "half"]),
    eth_protocol: s.enum("EthProtocol", ["udp", "zmq"]),

    flx_conf: s.record("FelixStreamParameters", [
      s.field("protocol", self.flx_protocol, "full", doc="Felix protocol"),
      s.field("mode", self.mode, "fix_rate", doc="fix_rate, var_rate"),
      s.field("host", self.host, doc="Felix hostname"),
      s.field("card", self.short, 0, doc="Card ID in readout host"),
      s.field("slr", self.short, 0, doc="SuperLogicRegion of reaodut card"),
      s.field("link", self.short, 0, doc="Link within SLR"),
    ], doc="A FELIX readout stream configuration"),

    eth_conf: s.record("EthStreamParameters", [
      s.field("protocol", self.eth_protocol, "udp", doc="Ethernet protocol used. udp or zmq"),
      s.field("mode", self.mode, "fix_rate", doc="fix_rate, var_rate"),
      s.field("rx_iface", self.short, 0, doc="Reaout interface"),
      s.field("rx_host", self.host, "localhost", doc="Readout hostname"),
      s.field("rx_mac", self.mac,  "00:00:00:00:00:00", doc="Destination MAC on readout host"),
      s.field("rx_ip", self.ipv4, "0.0.0.0", doc="Destination IP on readout host"),
      s.field("tx_host", self.host, "localhost", doc="Transmitter control host"),
      s.field("tx_mac", self.mac, "00:00:00:00:00:00", doc="Transmitter MAC"),
      s.field("tx_ip", self.ipv4, "0.0.0.0", doc="Transmitter IP"),
    ], doc="A Ethernet readout stream configuration"),


    stream_parameters: s.any("DROStreamConf", doc="Stream parameters"),

    stream_entry : s.record("DROStreamEntry", [
        s.field("src_id", self.size, 0, doc="Source ID"),
        s.field("geo_id", hdf5rdf.GeoID, doc="Geo ID"),
        s.field("kind", self.kind, doc="eth vs flx"),
        s.field("parameters", self.stream_parameters)
        // s.field("details", self.stream_details)
        // s.field("info", self.stream_info)
    ]),

    stream_map : s.sequence("DROStreamMap", self.stream_entry, doc="Detector Readout map" )

};

// Output a topologically sorted array.
s_hdf5rdf + moo.oschema.sort_select(cs)
