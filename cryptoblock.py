#!/usr/bin/env python
# -*- coding: utf-8 -*-


def Xor(buf):
    cccam = "CCcam"
    for i in range(0, 8):
        buf[8 + i] = 0xFF & (i * buf[i])
        if i < 5:
            buf[i] ^= ord(cccam[i])
    return buf


class CryptographicBlock(object):
    """"""

    def __init__(self, key, length):
        self._counter = 0
        self._sum = 0
        self._state = key[0]

        self._keytable = [x for x in range(0, 256)]
        j = 0
        for i in range(0, 256):
            j = 0xFF & (j + key[i % length] + self._keytable[i])
            self._keytable[i], self._keytable[j] = \
                self._keytable[j], self._keytable[i]

    def decrypt(self, data, length):
        """"""

        for i in range(0, length):
            self._counter = 0xFF & (self._counter + 1)
            self._sum = self._sum + self._keytable[self._counter]

            # Swapping values of keytable[counter] with keytable[sum]
            self._keytable[self._counter], self._keytable[self._sum & 0xFF] = \
                self._keytable[self._sum & 0xFF], self._keytable[self._counter]

            z = data[i]
            data[i] = z ^ self._keytable[  # ^ = xor
                (
                    self._keytable[self._counter] +  # Note the missing & 0xFF
                    self._keytable[self._sum & 0xFF]
                ) & 0xFF
            ] ^ self._state

            z = data[i]  # Why?
            self._state = 0xFF & (self._state ^ z)

    def encrypt(self, data, length):
        """"""

        for i in range(0, length):
            self._counter = 0xFF & (self._counter + 1)
            self._sum = self._sum + self._keytable[self._counter]

            # Swapping values of keytable[counter] with keytable[sum]
            self._keytable[self._counter], self._keytable[self._sum & 0xFF] = \
                self._keytable[self._sum & 0xFF], self._keytable[self._counter]

            z = data[i]
            data[i] = z ^ self._keytable[  # ^ = xor
                (
                    self._keytable[self._counter & 0xFF] +
                    self._keytable[self._sum & 0xFF]
                ) & 0xFF
            ] ^ self._state

            self._state = 0xFF & (self._state ^ z)
