#!/usr/bin/env python3
"""Cold-sync more than 2000 consecutive AuxPoW headers over actual P2P."""
import argparse
import tempfile
from pathlib import Path

from activation_regtest import Node, connect, mine_aux, ports, sync


def run(binary, root, blocks):
    assigned = ports(4)
    source = Node(binary, root / 'source', 0, assigned[0], assigned[1])
    peer = Node(binary, root / 'peer', 0, assigned[2], assigned[3])
    try:
        source.start(['-checkblockindex=0'])
        address = source.rpc('decodescript', '51')['p2sh']
        for height in range(1, blocks + 1):
            mine_aux(source, address)
            if height % 500 == 0:
                print(f'Prepared {height}/{blocks} AuxPoW blocks', flush=True)
        assert source.rpc('getblockcount') == blocks
        # A fresh node has neither the prefix nor any cached block headers.
        peer.start()
        connect(peer, source)
        sync((source, peer))
        assert peer.rpc('getblockcount') == peer.rpc('getblockchaininfo')['headers'] == blocks
        assert peer.rpc('getblockheader', peer.rpc('getblockhash', 1))['auxpow']
        assert peer.rpc('verifychain', 3, 0) is True
        print(f'PASS: cold P2P sync of {blocks} consecutive AuxPoW blocks across multiple headers-message limits', flush=True)
    finally:
        source.stop()
        peer.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blocks', type=int, default=2100)
    parser.add_argument('--binary', type=Path, default=Path(__file__).resolve().parents[2] / 'src/bitcoinoild')
    parser.add_argument('--tmpdir', type=Path)
    args = parser.parse_args()
    if not 2000 < args.blocks <= 10000:
        parser.error('Use between 2001 and 10000 blocks')
    if args.tmpdir:
        args.tmpdir.mkdir(parents=True, exist_ok=False)
        run(args.binary.resolve(), args.tmpdir.resolve(), args.blocks)
    else:
        with tempfile.TemporaryDirectory(prefix='btco-auxpow-headers-') as directory:
            run(args.binary.resolve(), Path(directory), args.blocks)


if __name__ == '__main__':
    main()
