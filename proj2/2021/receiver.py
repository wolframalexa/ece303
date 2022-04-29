# Written by S. Mevawala, modified by D. Gitzel
import logging
import channelsimulator
import utils
import sys
import socket

import hashlib

MAX_SEQUENCE_NUMBER = 256

class Receiver(object):

    def __init__(self, inbound_port=50005, outbound_port=50006, timeout=10, debug_level=logging.INFO):
        self.logger = utils.Logger(self.__class__.__name__, debug_level)

        self.inbound_port = inbound_port
        self.outbound_port = outbound_port
        self.simulator = channelsimulator.ChannelSimulator(inbound_port=inbound_port, outbound_port=outbound_port,
                                                           debug_level=debug_level)
        self.simulator.rcvr_setup(timeout)
        self.simulator.sndr_setup(timeout)

    def receive(self):
        raise NotImplementedError("The base API class has no implementation. Please override and add your own.")


class BogoReceiver(Receiver):
    ACK_DATA = bytes(123)

    def __init__(self):
        super(BogoReceiver, self).__init__()

    def receive(self):
        self.logger.info("Receiving on port: {} and replying with ACK on port: {}".format(self.inbound_port, self.outbound_port))
        while True:
            try:
                 data = self.simulator.u_receive()  # receive data
                 self.logger.info("Got data from socket: {}".format(
                     data.decode('ascii')))  # note that ASCII will only decode bytes in the range 0-127
	         sys.stdout.write(data)
                 self.simulator.u_send(BogoReceiver.ACK_DATA)  # send ACK
            except socket.timeout:
                sys.exit()

class myReceiver(BogoReceiver):
    def __init__(self, timeout = 0.1):
         super(myReceiver, self).__init__()
         self.timeout = timeout
         self.simulator.sndr_socket.settimeout(self.timeout)
         self.simulator.rcvr_socket.settimeout(self.timeout)

    @staticmethod
    def checksum(data):
        return hashlib.md5(data).hexdigest()


    def receive(self):
        self.logger.info("Received from port: {} and sending ACK to port: {}".format(self.inbound_port, self.outbound_port))

        dup = 0
        last_ack = -1
        recent_ack = bytearray([0 for _ in range(33)])
        last_checksum = bytearray([0 for _ in range(32)])

        while True:
            try:
                data = self.simulator.u_receive()
                self.logger.info("Received packet {}".format(data))

                self.logger.info(self.checksum(data[32:]))
                self.logger.info(data[0:32])

                # lower timeout for received packet
                if self.timeout > 0.1:
                    dup = 0
                    self.timeout /= 2
                    self.simulator.rcvr_socket.settimeout(self.timeout)

                # check checksum of received packet
                if self.checksum(data[32:]) == data[0:32]:
                    self.logger.info("checksum good")
                    acknum = (data[64] + 1) % MAX_SEQUENCE_NUMBER

                    if (data[64] == last_ack or last_ack == -1) and last_checksum == data[32:64]:
                        sys.stdout.write(data[65:])
                        sys.stdout.flush()

                        last_ack = acknum
                        last_checksum = data[0:32]

                        # create ack to send back
                        ack = bytearray([acknum])
                        ack = self.checksum(ack) + ack

                        recent_ack = ack
                        self.simulator.u_send(ack)
                        continue

                # if packet corrupt, send most recent
                self.simulator.u_send(recent_ack)

            except socket.timeout:
                self.logger.info("Timeout on Receiver")
                self.simulator.u_send(recent_ack)
                dup += 1
                if dup == 3:
                    dup = 0
                    self.timeout *= 2
                    if self.timeout > 10:
                        sys.exit()
                    self.simulator.rcvr_socket.settimeout(self.timeout)


if __name__ == "__main__":
    # test myReceiver
    rcvr = myReceiver()
    rcvr.receive()
