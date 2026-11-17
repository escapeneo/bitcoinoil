#!/usr/bin/env python3
# Copyright (c) 2026 The BitcoinOil Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""MWEB activates without a peg-in: the first HogEx has no inputs.

Litecoin stalls at the activation height until a peg-in is mined. BitcoinOil
lets the first MWEB block carry an empty HogEx instead."""
from decimal import Decimal

from test_framework.test_framework import BitcoinOilTestFramework
from test_framework.util import assert_equal, assert_raises_rpc_error

ACTIVATION = 432


class MWEBEmptyFirstHogExTest(BitcoinOilTestFramework):
    def add_options(self, parser):
        self.add_wallet_options(parser)

    def set_test_params(self):
        self.setup_clean_chain = True
        self.num_nodes = 2
        self.extra_args = [['-whitelist=noban@127.0.0.1']] * 2

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()

    def hogex(self, node, height):
        block = node.getblock(node.getblockhash(height), 2)
        return block, block['tx'][-1]

    def run_test(self):
        node, peer = self.nodes

        self.log.info("The wallet refuses MWEB transactions while a peg-in could still be mined unprotected")
        self.generate(node, ACTIVATION - 2)
        mweb_addr = node.getnewaddress(address_type='mweb')
        assert_raises_rpc_error(-6, "MWEB is not active yet", node.sendtoaddress, mweb_addr, 1)
        assert_equal(node.getrawmempool(), [])

        self.log.info("Mine up to the last block before activation, with an empty mempool")
        self.generate(node, 1)
        assert_equal(node.getrawmempool(), [])
        block, last = self.hogex(node, ACTIVATION - 1)
        assert_equal(len(block['tx']), 1)

        self.log.info("The activation block is mined without any peg-in")
        self.generate(node, 1)
        assert_equal(node.getblockcount(), ACTIVATION)
        block, hogex = self.hogex(node, ACTIVATION)
        assert_equal(len(block['tx']), 2)
        assert_equal(hogex['vin'], [])
        assert_equal(len(hogex['vout']), 1)
        assert_equal(hogex['vout'][0]['value'], Decimal('0'))
        first_hogex_txid = hogex['txid']

        self.log.info("The next block spends the empty HogEx")
        self.generate(node, 1)
        block, hogex = self.hogex(node, ACTIVATION + 1)
        assert_equal([(i['txid'], i['vout']) for i in hogex['vin']], [(first_hogex_txid, 0)])
        assert_equal(hogex['vout'][0]['value'], Decimal('0'))

        self.log.info("A peg-in after activation works and both nodes agree")
        mweb_addr = node.getnewaddress(address_type='mweb')
        node.sendtoaddress(mweb_addr, 10)
        self.sync_mempools()
        self.generate(node, 1)
        block, hogex = self.hogex(node, ACTIVATION + 2)
        assert_equal(len(hogex['vin']), 2)
        # The wallet may peg its change in too.
        assert hogex['vout'][0]['value'] >= Decimal('10')
        assert_equal(peer.getbestblockhash(), node.getbestblockhash())

        self.log.info("Send MWEB to MWEB and peg out")
        node.sendtoaddress(node.getnewaddress(address_type='mweb'), 3)
        self.generate(node, 1)
        node.sendtoaddress(node.getnewaddress(), 2)
        self.generate(node, 1)
        assert_equal(peer.getbestblockhash(), node.getbestblockhash())

        self.log.info("createauxblock still hands out work after activation")
        work = node.createauxblock(node.getnewaddress())
        assert_equal(work['height'], node.getblockcount() + 1)

        self.log.info("The chain survives a restart and a full reindex")
        tip = node.getbestblockhash()
        self.restart_node(0, extra_args=['-reindex', '-whitelist=noban@127.0.0.1'])
        self.wait_until(lambda: node.getblockcount() == ACTIVATION + 4)
        assert_equal(node.getbestblockhash(), tip)

        self.log.info("Reorg across the activation block")
        node.invalidateblock(node.getblockhash(ACTIVATION))
        assert_equal(node.getblockcount(), ACTIVATION - 1)
        node.reconsiderblock(tip)
        self.wait_until(lambda: node.getbestblockhash() == tip)


if __name__ == '__main__':
    MWEBEmptyFirstHogExTest().main()
