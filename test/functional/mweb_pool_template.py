#!/usr/bin/env python3
# Copyright (c) 2026 The BitcoinOil Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Build blocks from getblocktemplate the way a pool does, byte by byte.

The block is assembled from the template's hex fields only, without the test
framework's block classes, so this documents the exact format a pool has to
submit across MWEB activation:

    header | tx count | coinbase | template transactions | 01 | template "mweb"
"""
import hashlib
import struct

from test_framework.blocktools import create_coinbase
from test_framework.messages import CTxInWitness, CTxOut, ser_compact_size
from test_framework.test_framework import BitcoinOilTestFramework
from test_framework.util import assert_equal

ACTIVATION = 432


def sha256d(data):
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def merkle_root(txids):
    layer = [bytes.fromhex(t)[::-1] for t in txids]
    while len(layer) > 1:
        if len(layer) % 2:
            layer.append(layer[-1])
        layer = [sha256d(layer[i] + layer[i + 1]) for i in range(0, len(layer), 2)]
    return layer[0]


class MWEBPoolTemplateTest(BitcoinOilTestFramework):
    def add_options(self, parser):
        self.add_wallet_options(parser)

    def set_test_params(self):
        self.setup_clean_chain = True
        self.num_nodes = 2
        self.extra_args = [['-whitelist=noban@127.0.0.1']] * 2

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()

    def build(self, gbt, *, with_mweb):
        """Return the block as hex, built only from template fields."""
        coinbase = create_coinbase(height=gbt['height'])
        coinbase.vout[0].nValue = gbt['coinbasevalue']
        if 'default_witness_commitment' in gbt:
            coinbase.vout.append(CTxOut(0, bytes.fromhex(gbt['default_witness_commitment'])))
            coinbase.wit.vtxinwit = [CTxInWitness()]
            coinbase.wit.vtxinwit[0].scriptWitness.stack = [b'\x00' * 32]
        coinbase.rehash()

        root = merkle_root([coinbase.hash] + [tx['txid'] for tx in gbt['transactions']])
        target = int(gbt['target'], 16)
        nonce = 0
        while True:
            header = struct.pack('<i', gbt['version'])
            header += bytes.fromhex(gbt['previousblockhash'])[::-1]
            header += root
            header += struct.pack('<III', gbt['curtime'], int(gbt['bits'], 16), nonce)
            if int.from_bytes(sha256d(header), 'little') <= target:
                break
            nonce += 1

        block = header
        block += ser_compact_size(1 + len(gbt['transactions']))
        block += coinbase.serialize_with_witness()
        for tx in gbt['transactions']:
            block += bytes.fromhex(tx['data'])
        if with_mweb:
            block += b'\x01' + bytes.fromhex(gbt['mweb'])
        return block.hex()

    def run_test(self):
        node, peer = self.nodes
        self.generate(node, ACTIVATION - 2)

        self.log.info("Last block before activation: the old request and the old format still work")
        gbt = node.getblocktemplate({'rules': ['segwit']})
        assert 'mweb' not in gbt
        assert 'mweb' not in gbt['rules']
        assert_equal(node.submitblock(self.build(gbt, with_mweb=False)), None)
        assert_equal(node.getblockcount(), ACTIVATION - 1)

        self.log.info("Activation block: a request without the mweb rule still gets a template")
        # Merge-mining pool software (YIIMP) probes getblocktemplate like this for
        # every coin before it asks for aux work; an error here stopped mainnet.
        probe = node.getblocktemplate({'rules': ['segwit']})
        assert_equal(probe['height'], ACTIVATION)
        assert 'mweb' in probe['rules']
        assert 'mweb' in probe
        aux = node.createauxblock(node.getnewaddress())
        assert_equal(aux['height'], ACTIVATION)
        gbt = node.getblocktemplate({'rules': ['mweb', 'segwit']})
        assert_equal(gbt['mweb'], probe['mweb'])
        assert_equal(gbt['height'], ACTIVATION)
        assert 'mweb' in gbt['rules']
        # The only template transaction is the HogEx, which has no inputs here.
        assert_equal(len(gbt['transactions']), 1)

        self.log.info("Activation block without the MWEB part is refused")
        try:
            result = node.submitblock(self.build(gbt, with_mweb=False))
        except Exception as e:
            result = str(e)
        self.log.info("  -> %s", result)
        assert result is not None
        assert_equal(node.getblockcount(), ACTIVATION - 1)

        self.log.info("Activation block with 01 + mweb appended is accepted")
        assert_equal(node.submitblock(self.build(gbt, with_mweb=True)), None)
        assert_equal(node.getblockcount(), ACTIVATION)
        self.sync_blocks()

        self.log.info("Next block: the HogEx spends the previous one")
        gbt = node.getblocktemplate({'rules': ['mweb', 'segwit']})
        assert_equal(len(gbt['transactions']), 1)
        assert_equal(node.submitblock(self.build(gbt, with_mweb=True)), None)

        self.log.info("A block with a peg-in and a normal transaction")
        node.sendtoaddress(node.getnewaddress(address_type='mweb'), 5)
        node.sendtoaddress(node.getnewaddress(), 1)
        gbt = node.getblocktemplate({'rules': ['mweb', 'segwit']})
        assert_equal(len(gbt['transactions']), 3)
        # The HogEx is always the last transaction of the template.
        assert_equal(node.submitblock(self.build(gbt, with_mweb=True)), None)
        assert_equal(node.getblockcount(), ACTIVATION + 2)
        assert_equal(node.getrawmempool(), [])
        self.sync_blocks()
        assert_equal(peer.getbestblockhash(), node.getbestblockhash())

        self.log.info("An MWEB-to-MWEB transaction has no transparent part and is not in the list")
        self.generate(node, 1)
        node.sendtoaddress(node.getnewaddress(address_type='mweb'), 1)
        gbt = node.getblocktemplate({'rules': ['mweb', 'segwit']})
        self.log.info("  -> %d template transaction(s)", len(gbt['transactions']))
        assert_equal(node.submitblock(self.build(gbt, with_mweb=True)), None)
        assert_equal(node.getrawmempool(), [])
        self.sync_blocks()
        assert_equal(peer.getbestblockhash(), node.getbestblockhash())


if __name__ == '__main__':
    MWEBPoolTemplateTest().main()
