// Copyright (c) 2015-2022 The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <chain.h>
#include <chainparams.h>
#include <pow.h>
#include <test/asert_vectors.h>
#include <test/util/random.h>
#include <test/util/setup_common.h>

#include <boost/test/unit_test.hpp>

#include <memory>
#include <vector>

BOOST_FIXTURE_TEST_SUITE(pow_tests, BasicTestingSetup)

/* Test calculation of next difficulty target with no constraints applying */
BOOST_AUTO_TEST_CASE(get_next_work)
{
    const auto chainParams = CreateChainParams(*m_node.args, CBaseChainParams::MAIN);
    auto consensus = chainParams->GetConsensus();
    consensus.nPowTargetTimespan = 14 * 24 * 60 * 60;
    consensus.nPowTargetSpacing = 10 * 60;
    int64_t nLastRetargetTime = 1261130161; // Block #30240
    CBlockIndex pindexLast;
    pindexLast.nHeight = 32255;
    pindexLast.nTime = 1262152739;  // Block #32255
    pindexLast.nBits = 0x1d00ffff;

    // Here (and below): expected_nbits is calculated in
    // CalculateNextWorkRequired(); redoing the calculation here would be just
    // reimplementing the same code that is written in pow.cpp. Rather than
    // copy that code, we just hardcode the expected result.
    unsigned int expected_nbits = 0x1d00d86aU;
    BOOST_CHECK_EQUAL(CalculateNextWorkRequired(&pindexLast, nLastRetargetTime, consensus), expected_nbits);
    BOOST_CHECK(PermittedDifficultyTransition(consensus, pindexLast.nHeight+1, pindexLast.nBits, expected_nbits));
}

/* Test the constraint on the upper bound for next work */
BOOST_AUTO_TEST_CASE(get_next_work_pow_limit)
{
    const auto chainParams = CreateChainParams(*m_node.args, CBaseChainParams::MAIN);
    auto consensus = chainParams->GetConsensus();
    consensus.nPowTargetTimespan = 14 * 24 * 60 * 60;
    consensus.nPowTargetSpacing = 10 * 60;
    int64_t nLastRetargetTime = 1231006505; // Block #0
    CBlockIndex pindexLast;
    pindexLast.nHeight = 2015;
    pindexLast.nTime = 1233061996;  // Block #2015
    pindexLast.nBits = 0x1d00ffff;
    unsigned int expected_nbits = 0x1d00ffffU;
    BOOST_CHECK_EQUAL(CalculateNextWorkRequired(&pindexLast, nLastRetargetTime, consensus), expected_nbits);
    BOOST_CHECK(PermittedDifficultyTransition(consensus, pindexLast.nHeight+1, pindexLast.nBits, expected_nbits));
}

/* Test the constraint on the lower bound for actual time taken */
BOOST_AUTO_TEST_CASE(get_next_work_lower_limit_actual)
{
    const auto chainParams = CreateChainParams(*m_node.args, CBaseChainParams::MAIN);
    auto consensus = chainParams->GetConsensus();
    consensus.nPowTargetTimespan = 14 * 24 * 60 * 60;
    consensus.nPowTargetSpacing = 10 * 60;
    int64_t nLastRetargetTime = 1279008237; // Block #66528
    CBlockIndex pindexLast;
    pindexLast.nHeight = 68543;
    pindexLast.nTime = 1279297671;  // Block #68543
    pindexLast.nBits = 0x1c05a3f4;
    unsigned int expected_nbits = 0x1c0168fdU;
    BOOST_CHECK_EQUAL(CalculateNextWorkRequired(&pindexLast, nLastRetargetTime, consensus), expected_nbits);
    BOOST_CHECK(PermittedDifficultyTransition(consensus, pindexLast.nHeight+1, pindexLast.nBits, expected_nbits));
    // Test that reducing nbits further would not be a PermittedDifficultyTransition.
    unsigned int invalid_nbits = expected_nbits-1;
    BOOST_CHECK(!PermittedDifficultyTransition(consensus, pindexLast.nHeight+1, pindexLast.nBits, invalid_nbits));
}

/* Test the constraint on the upper bound for actual time taken */
BOOST_AUTO_TEST_CASE(get_next_work_upper_limit_actual)
{
    const auto chainParams = CreateChainParams(*m_node.args, CBaseChainParams::MAIN);
    auto consensus = chainParams->GetConsensus();
    consensus.nPowTargetTimespan = 14 * 24 * 60 * 60;
    consensus.nPowTargetSpacing = 10 * 60;
    int64_t nLastRetargetTime = 1263163443; // NOTE: Not an actual block time
    CBlockIndex pindexLast;
    pindexLast.nHeight = 46367;
    pindexLast.nTime = 1269211443;  // Block #46367
    pindexLast.nBits = 0x1c387f6f;
    unsigned int expected_nbits = 0x1d00e1fdU;
    BOOST_CHECK_EQUAL(CalculateNextWorkRequired(&pindexLast, nLastRetargetTime, consensus), expected_nbits);
    BOOST_CHECK(PermittedDifficultyTransition(consensus, pindexLast.nHeight+1, pindexLast.nBits, expected_nbits));
    // Test that increasing nbits further would not be a PermittedDifficultyTransition.
    unsigned int invalid_nbits = expected_nbits+1;
    BOOST_CHECK(!PermittedDifficultyTransition(consensus, pindexLast.nHeight+1, pindexLast.nBits, invalid_nbits));
}

