#!/usr/bin/env python3
# Copyright (c) 2026 The BitcoinOil Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Pure-Python BLAKE3 (unkeyed, 32-byte output) for the MWEB tests.

Used when the optional 'blake3' package is not installed. Slow, test use only."""
import struct

IV = [0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A, 0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19]
PERM = [2, 6, 3, 10, 7, 0, 4, 13, 1, 11, 12, 5, 9, 14, 15, 8]
CHUNK_START, CHUNK_END, PARENT, ROOT = 1, 2, 4, 8
M = 0xFFFFFFFF


def _rotr(x, n):
    return ((x >> n) | (x << (32 - n))) & M


def _g(s, a, b, c, d, mx, my):
    s[a] = (s[a] + s[b] + mx) & M
    s[d] = _rotr(s[d] ^ s[a], 16)
    s[c] = (s[c] + s[d]) & M
    s[b] = _rotr(s[b] ^ s[c], 12)
    s[a] = (s[a] + s[b] + my) & M
    s[d] = _rotr(s[d] ^ s[a], 8)
    s[c] = (s[c] + s[d]) & M
    s[b] = _rotr(s[b] ^ s[c], 7)


def _compress(cv, block, counter, block_len, flags):
    m = list(struct.unpack("<16I", block))
    s = cv[:8] + IV[:4] + [counter & M, (counter >> 32) & M, block_len, flags]
    for r in range(7):
        _g(s, 0, 4, 8, 12, m[0], m[1])
        _g(s, 1, 5, 9, 13, m[2], m[3])
        _g(s, 2, 6, 10, 14, m[4], m[5])
        _g(s, 3, 7, 11, 15, m[6], m[7])
        _g(s, 0, 5, 10, 15, m[8], m[9])
        _g(s, 1, 6, 11, 12, m[10], m[11])
        _g(s, 2, 7, 8, 13, m[12], m[13])
        _g(s, 3, 4, 9, 14, m[14], m[15])
        if r < 6:
            m = [m[i] for i in PERM]
    return [s[i] ^ s[i + 8] for i in range(8)]


def _chunk_cv(chunk, counter, root):
    cv = IV[:]
    blocks = [chunk[i:i + 64] for i in range(0, len(chunk), 64)] or [b""]
    for i, b in enumerate(blocks):
        flags = (CHUNK_START if i == 0 else 0) | (CHUNK_END if i == len(blocks) - 1 else 0)
        if root and i == len(blocks) - 1:
            flags |= ROOT
        cv = _compress(cv, b.ljust(64, b"\x00"), counter, len(b), flags)
    return cv


def _subtree_cv(chunks, first, root):
    n = len(chunks)
    if n == 1:
        return _chunk_cv(chunks[0], first, root)
    left = 1 << ((n - 1).bit_length() - 1)
    block = struct.pack("<16I", *(_subtree_cv(chunks[:left], first, False) + _subtree_cv(chunks[left:], first + left, False)))
    return _compress(IV[:], block, 0, 64, PARENT | (ROOT if root else 0))


class blake3:
    def __init__(self, data=b""):
        self._data = bytes(data)

    def digest(self):
        chunks = [self._data[i:i + 1024] for i in range(0, len(self._data), 1024)] or [b""]
        return struct.pack("<8I", *_subtree_cv(chunks, 0, True))

    def hexdigest(self):
        return self.digest().hex()
