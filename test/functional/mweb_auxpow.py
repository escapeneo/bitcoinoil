#!/usr/bin/env python3
# Copyright (c) 2026 The BitcoinOil Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Merge-mined (AuxPoW) blocks carry the MWEB extension block and HogEx.

Every block from the activation block on is mined with createauxblock /
submitauxblock (or getauxblock), relayed to a second node, and survives a
reindex."""
import os
import sys
from decimal import Decimal

from test_framework.test_framework import BitcoinOilTestFramework
from test_framework.util import assert_equal

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'contrib', 'auxpow'))
from activation_regtest import solve_aux  # noqa: E402

ACTIVATION = 432


class MWEBAuxpowTest(BitcoinOilTestFramework):
    def add_options(self, parser):
        self.add_wallet_options(parser)

    def set_test_params(self):
        self.setup_clean_chain = True
        self.num_nodes = 2
        self.extra_args = [['-whitelist=noban@127.0.0.1']] * 2

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()

    def mine_aux(self, node, use_getauxblock=False):
        if use_getauxblock:
            work = node.getauxblock()
        else:
            work = node.createauxblock(self.payout)
        proof = solve_aux(work['hash'], int.from_bytes(bytes.fromhex(work['_target']), 'little'))
        if use_getauxblock:
            assert_equal(node.getauxblock(work['hash'], proof), True)
        else:
            assert_equal(node.submitauxblock(work['hash'], proof), True)
        assert_equal(node.getbestblockhash(), work['hash'])
        self.sync_blocks()
        block = node.getblock(work['hash'], 2)
        assert 'auxpow' in block
        assert_equal(block['version'] >> 16, 0x0B0C)
        return block

    def run_test(self):
        node, peer = self.nodes
        self.payout = node.getnewaddress()

        self.log.info("Mine up to the block before activation")
        self.generate(node, ACTIVATION - 1)

        self.log.info("The activation block is merge-mined, with an empty HogEx")
        block = self.mine_aux(node)
        assert_equal(block['height'], ACTIVATION)
        hogex = block['tx'][-1]
        assert_equal(hogex['vin'], [])
        assert_equal(hogex['vout'][0]['value'], Decimal('0'))
        assert 'mweb' in block

        self.log.info("A peg-in is merge-mined")
        mweb_addr = node.getnewaddress(address_type='mweb')
        pegin_txid = node.sendtoaddress(mweb_addr, 10)
        self.sync_mempools()
        block = self.mine_aux(node)
        assert pegin_txid in [tx['txid'] for tx in block['tx']]
        assert block['tx'][-1]['vout'][0]['value'] >= Decimal('10')
        assert_equal(node.gettransaction(pegin_txid)['confirmations'], 1)

        self.log.info("An MWEB to MWEB transaction and a peg-out are merge-mined through getauxblock")
        peer_mweb = peer.getnewaddress(address_type='mweb')
        node.sendtoaddress(peer_mweb, 3)
        self.sync_mempools()
        self.mine_aux(node, use_getauxblock=True)
        self.wait_until(lambda: peer.getbalance() == Decimal('3'))
        peer.sendtoaddress(node.getnewaddress(), 1)
        self.sync_mempools()
        block = self.mine_aux(node, use_getauxblock=True)
        assert len(block['tx'][-1]['vout']) >= 2  # HogAddr plus the peg-out

        self.log.info("The second node can merge-mine on top")
        self.payout = peer.getnewaddress()
        self.mine_aux(peer)
        assert_equal(node.getbestblockhash(), peer.getbestblockhash())

        self.log.info("Plain and merge-mined blocks alternate")
        self.generate(node, 2)
        self.payout = node.getnewaddress()
        self.mine_aux(node)

        self.log.info("Reindex both nodes and compare")
        tip = node.getbestblockhash()
        height = node.getblockcount()
        for i in range(2):
            self.restart_node(i, extra_args=['-reindex', '-whitelist=noban@127.0.0.1'])
            self.wait_until(lambda: self.nodes[i].getblockcount() == height)
            assert_equal(self.nodes[i].getbestblockhash(), tip)
        self.connect_nodes(0, 1)

        self.log.info("Reorg a merge-mined MWEB block out and back")
        node.invalidateblock(tip)
        assert_equal(node.getblockcount(), height - 1)
        node.reconsiderblock(tip)
        self.wait_until(lambda: node.getbestblockhash() == tip)


if __name__ == '__main__':
    MWEBAuxpowTest().main()