BOOST_AUTO_TEST_CASE(CheckProofOfWork_test_negative_target)
{
    const auto consensus = CreateChainParams(*m_node.args, CBaseChainParams::MAIN)->GetConsensus();
    uint256 hash;
    unsigned int nBits;
    nBits = UintToArith256(consensus.powLimit).GetCompact(true);
    hash.SetHex("0x1");
    BOOST_CHECK(!CheckProofOfWork(hash, nBits, consensus));
}

BOOST_AUTO_TEST_CASE(CheckProofOfWork_test_overflow_target)
{
    const auto consensus = CreateChainParams(*m_node.args, CBaseChainParams::MAIN)->GetConsensus();
    uint256 hash;
    unsigned int nBits{~0x00800000U};
    hash.SetHex("0x1");
    BOOST_CHECK(!CheckProofOfWork(hash, nBits, consensus));
}

BOOST_AUTO_TEST_CASE(CheckProofOfWork_test_too_easy_target)
{
    const auto consensus = CreateChainParams(*m_node.args, CBaseChainParams::MAIN)->GetConsensus();
    uint256 hash;
    unsigned int nBits;
    arith_uint256 nBits_arith = UintToArith256(consensus.powLimit);
    nBits_arith *= 2;
    nBits = nBits_arith.GetCompact();
    hash.SetHex("0x1");
    BOOST_CHECK(!CheckProofOfWork(hash, nBits, consensus));
}

BOOST_AUTO_TEST_CASE(CheckProofOfWork_test_biger_hash_than_target)
{
    const auto consensus = CreateChainParams(*m_node.args, CBaseChainParams::MAIN)->GetConsensus();
    uint256 hash;
    unsigned int nBits;
    arith_uint256 hash_arith = UintToArith256(consensus.powLimit);
    nBits = hash_arith.GetCompact();
    hash_arith *= 2; // hash > nBits
    hash = ArithToUint256(hash_arith);
    BOOST_CHECK(!CheckProofOfWork(hash, nBits, consensus));
}

BOOST_AUTO_TEST_CASE(CheckProofOfWork_test_zero_target)
{
    const auto consensus = CreateChainParams(*m_node.args, CBaseChainParams::MAIN)->GetConsensus();
    uint256 hash;
    unsigned int nBits;
    arith_uint256 hash_arith{0};
    nBits = hash_arith.GetCompact();
    hash = ArithToUint256(hash_arith);
    BOOST_CHECK(!CheckProofOfWork(hash, nBits, consensus));
}

BOOST_AUTO_TEST_CASE(GetBlockProofEquivalentTime_test)
{
    const auto chainParams = CreateChainParams(*m_node.args, CBaseChainParams::MAIN);
    std::vector<CBlockIndex> blocks(10000);
    for (int i = 0; i < 10000; i++) {
        blocks[i].pprev = i ? &blocks[i - 1] : nullptr;
        blocks[i].nHeight = i;
        blocks[i].nTime = 1269211443 + i * chainParams->GetConsensus().nPowTargetSpacing;
        blocks[i].nBits = 0x207fffff; /* target 0x7fffff000... */
        blocks[i].nChainWork = i ? blocks[i - 1].nChainWork + GetBlockProof(blocks[i - 1]) : arith_uint256(0);
    }

    for (int j = 0; j < 1000; j++) {
        CBlockIndex *p1 = &blocks[InsecureRandRange(10000)];
        CBlockIndex *p2 = &blocks[InsecureRandRange(10000)];
        CBlockIndex *p3 = &blocks[InsecureRandRange(10000)];

        int64_t tdiff = GetBlockProofEquivalentTime(*p1, *p2, *p3, chainParams->GetConsensus());
        BOOST_CHECK_EQUAL(tdiff, p1->GetBlockTime() - p2->GetBlockTime());
    }
}

