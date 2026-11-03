#!/usr/bin/env python3
"""Isolated AuxPoW activation, headers, pruning, restart and reorg regression.

Use --height=155000 to exercise the exact mainnet boundary on easy-PoW
regtest. This never connects to mainnet and never accesses a user wallet.
Only the Python standard library and the built daemon are needed.
"""
import argparse
import base64
import hashlib
import json
import shutil
import socket
import struct
import sys
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from auxpow_helper import constructAuxpow, finishAuxpow

BASE_TIME = int(time.time())
MOCK_TIME = BASE_TIME + 165000 * 360


class RPCError(Exception):
    def __init__(self, error):
        self.code = error['code']
        super().__init__(error['message'])


def wait(predicate, timeout=180):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError('Timed out waiting for node state')


def ports(count):
    sockets = [socket.socket() for _ in range(count)]
    try:
        for sock in sockets:
            sock.bind(('127.0.0.1', 0))
        return [sock.getsockname()[1] for sock in sockets]
    finally:
        for sock in sockets:
            sock.close()


class Node:
    def __init__(self, binary, path, height, rpcport, port, prune=False):
        self.binary, self.path, self.height = binary, path, height
        self.rpcport, self.port, self.prune = rpcport, port, prune
        self.process = None

    def start(self, extra=()):
        self.path.mkdir(parents=True, exist_ok=True)
        (self.path / 'empty.conf').touch()
        args = [str(self.binary), f'-datadir={self.path}', f'-conf={self.path}/empty.conf',
                '-regtest', '-server', '-disablewallet', '-discover=0', '-dnsseed=0',
                '-fixedseeds=0', '-connect=0', '-upnp=0', '-natpmp=0', '-listenonion=0',
                '-listen=1', f'-bind=127.0.0.1:{self.port}', f'-port={self.port}',
                '-rpcbind=127.0.0.1', f'-rpcport={self.rpcport}',
                f'-auxpowstartheight={self.height}', f'-mocktime={MOCK_TIME}', '-printtoconsole=0']
        if self.prune:
            args += ['-prune=1', '-fastprune=1']
        self.log = (self.path / 'process.log').open('a')
        self.process = subprocess.Popen(args + list(extra), stdout=self.log, stderr=self.log)
        def ready():
            if self.process.poll() is not None:
                raise RuntimeError((self.path / 'process.log').read_text())
            try:
                self.rpc('getblockcount')
                return True
            except (RPCError, OSError, URLError):
                return False
        wait(ready)

    def rpc(self, method, *params):
        cookie = (self.path / 'regtest/.cookie').read_bytes().strip()
        request = Request(f'http://127.0.0.1:{self.rpcport}/',
                          json.dumps({'jsonrpc': '1.0', 'id': 1, 'method': method, 'params': params}).encode(),
                          {'Authorization': 'Basic ' + base64.b64encode(cookie).decode(),
                           'Content-Type': 'application/json'})
        try:
            response = urlopen(request, timeout=180)
        except HTTPError as exc:
            response = exc
        with response:
            result = json.load(response)
        if result['error'] is not None:
            raise RPCError(result['error'])
        return result['result']

    def stop(self, timeout=180):
        if self.process is not None:
            if self.process.poll() is None:
                try:
                    self.rpc('stop')
                except (OSError, RPCError, URLError):
                    pass  # It may already be shutting down.
                finally:
                    try:
                        self.process.wait(timeout=timeout)
                    except subprocess.TimeoutExpired:
                        self.process.kill()  # Only this isolated test process.
                        self.process.wait()
                        raise
            self.log.close()
            self.process = None


def rejects(function, message=None, code=None):
    try:
        function()
    except RPCError as exc:
        if message is not None:
            assert message in str(exc), str(exc)
        if code is not None:
            assert exc.code == code, (exc.code, str(exc))
        return
    raise AssertionError('Expected RPC rejection')


def digest(data):
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def solve_aux(blockhash, target, valid=True):
    tx, header = constructAuxpow(blockhash)
    header = bytearray.fromhex(header)
    for nonce in range(1_000_000):
        header[76:80] = nonce.to_bytes(4, 'little')
        if (int.from_bytes(digest(header), 'little') <= target) == valid:
            return finishAuxpow(tx, header.hex().encode())
    raise AssertionError('Could not construct regtest parent PoW')


