#!/usr/bin/env python3
# Copyright (c) 2026 The BitcoinOil Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Wallet behaviour BitcoinOil keeps from Bitcoin Core 25 after the MWEB port."""
from test_framework.test_framework import BitcoinOilTestFramework
from test_framework.util import assert_equal, assert_raises_rpc_error


class WalletBTCODefaultsTest(BitcoinOilTestFramework):
    def add_options(self, parser):
        self.add_wallet_options(parser)

    def set_test_params(self):
        self.setup_clean_chain = True
        self.num_nodes = 1

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()

    def run_test(self):
        node = self.nodes[0]
        self.generate(node, 101)
        addr = node.getnewaddress()

        self.log.info("listunspent lists immature coinbases only on request")
        assert_equal(len(node.listunspent()), 1)
        assert_equal(len(node.listunspent(query_options={"include_immature_coinbase": True})), 101)

        self.log.info("add_inputs=false adds no inputs, also when none were given")
        assert_raises_rpc_error(-4, "Insufficient funds", node.walletcreatefundedpsbt, [], [{addr: 1}], 0, {"add_inputs": False})
        raw = node.createrawtransaction([], [{addr: 1}])
        assert_raises_rpc_error(-4, "Insufficient funds", node.fundrawtransaction, raw, {"add_inputs": False})

        self.log.info("Transparent PSBTs default to version 0; version 2 stays available")
        psbt = node.walletcreatefundedpsbt([], [{addr: 1}])["psbt"]
        assert_equal(node.decodepsbt(psbt)["psbt_version"], 0)
        utxo = node.listunspent()[0]
        inputs = [{"txid": utxo["txid"], "vout": utxo["vout"]}]
        assert_equal(node.decodepsbt(node.createpsbt(inputs, [{addr: 1}]))["psbt_version"], 0)
        assert_equal(node.decodepsbt(node.createpsbt(inputs, [{addr: 1}], 0, False, 2))["psbt_version"], 2)

        self.log.info("A version 0 PSBT signs and broadcasts")
        signed = node.walletprocesspsbt(psbt)
        assert signed["complete"]
        node.sendrawtransaction(node.finalizepsbt(signed["psbt"])["hex"])

        self.log.info("Wallet transactions signal replaceability by default")
        txid = node.sendtoaddress(addr, 1)
        assert_equal(node.gettransaction(txid)["bip125-replaceable"], "yes")

        self.log.info("Mining RPCs refuse an MWEB payout address")
        mweb_addr = node.getnewaddress(address_type='mweb')
        assert_raises_rpc_error(-5, "Cannot mine to an MWEB address", node.createauxblock, mweb_addr)


if __name__ == '__main__':
    WalletBTCODefaultsTest().main()