void sanity_check_chainparams(const ArgsManager& args, std::string chainName)
{
    const auto chainParams = CreateChainParams(args, chainName);
    const auto consensus = chainParams->GetConsensus();

    // hash genesis is correct
    BOOST_CHECK_EQUAL(consensus.hashGenesisBlock, chainParams->GenesisBlock().GetHash());

    // target timespan is an even multiple of spacing
    BOOST_CHECK_EQUAL(consensus.nPowTargetTimespan % consensus.nPowTargetSpacing, 0);

    // genesis nBits is positive, doesn't overflow and is lower than powLimit
    arith_uint256 pow_compact;
    bool neg, over;
    pow_compact.SetCompact(chainParams->GenesisBlock().nBits, &neg, &over);
    BOOST_CHECK(!neg && pow_compact != 0);
    BOOST_CHECK(!over);
    BOOST_CHECK(UintToArith256(consensus.powLimit) >= pow_compact);

    // check max target * 4*nPowTargetTimespan doesn't overflow -- see pow.cpp:CalculateNextWorkRequired()
    if (!consensus.fPowNoRetargeting) {
        arith_uint256 targ_max("0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF");
        targ_max /= consensus.nPowTargetTimespan*4;
        BOOST_CHECK(UintToArith256(consensus.powLimit) < targ_max);
    }
}

/** A chain of block indexes with chosen times, for ASERT tests. */
struct AsertChain {
    std::vector<std::unique_ptr<CBlockIndex>> blocks;

    CBlockIndex* Add(int64_t time, uint32_t bits, CBlockIndex* prev = nullptr)
    {
        if (!prev && !blocks.empty()) prev = blocks.back().get();
        auto index = std::make_unique<CBlockIndex>();
        index->pprev = prev;
        index->nHeight = prev ? prev->nHeight + 1 : 0;
        index->nTime = time;
        index->nBits = bits;
        index->BuildSkip();
        blocks.push_back(std::move(index));
        return blocks.back().get();
    }
};

BOOST_AUTO_TEST_CASE(asert_official_vectors)
{
    arith_uint256 pow_limit;
    pow_limit.SetCompact(0x1d00ffff);
    size_t rows{0};
    for (const AsertVector& v : ASERT_VECTORS) {
        arith_uint256 anchor;
        anchor.SetCompact(v.anchor_bits);
        const uint32_t got{CalculateASERT(anchor, 600, v.time_diff, v.height_diff, pow_limit, 2 * 24 * 60 * 60).GetCompact()};
        BOOST_REQUIRE_MESSAGE(got == v.expected_bits, strprintf("row %u: got %08x, expected %08x", rows, got, v.expected_bits));
        ++rows;
    }
    BOOST_CHECK_EQUAL(rows, 14000U);
}

BOOST_AUTO_TEST_CASE(asert_schedule_and_bounds)
{
    const auto chainParams = CreateChainParams(*m_node.args, CBaseChainParams::MAIN);
    const auto& consensus = chainParams->GetConsensus();
    // Mainnet: ASERT and MWEB share one fixed height.
    BOOST_CHECK_EQUAL(consensus.nAsertHeight, 157000);
    BOOST_CHECK_EQUAL(consensus.MWEBHeight, 157000);
    BOOST_CHECK(!consensus.IsAsertEnabled(156999));
    BOOST_CHECK(consensus.IsAsertEnabled(157000));

    const arith_uint256 pow_limit{UintToArith256(consensus.powLimit)};
    const int64_t T{consensus.nPowTargetSpacing};
    const int64_t half_life{3600};
    arith_uint256 anchor;
    anchor.SetCompact(0x1802aee8);

    // On schedule: unchanged. One half-life late or early: double or half.
    BOOST_CHECK(CalculateASERT(anchor, T, T, 0, pow_limit, half_life) == anchor);
    BOOST_CHECK(CalculateASERT(anchor, T, 100 * T, 99, pow_limit, half_life) == anchor);
    BOOST_CHECK(CalculateASERT(anchor, T, T + half_life, 0, pow_limit, half_life) == anchor * 2);
    BOOST_CHECK(CalculateASERT(anchor, T, T - half_life, 0, pow_limit, half_life) == anchor / 2);

    // Later time never gives a harder target.
    arith_uint256 previous{CalculateASERT(anchor, T, -5000, 10, pow_limit, half_life)};
    for (int64_t t = -4990; t < 20000; t += 37) {
        const arith_uint256 next{CalculateASERT(anchor, T, t, 10, pow_limit, half_life)};
        BOOST_REQUIRE(next >= previous);
        previous = next;
    }

    // Clamped at both ends instead of overflowing.
    BOOST_CHECK(CalculateASERT(anchor, T, int64_t{4000000000}, 0, pow_limit, half_life) == pow_limit);
    BOOST_CHECK(CalculateASERT(anchor, T, -int64_t{4000000000}, 0, pow_limit, half_life) == arith_uint256{1});

    // Regtest's limit has only one leading zero bit.
    const auto regtest = CreateChainParams(*m_node.args, CBaseChainParams::REGTEST);
    const arith_uint256 regtest_limit{UintToArith256(regtest->GetConsensus().powLimit)};
    BOOST_CHECK(CalculateASERT(regtest_limit, T, T, 0, regtest_limit, half_life).GetCompact() == regtest_limit.GetCompact());
    BOOST_CHECK(CalculateASERT(regtest_limit, T, T + half_life, 0, regtest_limit, half_life).GetCompact() == regtest_limit.GetCompact());
    BOOST_CHECK(CalculateASERT(regtest_limit, T, T - half_life, 0, regtest_limit, half_life).GetCompact() == arith_uint256{regtest_limit / 2}.GetCompact());
}

