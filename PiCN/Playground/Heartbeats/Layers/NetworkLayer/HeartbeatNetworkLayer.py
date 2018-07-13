"""Extended ICN Forwarding Layer (heartbeat)"""

import multiprocessing

from PiCN.Packets import Name, Content, Interest, Packet, Nack, NackReason
from PiCN.Playground.Heartbeats.Layers.PacketEncoding.Heartbeat import Heartbeat
from PiCN.Layers.ICNLayer import BasicICNLayer


class HeartbeatNetworkLayer(BasicICNLayer):
    def __init__(self, log_level=255, interest_to_app: bool = False):
        super().__init__(log_level=log_level)
        # self.cs = cs
        # self.pit = pit
        # self.fib = fib
        # self._ageing_interval: int = 4
        self._interest_to_app: bool = interest_to_app

    def data_from_lower(self, to_lower: multiprocessing.Queue, to_higher: multiprocessing.Queue, data):
        if len(data) != 2:
            self.logger.warning("ICN Layer expects to receive [face id, packet] from lower layer")
            return
        if type(data[0]) != int:
            self.logger.warning("ICN Layer expects to receive [face id, packet] from lower layer")
            return
        if not isinstance(data[1], Packet):
            self.logger.warning("ICN Layer expects to receive [face id, packet] from lower layer")
            return

        face_id = data[0]
        packet = data[1]
        if isinstance(packet, Interest):
            self.handle_interest_from_lower(face_id, packet, to_lower, to_higher, False)
        elif isinstance(packet, Content):
            self.handle_content(face_id, packet, to_lower, to_higher, False)
        elif isinstance(packet, Nack):
            self.handle_nack(face_id, packet, to_lower, to_higher, False)
        elif isinstance(packet, Heartbeat):
            self.handle_heartbeat(packet)

    def data_from_higher(self, to_lower: multiprocessing.Queue, to_higher: multiprocessing.Queue, data):
        high_level_id = data[0]
        packet = data[1]
        if isinstance(packet, Interest):
            self.handle_interest_from_higher(high_level_id, packet, to_lower, to_higher)
        elif isinstance(packet, Content):
            self.handle_content(high_level_id, packet, to_lower, to_higher, True) #content handled same as for content from network
        elif isinstance(packet, Nack):
            self.handle_nack(high_level_id, packet, to_lower, to_higher, True) #Nack handled same as for NACK from network
        elif isinstance(packet, Heartbeat):
            self.handle_heartbeat(packet)

    def handle_heartbeat(self, heartbeat: Heartbeat):
        self.logger.info("Handling Heartbeat")
        # check if there is matching PIT entry
        pit_entry = self.pit.find_pit_entry(heartbeat.name)
        if pit_entry is not None:
            self.logger.info("Found PIT entry to update")
            self.pit.update_timestamp(pit_entry)
            # TODO -- forward heartbeat
            return
        else:
            self.logger.info("No PIT entry found")
