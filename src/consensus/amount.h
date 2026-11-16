// Copyright (c) 2009-2010 Satoshi Nakamoto
// Copyright (c) 2009-2020 The Bitcoin Core developers
// Copyright (c) 2024 The BitcoinOil Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef BITCOINOIL_CONSENSUS_AMOUNT_H
#define BITCOINOIL_CONSENSUS_AMOUNT_H

#include <cstdint>

/** Amount in satoshis (Can be negative) */
typedef int64_t CAmount;

/** The amount of satoshis in one BTCO. */
static constexpr CAmount COIN = 100000000;

/** No amount larger than this (in satoshi) is valid.
 *
 * Note that this constant is *not* the total money supply, which in BitcoinOil
 * currently happens to be less than 21,000,000 BTCO for various reasons, but
 * rather a sanity check. As this sanity check is used by consensus-critical
 * validation code, the exact value of the MAX_MONEY constant is consensus
 * critical; in unusual circumstances like a(nother) overflow bug that allowed
 * for the creation of coins out of thin air modification could lead to a fork.
 * */
static constexpr CAmount MAX_MONEY = 18590000 * COIN;
inline bool MoneyRange(const CAmount& nValue) { return (nValue >= 0 && nValue <= MAX_MONEY); }

#endif // BITCOINOIL_CONSENSUS_AMOUNT_H
