// Copyright (c) 2009-2010 Satoshi Nakamoto
// Copyright (c) 2009-2022 The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef BITCOINOIL_POW_H
#define BITCOINOIL_POW_H

#include <arith_uint256.h>
#include <consensus/params.h>

#include <stdint.h>

class CBlockHeader;
class CBlockIndex;
class PoWHash;

unsigned int GetNextWorkRequired(const CBlockIndex* pindexLast, const CBlockHeader *pblock, const Consensus::Params&);
unsigned int CalculateNextWorkRequired(const CBlockIndex* pindexLast, int64_t nFirstBlockTime, const Consensus::Params&);
unsigned int LwmaCalculateNextWorkRequired(const CBlockIndex* pindexLast, const Consensus::Params&);

/**
 * ASERT (aserti3) target, as specified for Bitcoin Cash in November 2020.
 *
 * @param refTarget          Target of the anchor block.
 * @param nPowTargetSpacing  Ideal seconds between blocks.
 * @param nTimeDiff          Time of the last block minus time of the anchor's parent.
 * @param nHeightDiff        Height of the last block minus height of the anchor.
 * @param powLimit           Easiest target allowed.
 * @param nHalfLife          Seconds off schedule that double or halve the target.
 */
arith_uint256 CalculateASERT(const arith_uint256& refTarget, int64_t nPowTargetSpacing, int64_t nTimeDiff, int64_t nHeightDiff, const arith_uint256& powLimit, int64_t nHalfLife) noexcept;

/** Target for the block after pindexLast under ASERT. The anchor is found on
 *  pindexLast's own branch, so a reorganisation across it needs no cache. */
unsigned int GetNextASERTWorkRequired(const CBlockIndex* pindexLast, const Consensus::Params& params);

/** Check whether a block hash satisfies the proof-of-work requirement specified by nBits */
bool CheckProofOfWork(const PoWHash& hash, unsigned int nBits, const Consensus::Params&);

/**
 * Check proof of work of a block header, taking auxpow into account.
 * @param block The block header.
 * @param params Consensus parameters.
 * @return True iff the PoW is correct.
 */
bool CheckProofOfWork(const CBlockHeader& block, const Consensus::Params& params);

/**
 * Return false if the proof-of-work requirement specified by new_nbits at a
 * given height is not possible, given the proof-of-work on the prior block as
 * specified by old_nbits.
 *
 * This function only checks that the new value is within a factor of 4 of the
 * old value for blocks at the difficulty adjustment interval, and otherwise
 * requires the values to be the same.
 *
 * Always returns true at ASERT heights: one block after a long gap may
 * legitimately move the target by more than any fixed factor.
 *
 * Always returns true on networks where min difficulty blocks are allowed,
 * such as regtest/testnet.
 */
bool PermittedDifficultyTransition(const Consensus::Params& params, int64_t height, uint32_t old_nbits, uint32_t new_nbits);

#endif // BITCOINOIL_POW_H
