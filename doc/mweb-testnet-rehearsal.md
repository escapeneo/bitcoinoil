# Testnet rehearsal of the ASERT + MWEB hard fork

This document is for pool operators and node runners who help rehearse the
next BitcoinOil hard fork on testnet before a mainnet height is announced.

The hard fork activates two things in the same block:

- **ASERT**, the new difficulty adjustment.
- **MWEB**, MimbleWimble extension blocks, ported from Litecoin 24.x.

Merge mining (AuxPoW, chain ID 2828) does not change. On mainnet it has been
active since block 155000; on testnet it is allowed from the first block.

Nothing in this document applies to mainnet. Both features are still disabled
there.

## Testnet parameters

| Item | Value |
|---|---|
| Activation height (ASERT and MWEB) | 110 |
| P2P port | 29712 |
| RPC port | 29711 |
| Block target | 6 minutes |
| Minimum difficulty | 1 |
| MWEB address prefix | `tbtcomweb1…` |
| Start option | `-testnet` |

The BitcoinOil testnet has no public nodes and no blocks yet, so the rehearsal
starts from the genesis block. As on mainnet, SegWit and the older soft forks
are active from the first block.

## How much hashrate this needs

Very little, and only for a short time.

- Every block below height 116 is at difficulty 1, whatever the hashrate,
  because the current difficulty algorithm (LWMA) needs 116 blocks of history
  before it adjusts. The activation height, 110, is below that on purpose.
- Any ASIC gets through those 109 blocks in a few minutes. A 6 TH/s miner
  needs well under a millisecond of hashing per block at difficulty 1; the
  pool software, not the miner, sets the pace.
- From block 110 on ASERT is in charge. It raises the difficulty while blocks
  arrive faster than one every 6 minutes and halves it for every 2 hours
  without a block, so the chain recovers by itself after a miner leaves.
- Coinbase outputs mature after 100 blocks, so MWEB transactions can be tested
  as soon as activation is reached.

In practice: **connect a miner for 15 to 30 minutes**, long enough to pass
block 110 and mine a few dozen blocks after it. There is no need to leave a
rig running. A small device of a few MH/s cannot bootstrap the chain alone
(about 70 minutes per difficulty-1 block at 1 MH/s) but can join later.

## Build

Build the `mweb/port-24x` branch. Compared with 25.2.0 there is one new build
dependency, libfmt 7.1.3:

```bash
contrib/mweb/build_libfmt.sh "$HOME/btco-fmt"
```

```bash
./autogen.sh
```

```bash
PKG_CONFIG_PATH="$HOME/btco-fmt/lib/pkgconfig" ./configure --without-gui
```

```bash
make -C src -j4 bitcoinoild bitcoinoil-cli
```

Builds through `depends` already include libfmt and need no extra step.

The script needs `cmake`. A distribution package (`libfmt-dev` on Debian and
Ubuntu) may also compile, but only 7.1.3 is tested and it is the version the
release binaries use; libfmt 12 is known not to compile.

Check that the right branch was built:

```bash
src/bitcoinoild --version
```

It must report `v25.3.0rc1`. If it reports `v25.2.0` or `v25.2.0rc2`, the
binary comes from the current release and has neither ASERT nor MWEB:

```bash
git remote add pan0ramix https://github.com/Pan0ramix/bitcoinoil.git
```

```bash
git fetch pan0ramix && git checkout -B mweb/port-24x pan0ramix/mweb/port-24x
```

## Starting the chain

Two things stop a fresh testnet node from handing out work, and both are
expected:

1. The genesis block is old, so the node believes it is still syncing.
   Start the first mining node with a large `-maxtipage` until the tip is recent.
2. `createauxblock` and `getauxblock` need at least one connected peer.
   Run a second node and connect the two with `-addnode`.

Example `bitcoinoil.conf` for the mining node:

```ini
testnet=1
[test]
server=1
rpcuser=<choose>
rpcpassword=<choose>
rpcallowip=127.0.0.1
maxtipage=100000000
fallbackfee=0.0001
addnode=<address of the second testnet node>:29712
```

Remove `maxtipage` once blocks are arriving normally. `fallbackfee` is needed
for wallet sends because a new chain has no fee estimates.