def target(bits):
    return (bits & 0x7fffff) << (8 * ((bits >> 24) - 3))


def raw_aux(node, address, chainid=0x0B0C):
    normal = bytes.fromhex(node.rpc('generateblock', address, [], False)['hex'])
    header = bytearray(normal[:80])
    header[:4] = struct.pack('<I', (chainid << 16) | 0x104)
    blockhash = digest(header)[::-1].hex()
    proof = bytes.fromhex(solve_aux(blockhash, target(struct.unpack_from('<I', header, 72)[0])))
    return bytes(header) + proof + normal[80:], bytes(header) + proof


def mine_aux(node, address):
    work = node.rpc('createauxblock', address)
    proof = solve_aux(work['hash'], int.from_bytes(bytes.fromhex(work['_target']), 'little'))
    assert node.rpc('submitauxblock', work['hash'], proof) is True
    assert node.rpc('getbestblockhash') == work['hash']
    return work['hash']


def connect(node, other):
    node.rpc('addnode', f'127.0.0.1:{other.port}', 'onetry')


def sync(nodes):
    wait(lambda: len({n.rpc('getbestblockhash') for n in nodes}) == 1)


def request_header(node, locator, blockhash):
    """Check the actual full P2P header served by a pruned peer."""
    magic = bytes.fromhex('fedc9aa7')
    with socket.create_connection(('127.0.0.1', node.port), timeout=10) as sock:
        sock.settimeout(10)
        def send(cmd, data=b''):
            sock.sendall(magic + cmd.encode().ljust(12, b'\0') + struct.pack('<I', len(data)) + digest(data)[:4] + data)
        def read(size):
            out = b''
            while len(out) < size:
                chunk = sock.recv(size-len(out))
                if not chunk:
                    raise EOFError('Peer disconnected')
                out += chunk
            return out
        addr = struct.pack('<Q', 9) + bytes(10) + b'\xff\xff\x7f\0\0\x01' + struct.pack('>H', node.port)
        agent = b'/auxpow-activation-test:1/'
        send('version', struct.pack('<iQq', 70017, 9, int(time.time())) + addr + addr +
             struct.pack('<Q', 123456789) + bytes([len(agent)]) + agent + struct.pack('<i?', 0, False))
        end = time.monotonic() + 20
        while time.monotonic() < end:
            header = read(24)
            assert header[:4] == magic
            size = struct.unpack_from('<I', header, 16)[0]
            assert size <= 4_000_000
            data = read(size)
            assert digest(data)[:4] == header[20:24]
            cmd = header[4:16].rstrip(b'\0')
            if cmd == b'version':
                send('verack')
            elif cmd == b'verack':
                send('getheaders', struct.pack('<i', 70017) + b'\x01' +
                     bytes.fromhex(locator)[::-1] + bytes.fromhex(blockhash)[::-1])
            elif cmd == b'ping':
                send('pong', data)
            elif cmd == b'headers':
                assert data[0] == 1 and data[-1] == 0
                return data[1:-1].hex()
    raise AssertionError('No P2P header reply')


