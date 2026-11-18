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
| Activation height (ASERT and MWEB) | 300 |
| P2P port | 29712 |
| RPC port | 29711 |
| Block target | 6 minutes |
| Minimum difficulty | 1 |
| MWEB address prefix | `tbtcomweb1…` |
| Start option | `-testnet` |

The BitcoinOil testnet has no public nodes and no blocks yet, so the rehearsal
starts from the genesis block. Difficulty 1 is not practical on a CPU; the
chain needs merge-mined work from a pool.

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

## What the pool needs to do

Point a small share of hashrate at the testnet daemon through the same
merge-mining interface used on mainnet (`createauxblock` / `submitauxblock`,
or `getauxblock`). No stratum change is expected.

`getblocktemplate` is different after activation: from block 299 on, the
request must include the `mweb` rule, for example
`{"rules": ["mweb", "segwit"]}`, and the template carries an `mweb` field
with the extension block. Pools that only use the AuxPoW RPCs are not
affected, because the daemon builds the whole block itself.

The payout address must be a normal address. MWEB addresses are refused as
mining payout.

## What to check

Please note the block height and the daemon's `debug.log` lines for anything
that does not match.

1. **Before activation (blocks 1 to 299):** blocks are found and accepted,
   `getmininginfo` shows `asert.enabled` false.
2. **Activation block 300:** it is mined without any special transaction.
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
5. **A node left on 25.2.0** stops at block 299 and never accepts block 300.
   This is the expected behaviour of a hard fork.
6. **Restart** the daemon after activation and confirm it comes back on the
   same tip. Running once with `-reindex` is a useful extra check.

## Known differences from Litecoin's MWEB

- The first MWEB block does not need a peg-in. Litecoin stalls at activation
  until one is mined; BitcoinOil accepts an empty first HogEx instead.
- The wallet and the mempool refuse MWEB transactions until the next block
  can carry them (block 299 on testnet).
- Kernel lock heights are enforced from the first MWEB block.
- BitcoinOil keeps its own relay policy: one `OP_RETURN` output per
  transaction with at most 83 bytes, and opt-in RBF enabled.
- Compact block relay uses version 3 only. Between an upgraded node and a
  25.2.0 node, blocks are relayed as headers and full blocks.

## Reporting

Send the height, the command that was run, its output, and the matching
`debug.log` lines. Do not send wallet files, private keys or RPC passwords.