BOOST_AUTO_TEST_CASE(asert_activation_and_anchor)
{
    const auto chainParams = CreateChainParams(*m_node.args, CBaseChainParams::MAIN);
    auto consensus = chainParams->GetConsensus();
    const int64_t T{consensus.nPowTargetSpacing};
    const uint32_t bits{0x1802aee8};
    consensus.nAsertHeight = 200;
    consensus.V2ForkHeight = 0; // LWMA from the start, as after block 3690 on mainnet
    consensus.nAsertHalfLife = 3600;

    AsertChain chain;
    int64_t time{1700000000};
    for (int h = 0; h < 199; ++h) chain.Add(time += T, bits);
    // Height 198 is the tip; the block at 199 still follows LWMA.
    CBlockHeader header;
    BOOST_CHECK_EQUAL(GetNextWorkRequired(chain.blocks.back().get(), &header, consensus),
                      LwmaCalculateNextWorkRequired(chain.blocks.back().get(), consensus));

    // Anchor at height 199, mined on schedule: block 200 keeps its target.
    CBlockIndex* anchor{chain.Add(time += T, bits)};
    BOOST_CHECK_EQUAL(anchor->nHeight, 199);
    BOOST_CHECK_EQUAL(GetNextWorkRequired(anchor, &header, consensus), bits);
    BOOST_CHECK(PermittedDifficultyTransition(consensus, 200, bits, 0x1d00ffff));
    BOOST_CHECK(!PermittedDifficultyTransition(consensus, 199, bits, 0x1d00ffff));

    // Fast blocks raise the difficulty, a long gap lowers it again, and the
    // result depends only on total time and height, not on the path.
    CBlockIndex* fork_point{anchor};
    arith_uint256 anchor_target, target;
    anchor_target.SetCompact(bits);
    for (int i = 0; i < 20; ++i) chain.Add(time += 10, bits);
    target.SetCompact(GetNextWorkRequired(chain.blocks.back().get(), &header, consensus));
    BOOST_CHECK(target < anchor_target / 2);
    CBlockIndex* slow{chain.Add(time += 20 * (T - 10) + T, bits)};
    BOOST_CHECK_EQUAL(GetNextWorkRequired(slow, &header, consensus), bits);

    // Another branch from the anchor has its own history but the same anchor.
    CBlockIndex* branch{chain.Add(fork_point->GetBlockTime() + T + 3600, bits, fork_point)};
    target.SetCompact(GetNextWorkRequired(branch, &header, consensus));
    BOOST_CHECK(target == anchor_target * 2);
    // The first branch is unaffected.
    BOOST_CHECK_EQUAL(GetNextWorkRequired(slow, &header, consensus), bits);

    // A timestamp before the previous block is handled.
    CBlockIndex* backwards{chain.Add(branch->GetBlockTime() - 600, bits, branch)};
    target.SetCompact(GetNextWorkRequired(backwards, &header, consensus));
    BOOST_CHECK(target < anchor_target * 2 && target > anchor_target);

    // With no-retargeting set, as on regtest, ASERT still applies once enabled.
    consensus.fPowNoRetargeting = true;
    BOOST_CHECK(GetNextWorkRequired(branch, &header, consensus) != bits);
    consensus.nAsertHeight = Consensus::ASERT_DISABLED;
    BOOST_CHECK_EQUAL(GetNextWorkRequired(branch, &header, consensus), bits);
}

BOOST_AUTO_TEST_CASE(ChainParams_MAIN_sanity)
{
    sanity_check_chainparams(*m_node.args, CBaseChainParams::MAIN);
}

BOOST_AUTO_TEST_CASE(ChainParams_REGTEST_sanity)
{
    sanity_check_chainparams(*m_node.args, CBaseChainParams::REGTEST);
}

BOOST_AUTO_TEST_CASE(ChainParams_TESTNET_sanity)
{
    sanity_check_chainparams(*m_node.args, CBaseChainParams::TESTNET);
}

BOOST_AUTO_TEST_CASE(ChainParams_SIGNET_sanity)
{
    sanity_check_chainparams(*m_node.args, CBaseChainParams::SIGNET);
}

BOOST_AUTO_TEST_SUITE_END()
