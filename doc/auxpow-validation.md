# AuxPoW candidate validation record

The proposal is based on upstream `9e491b31013bb379302d28e57803916147537a2c`.
The original AuxPoW implementation was validated at `9a84a1c`; the subsequent
validation work repairs inherited Bitcoin-specific test fixtures and extends
wallet, Qt and platform coverage. Mainnet activation remains **155000**.

## Reproducing the full suite

After building with tests enabled:

```sh
python3 contrib/auxpow/fetch_test_assets.py /tmp/btco-assets
DIR_UNIT_TEST_DATA=/tmp/btco-assets src/test/test_bitcoinoil --log_level=warning --report_level=short
QT_QPA_PLATFORM=offscreen src/qt/test/test_bitcoinoil-qt
```

The asset downloader pins Bitcoin Core's script vectors to commit
`9c61fa724af7566eaa9f97ad23c637374ef469ea` and verifies SHA256
`cd789a58ec45916e1721cdd14e82ca4c93100959f1cef4e229b22e3bf539f095`.
Without the vectors, the inherited suite emits a warning and skips that one
case. The complete recorded run includes the vectors.

## Inherited fixture repairs

The clean upstream suite originally failed (121/551 passing, with cascading
fixture aborts). The uncorrected AuxPoW candidate also failed (133/559 passing).
Those old counts are historical evidence, not the status of the repaired suite.

The repairs preserve test intent:

- Fixed address-manager ports are restored for the historical deterministic
  bucket vectors. No live network port or peer-selection implementation changes.
- Base58 and Bech32 address/key vectors are re-encoded with BTCO network prefixes
  and recomputed checksums, preserving payloads. Descriptor checksums are updated
  when their encoded keys change. Extended keys retain their existing prefixes.
- The Bloom test uses its original private scalar directly instead of decoding
  a Bitcoin WIF using BTCO rules. Expected Bloom output is unchanged.
- The SHA256 test's original 80-byte input is restored after an earlier branding
  substitution changed its bytes without changing the expected hash.
- Historical Bitcoin retarget vectors explicitly use their original timespan
  and spacing in local test parameters. Production difficulty is unchanged.
- Subsidy totals use complete 185900-block epochs, avoiding overcounting from a
  1000-block stride across a non-divisible halving boundary. The expected total
  is 1858999997955100 satoshis.
- Two signed Bitcoin transaction vectors exceed BTCO's lower monetary limit.
  The tests now require the correct monetary rejection and still execute all
  script checks on the original signed bytes.
- Message signatures use the BTCO signing domain; a crafted Bitcoin-domain
  signature is explicitly rejected. Capitalization and the Qt nested-RPC
  genesis-root expectation reflect the actual intended behavior.
- Regtest has a fixed, independently generated height-110 snapshot fixture
  (`ba5d4bc634522f09f690e352ee3759c493b35aad047f0e8f6ac2f463434f4266`,
  111 chain transactions). Mainnet snapshot trust is unchanged. The existing
  tests exercise malformed snapshots, background validation and hash mismatch;
  the fixture is not calculated from the snapshot under validation at runtime.

## Wallet upgrade and activation coverage

`wallet_upgrade_regtest.py` creates a disposable wallet with the previous
binary, mines regtest funds, encrypts and backs it up, then opens the same data
with the new binary. It verifies addresses, balance, history, lock state and
wrong-passphrase rejection, spends funds, accepts an AuxPoW reward, matures it,
restarts and restores the old encrypted backup with a rescan.

```sh
python3 contrib/auxpow/wallet_upgrade_regtest.py --old-binary=/path/to/old/bitcoinoild --binary=src/bitcoinoild
QT_QPA_PLATFORM=offscreen python3 contrib/auxpow/wallet_upgrade_regtest.py --old-binary=/path/to/old/bitcoinoild --binary=src/qt/bitcoinoil-qt
# Both binaries must be built with Berkeley DB 4.8 for the legacy format:
QT_QPA_PLATFORM=offscreen python3 contrib/auxpow/wallet_upgrade_regtest.py --legacy --old-binary=/path/to/old/bitcoinoild --binary=src/qt/bitcoinoil-qt
```