def run(binary, root, height):
    numbers = ports(6)
    nodes = [Node(binary, root / f'node{i}', height, numbers[i*2], numbers[i*2+1], prune=(i == 1)) for i in range(3)]
    a, b, c = nodes
    try:
        # Global block-index checking after every block is quadratic for a
        # 155k-block fixture. Re-enable the default checks at the boundary.
        a.start(['-checkblockindex=0'])
        address = a.rpc('decodescript', '51')['p2sh']
        assert a.rpc('getblockcount') <= height-2
        while a.rpc('getblockcount') < height - 2:
            count = a.rpc('getblockcount')
            a.rpc('setmocktime', BASE_TIME + count * 360)
            requested = min(1000, height-2-count)
            assert len(a.rpc('generatetoaddress', requested, address, 10000000)) == requested
            current = a.rpc('getblockcount')
            if count == 0 or current // 10000 != count // 10000 or current == height-2:
                print(f'Preparing boundary: {current}/{height-2}', flush=True)
        a.rpc('setmocktime', MOCK_TIME)
        rejects(lambda: a.rpc('createauxblock', address), 'not yet available')
        assert a.rpc('getmininginfo')['auxpow']['enabled'] is False
        early, early_header = raw_aux(a, address)
        assert a.rpc('submitblock', early.hex()) == 'early-auxpow-block'
        rejects(lambda: a.rpc('submitheader', early_header.hex()), 'early-auxpow-block')
        assert a.rpc('getblockcount') == height-2
        a.rpc('generatetoaddress', 1, address)
        parent = a.rpc('getbestblockhash')
        a.stop()
        for node in (b, c):
            # LevelDB *.log files are WALs and must be copied with the database.
            shutil.copytree(a.path, node.path, ignore=shutil.ignore_patterns('debug.log', 'process.log', '.cookie', '.lock', '*.pid'))
        for node in nodes:
            node.start()
            assert node.rpc('getblockcount') == height-1
        assert a.rpc('getmininginfo')['auxpow'] == {'chainid': 0x0B0C, 'startheight': height,
                                                   'nextblockheight': height, 'enabled': True}
        wrong, _ = raw_aux(a, address, chainid=0x0B0D)
        assert a.rpc('submitblock', wrong.hex()) is not None
        work = a.rpc('createauxblock', address)
        proof = solve_aux(work['hash'], int.from_bytes(bytes.fromhex(work['_target']), 'little'))
        bad_pow = solve_aux(work['hash'], int.from_bytes(bytes.fromhex(work['_target']), 'little'), valid=False)
        assert a.rpc('submitauxblock', work['hash'], bad_pow) is False
        tampered = bytearray.fromhex(proof)
        tampered[46] ^= 1  # Change the child hash in the parent's coinbase commitment.
        assert a.rpc('submitauxblock', work['hash'], tampered.hex()) is False
        rejects(lambda: a.rpc('submitauxblock', work['hash'], proof + '00'), 'Trailing data', -22)
        rejects(lambda: a.rpc('submitauxblock', work['hash'], 'zz'), 'hexadecimal', -22)
        rejects(lambda: a.rpc('submitauxblock', work['hash'], proof[:-2]))
        assert a.rpc('getbestblockhash') == parent
        assert a.rpc('submitauxblock', work['hash'], proof) is True
        first = work['hash']
        assert a.rpc('getblockcount') == height
        assert a.rpc('getblockheader', first)['version'] == 0x0B0C0104
        full_header = a.rpc('getblockheader', first, False)
        b.rpc('submitheader', full_header)
        assert b.rpc('getblockcount') == height-1
        assert b.rpc('getblockchaininfo')['headers'] == height
        assert b.rpc('getblockheader', first, False) == full_header
        b.stop()
        b.start()
        assert b.rpc('getblockheader', first, False) == full_header
        # getheaders serves the active chain, not a headers-only side branch.
        # Check headers-only persistence above, then download the complete
        # activation block from the node that actually has its data.
        connect(b, a)
        connect(c, a)
        sync(nodes)
        assert c.rpc('getblockchaininfo')['headers'] == height
        print(f'Boundary {height-1}/{height}, invalid proofs, headers-only restart and P2P: PASS', flush=True)

        a.rpc('generatetoaddress', 3, address)
        mine_aux(a, address)
        sync(nodes)
        old_tip = a.rpc('getbestblockhash')
        a.rpc('setnetworkactive', False)
        a.rpc('invalidateblock', parent)
        assert a.rpc('getblockcount') == height-2
        rejects(lambda: a.rpc('createauxblock', address), 'not yet available')
        rejects(lambda: a.rpc('submitauxblock', first, proof), 'not yet available')
        a.rpc('reconsiderblock', parent)
        assert a.rpc('getbestblockhash') == old_tip
        a.rpc('setnetworkactive', True)
        connect(a, b)
        connect(c, a)
        sync(nodes)

        c.rpc('setnetworkactive', False)
        c.rpc('invalidateblock', first)
        c.rpc('generatetoaddress', 10, address)
        c.rpc('setnetworkactive', True)
        connect(c, a)
        connect(c, b)
        sync(nodes)
        assert a.rpc('getblockcount') == height+9
        assert a.rpc('getblockheader', a.rpc('getblockhash', height))['version'] & 0x100 == 0
        prune_parent = a.rpc('getbestblockhash')
        prune_hash = mine_aux(a, address)
        prune_header = a.rpc('getblockheader', prune_hash, False)
        sync(nodes)
        print('Mixed blocks and greater-work legacy reorg across activation: PASS', flush=True)

        # Bulk pruning fixture: keep consensus checks, avoid an O(n^2) global
        # index scan for every one of the next 600 blocks on all three nodes.
        for node in nodes:
            node.stop()
            node.start(['-checkblockindex=0'])
        connect(b, a)
        connect(c, a)
        assert len(a.rpc('generatetoaddress', 600, address)) == 600
        assert a.rpc('getblockcount') == height+610
        sync(nodes)
        # Fast-prune files are 64 KiB, so the first file can span >110 blocks.
        pruned = b.rpc('pruneblockchain', height+310)
        assert pruned >= height+10, pruned
        rejects(lambda: b.rpc('getblock', prune_hash), 'pruned')
        assert b.rpc('getblockheader', prune_hash, False) == prune_header
        b.stop()
        b.start()
        assert b.rpc('getblockheader', prune_hash, False) == prune_header
        assert request_header(b, prune_parent, prune_hash) == prune_header
        print('Pruned AuxPoW header survives restart and P2P serving: PASS', flush=True)

        tip = a.rpc('getbestblockhash')
        a.stop()
        a.start(['-reindex-chainstate', '-checkblockindex=0'])
        wait(lambda: a.rpc('getbestblockhash') == tip)
        assert a.rpc('verifychain', 3, 0) is True
        a.stop()
        a.start(['-reindex', '-checkblockindex=0'])
        wait(lambda: a.rpc('getbestblockhash') == tip)
        assert a.rpc('verifychain', 3, 0) is True
        a.stop()
        a.start()  # Default global index checks are enabled again.
        assert a.rpc('getbestblockhash') == tip
        print('Reindex-chainstate, full reindex and verifychain: PASS', flush=True)

        # Regression for Bitcoin Core #27722/#28551: abort a pending HTTP RPC
        # with a TCP reset. A successful-reply callback alone leaks the request
        # and hangs StopHTTPServer. The closed-connection tracker must clear it.
        cookie = (a.path / 'regtest/.cookie').read_bytes().strip()
        body = json.dumps({'id': 7, 'method': 'waitfornewblock', 'params': [60000]}).encode()
        pending = socket.create_connection(('127.0.0.1', a.rpcport), timeout=10)
        pending.sendall(b'POST / HTTP/1.1\r\nHost: localhost\r\nAuthorization: Basic ' +
                        base64.b64encode(cookie) + b'\r\nContent-Type: application/json\r\nContent-Length: ' +
                        str(len(body)).encode() + b'\r\n\r\n' + body)
        wait(lambda: any(cmd['method'] == 'waitfornewblock' for cmd in a.rpc('getrpcinfo')['active_commands']))
        linger_format = 'HH' if sys.platform == 'win32' else 'ii'
        pending.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack(linger_format, 1, 0))
        pending.close()
        a.rpc('generatetoaddress', 1, address)
        a.stop(timeout=20)
        print('Disconnected RPC client does not hang clean shutdown: PASS', flush=True)
        print(f'ALL CHECKS PASSED (activation height {height})', flush=True)
    finally:
        for node in nodes:
            node.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--height', type=int, default=120)
    parser.add_argument('--binary', type=Path, default=Path(__file__).resolve().parents[2] / 'src/bitcoinoild')
    parser.add_argument('--tmpdir', type=Path, help='New directory; retained for inspection')
    parser.add_argument('--resume-prefix', action='store_true', help='Resume an interrupted prefix preparation in --tmpdir')
    args = parser.parse_args()
    if args.height < 3 or args.height > 250000:
        parser.error('Use an activation height between 3 and 250000')
    if args.resume_prefix and args.tmpdir is None:
        parser.error('--resume-prefix requires --tmpdir')
    if args.tmpdir:
        if args.resume_prefix:
            if not (args.tmpdir / 'node0/regtest').is_dir() or any((args.tmpdir / f'node{i}').exists() for i in (1, 2)):
                parser.error('Can only resume a prefix before the other test nodes were created')
        else:
            args.tmpdir.mkdir(parents=True, exist_ok=False)
        run(args.binary.resolve(), args.tmpdir.resolve(), args.height)
    else:
        with tempfile.TemporaryDirectory(prefix='btco-activation-') as directory:
            run(args.binary.resolve(), Path(directory), args.height)


if __name__ == '__main__':
    main()
