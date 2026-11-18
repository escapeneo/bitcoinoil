#!/usr/bin/env python3
# Copyright (c) 2026 The BitcoinOil Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""AuxPoW, MWEB and ASERT active together, in both activation orders.

Nodes 0 and 1 activate ASERT after MWEB, nodes 2 and 3 before it, nodes 4 and
5 in the same block. Each pair
merge-mines MWEB blocks across both activations, checks that the difficulty
moves under ASERT, reindexes and reorgs across both heights."""
import os
import sys
from decimal import Decimal

from test_framework.test_framework import BitcoinOilTestFramework
from test_framework.util import assert_equal

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'contrib', 'auxpow'))
from activation_regtest import solve_aux  # noqa: E402

MWEB_HEIGHT = 432
ASERT_AFTER = 436
ASERT_BEFORE = 425
ASERT_SAME = MWEB_HEIGHT
LAST_HEIGHT = 446


class MWEBAuxpowAsertTest(BitcoinOilTestFramework):
    def add_options(self, parser):
        self.add_wallet_options(parser)

    def set_test_params(self):
        self.setup_clean_chain = True
        self.num_nodes = 6
        common = ['-whitelist=noban@127.0.0.1', '-aserthalflife=3600']
        self.extra_args = [common + [f'-asertheight={ASERT_AFTER}']] * 2 + [common + [f'-asertheight={ASERT_BEFORE}']] * 2 + [common + [f'-asertheight={ASERT_SAME}']] * 2

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()

    def setup_network(self):
        self.setup_nodes()
        self.connect_nodes(0, 1)
        self.connect_nodes(2, 3)
        self.connect_nodes(4, 5)

    def mine_aux(self, node, peer):
        work = node.createauxblock(node.getnewaddress())
        proof = solve_aux(work['hash'], int.from_bytes(bytes.fromhex(work['_target']), 'little'))
        assert_equal(node.submitauxblock(work['hash'], proof), True)
        assert_equal(node.getbestblockhash(), work['hash'])
        self.sync_blocks([node, peer])
        return node.getblock(work['hash'], 2)

    def mine_to(self, node, peer, height):
        """Alternate plain and merge-mined blocks up to a height."""
        while node.getblockcount() < height:
            if node.getblockcount() % 2:
                self.mine_aux(node, peer)
            else:
                self.generate(node, 1, sync_fun=lambda: self.sync_blocks([node, peer]))

    def run_pair(self, node, peer, asert_height):
        pair = [node, peer]
        self.generate(node, min(MWEB_HEIGHT, asert_height) - 2, sync_fun=lambda: self.sync_blocks(pair))

        self.log.info("  cross both activation heights with alternating plain and merge-mined blocks")
        self.mine_to(node, peer, MWEB_HEIGHT - 1)
        block = self.mine_aux(node, peer)
        assert_equal(block['height'], MWEB_HEIGHT)
        assert_equal(block['tx'][-1]['vin'], [])
        self.mine_to(node, peer, max(MWEB_HEIGHT, asert_height) + 1)

        self.log.info("  peg in, send MWEB to MWEB and peg out with all three rules active")
        node.sendtoaddress(node.getnewaddress(address_type='mweb'), 10)
        self.sync_mempools(pair)
        block = self.mine_aux(node, peer)
        assert block['tx'][-1]['vout'][0]['value'] >= Decimal('10')
        node.sendtoaddress(peer.getnewaddress(address_type='mweb'), 3)
        self.sync_mempools(pair)
        self.mine_aux(node, peer)
        self.wait_until(lambda: peer.getbalance() == Decimal('3'))
        peer.sendtoaddress(node.getnewaddress(), 1)
        self.sync_mempools(pair)
        block = self.mine_aux(node, peer)
        assert len(block['tx'][-1]['vout']) >= 2
        self.mine_to(node, peer, LAST_HEIGHT)

        self.log.info("  ASERT moves the target, and both nodes agree on it")
        before = node.getblockheader(node.getblockhash(asert_height - 1))['bits']
        after = node.getblockheader(node.getblockhash(LAST_HEIGHT))['bits']
        assert before != after, "blocks mined seconds apart must raise the difficulty under ASERT"
        tip = node.getbestblockhash()
        assert_equal(peer.getbestblockhash(), tip)
        assert_equal(peer.getblockheader(tip)['bits'], after)

        self.log.info("  reorg across both activation heights")
        fork_hash = node.getblockhash(min(MWEB_HEIGHT, asert_height) - 1)
        node.invalidateblock(fork_hash)
        assert_equal(node.getblockcount(), min(MWEB_HEIGHT, asert_height) - 2)
        node.reconsiderblock(fork_hash)
        self.wait_until(lambda: node.getbestblockhash() == tip)
        return tip

    def run_test(self):
        self.log.info("ASERT activates after MWEB")
        tip_a = self.run_pair(self.nodes[0], self.nodes[1], ASERT_AFTER)
        self.log.info("ASERT activates before MWEB")
        tip_b = self.run_pair(self.nodes[2], self.nodes[3], ASERT_BEFORE)

        self.log.info("ASERT and MWEB activate in the same block")
        tip_c = self.run_pair(self.nodes[4], self.nodes[5], ASERT_SAME)

        self.log.info("Reindex every node and compare tips")
        for i, tip in enumerate([tip_a, tip_a, tip_b, tip_b, tip_c, tip_c]):
            self.restart_node(i, extra_args=self.extra_args[i] + ['-reindex'])
            self.wait_until(lambda: self.nodes[i].getblockcount() == LAST_HEIGHT)
            assert_equal(self.nodes[i].getbestblockhash(), tip)


if __name__ == '__main__':
    MWEBAuxpowAsertTest().main()
