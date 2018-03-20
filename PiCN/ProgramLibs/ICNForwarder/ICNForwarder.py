"""A ICN Forwarder using PiCN"""

import multiprocessing

from PiCN.Layers.ICNLayer import BasicICNLayer
from PiCN.Layers.ICNLayer.ForwardingInformationBase import ForwardingInformationBaseMemoryPrefix
from PiCN.Layers.ICNLayer.PendingInterestTable import PendingInterstTableMemoryExact
from PiCN.Layers.PacketEncodingLayer import BasicPacketEncodingLayer
from PiCN.Layers.AutoconfigLayer import AutoconfigServerLayer

from PiCN.Layers.ICNLayer.ContentStore import ContentStoreMemoryExact
from PiCN.Layers.LinkLayer import UDP4LinkLayer
from PiCN.Layers.PacketEncodingLayer.Encoder import BasicEncoder, SimpleStringEncoder
from PiCN.Logger import Logger
from PiCN.Mgmt import Mgmt
from PiCN.Routing import BasicRouting
from PiCN.Packets import Name


class ICNForwarder(object):
    """A ICN Forwarder using PiCN"""

    def __init__(self, port=9000, log_level=255, encoder: BasicEncoder = None, autoconfig: bool = False):
        # debug level
        logger = Logger("ICNForwarder", log_level)

        # packet encoder
        if encoder == None:
            self.encoder = SimpleStringEncoder
        else:
            encoder.set_log_level(log_level)
            self.encoder = encoder

        self._autoconfig = autoconfig

        # initialize layers
        self.linklayer = UDP4LinkLayer(port, log_level=log_level)
        self.packetencodinglayer = BasicPacketEncodingLayer(self.encoder, log_level=log_level)
        self.icnlayer = BasicICNLayer(log_level=log_level)

        # setup data structures
        self.cs = ContentStoreMemoryExact(self.icnlayer.manager)
        self.fib = ForwardingInformationBaseMemoryPrefix(self.icnlayer.manager)
        self.pit = PendingInterstTableMemoryExact(self.icnlayer.manager)

        if self._autoconfig:
            self.autoconfiglayer: AutoconfigServerLayer = AutoconfigServerLayer(linklayer=self.linklayer,
                                                                                fib=self.fib,
                                                                                address='127.0.0.1',
                                                                                broadcast='127.255.255.255',
                                                                                registration_prefixes=
                                                                                    [Name('/testnetwork/repos')],
                                                                                interest_to_app=False,
                                                                                log_level=log_level)
            self.icnlayer._interest_to_app = True

        # setup communication queues
        self.q_link_packet_up = multiprocessing.Queue()
        self.q_packet_link_down = multiprocessing.Queue()

        self.q_packet_icn_up = multiprocessing.Queue()
        self.q_icn_packet_down = multiprocessing.Queue()

        self.q_routing_icn_up = multiprocessing.Queue()
        self.q_icn_routing_down = multiprocessing.Queue()

        if self._autoconfig:
            self.q_icn_autoconfig_up = multiprocessing.Queue()
            self.q_autoconfig_icn_down = multiprocessing.Queue()

        # set link layer queues
        self.linklayer.queue_to_higher = self.q_link_packet_up
        self.linklayer.queue_from_higher = self.q_packet_link_down

        # set packet encoding layer queues
        self.packetencodinglayer.queue_to_lower = self.q_packet_link_down
        self.packetencodinglayer.queue_from_lower = self.q_link_packet_up
        self.packetencodinglayer.queue_to_higher = self.q_packet_icn_up
        self.packetencodinglayer.queue_from_higher = self.q_icn_packet_down

        # set icn layer queues
        self.icnlayer.queue_to_lower = self.q_icn_packet_down
        self.icnlayer.queue_from_lower = self.q_packet_icn_up

        if self._autoconfig:
            self.icnlayer.queue_to_higher = self.q_icn_autoconfig_up
            self.icnlayer.queue_from_higher = self.q_autoconfig_icn_down
            self.autoconfiglayer.queue_from_lower = self.q_icn_autoconfig_up
            self.autoconfiglayer.queue_to_lower = self.q_autoconfig_icn_down

        self.icnlayer.cs = self.cs
        self.icnlayer.fib = self.fib
        self.icnlayer.pit = self.pit

        # routing
        self.routing = BasicRouting(self.icnlayer.pit, None, log_level=log_level)  # TODO NOT IMPLEMENTED YET

        # mgmt
        self.mgmt = Mgmt(self.cs, self.fib, self.pit, self.linklayer, self.linklayer.get_port(),
                         self.stop_forwarder, log_level=log_level)

    def start_forwarder(self):
        # start processes
        self.linklayer.start_process()
        self.packetencodinglayer.start_process()
        self.icnlayer.start_process()
        self.icnlayer.ageing()
        self.mgmt.start_process()
        if self._autoconfig:
            self.autoconfiglayer.start_process()

    def stop_forwarder(self):
        # Stop processes
        self.mgmt.stop_process()
        self.linklayer.stop_process()
        self.packetencodinglayer.stop_process()
        self.icnlayer.stop_process()
        if self._autoconfig:
            self.autoconfiglayer.stop_process()

        # close queues file descriptors
        self.q_link_packet_up.close()
        self.q_packet_link_down.close()
        self.q_packet_icn_up.close()
        self.q_icn_packet_down.close()
        if self._autoconfig:
            self.q_icn_autoconfig_up.close()
            self.q_autoconfig_icn_down.close()
