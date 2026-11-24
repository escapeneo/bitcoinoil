#!/usr/bin/env python3
# Copyright (c) 2026 The BitcoinOil Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Merge-mining work is renewed after 20 minutes, even with an empty mempool.

On mainnet, pools mined hours-old work because nothing changed in the mempool.
The block then carried the time at which the work was first created, and ASERT
lowered the difficulty one block late. Work must not change more often than
needed: YIIMP submits the newest hash with a proof for an older one."""
import os
import sys

from test_framework.test_framework import BitcoinOilTestFramework
from test_framework.util import assert_equal, assert_raises_rpc_error

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'contrib', 'auxpow'))
from activation_regtest import solve_aux  # noqa: E402

ACTIVATION = 432


class AuxpowWorkTimeTest(BitcoinOilTestFramework):
    def add_options(self, parser):
        self.add_wallet_options(parser)

    def set_test_params(self):
        self.setup_clean_chain = True
        self.num_nodes = 1
        self.extra_args = [[f'-asertheight={ACTIVATION}']]  # MWEB activates there as well

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()

    def submit(self, work):
        proof = solve_aux(work['hash'], int.from_bytes(bytes.fromhex(work['_target']), 'little'))
        assert_equal(self.nodes[0].submitauxblock(work['hash'], proof), True)
        return self.nodes[0].getblockheader(work['hash'])['time']

    def run_test(self):
        node = self.nodes[0]
        addr, addr2 = node.getnewaddress(), node.getnewaddress()
        self.generate(node, ACTIVATION + 2)
        now = node.getblockheader(node.getbestblockhash())['time'] + 100
        node.setmocktime(now)

        self.log.info("Work stays the same for 20 minutes, then is renewed without any mempool change")
        work = node.createauxblock(addr)
        node.setmocktime(now + 30)
        other = node.createauxblock(addr2)  # the age counts for each script
        for wait in (30, 600, 1200):
            node.setmocktime(now + wait)
            assert_equal(node.createauxblock(addr)['hash'], work['hash'])
            assert_equal(node.createauxblock(addr2)['hash'], other['hash'])
        now += 1201
        node.setmocktime(now)
        new = node.createauxblock(addr)
        assert new['hash'] != work['hash']
        assert_equal(new['bits'], work['bits'])
        assert_equal(node.createauxblock(addr)['hash'], new['hash'])
        assert_equal(node.createauxblock(addr2)['hash'], other['hash'])
        node.setmocktime(now + 30)
        assert node.createauxblock(addr2)['hash'] != other['hash']
        assert_equal(node.createauxblock(addr)['hash'], new['hash'])

        self.log.info("New transactions do not renew it earlier, and are included at the next renewal")
        txid = node.sendtoaddress(node.getnewaddress(), 1)
        for wait in (61, 600, 1200):
            node.setmocktime(now + wait)
            assert_equal(node.createauxblock(addr)['hash'], new['hash'])
        now += 1201
        node.setmocktime(now)
        renewed = node.createauxblock(addr)['hash']
        assert renewed != new['hash']
        assert_equal(node.createauxblock(addr)['hash'], renewed)

        self.log.info("The same holds for getauxblock")
        g1 = node.getauxblock()['hash']
        node.setmocktime(now + 600)
        assert_equal(node.getauxblock()['hash'], g1)
        now += 1201
        node.setmocktime(now)
        assert node.getauxblock()['hash'] != g1

        self.log.info("A block found after a long wait carries a recent time")
        now += 4000
        node.setmocktime(now)
        assert_equal(self.submit(node.createauxblock(addr)), now)
        assert txid in node.getblock(node.getbestblockhash())['tx']

        self.log.info("Older work can be submitted while the tip does not change")
        work = node.createauxblock(addr)
        node.setmocktime(now + 1300)
        assert node.createauxblock(addr)['hash'] != work['hash']
        node.setmocktime(now + 5000)
        new = node.createauxblock(addr)
        assert_equal(new['bits'], work['bits'])  # ASERT bits depend on the tip only
        assert_equal(self.submit(work), now)
        assert 'mweb' in node.getblock(work['hash'], 2)

        self.log.info("Work for the old tip is dropped")
        node.createauxblock(addr)
        assert_raises_rpc_error(-8, "block hash unknown", node.submitauxblock, new['hash'], '00')


if __name__ == '__main__':
    AuxpowWorkTimeTest().main()
