#!/usr/bin/env python
# -*- coding: utf-8 -*-

import array
import hashlib
import logging
import re
import socket

from cryptoblock import CryptographicBlock, Xor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ClineTester(object):
    """"""

    CLINE_REGEX = '[Cc]:[ \t]+([^ \t]+)[ \t]+([0-9]+)[ \t]+([^ \t]+)[ \t]+([^ \t]+)'
    SOCKET_TIMEOUT = 30  # seconds
    REQUEST_TYPE = "CCcam"

    FAIL_INVALID = 'invalid'

    def __init__(self, cline, *args, **kwargs):
        self.cline = cline
        self._receive_block = None
        self._send_block = None

    def handshake(self, socket):
        response = bytearray(16)

        # Receiving the "Hello" response from the server into `response`
        socket.recv_into(response, 16)

        logger.info("Hello byte response: %s " % response)

        # Do a Xor with "CCcam" string to the hello bytes
        response = Xor(response)

        # Creating a sha1 hash with the xor hello bytes
        sha1 = hashlib.sha1()
        sha1.update(response)
        sha1hash = self.get_bytearray(sha1.digest(), 20)

        # Initializing the receive handler
        self._receive_block = CryptographicBlock(sha1hash, 20)
        self._receive_block.decrypt(response, 16)

        # Initializing the send handler
        self._send_block = CryptographicBlock(response, 16)
        self._send_block.decrypt(sha1hash, 20)

        # Sending an encrypted sha1 hash
        n_bytes = self.send_message(sha1hash, socket)

        return n_bytes

    def get_bytearray(self, string, length=None, pad_with=0):
        """Converts a string into a bytearray of fixed length"""

        length = length or len(string)
        arr = array.array("B", string)  # binary array
        b_array = bytearray(length)

        # filling the bytearray with the byte-converted string, up to `lenght`
        n = min([length, len(arr)])
        for i, el in enumerate(arr[:n]):
            b_array[i] = el

        return b_array

    def send_message(self, data, socket):
        """Sending an encrypted message to the server. This is used to transit
        username, password
        """
        self._send_block.encrypt(data, len(data))
        n_bytes = socket.send(data)

        return n_bytes

    def test(self):
        """"""

        logger.info("Testing CLine: %s " % self.cline)

        is_valid = False
        error_msg = ''
        regex = re.compile(self.CLINE_REGEX)

        match = regex.search(self.cline)

        if match is None:
            logger.error("Not avalid CLine: %s " % self.cline)
            return False, "Not a valid CLine."

        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM,
                                    socket.IPPROTO_IP)
        test_socket.settimeout(self.SOCKET_TIMEOUT)

        host, port, username, password = match.groups()
        port = int(port)

        try:
            ip = socket.gethostbyname(host)
            test_socket.connect((ip, port))

            # Trying a handshake with the cccam server, checking if the
            # server is responding 'hello'
            n_bytes = self.handshake(test_socket)

            if n_bytes == 0:
                logger.error("Server responded 0 bytes: %s " % self.cline)
                return False, "Server empty response."

            try:
                username_b_array = self.get_bytearray(username, 20)
                self.send_message(username_b_array, test_socket)

                password_b_array = self.get_bytearray(password, len(password))
                self._send_block.encrypt(password_b_array,
                                         len(password_b_array))

                # Sending 'CCcam' string together with the encrypted password
                # in the same block
                cccam_b_array = self.get_bytearray(self.REQUEST_TYPE, 6)
                self.send_message(cccam_b_array, test_socket)

                # Getting the response to out username + password + 'CCcam'
                # request
                response = bytearray(20)
                n_bytes = test_socket.recv_into(response, 20)

                if n_bytes > 0:
                    self._receive_block.decrypt(response, 20)
                    if (response.decode("ascii").rstrip('\0') ==
                            self.REQUEST_TYPE):
                        logger.info(
                            "SUCCESS! Working cline: %s" % self.cline)
                        is_valid = True
                    else:
                        logger.error("Wrong ACK: %s " % self.cline)
                        error_msg = "Wrong ACK received."
                else:
                    logger.error("Bad username/password: %s " % self.cline)
                    error_msg = "Bad username/password."

            except socket.error as e:
                logger.exception("%s %s: %s" % (type(e), e.message, self.cline))
                error_msg = "Server connection."
            except Exception as e:
                logger.exception("%s %s: %s" % (type(e), e.message, self.cline))
                error_msg = "Server error."
        except Exception as e:
            logger.exception("%s %s: %s" % (type(e), e.message, self.cline))
            error_msg = "Server error."
        finally:
            test_socket.close()

        return is_valid, error_msg
