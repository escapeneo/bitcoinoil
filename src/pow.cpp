// Copyright (c) 2009-2010 Satoshi Nakamoto
// Copyright (c) 2009-2022 The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <pow.h>

#include <arith_uint256.h>
#include <auxpow.h>
#include <chain.h>
#include <logging.h>
#include <primitives/block.h>
#include <uint256.h>

#include <cstdlib>

unsigned int GetNextWorkRequired(const CBlockIndex* pindexLast, const CBlockHeader *pblock, const Consensus::Params& params)
{
    assert(pindexLast != nullptr);
    // ASERT is checked first so that regtest can opt in with -asertheight.
    if (params.IsAsertEnabled(pindexLast->nHeight + 1)) return GetNextASERTWorkRequired(pindexLast, params);
    // Regtest must stay at its fixed target even after the LWMA fork height.
    // Mainnet and testnet do not enable this flag.
    if (params.fPowNoRetargeting) return pindexLast->nBits;
    unsigned int nProofOfWorkLimit = UintToArith256(params.powLimit).GetCompact();

    if (pindexLast->nHeight >= params.V2ForkHeight) {
        return LwmaCalculateNextWorkRequired(pindexLast, params);
    } else {
    // Only change once per difficulty adjustment interval
    if ((pindexLast->nHeight+1) % params.DifficultyAdjustmentInterval() != 0)
    {
        if (params.fPowAllowMinDifficultyBlocks)
        {
            // Special difficulty rule for testnet:
            // If the new block's timestamp is more than 2* 10 minutes
            // then allow mining of a min-difficulty block.
            if (pblock->GetBlockTime() > pindexLast->GetBlockTime() + params.nPowTargetSpacing*2)
                return nProofOfWorkLimit;
            else
            {
                // Return the last non-special-min-difficulty-rules-block
                const CBlockIndex* pindex = pindexLast;
                while (pindex->pprev && pindex->nHeight % params.DifficultyAdjustmentInterval() != 0 && pindex->nBits == nProofOfWorkLimit)
                    pindex = pindex->pprev;
                return pindex->nBits;
            }
        }
        return pindexLast->nBits;
    }

    // Go back by what we want to be 14 days worth of blocks
    int nHeightFirst = pindexLast->nHeight - (params.DifficultyAdjustmentInterval()-1);
    assert(nHeightFirst >= 0);
    const CBlockIndex* pindexFirst = pindexLast->GetAncestor(nHeightFirst);
    assert(pindexFirst);

    return CalculateNextWorkRequired(pindexLast, pindexFirst->GetBlockTime(), params);
    }
}

unsigned int LwmaCalculateNextWorkRequired(const CBlockIndex* pindexLast, const Consensus::Params& params)
{
    const int64_t T = params.nPowTargetSpacing;
    const int64_t N = 116;
    const int64_t k = N * (N + 1) * T / 2;
    const int64_t height = pindexLast->nHeight;
    const arith_uint256 powLimit = UintToArith256(params.powLimit);

    if (height < N) { return powLimit.GetCompact(); }

    arith_uint256 sumTarget, nextTarget;
    int64_t thisTimestamp, previousTimestamp;
    int64_t t = 0, j = 0;

    const CBlockIndex* blockPreviousTimestamp = pindexLast->GetAncestor(height - N);
    previousTimestamp = blockPreviousTimestamp->GetBlockTime();

    // Loop through N most recent blocks. 
    for (int64_t i = height - N + 1; i <= height; i++) {
        const CBlockIndex* block = pindexLast->GetAncestor(i);
        thisTimestamp = (block->GetBlockTime() > previousTimestamp) ? 
                            block->GetBlockTime() : previousTimestamp + 1;

        int64_t solvetime = std::min(6 * T, thisTimestamp - previousTimestamp);
        previousTimestamp = thisTimestamp;

        j++;
        t += solvetime * j; // Weighted solvetime sum.
        arith_uint256 target;
        target.SetCompact(block->nBits);
        sumTarget += target / (k * N);
    }
    nextTarget = t * sumTarget;

    if (nextTarget > powLimit) { nextTarget = powLimit; }

    return nextTarget.GetCompact();
}

