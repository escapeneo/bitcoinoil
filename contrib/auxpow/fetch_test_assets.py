#!/usr/bin/env python3
"""Fetch the pinned upstream script vectors, verifying their SHA256 digest."""
import argparse
import hashlib
from pathlib import Path
from urllib.request import urlopen

REVISION = '9c61fa724af7566eaa9f97ad23c637374ef469ea'
SHA256 = 'cd789a58ec45916e1721cdd14e82ca4c93100959f1cef4e229b22e3bf539f095'
URL = f'https://raw.githubusercontent.com/bitcoin-core/qa-assets/{REVISION}/unit_test_data/script_assets_test.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    target = args.directory / 'script_assets_test.json'
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == SHA256:
        return
    with urlopen(URL, timeout=120) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError('Script asset checksum mismatch')
    temporary = target.with_suffix('.json.tmp')
    temporary.write_bytes(data)
    temporary.replace(target)


if __name__ == '__main__':
    main()
