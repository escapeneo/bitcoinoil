# AuxPoW rollout and maintainer handoff

This is a proposed network upgrade, not an announcement of an approved release.
The candidate fixes mainnet activation at **155000**, chain ID **2828 (0x0B0C)**.
The maintainer must explicitly accept the consensus change and coordinate its
deployment. Merging a PR does not install new software on network participants.

## Decisions before merge and release

- Review the consensus implementation and [activation guide](auxpow-activation.md),
  especially height boundaries, parent proof validation, index persistence,
  headers limits and reorganizations. Obtain independent review of the final SHA.
- Run the AuxPoW workflow on the final PR SHA. Require the full unit suite, Qt tests, wallet upgrade tests and platform
  checks; preparing a workflow locally is not a successful GitHub run.
- Agree that 155000 still provides adequate deployment time. Measure the live
  tip and recent block rate; do not convert the remaining blocks into a promised
  calendar deadline. If the window is insufficient, agree a later height and
  change code, tests and documentation together before release.
- Nominate the release coordinator and record acknowledgements from pools,
  exchanges, explorers and independent full-node operators. An unanswered
  announcement is not an upgrade acknowledgement.
- Build and test each supported OS/architecture, including the Qt wallet and
  supported wallet formats. Publish authenticated release artifacts and
  checksums through the project's established release process.

## Operator readiness record

Keep this record in the release issue or another shared maintainer-controlled
location. Fill it with real operator confirmations; none are implied here.

| Role | Required evidence | Status at proposal |
| --- | --- | --- |
| Maintainer/release coordinator | Final commit, review, CI and release decision | Pending |
| Full-node operators (at least two independent) | Updated binary, reachable P2P, matching height/hash | Pending |
| Pools | Updated daemon, tested RPC proof submission and payout address, deployment acknowledgement | Pending |
| Exchanges/custodians | Updated backend, matching tip, wallet backup and deposit/withdrawal checks | Pending |
| Explorers | Updated backend, successful AuxPoW header/block decoding and indexing | Pending |
| Qt wallet users/distributors | Supported packages, backup instructions and sync verification | Pending |

The known Shears hostname and its IP are the same operator. During the rollout,
the P2P agent deliberately remains `/BitcoinOil:25.1.1/` below activation;
request operator-side `getnetworkinfo` and `getmininginfo` evidence to confirm
the installed version and activation parameters. Do not request wallet secrets
or RPC credentials.

## Upgrade procedure

1. Back up wallets and configuration; stop the node cleanly.
2. Verify the release checksum/authenticity and install the supported package.
3. Start with the existing data directory and configuration. Ordinary pre-fork
   mainnet data needs no routine reindex. Experimental AuxPoW databases may need
   a full reindex as explained in the activation guide.
4. Check `getnetworkinfo`, `getblockchaininfo`, `getpeerinfo` and `getmininginfo`.
   Expect version 25.2.0, protocol 70017, `auxpow.startheight` 155000 and
   `auxpow.chainid` 2828. Compare the same block height and hash with independent
   updated nodes; require `initialblockdownload` false.
5. Pools test `createauxblock` / `submitauxblock` on regtest before switching
   production. Before the boundary, AuxPoW work is rejected by design. Normal
   SHA256d mining remains valid before and after activation.

## Activation monitoring and incident handling

At tip 154999, `getmininginfo.auxpow.enabled` must be true for candidate 155000.
At and after 155000, both valid normal PoW and valid AuxPoW are accepted. The
first block at that height need not be merge mined. Confirm block hashes across
independent upgraded nodes and check pool submissions, explorer indexing and
exchange backend sync. Reorganizations below the boundary disable AuxPoW work
again until the next candidate reaches the activation height.

If upgraded nodes disagree, preserve logs and block hashes, pause affected
pool submissions or exchange processing under each operator's procedures, and
investigate with the maintainer. Do not bypass proof validation, force a chain
with invalidation commands, or downgrade a data directory that accepted AuxPoW.
Restoring an old binary does not restore compatibility with the upgraded chain.

## Announcement text for the approved release

Fill in the release URL and final commit only after the release decision.

> BitcoinOil's coordinated AuxPoW upgrade activates at block 155000. Install
> the approved 25.2.0 release before that block: RELEASE_URL (commit FINAL_SHA).
> This is a consensus hard fork; older nodes cannot validate merge-mined blocks.
> Ordinary SHA256d mining remains supported. Back up your wallet, stop the old
> client cleanly, install the verified package and confirm synchronization.
> Pools must separately integrate createauxblock/submitauxblock using chain ID
> 2828. Please acknowledge your upgrade and report the verified height/hash to
> the release coordinator. See the activation guide for detailed instructions.

This template has not been sent to any operator.
