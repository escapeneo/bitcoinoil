# Libraries

| Name                     | Description |
|--------------------------|-------------|
| *libbitcoinoil_cli*         | RPC client functionality used by *bitcoinoil-cli* executable |
| *libbitcoinoil_common*      | Home for common functionality shared by different executables and libraries. Similar to *libbitcoinoil_util*, but higher-level (see [Dependencies](#dependencies)). |
| *libbitcoinoil_consensus*   | Stable, backwards-compatible consensus functionality used by *libbitcoinoil_node* and *libbitcoinoil_wallet* and also exposed as a [shared library](../shared-libraries.md). |
| *libbitcoinoilconsensus*    | Shared library build of static *libbitcoinoil_consensus* library |
| *libbitcoinoil_kernel*      | Consensus engine and support library used for validation by *libbitcoinoil_node* and also exposed as a [shared library](../shared-libraries.md). |
| *libbitcoinoilqt*           | GUI functionality used by *bitcoinoil-qt* and *bitcoinoil-gui* executables |
| *libbitcoinoil_ipc*         | IPC functionality used by *bitcoinoil-node*, *bitcoinoil-wallet*, *bitcoinoil-gui* executables to communicate when [`--enable-multiprocess`](multiprocess.md) is used. |
| *libbitcoinoil_node*        | P2P and RPC server functionality used by *bitcoinoild* and *bitcoinoil-qt* executables. |
| *libbitcoinoil_util*        | Home for common functionality shared by different executables and libraries. Similar to *libbitcoinoil_common*, but lower-level (see [Dependencies](#dependencies)). |
| *libbitcoinoil_wallet*      | Wallet functionality used by *bitcoinoild* and *bitcoinoil-wallet* executables. |
| *libbitcoinoil_wallet_tool* | Lower-level wallet functionality used by *bitcoinoil-wallet* executable. |
| *libbitcoinoil_zmq*         | [ZeroMQ](../zmq.md) functionality used by *bitcoinoild* and *bitcoinoil-qt* executables. |

## Conventions

- Most libraries are internal libraries and have APIs which are completely unstable! There are few or no restrictions on backwards compatibility or rules about external dependencies. Exceptions are *libbitcoinoil_consensus* and *libbitcoinoil_kernel* which have external interfaces documented at [../shared-libraries.md](../shared-libraries.md).

- Generally each library should have a corresponding source directory and namespace. Source code organization is a work in progress, so it is true that some namespaces are applied inconsistently, and if you look at [`libbitcoinoil_*_SOURCES`](../../src/Makefile.am) lists you can see that many libraries pull in files from outside their source directory. But when working with libraries, it is good to follow a consistent pattern like:

  - *libbitcoinoil_node* code lives in `src/node/` in the `node::` namespace
  - *libbitcoinoil_wallet* code lives in `src/wallet/` in the `wallet::` namespace
  - *libbitcoinoil_ipc* code lives in `src/ipc/` in the `ipc::` namespace
  - *libbitcoinoil_util* code lives in `src/util/` in the `util::` namespace
  - *libbitcoinoil_consensus* code lives in `src/consensus/` in the `Consensus::` namespace

## Dependencies

- Libraries should minimize what other libraries they depend on, and only reference symbols following the arrows shown in the dependency graph below:

<table><tr><td>

```mermaid

%%{ init : { "flowchart" : { "curve" : "basis" }}}%%

graph TD;

bitcoinoil-cli[bitcoinoil-cli]-->libbitcoinoil_cli;

bitcoinoild[bitcoinoild]-->libbitcoinoil_node;
bitcoinoild[bitcoinoild]-->libbitcoinoil_wallet;

bitcoinoil-qt[bitcoinoil-qt]-->libbitcoinoil_node;
bitcoinoil-qt[bitcoinoil-qt]-->libbitcoinoilqt;
bitcoinoil-qt[bitcoinoil-qt]-->libbitcoinoil_wallet;

bitcoinoil-wallet[bitcoinoil-wallet]-->libbitcoinoil_wallet;
bitcoinoil-wallet[bitcoinoil-wallet]-->libbitcoinoil_wallet_tool;

libbitcoinoil_cli-->libbitcoinoil_util;
libbitcoinoil_cli-->libbitcoinoil_common;

libbitcoinoil_common-->libbitcoinoil_consensus;
libbitcoinoil_common-->libbitcoinoil_util;

libbitcoinoil_kernel-->libbitcoinoil_consensus;
libbitcoinoil_kernel-->libbitcoinoil_util;

libbitcoinoil_node-->libbitcoinoil_consensus;
libbitcoinoil_node-->libbitcoinoil_kernel;
libbitcoinoil_node-->libbitcoinoil_common;
libbitcoinoil_node-->libbitcoinoil_util;

libbitcoinoilqt-->libbitcoinoil_common;
libbitcoinoilqt-->libbitcoinoil_util;

libbitcoinoil_wallet-->libbitcoinoil_common;
libbitcoinoil_wallet-->libbitcoinoil_util;

libbitcoinoil_wallet_tool-->libbitcoinoil_wallet;
libbitcoinoil_wallet_tool-->libbitcoinoil_util;

classDef bold stroke-width:2px, font-weight:bold, font-size: smaller;
class bitcoinoil-qt,bitcoinoild,bitcoinoil-cli,bitcoinoil-wallet bold
```
</td></tr><tr><td>

**Dependency graph**. Arrows show linker symbol dependencies. *Consensus* lib depends on nothing. *Util* lib is depended on by everything. *Kernel* lib depends only on consensus and util.

</td></tr></table>

- The graph shows what _linker symbols_ (functions and variables) from each library other libraries can call and reference directly, but it is not a call graph. For example, there is no arrow connecting *libbitcoinoil_wallet* and *libbitcoinoil_node* libraries, because these libraries are intended to be modular and not depend on each other's internal implementation details. But wallet code is still able to call node code indirectly through the `interfaces::Chain` abstract class in [`interfaces/chain.h`](../../src/interfaces/chain.h) and node code calls wallet code through the `interfaces::ChainClient` and `interfaces::Chain::Notifications` abstract classes in the same file. In general, defining abstract classes in [`src/interfaces/`](../../src/interfaces/) can be a convenient way of avoiding unwanted direct dependencies or circular dependencies between libraries.

- *libbitcoinoil_consensus* should be a standalone dependency that any library can depend on, and it should not depend on any other libraries itself.

- *libbitcoinoil_util* should also be a standalone dependency that any library can depend on, and it should not depend on other internal libraries.

- *libbitcoinoil_common* should serve a similar function as *libbitcoinoil_util* and be a place for miscellaneous code used by various daemon, GUI, and CLI applications and libraries to live. It should not depend on anything other than *libbitcoinoil_util* and *libbitcoinoil_consensus*. The boundary between _util_ and _common_ is a little fuzzy but historically _util_ has been used for more generic, lower-level things like parsing hex, and _common_ has been used for bitcoinoil-specific, higher-level things like parsing base58. The difference between util and common is mostly important because *libbitcoinoil_kernel* is not supposed to depend on *libbitcoinoil_common*, only *libbitcoinoil_util*. In general, if it is ever unclear whether it is better to add code to *util* or *common*, it is probably better to add it to *common* unless it is very generically useful or useful particularly to include in the kernel.


- *libbitcoinoil_kernel* should only depend on *libbitcoinoil_util* and *libbitcoinoil_consensus*.

- The only thing that should depend on *libbitcoinoil_kernel* internally should be *libbitcoinoil_node*. GUI and wallet libraries *libbitcoinoilqt* and *libbitcoinoil_wallet* in particular should not depend on *libbitcoinoil_kernel* and the unneeded functionality it would pull in, like block validation. To the extent that GUI and wallet code need scripting and signing functionality, they should be get able it from *libbitcoinoil_consensus*, *libbitcoinoil_common*, and *libbitcoinoil_util*, instead of *libbitcoinoil_kernel*.

- GUI, node, and wallet code internal implementations should all be independent of each other, and the *libbitcoinoilqt*, *libbitcoinoil_node*, *libbitcoinoil_wallet* libraries should never reference each other's symbols. They should only call each other through [`src/interfaces/`](`../../src/interfaces/`) abstract interfaces.

## Work in progress

- Validation code is moving from *libbitcoinoil_node* to *libbitcoinoil_kernel* as part of [The libbitcoinoilkernel Project #24303](https://github.com/bitcoinoil/bitcoinoil/issues/24303)
- Source code organization is discussed in general in [Library source code organization #15732](https://github.com/bitcoinoil/bitcoinoil/issues/15732)