arith_uint256 CalculateASERT(const arith_uint256& refTarget, const int64_t nPowTargetSpacing, const int64_t nTimeDiff, const int64_t nHeightDiff, const arith_uint256& powLimit, const int64_t nHalfLife) noexcept
{
    assert(refTarget > 0 && refTarget <= powLimit);
    assert(nHeightDiff >= 0);
    assert(nHalfLife > 0);

    // The 17-bit factor below needs headroom above the target. Real networks
    // keep 32 leading zero bits in powLimit. Regtest does not, so its targets
    // are scaled down for the calculation and back up afterwards.
    const unsigned int scale{powLimit.bits() > 224 ? powLimit.bits() - 224 : 0};
    const arith_uint256 limit{powLimit >> scale};
    arith_uint256 target{refTarget >> scale};
    if (target == 0) target = 1;

    // Heights and header times keep this far inside int64_t.
    assert(std::llabs(nTimeDiff - nPowTargetSpacing * nHeightDiff) < (int64_t{1} << (63 - 16)));
    // Truncating division, as in the specification.
    const int64_t exponent{((nTimeDiff - nPowTargetSpacing * (nHeightDiff + 1)) * 65536) / nHalfLife};

    // Split into whole doublings and a 16-bit fraction, flooring explicitly
    // instead of relying on right shifts of negative numbers.
    int64_t shifts{exponent / 65536};
    if (exponent < 0 && exponent % 65536 != 0) --shifts;
    const uint64_t frac{static_cast<uint64_t>(exponent - shifts * 65536)};
    assert(frac < 65536);

    // 2^x ~= 1 + 0.695502049*x + 0.2262698*x^2 + 0.0782318*x^3 for 0 <= x < 1.
    const uint32_t factor{65536 + static_cast<uint32_t>((
        195766423245049ULL * frac +
        971821376ULL * frac * frac +
        5127ULL * frac * frac * frac +
        (1ULL << 47)) >> 48)};

    target *= factor;

    // Undo the 16 fractional bits of the factor together with the doublings.
    shifts -= 16;
    if (shifts <= 0) {
        if (shifts <= -256) {
            target = 0;
        } else {
            target >>= static_cast<unsigned int>(-shifts);
        }
    } else if (shifts >= 256) {
        target = limit;
    } else {
        const arith_uint256 shifted{target << static_cast<unsigned int>(shifts)};
        // A shift that loses bits means the result is beyond the limit.
        target = (shifted >> static_cast<unsigned int>(shifts)) != target ? limit : shifted;
    }

    if (target == 0) {
        target = 1;
    } else if (target > limit) {
        target = limit;
    }
    target <<= scale;
    return target > powLimit ? powLimit : target;
}

unsigned int GetNextASERTWorkRequired(const CBlockIndex* pindexLast, const Consensus::Params& params)
{
    assert(pindexLast != nullptr);
    assert(params.nAsertHeight >= 1 && pindexLast->nHeight >= params.nAsertHeight - 1);

    // The anchor is the last block before ASERT. Its target came from the
    // previous rules, and every later target follows from it.
    const CBlockIndex* anchor{pindexLast->GetAncestor(params.nAsertHeight - 1)};
    assert(anchor != nullptr);
    const int64_t anchor_parent_time{anchor->pprev ? anchor->pprev->GetBlockTime() : anchor->GetBlockTime() - params.nPowTargetSpacing};

    const arith_uint256 pow_limit{UintToArith256(params.powLimit)};
    arith_uint256 ref_target;
    ref_target.SetCompact(anchor->nBits);
    if (ref_target > pow_limit) ref_target = pow_limit;

    return CalculateASERT(ref_target,
                          params.nPowTargetSpacing,
                          pindexLast->GetBlockTime() - anchor_parent_time,
                          pindexLast->nHeight - anchor->nHeight,
                          pow_limit,
                          params.nAsertHalfLife).GetCompact();
}

unsigned int CalculateNextWorkRequired(const CBlockIndex* pindexLast, int64_t nFirstBlockTime, const Consensus::Params& params)
{
    if (params.fPowNoRetargeting)
        return pindexLast->nBits;

    // Limit adjustment step
    int64_t nActualTimespan = pindexLast->GetBlockTime() - nFirstBlockTime;
    if (nActualTimespan < params.nPowTargetTimespan/4)
        nActualTimespan = params.nPowTargetTimespan/4;
    if (nActualTimespan > params.nPowTargetTimespan*4)
        nActualTimespan = params.nPowTargetTimespan*4;

    // Retarget
    const arith_uint256 bnPowLimit = UintToArith256(params.powLimit);
    arith_uint256 bnNew;
    bnNew.SetCompact(pindexLast->nBits);
    bnNew *= nActualTimespan;
    bnNew /= params.nPowTargetTimespan;

    if (bnNew > bnPowLimit)
        bnNew = bnPowLimit;

    return bnNew.GetCompact();
}

