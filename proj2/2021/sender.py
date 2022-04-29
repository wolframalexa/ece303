# Written by S. Mevawala, modified by D. Gitzel

import logging
import socket

import channelsimulator
import utils
import sys
import hashlib

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
        self.logger.info("Sending on port: {} and waiting for ACK on port: {}".format(self.outbound_port, self.inbound_port))
        while True:
            try:
                self.simulator.u_send(data)  # send data
                ack = self.simulator.u_receive()  # receive ACK
                self.logger.info("Got ACK from socket: {}".format(
                    ack.decode('ascii')))  # note that ASCII will only decode bytes in the range 0-127
                break
            except socket.timeout:
                pass

MAX_SEQUENCE_NUMBER = 256

class mySender(BogoSender):
    def __init__(self, max_segment_size=959, timeout = 0.1):
        super(mySender, self).__init__()
        self.MSS = max_segment_size
        self.timeout = timeout
        self.simulator.sndr_socket.settimeout(self.timeout)
        self.simulator.rcvr_socket.settimeout(self.timeout)

    @staticmethod
    def checksum(data):
        return hashlib.md5(data).hexdigest() # https://stackoverflow.com/questions/16874598/how-do-i-calculate-the-md5-checksum-of-a-file-in-python

    def send(self, data): # override send method from BogoSend
        self.logger.info("Sending on port: {} and waiting for ACK on port: {}".format(self.outbound_port, self.inbound_port))

        i = 0
        resend = False
        packet = None
	seq_num = 0
        last_checksum = bytearray([0 for _ in range(32)])

        while True:
            try:
                if not resend: # create new packet to send
                    # 0:32 checksum, 32:64 previous checksum, 64 sequence num, 65-end data
                    packet = bytearray([seq_num])
                    seq_num = (seq_num + 1) % MAX_SEQUENCE_NUMBER
                    packet += data[i:i+self.MSS]

                    packet = last_checksum + packet
                    checksum = self.checksum(packet)
                    send_array = checksum + packet
                    last_checksum = checksum
                    i += self.MSS
                    self.logger.info("sending packet {}".format(packet))
                    self.simulator.u_send(packet)
                else:
                    self.logger.info("Sending previous packet {}".format(packet))
                    # send previous packet
                    self.simulator.u_send(packet)

                ACK = self.simulator.u_receive()

                # check checksum: handle random bit errors
                self.logger.info("Received ACK: {}".format(ACK))
                self.logger.info(ACK[0:32])
                self.logger.info(self.checksum(ACK[32:]))

                if self.checksum(ACK[32:]) == ACK[0:32]:
                    if ack[32] == seq_num:
                        if i >= len(data): # reached the end of our data
                            break
                        resend = False
                    else:
                        resend = True
                else:
                    resend = True

            except socket.timeout:
                self.logger.info("Timeout on send")
                resend = True

if __name__ == "__main__":
    # test out mySender
    DATA = bytearray(sys.stdin.read())
    sndr = mySender()
    sndr.send(DATA)
