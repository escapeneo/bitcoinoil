# BitcoinOil Core 25.2.0 release candidate 1

This candidate introduces a **mainnet hard fork at block 155000** to permit
SHA256d merge mining (AuxPoW), chain ID **0x0B0C**. Normal SHA256d mining remains
valid after the activation. All network participants must upgrade before the
first AuxPoW block; publishing source on GitHub does not perform that upgrade.

Changes include `createauxblock` / `submitauxblock`, AuxPoW activation status in
`getmininginfo`, proof persistence for headers-only and pruned nodes, strict
regtest override validation, and additional bootstrap peer discovery. Existing
ordinary block-index entries retain their format. Proof of work is checked
again when loading both ordinary and AuxPoW block-index entries.

The old exact-user-agent peer restriction is removed. Before activation, the
mainnet wire user-agent stays compatible with 25.1.1 peers; the actual release
version is available through RPC and AuxPoW support uses protocol 70017.
Regtest honors its fixed-difficulty flag even beyond the LWMA fork; mainnet
difficulty is unchanged.

Includes a backport of [Bitcoin Core #28551](https://github.com/bitcoin/bitcoin/pull/28551)
to prevent HTTP shutdown hanging when an RPC client disconnects before the
reply. Regression tests cover a TCP-reset client and bounded clean shutdown.

The candidate adds automatic regression coverage for the exact activation
boundary, invalid proofs, restarts, P2P sync, pruning, reorganizations and
reindexing. The height remains dependent on a coordinated network rollout:
do not tag a production release without completing the deployment checks.

See [the activation and upgrade guide](../../auxpow-activation.md) for the
complete requirements, tests, pool integration and downgrade limitations.
