#!/usr/bin/env python3
# Copyright (c) 2026 The BitcoinOil Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Upgrade boundary rehearsal on regtest: upgraded nodes and a v25.2.0 node.

Two upgraded nodes activate ASERT and MWEB at the same height H. A node built
from the previous release follows the chain up to H-1 and must stop there.
The script then lets the old node mine a longer chain of its own and checks
that the upgraded nodes ignore it, stay connected to each other and keep
processing MWEB transactions. Only the standard library is needed.

Usage: upgrade_boundary_regtest.py --old-binary=<v25.2.0 bitcoinoild> [--binary=src/bitcoinoild]
"""
import argparse
import json
import os
import shutil
import subprocess
import tempfile
import time

H = 150


NEW_CLI = None


class Node:
    def __init__(self, name, daemon, root, port, extra):
        self.name, self.daemon, self.port = name, daemon, port
        self.cli_bin = os.path.join(os.path.dirname(daemon), "bitcoinoil-cli")
        if not os.path.exists(self.cli_bin):
            # The previous release may be built without its client; the RPC
            # interface used here is the same, so the new client serves both.
            self.cli_bin = NEW_CLI
        self.dir = os.path.join(root, name)
        os.makedirs(self.dir)
        open(os.path.join(self.dir, "bitcoinoil.conf"), "w").close()
        self.base = [f"-datadir={self.dir}", "-regtest", f"-rpcport={port + 1}"]
        self.args = [f"-port={port}", "-listen=1", "-bind=127.0.0.1", "-discover=0", "-dnsseed=0", "-fixedseeds=0",
                     "-fallbackfee=0.0001", "-whitelist=noban@127.0.0.1", "-daemonwait"] + extra

    def start(self):
        subprocess.run([self.daemon] + self.base + self.args, check=True, stdout=subprocess.DEVNULL)

    def cli(self, *args, ok=True):
        r = subprocess.run([self.cli_bin] + self.base + [str(a) for a in args], capture_output=True, text=True)
        if r.returncode != 0:
            if ok:
                raise AssertionError(f"{self.name} {args}: {r.stderr.strip()}")
            return None
        out = r.stdout.strip()
        try:
            return json.loads(out)
        except ValueError:
            return out

    def stop(self):
        self.cli("stop", ok=False)


def wait(predicate, what, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return
        time.sleep(0.5)
    raise AssertionError(f"timed out: {what}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-binary", required=True)
    parser.add_argument("--binary", default="src/bitcoinoild")
    parser.add_argument("--tmpdir")
    opts = parser.parse_args()
    root = opts.tmpdir or tempfile.mkdtemp(prefix="btco-upgrade-")
    os.makedirs(root, exist_ok=True)
    new_args = [f"-mwebheight={H}", f"-asertheight={H}", "-aserthalflife=3600"]
    global NEW_CLI
    NEW_CLI = os.path.join(os.path.dirname(os.path.abspath(opts.binary)), "bitcoinoil-cli")
    a = Node("new-a", os.path.abspath(opts.binary), root, 19900, new_args)
    b = Node("new-b", os.path.abspath(opts.binary), root, 19904, new_args)
    old = Node("old", os.path.abspath(opts.old_binary), root, 19908, [])
    nodes = [a, b, old]
    try:
        for n in nodes:
            n.start()
        a.cli("createwallet", "w")
        old.cli("createwallet", "w")
        for x, y in ((a, b), (a, old), (b, old)):
            x.cli("addnode", f"127.0.0.1:{y.port}", "add")
        wait(lambda: all(n.cli("getconnectioncount") >= 2 for n in nodes), "nodes connect")
        addr = a.cli("getnewaddress")

        a.cli("generatetoaddress", H - 1, addr)
        tip = a.cli("getbestblockhash")
        wait(lambda: all(n.cli("getbestblockhash") == tip for n in nodes), "all nodes reach H-1")
        print(f"[1] upgraded and v25.2.0 nodes agree up to H-1 = {H - 1}")

        a.cli("generatetoaddress", 1, addr)
        first = a.cli("getbestblockhash")
        wait(lambda: b.cli("getbestblockhash") == first, "upgraded peer accepts the activation block")
        time.sleep(5)
        assert old.cli("getblockcount") == H - 1, "the old node must not accept the activation block"
        assert old.cli("getbestblockhash") == tip
        print(f"[2] activation block {H} accepted by upgraded nodes; the v25.2.0 node stays at {H - 1}")

        mweb = a.cli("getnewaddress", "", "mweb")
        a.cli("sendtoaddress", mweb, 10)
        a.cli("generatetoaddress", 3, addr)
        wait(lambda: b.cli("getblockcount") == H + 3, "upgraded nodes continue")
        print(f"[3] peg-in mined after activation; upgraded nodes at {H + 3}")

        old_addr = old.cli("getnewaddress")
        old.cli("generatetoaddress", 12, old_addr)
        assert old.cli("getblockcount") == H + 11
        time.sleep(8)
        new_tip = a.cli("getbestblockhash")
        assert a.cli("getblockcount") == H + 3 and b.cli("getbestblockhash") == new_tip, "upgraded nodes must ignore the longer old chain"
        print(f"[4] old node mined a longer chain ({H + 11}); upgraded nodes ignore it and stay on theirs ({H + 3})")

        peers_a = {p["addr"].split(":")[1] for p in a.cli("getpeerinfo")}
        assert str(b.port) in peers_a or a.cli("getconnectioncount") >= 1
        a.cli("sendtoaddress", a.cli("getnewaddress", "", "mweb"), 2)
        a.cli("generatetoaddress", 2, addr)
        wait(lambda: b.cli("getblockcount") == H + 5, "upgraded nodes still relay to each other")
        banned = a.cli("listbanned") + b.cli("listbanned")
        assert not banned, banned
        print(f"[5] upgraded nodes still connected to each other and relaying MWEB blocks ({H + 5}); nobody banned")

        for n in (a, b):
            n.stop()
        time.sleep(4)
        for n in (a, b):
            n.start()
        a.cli("loadwallet", "w", ok=False)
        final = a.cli("getbestblockhash")
        assert a.cli("getblockcount") == H + 5 and b.cli("getbestblockhash") == final
        print("[6] upgraded nodes restart on the same tip")
        print("Upgrade boundary checks passed")
    finally:
        for n in nodes:
            n.stop()
        time.sleep(3)
        if not opts.tmpdir:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