Use `contrib/auxpow/build_bdb4.sh` to build the checksum-verified BDB dependency
outside the system installation. Tests use fresh regtest directories and never
open a user wallet. Mainnet wallet backups are still required before upgrade.

The activation regression covers 120 and the exact 154999/155000 boundary,
invalid proofs, headers-only restart, P2P, pruning, reorganizations, full reindex,
chainstate reindex, verifychain and disconnected-RPC shutdown. The header test
cold-syncs 2100 consecutive AuxPoW blocks. Commands are in
[auxpow-activation.md](auxpow-activation.md).

## Recorded validation results (2026-11-01)

| Check | Result |
| --- | --- |
| macOS full unit suite, SQLite build, external script vectors included | 559/559 pass |
| macOS full unit suite, SQLite + Berkeley DB build, external vectors included | 563/563 pass |
| Linux arm64 full unit suite, SQLite build, external vectors included | 560/560 pass |
| Linux arm64 Qt interface tests | Pass |
| Linux arm64 wallet smoke, exact activation 155000 and 2100-header cold sync | Pass |
| Windows x86_64 cross-build: daemon, CLI, Qt and both test executables | Pass |
| All Qt interface test suites | Pass |
| Official old daemon to new daemon, encrypted descriptor wallet | Pass |
| Official old daemon to new Qt, encrypted descriptor and BDB wallets | Pass |
| New Qt activation regression at 120 | Pass |
| Repeated exact 154999/155000 daemon regression after fixture repairs | Pass |
| Bundled .app dependency audit, ad-hoc signature verification and wallet upgrade smoke | Pass |

Linux wallet and chain fixtures run on the VM's native filesystem; a first
wallet restore attempt on the macOS-shared virtiofs directory hit a permission
error. Repeating the same regression on native Linux storage passed without
weakening wallet permissions or skipping restore checks.

The packaged app was exercised on macOS 26.5.2 arm64. It is a local test package,
not a notarized release for every supported macOS version. The packaging helper
is `contrib/auxpow/package_macos.sh`; set `QT_BINS` and invoke it from the build
root. Release signing must use the maintainer's release process.

## Platform checks and release limits

`.github/workflows/auxpow.yml` runs the full Linux unit suite, Qt tests, an
upgrade from the previous official daemon and AuxPoW regressions.
`.github/workflows/auxpow-platforms.yml` adds macOS with both wallet formats,
a Windows cross-build and native Windows test execution. Native Windows CI
must actually pass on the PR SHA; preparing a workflow is not a passing run.

The local Windows cross-build completed on Ubuntu 24.04 arm64 using MinGW GCC
13-posix, with pinned Qt 5.15.11 and both wallet backends. This is compilation
evidence, not native Windows execution.

Cross-build repairs restore executable permissions on the depends scripts and
use the official Boost and Qt archive URLs, retaining the original dependency
hashes. The MSVC consensus source list includes the new pure-header file.

Local validation does not certify every OS version, third-party pool, hardware
wallet, GUI interaction or installation. Release signing/notarization,
independent consensus review and operator acknowledgements remain release
responsibilities. Follow [auxpow-rollout.md](auxpow-rollout.md).

## Mainnet compatibility snapshot

An isolated candidate revalidated mainnet chainstate with `-assumevalid=0`,
passed `verifychain 3 1000`, and connected to an old 25.1.1 peer. On 2026-11-01,
it reached height 152445 with matching headers, `initialblockdownload=false`,
and hash `0000000000000f1ca92545ff27a4cb6a8ef05d95b0a931ebca59d24287e0c89b`.
That left 2555 blocks before activation at the time of the check. It is not a
calendar deadline or evidence of network-wide readiness. The isolated node was
stopped after verification.
