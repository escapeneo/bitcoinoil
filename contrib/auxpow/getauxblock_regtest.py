#!/usr/bin/env python3
"""Check the getauxblock calls that YIIMP stratum servers make, on regtest."""
import json, os, shutil, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(__file__))
from auxpow_helper import constructAuxpow, finishAuxpow, doubleHashHex, reverseHex

BIN = os.environ.get("BTCO_BIN", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
FORK = 120
D = tempfile.mkdtemp(prefix="btco-getauxblock-")
open(os.path.join(D, "empty.conf"), "w").close()
BASE = [f"-datadir={D}", f"-conf={D}/empty.conf", "-regtest", "-rpcport=19897"]


def cli(*args, ok=True, wallet=None):
    extra = [f"-rpcwallet={wallet}"] if wallet else []
    r = subprocess.run([f"{BIN}/bitcoinoil-cli"] + BASE + extra + [str(a) for a in args], capture_output=True, text=True)
    if ok and r.returncode != 0:
        raise RuntimeError(f"{args}: {r.stderr}")
    if r.returncode != 0:
        return ("ERR", r.stderr.strip())
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return r.stdout.strip()


def solve(job):
    """Build the proof in the layout YIIMP sends: tx, hash, branches, header."""
    tx, header = constructAuxpow(job["hash"])
    target = int(reverseHex(job["target"]).decode(), 16)
    hdr = bytearray.fromhex(header)
    for nonce in range(1 << 32):
        hdr[76:80] = nonce.to_bytes(4, "little")
        if int(doubleHashHex(hdr.hex()).decode(), 16) <= target:
            break
    return finishAuxpow(tx, hdr.hex().encode("ascii"))


def fail(result, text):
    assert isinstance(result, tuple) and text in result[1], result


def main():
    subprocess.run([f"{BIN}/bitcoinoild", "-daemon", "-noconnect", "-port=19896", f"-auxpowstartheight={FORK}"] + BASE, check=True)
    try:
        for _ in range(120):
            if not isinstance(cli("getblockcount", ok=False), tuple):
                break
            time.sleep(0.5)
        fail(cli("getauxblock", ok=False), "No wallet")
        cli("createwallet", "w")
        address = cli("getnewaddress")
        cli("generatetoaddress", FORK - 2, address)

        fail(cli("getauxblock", ok=False), "not yet available")
        print("[1] refused before the fork height")
        cli("generatetoaddress", 1, address)

        fail(cli("getauxblock", "00" * 32, ok=False), "together")
        job = cli("getauxblock")
        assert job["height"] == FORK and job["chainid"] == 2828, job
        assert job["target"] == job["_target"], job
        print("[2] job returned with chain id 2828 and target")

        used = cli("getwalletinfo")["keypoolsize"]
        again = cli("getauxblock")
        assert again["hash"] == job["hash"], (job, again)
        assert cli("getwalletinfo")["keypoolsize"] == used
        print("[3] repeated requests reuse the job and the address")

        assert cli("getauxblock", job["hash"], solve(job)) is True
        assert cli("getblockcount") == FORK
        tip = cli("getblock", cli("getbestblockhash"), 2)
        assert tip["hash"] == job["hash"]
        output = tip["tx"][0]["vout"][0]["scriptPubKey"]["address"]
        assert cli("getaddressinfo", output)["ismine"] is True
        print("[4] proof accepted and the reward paid this wallet")

        next_job = cli("getauxblock")
        assert next_job["height"] == FORK + 1
        assert cli("getauxblock", next_job["hash"], solve(next_job)) is True
        next_output = cli("getblock", cli("getbestblockhash"), 2)["tx"][0]["vout"][0]["scriptPubKey"]["address"]
        assert next_output != output
        print("[5] next block pays a new address")

        stale = cli("getauxblock")
        assert stale["height"] == FORK + 2
        assert cli("getauxblock", "11" * 32, solve(stale), ok=False)[0] == "ERR"
        print("[6] unknown block hash refused")

        cli("createwallet", "second")
        fail(cli("getauxblock", ok=False), "wallet")
        assert cli("getauxblock", wallet="second")["height"] == FORK + 2
        print("[7] a second wallet needs -rpcwallet, as for any wallet call")

        # Cross submission: a job from "second" sent through "w" pays "second"
        # and must not renew the address "w" is using.
        cli("unloadwallet", "second")
        w_job = cli("getauxblock")
        w_keys = cli("getwalletinfo")["keypoolsize"]
        cli("loadwallet", "second")
        other = cli("getauxblock", wallet="second")
        assert cli("getauxblock", other["hash"], solve(other), wallet="w") is True
        paid = cli("getblock", cli("getbestblockhash"), 2)["tx"][0]["vout"][0]["scriptPubKey"]["address"]
        assert cli("getaddressinfo", paid, wallet="second")["ismine"] is True
        assert cli("getaddressinfo", paid, wallet="w")["ismine"] is False
        renewed = cli("getauxblock", wallet="w")
        assert renewed["height"] == w_job["height"] + 1
        assert cli("getwalletinfo", wallet="w")["keypoolsize"] == w_keys
        print("[8] a proof sent through another wallet renews only the paying wallet")

        # Replace "w" by a different wallet with the same name: the old
        # address must not be reused for the new wallet.
        cli("unloadwallet", "w")
        wdir = os.path.join(D, "regtest", "wallets")
        os.rename(os.path.join(wdir, "w"), os.path.join(wdir, "w-old"))
        cli("createwallet", "w")
        fresh = cli("getauxblock", wallet="w")
        assert cli("getauxblock", fresh["hash"], solve(fresh), wallet="w") is True
        paid = cli("getblock", cli("getbestblockhash"), 2)["tx"][0]["vout"][0]["scriptPubKey"]["address"]
        assert cli("getaddressinfo", paid, wallet="w")["ismine"] is True
        print("[9] a replaced wallet with the same name gets its own address")
    finally:
        subprocess.run([f"{BIN}/bitcoinoil-cli"] + BASE + ["stop"], capture_output=True)
        time.sleep(3)
        shutil.rmtree(D, ignore_errors=True)
    print("getauxblock checks passed")


if __name__ == "__main__":
    main()
