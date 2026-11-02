#!/usr/bin/env bash
# Build the pinned wallet-compatible Berkeley DB without installing system-wide.
set -euo pipefail
prefix=${1:?Usage: build_bdb4.sh ABSOLUTE_PREFIX ABSOLUTE_WORKDIR}
workdir=${2:?Usage: build_bdb4.sh ABSOLUTE_PREFIX ABSOLUTE_WORKDIR}
case "$prefix:$workdir" in /*:/*) ;; *) echo 'Both paths must be absolute' >&2; exit 1;; esac
repo=$(cd -- "$(dirname -- "$0")/../.." && pwd)
mkdir -p "$workdir"
curl --fail --location --retry 3 --max-time 180 https://download.oracle.com/berkeley-db/db-4.8.30.NC.tar.gz -o "$workdir/db.tar.gz"
python3 - "$workdir/db.tar.gz" <<'PY'
import hashlib,sys
with open(sys.argv[1], 'rb') as f:
    if hashlib.sha256(f.read()).hexdigest() != '12edc0df75bf9abd7f82f821795bcee50f42cb2e5f76a6a281b85732798364ef':
        raise SystemExit('Berkeley DB checksum mismatch')
PY
# Require a fresh source directory rather than silently patch an old build.
test ! -e "$workdir/db-4.8.30.NC"
tar -xf "$workdir/db.tar.gz" -C "$workdir"
cd "$workdir/db-4.8.30.NC"
patch -p1 < "$repo/depends/patches/bdb/clang_cxx_11.patch"
# The tarball ships these read-only; replace them with the newer copies.
chmod u+w dist/config.guess dist/config.sub
cp "$repo/depends/config.guess" "$repo/depends/config.sub" dist/
cd build_unix
CFLAGS='-Wno-error=implicit-function-declaration -Wno-error=implicit-int' ../dist/configure --prefix="$prefix" --disable-shared --enable-cxx --disable-replication
make -j2 libdb_cxx-4.8.a libdb-4.8.a
make install_lib install_include
