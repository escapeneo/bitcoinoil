#!/usr/bin/env python3
"""Check ASERT activation on regtest against an independent Python model.

Covers the boundary block, fast and slow blocks, a merge-mined block, a
reorganisation across the anchor, restart, P2P sync to a second node and
rejection by a node without ASERT.
"""
import json, os, shutil, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "auxpow"))
from auxpow_helper import constructAuxpow, finishAuxpow, doubleHashHex, reverseHex

BIN = os.environ.get("BTCO_BIN", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
ASERT_HEIGHT = 150
HALF_LIFE = 3600
SPACING = 360
LIMIT = (1 << 255) - 1
START = 1800000000
ROOT = tempfile.mkdtemp(prefix="btco-asert-")


def to_target(bits):
    size, word = bits >> 24, bits & 0x007fffff
    return word >> (8 * (3 - size)) if size <= 3 else word << (8 * (size - 3))


def to_bits(target):
    size = (target.bit_length() + 7) // 8
    word = target << (8 * (3 - size)) if size <= 3 else target >> (8 * (size - 3))
    if word & 0x00800000:
        word >>= 8
        size += 1
    return word | (size << 24)


def asert(anchor_bits, time_diff, height_diff):
    """Same arithmetic as CalculateASERT, including the regtest scaling."""
    scale = max(0, LIMIT.bit_length() - 224)
    limit = LIMIT >> scale
    target = max(1, to_target(anchor_bits) >> scale)
    n = (time_diff - SPACING * (height_diff + 1)) * 65536
    exponent = n // HALF_LIFE if n >= 0 else -((-n) // HALF_LIFE)
    shifts = exponent // 65536
    frac = exponent - shifts * 65536
    factor = 65536 + ((195766423245049 * frac + 971821376 * frac ** 2 + 5127 * frac ** 3 + (1 << 47)) >> 48)
    target *= factor
    shifts -= 16
    target = target >> -shifts if shifts <= 0 else target << shifts
    target = max(1, min(target, limit))
    return to_bits(min(target << scale, LIMIT))


class Node:
    def __init__(self, name, port, extra):
        self.dir = os.path.join(ROOT, name)
        os.makedirs(self.dir)
        open(os.path.join(self.dir, "empty.conf"), "w").close()
        self.base = [f"-datadir={self.dir}", f"-conf={self.dir}/empty.conf", "-regtest", f"-rpcport={port + 1}"]
        self.args = [f"-port={port}", "-fallbackfee=0.0001", f"-mocktime={START}"] + extra
        self.port = port

    def cli(self, *args, ok=True):
        r = subprocess.run([f"{BIN}/bitcoinoil-cli"] + self.base + [str(a) for a in args], capture_output=True, text=True)
        if r.returncode != 0:
            if ok:
                raise RuntimeError(f"{args}: {r.stderr}")
            return ("ERR", r.stderr.strip())
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            return r.stdout.strip()

    def start(self, extra=()):
        subprocess.run([f"{BIN}/bitcoinoild", "-daemon"] + self.base + self.args + list(extra), check=True, capture_output=True)
        for _ in range(120):
            if not isinstance(self.cli("getblockcount", ok=False), tuple):
                return
            time.sleep(0.5)
        raise RuntimeError("node did not start")

    def stop(self):
        self.cli("stop", ok=False)
        pid = os.path.join(self.dir, "regtest", "bitcoinoild.pid")
        for _ in range(120):
            if not os.path.exists(pid):
                return
            time.sleep(0.5)

    def header(self, height):
        return self.cli("getblockheader", self.cli("getblockhash", height))


def check_chain(node, first, last):
    """Every ASERT block's bits must match the model, from this node's own headers."""
    anchor = node.header(ASERT_HEIGHT - 1)
    anchor_parent = node.header(ASERT_HEIGHT - 2)
    prev = node.header(first - 1)
    for height in range(first, last + 1):
        want = asert(int(anchor["bits"], 16), prev["time"] - anchor_parent["time"], prev["height"] - anchor["height"])
        cur = node.header(height)
        assert int(cur["bits"], 16) == want, (height, cur["bits"], hex(want))
        prev = cur


def main():
    asert_args = [f"-asertheight={ASERT_HEIGHT}", f"-aserthalflife={HALF_LIFE}"]
    a = Node("a", 19870, asert_args)
    b = Node("b", 19874, asert_args)
    old = Node("old", 19878, [])
    nodes = [a, b, old]
    try:
        a.start()
        a.cli("createwallet", "w")
        address = a.cli("getnewaddress")
        now = START

        def mine(node, step, count=1):
            nonlocal now
            for _ in range(count):
                now += step
                node.cli("setmocktime", now)
                node.cli("generatetoaddress", 1, address)

        info = a.cli("getmininginfo")["asert"]
        assert info == {"startheight": ASERT_HEIGHT, "halflife": HALF_LIFE, "enabled": False}, info
        mine(a, SPACING, ASERT_HEIGHT - 2)
        assert a.cli("getmininginfo")["asert"]["enabled"] is False
        mine(a, SPACING)
        assert a.cli("getblockcount") == ASERT_HEIGHT - 1
        assert a.cli("getmininginfo")["asert"]["enabled"] is True
        limit_bits = a.header(ASERT_HEIGHT - 1)["bits"]
        print("[1] chain mined to the anchor at", ASERT_HEIGHT - 1, "bits", limit_bits)

        mine(a, SPACING)
        assert a.header(ASERT_HEIGHT)["bits"] == limit_bits
        print("[2] first ASERT block on schedule keeps the anchor target")

        mine(a, 10, 25)
        fast = a.header(a.cli("getblockcount"))
        assert to_target(int(fast["bits"], 16)) < to_target(int(limit_bits, 16)) // 4
        check_chain(a, ASERT_HEIGHT, a.cli("getblockcount"))
        print("[3] 25 fast blocks raise the difficulty exactly as the model says:", fast["bits"])

        mine(a, 3 * HALF_LIFE)
        mine(a, SPACING)
        slow = a.header(a.cli("getblockcount"))
        assert to_target(int(slow["bits"], 16)) > 4 * to_target(int(fast["bits"], 16))
        check_chain(a, ASERT_HEIGHT, a.cli("getblockcount"))
        print("[4] a three half-life gap lowers it again:", slow["bits"])

        job = a.cli("createauxblock", address)
        tx, header = constructAuxpow(job["hash"])
        target = int(reverseHex(job["_target"]).decode(), 16)
        hdr = bytearray.fromhex(header)
        for nonce in range(1 << 32):
            hdr[76:80] = nonce.to_bytes(4, "little")
            if int(doubleHashHex(hdr.hex()).decode(), 16) <= target:
                break
        assert a.cli("submitauxblock", job["hash"], finishAuxpow(tx, hdr.hex().encode("ascii"))) is True
        tip = a.cli("getblockcount")
        assert a.header(tip)["version"] & 0x100
        check_chain(a, ASERT_HEIGHT, tip)
        print("[5] merge-mined block accepted with the ASERT target")

        # Reorganise across the anchor: new blocks 148.. with other times.
        old_tip_hash = a.cli("getbestblockhash")
        a.cli("invalidateblock", a.cli("getblockhash", ASERT_HEIGHT - 2))
        assert a.cli("getblockcount") == ASERT_HEIGHT - 3
        other = a.cli("getnewaddress")
        address = other
        mine(a, 500, 2)
        new_anchor = a.header(ASERT_HEIGHT - 1)
        mine(a, 30, 40)
        mine(a, 2 * HALF_LIFE, 2)
        tip = a.cli("getblockcount")
        assert a.cli("getbestblockhash") != old_tip_hash
        check_chain(a, ASERT_HEIGHT, tip)
        print("[6] reorg across the anchor: targets follow the new anchor, tip", tip)

        tip_hash = a.cli("getbestblockhash")
        a.stop()
        a.start([f"-mocktime={now}"])
        assert a.cli("getbestblockhash") == tip_hash
        assert a.cli("verifychain", 4, 0) is True
        print("[7] restart and verifychain keep the same tip")

        b.start([f"-mocktime={now}"])
        b.cli("addnode", f"127.0.0.1:{a.port}", "onetry")
        for _ in range(120):
            if b.cli("getbestblockhash") == tip_hash:
                break
            time.sleep(0.5)
        assert b.cli("getbestblockhash") == tip_hash
        check_chain(b, ASERT_HEIGHT, tip)
        print("[8] a second ASERT node synced the chain over P2P")

        # Future-time limit: 15 minutes under ASERT. Node b's clock stays behind.
        b_clock = now
        now += 1000
        a.cli("setmocktime", now)
        ahead = a.cli("generatetoaddress", 1, address)[0]
        raw = a.cli("getblock", ahead, 0)
        assert b.cli("submitblock", raw) == "time-too-new"
        b.cli("setmocktime", b_clock + 200)
        result = b.cli("submitblock", raw)
        assert result in ("", None, "duplicate", "inconclusive"), result
        for _ in range(60):
            if b.cli("getbestblockhash") == ahead:
                break
            time.sleep(0.5)
        assert b.cli("getbestblockhash") == ahead
        tip, tip_hash = tip + 1, ahead
        print("[8b] a block 1000 s ahead is refused, and accepted once it is 800 s ahead")

        old.start([f"-mocktime={now}"])
        old.cli("addnode", f"127.0.0.1:{a.port}", "onetry")
        time.sleep(8)
        first_changed = next(h for h in range(ASERT_HEIGHT, tip + 1) if a.header(h)["bits"] != new_anchor["bits"])
        info = old.cli("getblockchaininfo")
        # Headers arrive in one batch, so the whole batch is refused when one
        # header in it has a target this node does not expect.
        assert info["headers"] < first_changed and info["blocks"] < first_changed, (info["headers"], info["blocks"], first_changed)
        assert old.cli("getbestblockhash") != tip_hash
        print("[9] a node without ASERT refuses the chain: headers", info["headers"], "first changed target at", first_changed)
    finally:
        for node in nodes:
            node.stop()
        shutil.rmtree(ROOT, ignore_errors=True)
    print("ASERT regtest checks passed")


if __name__ == "__main__":
    main()
