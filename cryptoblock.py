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

    """A class that attempts decryption/encryption of cccam server strings.

    This module has been imported from
    https://github.com/gavazquez/CLineTester
    and rewritten in an attempt to make it more readable and understandable.
    Since my knowledge on the subject is basically zero I can't do much
    to explain what this class does.
    """

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
        """Applying *magic* to decrypt cccam server response."""

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
        """Applying more *magic* to encrypt cccam server response."""

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
