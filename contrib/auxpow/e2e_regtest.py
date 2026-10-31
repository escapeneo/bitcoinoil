"""End-to-end regtest check of the BitcoinOil auxpow fork transition."""
import json, os, shutil, subprocess, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from auxpow_helper import constructAuxpow, finishAuxpow, doubleHashHex, reverseHex

BIN = os.environ.get("BTCO_BIN", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
D = os.environ.get("BTCO_TMPDIR", "/tmp/btco-auxpow-e2e")
FORK = 120
ARGS = [f"-datadir={D}", f"-conf={os.path.abspath(D)}/empty.conf", "-regtest", "-rpcport=19899", "-port=19898", "-listen=0",
        f"-auxpowstartheight={FORK}", "-fallbackfee=0.0001"]

def cli(*a, ok=True):
    r = subprocess.run([f"{BIN}/bitcoinoil-cli", f"-datadir={D}", "-regtest", "-rpcport=19899",
                        f"-conf={D}/empty.conf"] + [str(x) for x in a], capture_output=True, text=True)
    if ok and r.returncode != 0:
        raise RuntimeError(f"{a}: {r.stderr}")
    out = r.stdout.strip()
    try:
        return json.loads(out)
    except Exception:
        return out if r.returncode == 0 else ("ERR", r.stderr.strip())

def start(extra=()):
    subprocess.run([f"{BIN}/bitcoinoild", "-daemon"] + ARGS + list(extra), check=True)
    for _ in range(60):
        if cli("getblockcount", ok=False) not in ("",) and not isinstance(cli("getblockcount", ok=False), tuple):
            return
        time.sleep(0.5)
    raise RuntimeError("node did not start")

def stop(datadir=None):
    cli("stop")
    pid = os.path.join(D, "regtest", "bitcoinoild.pid")
    for _ in range(60):
        if not os.path.exists(pid): return
        time.sleep(0.5)

def mine_aux(addr, chainid_override=None):
    blk = cli("createauxblock", addr)
    tx, header = constructAuxpow(blk["hash"])
    target = int(reverseHex(blk["_target"]).decode(), 16)
    hdr = bytearray.fromhex(header)
    for nonce in range(1 << 32):
        hdr[76:80] = nonce.to_bytes(4, "little")
        if int(doubleHashHex(hdr.hex()).decode(), 16) <= target:
            break
    return blk, cli("submitauxblock", blk["hash"], finishAuxpow(tx, hdr.hex().encode("ascii")), ok=False)

shutil.rmtree(D, ignore_errors=True); os.makedirs(D); open(f"{D}/empty.conf", "w").close()
start()
cli("createwallet", "w")
addr = cli("getnewaddress")
cli("generatetoaddress", FORK - 2, addr)
assert cli("getblockcount") == FORK - 2
v = cli("getblockheader", cli("getbestblockhash"))["version"]
print(f"[1] regular pre-fork blocks mined, tip version=0x{v:08x}")

r = cli("createauxblock", addr, ok=False)
assert isinstance(r, tuple) and "not yet available" in r[1], r
print("[2] createauxblock refused before fork height: OK")

cli("generatetoaddress", 1, addr)  # tip FORK-1: the next block is the first that may be merge-mined
blk, res = mine_aux(addr)
assert res is True, res
h = cli("getbestblockhash"); b = cli("getblock", h)
assert h == blk["hash"] and "auxpow" in b and b["height"] == FORK, b.keys()
print(f"[3] merge-mined block accepted at height {b['height']}, version=0x{b['version']:08x}, chainid=0x{b['version']>>16:04x}")

cli("generatetoaddress", 3, addr)
print(f"[4] regular blocks still valid after fork: height {cli('getblockcount')}")
for _ in range(3):
    _, res = mine_aux(addr); assert res is True, res
hdr = cli("getblockheader", cli("getbestblockhash"))
assert "auxpow" in hdr
print(f"[5] mixed chain OK, height {cli('getblockcount')}, getblockheader shows auxpow")

tip = cli("getbestblockhash"); n = cli("getblockcount")
stop(); start(["-reindex"])
for _ in range(60):
    if cli("getblockcount") == n: break
    time.sleep(1)
assert cli("getbestblockhash") == tip
print(f"[6] -reindex reloads auxpow blocks from disk: tip matches at {n}")

# Second node syncing over P2P (headers + blocks with auxpow).
D2 = D + "2"; shutil.rmtree(D2, ignore_errors=True); os.makedirs(D2)
subprocess.run([f"{BIN}/bitcoinoild", "-daemon", f"-datadir={D2}", f"-conf={os.path.abspath(D)}/empty.conf", "-regtest", "-rpcport=19999", "-port=19998",
                f"-auxpowstartheight={FORK}", "-connect=127.0.0.1:19898"], check=True)
stop(); start(["-listen=1", "-bind=127.0.0.1:19898"])
c2 = lambda *a: subprocess.run([f"{BIN}/bitcoinoil-cli", f"-datadir={D2}", f"-conf={os.path.abspath(D)}/empty.conf", "-regtest", "-rpcport=19999"] + list(a), capture_output=True, text=True).stdout.strip()
for _ in range(90):
    if c2("getbestblockhash") == tip: break
    time.sleep(1)
assert c2("getbestblockhash") == tip, (c2("getblockcount"), n)
print(f"[7] second node synced the mixed chain over P2P to {n}")
c2("stop"); stop()
print("ALL OK")
