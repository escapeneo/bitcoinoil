#!/usr/bin/env python3
# Copyright (c) 2017-2022 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Test wallet replace-by-fee capabilities in conjunction with the fallbackfee."""

from test_framework.blocktools import COINBASE_MATURITY
from test_framework.test_framework import BitcoinOilTestFramework
from test_framework.util import assert_equal, assert_raises_rpc_error

class WalletRBFTest(BitcoinOilTestFramework):
    def add_options(self, parser):
        self.add_wallet_options(parser)

    def set_test_params(self):
        self.num_nodes = 1
        self.setup_clean_chain = True

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()

    def run_test(self):
        self.generate(self.nodes[0], COINBASE_MATURITY + 1)

        # sending a transaction without fee estimations must be possible by default on regtest
        self.nodes[0].sendtoaddress(self.nodes[0].getnewaddress(), 1)

        # the default must also allow it, without -fallbackfee in the configuration
        self.nodes[0].replace_in_config([("fallbackfee=0.0002\n", "")])
        self.restart_node(0)
        assert_equal(self.nodes[0].estimatesmartfee(6).get('feerate'), None)
        txid = self.nodes[0].sendtoaddress(self.nodes[0].getnewaddress(), 1)
        entry = self.nodes[0].getmempoolentry(txid)
        # 10 sat/vB, give or take the signature size
        feerate = entry['fees']['base'] * 100000000 / entry['vsize']
        assert 9.5 < feerate < 10.5, feerate

        # test sending a tx with disabled fallback fee (must fail)
        self.restart_node(0, extra_args=["-fallbackfee=0"])
        assert_raises_rpc_error(-6, "Fee estimation failed", lambda: self.nodes[0].sendtoaddress(self.nodes[0].getnewaddress(), 1))
        assert_raises_rpc_error(-4, "Fee estimation failed", lambda: self.nodes[0].fundrawtransaction(self.nodes[0].createrawtransaction([], {self.nodes[0].getnewaddress(): 1})))
        assert_raises_rpc_error(-6, "Fee estimation failed", lambda: self.nodes[0].sendmany("", {self.nodes[0].getnewaddress(): 1}))

if __name__ == '__main__':
    WalletRBFTest().main()
