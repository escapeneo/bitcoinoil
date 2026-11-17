#!/usr/bin/env bash
# Copyright (c) 2026 The BitcoinOil Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
#
# Build the libfmt release that depends/packages/libfmt.mk pins, for builds
# that do not use depends (CI on Linux and macOS, local development).
# Usage: contrib/mweb/build_libfmt.sh <install-prefix>
# Then: PKG_CONFIG_PATH=<install-prefix>/lib/pkgconfig ./configure ...
set -euo pipefail

PREFIX="${1:?usage: build_libfmt.sh <install-prefix>}"
VERSION=7.1.3
SHA256=5cae7072042b3043e12d53d50ef404bbb76949dad1de368d7f993a15c8c05ecc

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
curl --fail --location --silent --show-error -o "$WORK/fmt.tar.gz" "https://github.com/fmtlib/fmt/archive/${VERSION}.tar.gz"
echo "${SHA256}  $WORK/fmt.tar.gz" | shasum -a 256 -c -
tar -xzf "$WORK/fmt.tar.gz" -C "$WORK"
cmake -S "$WORK/fmt-${VERSION}" -B "$WORK/build" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$PREFIX" \
    -DCMAKE_INSTALL_LIBDIR=lib -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DFMT_DOC=OFF -DFMT_TEST=OFF -DCMAKE_POLICY_VERSION_MINIMUM=3.5
cmake --build "$WORK/build" --parallel 2
cmake --install "$WORK/build"
test -f "$PREFIX/lib/pkgconfig/fmt.pc"
