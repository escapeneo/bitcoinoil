# AuxPoW mainnet activation: block 155000

This is a consensus hard fork. Mainnet first permits merge-mined blocks at
**height 155000**, with chain ID **0x0B0C (2828)**. The activation height is a
compiled constant, not a mainnet configuration option or a wall-clock time.
`-auxpowstartheight` is accepted only on regtest and rejects invalid heights.

| Candidate block | Normal SHA256d PoW | AuxPoW |
| --- | --- | --- |
| 154999 and earlier | Existing consensus rules | Rejected |
| 155000 and later | Remains supported | Accepted if the complete proof is valid |

The difficulty algorithm, block interval, rewards, addresses and wallet keys
are unchanged. The AuxPoW parent must meet the **BTCO** target; the child must
commit to the correct chain ID, coinbase and Merkle proof. A coinbase containing
a merge-mining tag alone does not make a block an AuxPoW block.

## Upgrade and deployment

Publishing a GitHub commit does not update deployed nodes. Pool operators,
explorers, exchanges and wallet users must install the coordinated release
**before block 155000**. Older nodes cannot validate an AuxPoW block and may
remain on a different branch after the first merge-mined block.

1. Require the AuxPoW CI workflow to pass on the exact release commit. Review
   the code and the test logs independently before tagging a production release.
2. Build and smoke-test the daemon and Qt wallet on each supported target OS.
   A passing Linux workflow and macOS daemon test do not certify Windows or Qt.
3. Coordinate the height, chain ID and RPC integration with operators. Confirm
   at least two independently operated, reachable updated full nodes. The
   currently supplied Shears hostname and IP refer to **one** node, not two.
4. Check the live tip immediately before release and allow enough blocks for
   operators to upgrade. If coordination cannot finish before 155000, do not
   publish this candidate as a ready production release; agree a new future
   height and rerun the tests before making a new release decision.
5. Stop each node cleanly and back up its complete data directory and wallets.
   Replace binaries, preserve the existing configuration and start normally.
   Existing ordinary mainnet block-index records remain byte-compatible and
   do not require a routine reindex.
6. Check `getnetworkinfo`, `getpeerinfo`, `getblockchaininfo` and `getmininginfo`.
   Confirm the expected release, peer connections, matching tip hashes and
   `initialblockdownload: false`. For pools, verify `auxpow.chainid == 2828` and
   `auxpow.startheight == 155000`.

`getmininginfo.auxpow.enabled` describes the **next candidate block**. It becomes
true when the active tip reaches 154999, because pools can then request work
for block 155000. Reorganizations below the boundary disable AuxPoW work again.

### Compatibility with existing 25.1.1 peers

The old code disconnects peers whose user-agent string differs from its own.
Updated nodes remove this restriction. To remain reachable by old mainnet
nodes during the rollout, the candidate advertises `/BitcoinOil:25.1.1/` on
mainnet P2P connections while its active height is below 155000. Its actual
software version is still reported by `getnetworkinfo` (25.2.0), and its wire
protocol version is **70017**. Do not use the pre-fork P2P user-agent alone to
count upgraded nodes. At and after height 155000 it advertises its real version.

Regtest also now honors `fPowNoRetargeting` before the LWMA branch, fixing an
existing test-network bug. Mainnet and testnet set that flag to false, so their
difficulty calculation is unchanged.

After a node has accepted AuxPoW, do not downgrade it to a non-AuxPoW release
against the same data directory. Restoring a backup and an old binary does not
restore compatibility with the upgraded network. Early, unpublished AuxPoW
builds that stored proofs only in block files need a full `-reindex` before
using this candidate's persistent AuxPoW index; ordinary pre-fork data does not.

## Peers

The supplied discovery fallback is `stratum.shears.co.uk:19712` (IP verified on
2026-11-01: `57.129.180.69`). A hostname resolving to a full node is a bootstrap
fallback, not a redundant crawler-backed DNS seeder. Operators should add their
own independent peers and arrange durable DNS seeds before broad deployment.

```ini
addnode=stratum.shears.co.uk:19712
```

Do not expose an unauthenticated RPC service. Pools should use loopback RPC or
a separately secured private connection. Installing this release does not
start a miner or enable merge mining automatically.

## Pool RPCs

Use `createauxblock <BTCO-address>` and submit the resulting job with
`submitauxblock <child-hash> <serialized-auxpow>`. The child hash commits to the
chain ID and BTCO block contents; it is inserted in the parent's merge-mining
coinbase commitment. Only `submitauxblock` receives the completed proof.

`createauxblock` rejects requests before the next candidate reaches 155000.
It also rejects disconnected or initial-download mainnet nodes. Normal
`getblocktemplate` mining remains available. Pools must refresh jobs when the
BTCO tip changes and use a payout address they control.

## Reproducible verification

From the repository root, after building daemon and tests:

```sh
src/test/test_bitcoinoil --run_test=auxpow_tests,headers_sync_chainwork_tests --log_level=test_suite
python3 contrib/auxpow/activation_regtest.py --height=120
python3 contrib/auxpow/activation_regtest.py --height=155000
python3 contrib/auxpow/headers_regtest.py
# After a Qt-enabled build, test the graphical wallet backend headlessly:
QT_QPA_PLATFORM=offscreen python3 contrib/auxpow/activation_regtest.py --binary=src/qt/bitcoinoil-qt --height=120
```

The second regtest uses easy PoW but the **exact 154999/155000 boundary**. It
checks early rejection through both block and header RPCs, malformed and
incorrect proofs, full AuxPoW header persistence without block data, P2P
headers-first synchronization, normal mining after activation, greater-work
reorganizations across activation, pruning and P2P header serving after
restart, full reindex, chainstate reindex and `verifychain`. They also abort an
HTTP RPC client with a TCP reset and require clean shutdown within 20 seconds,
covering the backport of [Bitcoin Core #28551](https://github.com/bitcoin/bitcoin/pull/28551).

Global `-checkblockindex` scans are disabled only while constructing the large
prefix, the 600-block pruning fixture and reindexing, avoiding quadratic test
cost. Normal consensus, transaction and PoW validation remain enabled. The
default global index checks are enabled for the activation, header restart,
reorganizations, pruned-node restart and final startup.

The additional headers regression cold-syncs 2100 consecutive AuxPoW blocks
from genesis, crossing both the legacy 2000-header count and the new variable-
size headers-message budgets.

These tests and existing-mainnet validation reduce implementation risk. They
do not guarantee zero bugs, certify all pool software or replace operator
coordination and review. No production release is implied by preparing this
candidate.
