# 25.1.0 Release Notes

BitcoinOil version 25.1.0 is now available from:

  <https://github.com/escapeneo/bitcoinoil/tree/v25.1.0/>

This release brings new features, a range of bug fixes, performance improvements, and protocol updates that align with Bitcoin's v25 release while maintaining BitcoinOil's unique enhancements and goals.

Please report any issues using the GitHub issue tracker:

  <https://github.com/escapeneo/bitcoinoil/issues>

## How to Upgrade

The upgrade process for BitcoinOil is straightforward. Download the latest version from the [release page](https://github.com/escapeneo/bitcoinoil/releases/tag/v25.1.0). If you are upgrading from an older version, ensure the application is fully shut down before replacing the previous installation. 

- **On Windows**: Run the installer.
- **On macOS**: Copy over the `/Applications/BitcoinOil-Qt` file.
- **On Linux**: Replace the `bitcoinoild` and `bitcoinoil-qt` binaries as needed.

Older wallet versions are generally supported, though certain data migrations may require additional time when upgrading from a much earlier version.

## Compatibility

BitcoinOil is extensively tested on Linux, macOS 10.15+, and Windows 7 or newer. While it is expected to work on other Unix-like systems, official support is limited to the platforms mentioned.

## Consensus and Protocol Changes | Security and Stability Improvements

- **Soft Fork Activation Controls**: This release includes improved control mechanisms for soft fork activations, allowing for smoother integration of consensus rule updates at specified block heights without requiring hard forks.

- **Enhanced Version Bits Management**: New controls for version bits improve compatibility with future protocol adjustments, reducing the likelihood of network splits or unintentional hard forks.

- **Taproot Compatibility and Future Upgrade Readiness**: This version introduces the necessary groundwork to ensure compatibility with Taproot and other anticipated consensus changes. These enhancements are drawn from Bitcoin's v25 improvements and adapted for BitcoinOil’s ecosystem.

## Notable Changes

- [Implementation of LWMA Difficulty Algorithm](https://github.com/escapeneo/bitcoinoil/commit/f196b1fedc6ba848b19f151851d1d635bbb5d1d2): This change introduces the LWMA (Linear Weighted Moving Average) difficulty adjustment algorithm, improving block generation stability and providing better resistance to hashrate fluctuations.

- [New RPC Commands for Enhanced Control](https://github.com/escapeneo/bitcoinoil/commit/4d7c6ffdfc3cd9a6786a024f2b9de19656a84cbb): Adds new RPC commands to enhance wallet management and provide advanced control for developers and node operators.

- [Activation Threshold and Confirmation Window Enhancements](https://github.com/escapeneo/bitcoinoil/commit/b3282a38030b4deaa0c058058356492579895e23): Introduces `nRuleChangeActivationThresholdV2` and `nMinerConfirmationWindowV2`, improving security and ensuring a smoother transition for consensus rule updates.

## Credits

This release is the result of the dedicated efforts of the BitcoinOil development team, with substantial upstream contributions and inspiration from the Bitcoin Core team. We extend our gratitude to the Bitcoin Core developers for their invaluable foundational work that supports ongoing advancements in BitcoinOil.