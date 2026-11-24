BitcoinOil Core
===============

BitcoinOil (BTCO) uses SHA-256d and supports AuxPoW merged mining.

Stable release: [v25.3.3 — source, binaries and checksums](https://github.com/escapeneo/bitcoinoil/releases/tag/v25.3.3).

ASERT difficulty adjustment and MWEB have been active since **mainnet block 157500**
(23 November 2026). Nodes on 25.2.0 or older cannot follow the chain past block
157499 and must upgrade. v25.3.3 is recommended for pool daemons and wallets.
AuxPoW has been active since block 155000; the mining algorithm remains SHA-256d.

Pool operators
--------------

Required integration changes depend on who constructs the BTCO block, including
when BTCO is an auxiliary chain:

- With `createauxblock` / `submitauxblock` or `getauxblock`, the upgraded daemon
  constructs the complete block, including MWEB. A proxy that only passes work
  hashes and AuxPoW proofs through these RPCs needs no MWEB block serialization.
- With `getblocktemplate` + `submitblock`, request
  `{"rules":["segwit","mweb"]}`. Once MWEB activates, preserve the template
  transactions and their order, keep HogEx last, and append byte `01` followed
  by the template's `mweb` hex after the transaction list.
- Custom coinbases must preserve the required witness commitment and reward
  limits. Recompute the BTCO merkle root before committing the child-block hash
  into AuxPoW. Any intermediate proxy must pass the MWEB template data through.
- Use a transparent payout address for mining rewards.

See the [pool integration and testnet rehearsal guide](doc/mweb-testnet-rehearsal.md).
Test the actual pool/proxy submission path after testnet activation, including
transactions, before using it on mainnet.

For a pinned production source checkout:

```sh
git clone --branch v25.3.3 https://github.com/escapeneo/bitcoinoil.git
```

Follow the build dependencies and instructions in the guide, including libfmt.

What is BitcoinOil Core?
---------------------

BitcoinOil Core connects to the BitcoinOil peer-to-peer network to download and fully
validate blocks and transactions. It also includes a wallet and graphical user
interface, which can be optionally built.

Further information about BitcoinOil Core is available in the [doc folder](/doc).

License
-------

BitcoinOil Core is released under the terms of the MIT license. See [COPYING](COPYING) for more
information or see https://opensource.org/licenses/MIT.

Development Process
-------------------

The `main` branch tracks the published stable code and its documentation.
The `next` branch integrates changes for future releases. Changes in `next`
are not a new stable release until explicitly tagged and published.

Use a [release tag](https://github.com/escapeneo/bitcoinoil/releases) for production
deployments rather than relying on a moving branch. Stable code is promoted to
`main` after the release checks pass.

The contribution workflow is described in [CONTRIBUTING.md](CONTRIBUTING.md)
and useful hints for developers can be found in [doc/developer-notes.md](doc/developer-notes.md).

Testing
-------

Testing and code review is the bottleneck for development; we get more pull
requests than we can review and test on short notice. Please be patient and help out by testing
other people's pull requests, and remember this is a security-critical project where any mistake might cost people
lots of money.

### Automated Testing

Developers are strongly encouraged to write [unit tests](src/test/README.md) for new code, and to
submit new unit tests for old code. Unit tests can be compiled and run
(assuming they weren't disabled in configure) with: `make check`. Further details on running
and extending unit tests can be found in [/src/test/README.md](/src/test/README.md).

There are also [regression and integration tests](/test), written
in Python.
These tests can be run (if the [test dependencies](/test) are installed) with: `test/functional/test_runner.py`

The CI (Continuous Integration) systems make sure that every pull request is built for Windows, Linux, and macOS,
and that unit/sanity tests are run automatically.

### Manual Quality Assurance (QA) Testing

Changes should be tested by somebody other than the developer who wrote the
code. This is especially important for large or high-risk changes. It is useful
to add a test plan to the pull request description if testing the changes is
not straightforward.

Translations
------------

Changes to translations as well as new translations can be submitted to
[BitcoinOil Core's Transifex page](https://www.transifex.com/bitcoinoil/bitcoinoil/).

Translations are periodically pulled from Transifex and merged into the git repository. See the
[translation process](doc/translation_process.md) for details on how this works.

**Important**: We do not accept translation changes as GitHub pull requests because the next
pull from Transifex would automatically overwrite them again.
