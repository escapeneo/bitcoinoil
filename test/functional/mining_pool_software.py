#!/usr/bin/env python3
# Copyright (c) 2026 The BitcoinOil Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Replay the daemon calls of common pool software across the ASERT + MWEB fork.

Mainnet stopped at the block before activation (157499) because 25.3.1
answered the template request of a YIIMP pool with an error, and YIIMP then
stopped asking for aux work. This test sends the exact requests that pool
software sends, taken from its source, at every height around activation,
and mines a block through each path.

- YIIMP (tpruvot/yiimp, stratum/coind_template.cpp): getblocktemplate
  [{"rules":["segwit"]}], requires "transactions" and, for an aux coin,
  "coinbaseaux"; then getauxblock, reads chainid, target and hash, and submits
  with getauxblock <hash> <auxpow>.
- NOMP (node-stratum-pool, lib/pool.js): validateaddress, getdifficulty,
  getmininginfo, submitblock without arguments (to detect the method),
  getblockchaininfo, getnetworkinfo; getblocktemplate with capabilities and
  the segwit rule.
- Miningcore (BitcoinJobManagerBase.GetBlockTemplateParams):
  getblocktemplate {"rules":["segwit"]}.
- Pools on createauxblock / submitauxblock.
"""
import os
import sys

from test_framework.test_framework import BitcoinOilTestFramework
from test_framework.util import assert_equal

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'contrib', 'auxpow'))
from activation_regtest import solve_aux  # noqa: E402

ACTIVATION = 432
YIIMP_GBT = [{"rules": ["segwit"]}]
NOMP_GBT = [{"capabilities": ["coinbasetxn", "workid", "coinbase/append"], "rules": ["segwit"]}]
MININGCORE_GBT = [{"rules": ["segwit"]}]


class MiningPoolSoftwareTest(BitcoinOilTestFramework):
    def add_options(self, parser):
        self.add_wallet_options(parser)

    def set_test_params(self):
        self.setup_clean_chain = True
        self.num_nodes = 2
        self.extra_args = [['-whitelist=noban@127.0.0.1', f'-asertheight={ACTIVATION}']] * 2

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()

    def check_templates(self, node):
        """Every pool's template request must succeed and carry what it reads."""
        height = node.getblockcount() + 1
        for name, params in (("YIIMP", YIIMP_GBT), ("NOMP", NOMP_GBT), ("Miningcore", MININGCORE_GBT)):
            gbt = node.getblocktemplate(*params)
            assert_equal(gbt['height'], height)
            assert isinstance(gbt['transactions'], list), name
            assert isinstance(gbt['coinbaseaux'], dict), name
            assert '!segwit' in gbt['rules'], name  # same spelling as Bitcoin Core
            assert 'default_witness_commitment' in gbt, name
            if height >= ACTIVATION:
                assert 'mweb' in gbt['rules'], name
                assert 'mweb' in gbt, name

    def nomp_startup(self, node):
        node.validateaddress(self.payout)
        node.getdifficulty()
        node.getmininginfo()
        node.getblockchaininfo()
        node.getnetworkinfo()
        try:
            node.submitblock()
        except Exception as e:
            # NOMP only needs the method to exist.
            assert 'Method not found' not in str(e), e

    def mine_yiimp(self, node):
        self.check_templates(node)
        work = node.getauxblock()
        for field in ('chainid', 'target', 'hash'):
            assert field in work, field
        assert_equal(work['chainid'], 2828)
        proof = solve_aux(work['hash'], int.from_bytes(bytes.fromhex(work['_target']), 'little'))
        assert_equal(node.getauxblock(work['hash'], proof), True)
        assert_equal(node.getbestblockhash(), work['hash'])

    def mine_createauxblock(self, node):
        self.check_templates(node)
        work = node.createauxblock(self.payout)
        proof = solve_aux(work['hash'], int.from_bytes(bytes.fromhex(work['_target']), 'little'))
        assert_equal(node.submitauxblock(work['hash'], proof), True)
        assert_equal(node.getbestblockhash(), work['hash'])

    def run_test(self):
        node, peer = self.nodes
        self.payout = node.getnewaddress()
        self.nomp_startup(node)

        self.log.info("Mine to three blocks before activation")
        self.generate(node, ACTIVATION - 4)

        self.log.info("YIIMP mines every block from H-3 to H+3, polling stale work in between")
        for _ in range(7):
            node.getauxblock()
            self.mine_yiimp(node)
            self.nomp_startup(node)
        assert_equal(node.getblockcount(), ACTIVATION + 3)
        block = node.getblock(node.getblockhash(ACTIVATION), 2)
        assert 'mweb' in block
        assert_equal(block['tx'][-1]['vin'], [])
        self.sync_blocks()

        self.log.info("createauxblock pools and YIIMP alternate after activation")
        self.mine_createauxblock(peer)
        self.sync_blocks()
        self.mine_yiimp(node)
        self.sync_blocks()
        assert_equal(peer.getbestblockhash(), node.getbestblockhash())


if __name__ == '__main__':
    MiningPoolSoftwareTest().main()
