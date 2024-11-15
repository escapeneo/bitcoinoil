// Copyright (c) 2011-2020 The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef BITCOINOIL_QT_BITCOINOILADDRESSVALIDATOR_H
#define BITCOINOIL_QT_BITCOINOILADDRESSVALIDATOR_H

#include <QValidator>

/** Base58 entry widget validator, checks for valid characters and
 * removes some whitespace.
 */
class BitcoinOilAddressEntryValidator : public QValidator
{
    Q_OBJECT

public:
    explicit BitcoinOilAddressEntryValidator(QObject *parent);

    State validate(QString &input, int &pos) const override;
};

/** BitcoinOil address widget validator, checks for a valid bitcoinoil address.
 */
class BitcoinOilAddressCheckValidator : public QValidator
{
    Q_OBJECT

public:
    explicit BitcoinOilAddressCheckValidator(QObject *parent);

    State validate(QString &input, int &pos) const override;
};

#endif // BITCOINOIL_QT_BITCOINOILADDRESSVALIDATOR_H