## Joining the rehearsal chain

A rehearsal chain already exists, so there is no need to start from the
genesis block. The coordinating node is behind a home connection and cannot
accept incoming connections. Instead:

1. Run your testnet node on a machine with a public address and leave the
   P2P port (29712) open.
2. Send that address to the coordinator. Their node connects out to yours and
   your node downloads the chain from it.
3. Ask for testnet coins if you want to try MWEB transactions without waiting
   for your own coinbase outputs to mature.

There is no public testnet stratum. The point of the rehearsal is to run your
own pool software against the new daemon, because that is what has to work on
mainnet.

## What the pool needs to do

Point a small share of hashrate at the testnet daemon through the same
merge-mining interface used on mainnet (`createauxblock` / `submitauxblock`,
or `getauxblock`). No stratum change is expected.

`getblocktemplate` is different after activation: once the tip is block 109,
the request must include the `mweb` rule, for example
`{"rules": ["mweb", "segwit"]}`, and the template carries an `mweb` field
with the extension block. Pools that only use the AuxPoW RPCs are not
affected, because the daemon builds the whole block itself.

A pool that builds its own block from the template has to submit it in this
format, the same one Litecoin uses:

```text
header | tx count | coinbase | template transactions | 01 | template "mweb"
```

- The template for block 109 (requested with `{"rules": ["segwit"]}`) has no
  `mweb` field and the block is submitted exactly as today.
- From the template for block 110 on, a request without the `mweb` rule
  fails with "getblocktemplate must be called with the segwit & mweb rule
  set".
- Copy each transaction's `data` unchanged and keep the order. The last one
  is the HogEx; in block 110 it has no inputs.
- After the last transaction append the byte `01` and then the template's
  `mweb` hex. A block without that part fails with "Block decode failed".
- The merkle root uses the `txid` fields as usual, and
  `default_witness_commitment` can be used as it is.
- MWEB-to-MWEB transactions do not appear in `transactions`; they live inside
  the `mweb` field.

`test/functional/mweb_pool_template.py` builds blocks this way, byte by byte,
across activation.

The payout address must be a normal address. MWEB addresses are refused as
mining payout.

## What to check

Please note the block height and the daemon's `debug.log` lines for anything
that does not match.

1. **Before activation (blocks 1 to 109):** blocks are found and accepted,
   `getmininginfo` shows `asert.enabled` false.
2. **Activation block 110:** it is mined without any special transaction.
   `getblock <hash> 2` shows a last transaction with no inputs and one output
   of value 0 (the first HogEx), and an `mweb` section.
3. **After activation:** blocks keep coming, `getmininginfo` shows
   `asert.enabled` true, and difficulty follows the hashrate. Stopping the
   miner for a few hours and starting again should lower and then raise the
   difficulty smoothly.
4. **MWEB transactions**, once a coinbase has matured (100 blocks):
   - `getnewaddress "" mweb` returns a `tbtcomweb1…` address.
   - `sendtoaddress <mweb address> <amount>` pegs coins in.
   - Sending from that balance to another MWEB address stays inside MWEB.
   - Sending from that balance to a normal address pegs out. Pegged-out
     coins need 6 confirmations before they can be spent.
5. **A node left on 25.2.0** stops at block 109 and never accepts block 110.
   This is the expected behaviour of a hard fork.
6. **Restart** the daemon after activation and confirm it comes back on the
   same tip. Running once with `-reindex` is a useful extra check.

## Known differences from Litecoin's MWEB

- The first MWEB block does not need a peg-in. Litecoin stalls at activation
  until one is mined; BitcoinOil accepts an empty first HogEx instead.
- The wallet and the mempool refuse MWEB transactions until the next block
  can carry them (block 109 on testnet).
- Kernel lock heights are enforced from the first MWEB block.
- BitcoinOil keeps its own relay policy: one `OP_RETURN` output per
  transaction with at most 83 bytes, and opt-in RBF enabled.
- Compact block relay uses version 3 only. Between an upgraded node and a
  25.2.0 node, blocks are relayed as headers and full blocks.

## Reporting

Send the height, the command that was run, its output, and the matching
`debug.log` lines. Do not send wallet files, private keys or RPC passwords.