// Check that on difficulty adjustments, the new difficulty does not increase
// or decrease beyond the permitted limits.
bool PermittedDifficultyTransition(const Consensus::Params& params, int64_t height, uint32_t old_nbits, uint32_t new_nbits)
{
    if (params.fPowAllowMinDifficultyBlocks) return true;
    if (params.IsAsertEnabled(height)) return true;

    if (height % params.DifficultyAdjustmentInterval() == 0) {
        int64_t smallest_timespan = params.nPowTargetTimespan/4;
        int64_t largest_timespan = params.nPowTargetTimespan*4;

        const arith_uint256 pow_limit = UintToArith256(params.powLimit);
        arith_uint256 observed_new_target;
        observed_new_target.SetCompact(new_nbits);

        // Calculate the largest difficulty value possible:
        arith_uint256 largest_difficulty_target;
        largest_difficulty_target.SetCompact(old_nbits);
        largest_difficulty_target *= largest_timespan;
        largest_difficulty_target /= params.nPowTargetTimespan;

        if (largest_difficulty_target > pow_limit) {
            largest_difficulty_target = pow_limit;
        }

        // Round and then compare this new calculated value to what is
        // observed.
        arith_uint256 maximum_new_target;
        maximum_new_target.SetCompact(largest_difficulty_target.GetCompact());
        if (maximum_new_target < observed_new_target) return false;

        // Calculate the smallest difficulty value possible:
        arith_uint256 smallest_difficulty_target;
        smallest_difficulty_target.SetCompact(old_nbits);
        smallest_difficulty_target *= smallest_timespan;
        smallest_difficulty_target /= params.nPowTargetTimespan;

        if (smallest_difficulty_target > pow_limit) {
            smallest_difficulty_target = pow_limit;
        }

        // Round and then compare this new calculated value to what is
        // observed.
        arith_uint256 minimum_new_target;
        minimum_new_target.SetCompact(smallest_difficulty_target.GetCompact());
        if (minimum_new_target > observed_new_target) return false;
    } else if (old_nbits != new_nbits) {
        return false;
    }
    return true;
}

bool CheckProofOfWork(uint256 hash, unsigned int nBits, const Consensus::Params& params)
{
    bool fNegative;
    bool fOverflow;
    arith_uint256 bnTarget;

    bnTarget.SetCompact(nBits, &fNegative, &fOverflow);

    // Check range
    if (fNegative || bnTarget == 0 || fOverflow || bnTarget > UintToArith256(params.powLimit))
        return false;

    // Check proof of work matches claimed amount
    if (UintToArith256(hash) > bnTarget)
        return false;

    return true;
}

bool CheckProofOfWork(const CBlockHeader& block, const Consensus::Params& params)
{
    /* BitcoinOil: only merge-mined blocks carry a chain ID.  Regular blocks
       (including all blocks before nAuxpowStartHeight, which use BIP9-style
       versions like 0x20000000) are checked exactly as before.  Whether
       auxpow is allowed at this height is checked in
       ContextualCheckBlockHeader where the height is known.  */
    if (block.IsAuxpow() && params.fStrictChainId
        && block.GetChainId() != params.nAuxpowChainId)
        return error("%s : block does not have our chain ID"
                     " (got %d, expected %d, full nVersion %d)",
                     __func__, block.GetChainId(),
                     params.nAuxpowChainId, block.nVersion);

    /* If there is no auxpow, just check the block hash.  */
    if (!block.auxpow)
    {
        if (block.IsAuxpow())
            return error("%s : no auxpow on block with auxpow version",
                         __func__);

        if (!CheckProofOfWork(block.GetHash(), block.nBits, params))
            return error("%s : non-AUX proof of work failed", __func__);

        return true;
    }

    /* We have auxpow.  Check it.  */
    if (!block.IsAuxpow())
        return error("%s : auxpow on block with non-auxpow version", __func__);

    if (!CheckProofOfWork(block.auxpow->getParentBlockHash(), block.nBits, params))
        return error("%s : AUX proof of work failed", __func__);
    if (!block.auxpow->check(block.GetHash(), block.GetChainId(), params))
        return error("%s : AUX POW is not valid", __func__);

    return true;
}
