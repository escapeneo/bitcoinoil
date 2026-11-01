# AuxPoW candidate validation record

Recorded on 2026-11-01. Production-code tests below were run against
`9a84a1ca5da25a724bd096f25cb66889d4194dbb`, based on upstream
`9e491b31013bb379302d28e57803916147537a2c`. Subsequent handoff changes add
documentation and the missing `primitives/pureheader.cpp` entry to the MSVC
consensus project; they do not change the tested C++ implementation.

## Focused tests

- macOS arm64: daemon, CLI and unit-test build; 10 AuxPoW/header-sync unit
  cases and 109 assertions pass.
- Ubuntu 24.04 arm64: daemon, CLI, Qt5 and unit-test build; the same focused
  unit suite passes.
- Both systems: activation at 120 and the exact 154999/155000 boundary,
  invalid proofs, headers-only restart, P2P, pruning, reorganizations,
  full reindex, chainstate reindex, verifychain and disconnected-RPC shutdown.
- Both systems: a cold node synchronizes 2100 consecutive AuxPoW blocks.
- Linux Qt5: offscreen activation regression at 120, with wallets disabled.
- The four-commit implementation patch reapplies to the clean upstream base
  and yields the exact tested source tree.

Use the commands in [auxpow-activation.md](auxpow-activation.md) to reproduce
these checks. CI must run again on the actual PR head; local ARM64 Linux
results do not certify the GitHub AMD64 runner.

## Mainnet compatibility snapshot

An isolated candidate revalidated the existing mainnet chainstate with
`-assumevalid=0`, passed `verifychain 3 1000`, and connected to an old 25.1.1
peer. A subsequent check reached height 152445, with headers at the same height,
`initialblockdownload=false`, and block hash:

```text
0000000000000f1ca92545ff27a4cb6a8ef05d95b0a931ebca59d24287e0c89b
```

That snapshot left 2555 blocks before activation. It verifies pre-fork
compatibility with the contacted peer, not independent network-wide agreement
or operator readiness. The test node was stopped after verification.

## Full inherited unit suite: not green

Both builds were run with `--log_level=error --report_level=short` on macOS
arm64. The upstream build used an unmodified `git archive` of the base SHA
above, configured without GUI/BDB/bench/fuzz, with `CXXFLAGS='-O2 -g0'`.

| Tree | Cases | Passed | Failed | Aborted (included in failed) |
| --- | ---: | ---: | ---: | ---: |
| Upstream base | 551 | 121 | 430 | 427 |
| AuxPoW implementation | 559 | 133 | 426 | 423 |

These totals include cascading failures and must not be interpreted as hundreds
of independent defects. Three address-manager assertions fail identically in
both builds (selected port count and two deterministic bucket expectations).
The upstream full run also encounters `time-too-new` fixture errors; the
candidate already adjusts the fixture mock time for BitcoinOil's genesis.

The test `bloom_tests/bloom_create_insert_key` uses a hardcoded Bitcoin WIF
secret, while BitcoinOil uses a different secret-key prefix. `DecodeSecret`
returns an invalid key and `GetPubKey` asserts. Subsequent fixtures repeatedly
abort in `AddArg`, so later suite results are not independent coverage.

The three address-manager cases and the Bloom case were each rerun in a fresh
process against both upstream and candidate; all four failed on both builds
(exit 201). Their test source files are unchanged by this proposal. This
confirms those failures are inherited; it does not prove that every later
cascading failure has the same cause or that no other regression exists.

Do not report the entire suite as passing or hide the failures with a CI success
override. The dedicated AuxPoW workflow runs the stated focused cases. Broader
test-fixture repair and a clean full-suite run remain desirable before release
and need maintainer review alongside the consensus change.

## Scope limits

Windows and macOS Qt distribution packages are not certified. The MSVC source
entry change was checked by parsing XML and validating that source paths exist;
that is not a Windows build. Wallet-disabled and headless tests do not certify
real wallet migration, UI behavior or third-party pool software.

Follow [auxpow-rollout.md](auxpow-rollout.md) before a production release.
