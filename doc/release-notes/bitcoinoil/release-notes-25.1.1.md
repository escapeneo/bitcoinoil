# **Release Notes - 25.1.1**

---

#### **BitcoinOil Core v25.1.1 (Critical Update)**
This release addresses critical issues identified in the v25.1.0 release, along with additional fixes to ensure smoother syncing, reindexing, and overall blockchain stability. It is a highly recommended update for all users.

---

#### **Bug Fixes**
- **Reindexing Issues Fixed**: Resolved a longstanding issue where reindexing failed due to invalid block height validation at specific checkpoints, particularly affecting blocks at height 0 and 1. Added height-based exceptions to `validation.cpp`.
  [Commit](https://github.com/escapeneo/bitcoinoil/commit/4152a36ae5770217324fb4a763b02ee7ebd5fdf8)
- **Genesis Block Validation**: Enhanced logic in `ContextualCheckBlock` to skip unnecessary validation checks for the genesis block and known problematic blocks (e.g., height 1).
- **Syncing Enhancements**: Fixed syncing issues caused by misconfigured `nMinimumChainWork` and `defaultAssumeValid` values for blocks past height 2000.
  [Commit](https://github.com/escapeneo/bitcoinoil/commit/5df32a3196d22cde63329166532d041fdcd99efc)  
- **Branch Length Validations**: Improved handling of invalid block branches, ensuring proper rejection and logging for competing forks.

#### **Improvements**
- **Height-Based Coinbase Validation**: Refactored validation logic to handle exceptions gracefully while maintaining security and consensus integrity.
- **Dynamic Logging for Validation**: Added debug logs to `validation.cpp` to provide clear insights into height-based decisions during reindexing and syncing.
- **Peer Compatibility Enhancements**: Improved peer connection logic, ensuring proper compatibility checks for nodes running v25.1.x versions.
- **Deployment Handling for CSV and Taproot**: Refined deployment checks for consistent behavior across all active deployment versions.
- **Versionbit Checker**: Enhanced `getversionbitsinfo` RPC command with deployment descriptions and better handling of undefined bits.  
  [Commit](https://github.com/escapeneo/bitcoinoil/commit/cf5d25577682cba9d0226ed57c6753857d6a6554)  
- **Activation Thresholds**: Refined `nMinerConfirmationWindow` and `nRuleChangeActivationThreshold` handling for improved syncing at varying heights.  
  [Commit](https://github.com/escapeneo/bitcoinoil/commit/68b0410d0383c0a20ff1669af17eb3afd14190e5)

---

### **Upgrading**
1. Stop your current BitcoinOil wallet or node.
2. Replace the binaries with the v25.1.1 binaries.
3. Start the wallet/node. Any fixes to the blockchain or syncing will automatically apply.

**Compatibility Note**: Wallets running v25.0.0 or v25.1.0 may encounter reindexing and syncing issues. It is strongly advised to upgrade to v25.1.1 to avoid these problems.

---

### **For Developers**
The following files have been updated:
- **`validation.cpp`**:
  - Added height-based exceptions for blocks 0 and 1.
  - Improved logging for block validation.
- **`chainparams.cpp`**:
  - Updated `nMinimumChainWork` and `defaultAssumeValid` to reflect the latest stable checkpoints.
- **`versionbits.cpp`**:
  - Enhanced logic for handling active and future deployments, ensuring alignment with network rules.
- **`net_processing.cpp`**:
  - Adjusted logic for peer compatibility to avoid unnecessary disconnects.

For detailed changes, see the commits included in this release.

---


### **All commits**
[4152a36ae5...](https://github.com/escapeneo/bitcoinoil/commit/4152a36ae5770217324fb4a763b02ee7ebd5fdf8)

[5df32a3196...](https://github.com/escapeneo/bitcoinoil/commit/5df32a3196d22cde63329166532d041fdcd99efc)

[cf5d255776...](https://github.com/escapeneo/bitcoinoil/commit/cf5d25577682cba9d0226ed57c6753857d6a6554)

[68b0410d03...](https://github.com/escapeneo/bitcoinoil/commit/68b0410d0383c0a20ff1669af17eb3afd14190e5)

[d2279676eb...](https://github.com/escapeneo/bitcoinoil/commit/d2279676eb9670b38225ccab3dc2460dc98c041c)

[13e6d15b6a...](https://github.com/escapeneo/bitcoinoil/commit/13e6d15b6a05411d3a7459e5f5940e29a427b2f7)

[e7e8f60426...](https://github.com/escapeneo/bitcoinoil/commit/e7e8f6042676321211b6f6db4e937627849d7034)

