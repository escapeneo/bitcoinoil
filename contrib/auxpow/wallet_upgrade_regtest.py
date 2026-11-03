#!/usr/bin/env python3
"""Upgrade a disposable encrypted regtest wallet; never open a user's wallet."""
import argparse
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
from urllib.error import URLError

from activation_regtest import Node, RPCError, ports, rejects, solve_aux, wait


class WalletNode(Node):
    def start(self, extra=()):
        self.path.mkdir(parents=True, exist_ok=True)
        (self.path / 'empty.conf').touch()
        args = [str(self.binary), f'-datadir={self.path}', f'-conf={self.path}/empty.conf',
                '-regtest', '-server', '-discover=0', '-dnsseed=0', '-fixedseeds=0',
                '-connect=0', '-listen=0', '-listenonion=0', '-upnp=0', '-natpmp=0',
                '-rpcbind=127.0.0.1', f'-rpcport={self.rpcport}',
                f'-mocktime={self.mocktime}', '-printtoconsole=0']
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old-binary', required=True, type=Path)
    parser.add_argument('--binary', default=Path('src/bitcoinoild'), type=Path)
    parser.add_argument('--legacy', action='store_true', help='Test Berkeley DB instead of SQLite descriptors')
    parser.add_argument('--tmpdir', type=Path)
    args = parser.parse_args()
    root = args.tmpdir or Path(tempfile.mkdtemp(prefix='btco-wallet-upgrade-'))
    root.mkdir(parents=True, exist_ok=True)
    assert not (root / 'node').exists(), 'Use a new test directory'
    rpcport, port = ports(2)
    node = WalletNode(args.old_binary.resolve(), root / 'node', 120, rpcport, port)
    password = secrets.token_urlsafe(32)
    now = int(time.time())
    node.mocktime = now + 200000
    try:
        node.start()
        node.rpc('createwallet', 'upgrade', False, False, '', False, not args.legacy)
        address = node.rpc('getnewaddress', 'upgrade-receive')
        # The old node's regtest retarget bug requires spaced timestamps.
        for height in range(1, 106):
            node.rpc('setmocktime', now + height * 360)
            assert len(node.rpc('generatetoaddress', 1, address, 1000000)) == 1
        old_balance = node.rpc('getbalance')
        assert old_balance > 0
        old_tip = node.rpc('getbestblockhash')
        old_txcount = node.rpc('getwalletinfo')['txcount']
        node.rpc('encryptwallet', password)
        backup = (root / 'encrypted-backup.dat').resolve()
        node.rpc('backupwallet', str(backup))
        node.stop()

        node.binary = args.binary.resolve()
        node.start(('-auxpowstartheight=120',))
        if 'upgrade' not in node.rpc('listwallets'):
            node.rpc('loadwallet', 'upgrade')
        assert node.rpc('getbestblockhash') == old_tip
        assert node.rpc('getbalance') == old_balance
        assert node.rpc('getwalletinfo')['txcount'] == old_txcount
        assert node.rpc('getaddressinfo', address)['ismine']
        assert node.rpc('getwalletinfo')['unlocked_until'] == 0
        rejects(lambda: node.rpc('walletpassphrase', 'incorrect-test-password', 60))
        node.rpc('walletpassphrase', password, 600)
        receiver = node.rpc('getnewaddress', 'post-upgrade')
        node.rpc('settxfee', 0.00001)
        txid = node.rpc('sendtoaddress', receiver, 1)
        node.rpc('setmocktime', now + 120 * 360)
        node.rpc('generatetoaddress', 14, address)
        assert node.rpc('gettransaction', txid)['confirmations'] > 0
        job = node.rpc('createauxblock', address)
        assert node.rpc('submitauxblock', job['hash'], solve_aux(job['hash'], int.from_bytes(bytes.fromhex(job['_target']), 'little')))
        assert node.rpc('getblockcount') == 120
        node.rpc('generatetoaddress', 101, address)
        assert node.rpc('getwalletinfo')['balance'] > old_balance
        node.rpc('walletlock')
        node.stop()

        node.start(('-auxpowstartheight=120',))
        if 'upgrade' not in node.rpc('listwallets'):
            node.rpc('loadwallet', 'upgrade')
        node.rpc('unloadwallet', 'upgrade')
        node.rpc('restorewallet', 'restored', str(backup))
        assert node.rpc('getaddressinfo', address)['ismine']
        assert node.rpc('getwalletinfo')['unlocked_until'] == 0
        node.rpc('walletpassphrase', password, 60)
        assert node.rpc('getbalance') > old_balance
        assert node.rpc('gettransaction', txid)['confirmations'] > 0
        assert node.rpc('verifychain', 3, 0)
        node.stop()
        print('PASS: encrypted wallet upgrade, spend, AuxPoW maturity, restart and backup restore', flush=True)
    finally:
        node.stop()


if __name__ == '__main__':
    main()
