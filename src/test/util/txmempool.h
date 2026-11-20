// Copyright (c) 2022 The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef BITCOINOIL_TEST_UTIL_TXMEMPOOL_H
#define BITCOINOIL_TEST_UTIL_TXMEMPOOL_H

#include <txmempool.h>
#include <util/time.h>

namespace node {
struct NodeContext;
}

CTxMemPool::Options MemPoolOptionsForTest(const node::NodeContext& node);

struct TestMemPoolEntryHelper {
    // Default values
    CAmount nFee{0};
    NodeSeconds time{};
    unsigned int nHeight{1};
    bool spendsCoinbase{false};
    unsigned int sigOpCost{4};
    LockPoints lp;

    CTxMemPoolEntry FromTx(const CMutableTransaction& tx) const;
    CTxMemPoolEntry FromTx(const CTransactionRef& tx) const;

    // Change the default value
    TestMemPoolEntryHelper& Fee(CAmount _fee) { nFee = _fee; return *this; }
    TestMemPoolEntryHelper& Time(NodeSeconds tp) { time = tp; return *this; }
    TestMemPoolEntryHelper& Height(unsigned int _height) { nHeight = _height; return *this; }
    TestMemPoolEntryHelper& SpendsCoinbase(bool _flag) { spendsCoinbase = _flag; return *this; }
    TestMemPoolEntryHelper& SigOpsCost(unsigned int _sigopsCost) { sigOpCost = _sigopsCost; return *this; }
};

/** Remove every transaction from the mempool. Bitcoin Core 25 no longer has
 *  CTxMemPool::clear(); the MWEB tests ported from Litecoin still need it. */
inline void ClearMempool(CTxMemPool& pool)
{
    LOCK2(::cs_main, pool.cs);
    std::vector<CTransactionRef> txs;
    for (const auto& entry : pool.mapTx) txs.push_back(entry.GetSharedTx());
    for (const auto& tx : txs) pool.removeRecursive(*tx, MemPoolRemovalReason::REPLACED);
}

#endif // BITCOINOIL_TEST_UTIL_TXMEMPOOL_H
