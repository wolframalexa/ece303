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
        self.logger.info(
            "Receiving on port: {} and replying with ACK on port: {}".format(self.inbound_port, self.outbound_port))
        while True:
            try:
                data = self.simulator.u_receive()  # receive data
                self.logger.info("Got data from socket: {}".format(
                    data.decode('ascii')))  # note that ASCII will only decode bytes in the range 0-127
                sys.stdout.write(data)
                self.simulator.u_send(BogoReceiver.ACK_DATA)  # send ACK
            except socket.timeout:
                sys.exit()


class OurReceiver(BogoReceiver):

    def __init__(self, timeout=0.01):
        super(OurReceiver, self).__init__()
        self.timeout = timeout
        self.simulator.sndr_socket.settimeout(self.timeout)
        self.simulator.rcvr_socket.settimeout(self.timeout)

    # produce a checksum value
    @staticmethod
    def checksum(data):
        return hashlib.md5(data).hexdigest()

    def receive(self):
        self.logger.info(
            "Receiving on port: {} and replying with ACK on port: {}".format(self.inbound_port, self.outbound_port))
        # initialize parameters
        duplicates = 0
        previous_ack_number = -1
        recent_ack = bytearray([0 for _ in range(33)])
        previous_checksum = bytearray([0 for _ in range(32)])
        while True:
            try:
                data = self.simulator.u_receive()
                # bring down timeout for received packet
                if self.timeout > 0.1:
                    duplicates = 0
                    self.timeout /= 2
                    self.simulator.rcvr_socket.settimeout(self.timeout)

                # check the checksum of the received packet
                if self.checksum(data[32:]) == data[0:32]:
                    ack_number = (data[64] + 1) % MAX_SEQUENCE_NUMBER
                    # make sure sequence number is correct and that the previous checksum matches
                    # include previous checksum because in some instances MAX_SEQUENCE_NUMBER packets were dropped in a row
                    # can alternatively include checksum in ACK
                    if (data[64] == previous_ack_number or previous_ack_number == -1) and previous_checksum == data[32:64]:
                        sys.stdout.write(data[65:])
                        sys.stdout.flush()
                        # store sequence number and checksum
                        previous_ack_number = ack_number
                        previous_checksum = data[0:32]

                        send_array = bytearray([ack_number])
                        send_array = self.checksum(send_array) + send_array
                        # store ACK and send
                        recent_ack = send_array
                        self.simulator.u_send(send_array)
                        continue
                # corrupt packet -> send most recent packet
                self.simulator.u_send(recent_ack)
            # socket timeout -> send most recent ACK
            except socket.timeout:
                self.simulator.u_send(recent_ack)
                duplicates += 1
                if duplicates == 3:
                    duplicates = 0
                    self.timeout *= 2
                    if self.timeout > 10:
                        sys.exit()
                    self.simulator.rcvr_socket.settimeout(self.timeout)


if __name__ == "__main__":
    # test out BogoReceiver
    # rcvr = BogoReceiver()
    # rcvr.receive()
    # use OurReceiver
    rcvr = OurReceiver()
    rcvr.receive()
