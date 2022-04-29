# Written by S. Mevawala, modified by D. Gitzel

import logging
import socket

import channelsimulator
import utils
import sys

import hashlib

MAX_SEQUENCE_NUMBER = 256


class Sender(object):

    def __init__(self, inbound_port=50006, outbound_port=50005, timeout=10, debug_level=logging.INFO):
        self.logger = utils.Logger(self.__class__.__name__, debug_level)

        self.inbound_port = inbound_port
        self.outbound_port = outbound_port
        self.simulator = channelsimulator.ChannelSimulator(inbound_port=inbound_port, outbound_port=outbound_port,
                                                           debug_level=debug_level)
        self.simulator.sndr_setup(timeout)
        self.simulator.rcvr_setup(timeout)

    def send(self, data):
        raise NotImplementedError("The base API class has no implementation. Please override and add your own.")


class BogoSender(Sender):

    def __init__(self):
        super(BogoSender, self).__init__()

    def send(self, data):
        self.logger.info(
            "Sending on port: {} and waiting for ACK on port: {}".format(self.outbound_port, self.inbound_port))
        while True:
            try:
                self.simulator.u_send(data)  # send data
                ack = self.simulator.u_receive()  # receive ACK
                self.logger.info("Got ACK from socket: {}".format(
                    ack.decode('ascii')))  # note that ASCII will only decode bytes in the range 0-127
                break
            except socket.timeout:
                pass


class OurSender(BogoSender):

    def __init__(self, max_segment_size=959, timeout=0.01):
        super(OurSender, self).__init__()
        self.MSS = max_segment_size
        self.timeout = timeout
        self.simulator.sndr_socket.settimeout(self.timeout)
        self.simulator.rcvr_socket.settimeout(self.timeout)

    # produce a checksum value
    @staticmethod
    def checksum(data):
        return hashlib.md5(data).hexdigest()

    def send(self, data):
        self.logger.info(
            "Sending on port: {} and waiting for ACK on port: {}".format(self.outbound_port, self.inbound_port))
        # initialize parameters
        start = 0
        resend = False
        send_array = None
        sequence_number = 0
        previous_checksum = bytearray([0 for _ in range(32)])
        while True:
            try:
                # 0:32 - md5
                # 32:64 - previous md5
                # 64 - sequence_number
                # 65: - data
                # include previous checksum because in some instances MAX_SEQUENCE_NUMBER packets were dropped in a row
                # can alternatively include checksum in ACK
                if not resend:
                    # send a new packet
                    send_array = bytearray([sequence_number])
                    sequence_number = (sequence_number + 1) % MAX_SEQUENCE_NUMBER
                    send_array += data[start:start+self.MSS]
                    send_array = previous_checksum + send_array
                    checksum = self.checksum(send_array)
                    send_array = checksum + send_array
                    previous_checksum = checksum
                    start += self.MSS
                    self.simulator.u_send(send_array)
                else:
                    # send previous packet
                    self.simulator.u_send(send_array)

                ack = self.simulator.u_receive()
                # check the checksum of the ACK
                if self.checksum(ack[32:]) == ack[0:32]:
                    if ack[32] == sequence_number:
                        if start >= len(data):
                            break
                        resend = False
                    else:
                        resend = True
                else:
                    resend = True
            except socket.timeout:
                resend = True


if __name__ == "__main__":
    # test out BogoSender
    DATA = bytearray(sys.stdin.read())
    # sndr = BogoSender()
    # sndr.send(DATA)
    # use OurSender
    sndr = OurSender()
    sndr.send(DATA)
