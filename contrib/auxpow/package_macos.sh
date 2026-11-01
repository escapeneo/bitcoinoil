#!/usr/bin/env bash
# Package a local test app. Ad-hoc signing is not Developer ID notarization.
set -euo pipefail
qt_bins=${QT_BINS:?Set QT_BINS to the Qt bin directory containing macdeployqt}
output=${1:?Usage: QT_BINS=/path/to/qt/bin package_macos.sh OUTPUT_ZIP}
test "$(uname -s)" = Darwin
app=BitcoinOil-Qt.app
make "$app/Contents/PkgInfo" "$app/Contents/Resources/empty.lproj" \
  "$app/Contents/Resources/bitcoinoil.icns" "$app/Contents/Info.plist" \
  "$app/Contents/MacOS/BitcoinOil-Qt" "$app/Contents/Resources/Base.lproj/InfoPlist.strings"
"$qt_bins/macdeployqt" "$app" -always-overwrite -verbose=1
python3 - "$app" <<'PY'
from pathlib import Path
import re, subprocess, sys
app = Path(sys.argv[1])
checked = 0
for path in app.rglob('*'):
    if not path.is_file() or path.is_symlink():
        continue
    with path.open('rb') as file:
        magic = file.read(4)
    if magic not in (b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe', b'\xca\xfe\xba\xbe'):
        continue
    checked += 1
    headers = subprocess.check_output(['otool', '-l', str(path)], text=True)
    for command in headers.split('Load command ')[1:]:
        if re.search(r'cmd LC_(?:LOAD|LOAD_WEAK|REEXPORT)_DYLIB\b', command):
            name = re.search(r'\n\s+name (.+?) \(offset', command)[1]
            if name.startswith('/') and not name.startswith(('/usr/lib/', '/System/Library/')):
                raise SystemExit(f'Unbundled dependency: {path}: {name}')
if checked == 0:
    raise SystemExit('No Mach-O binaries found')
print(f'Checked dependencies of {checked} Mach-O files')
PY
codesign --force --deep --sign - "$app"
codesign --verify --deep --strict "$app"
ditto -c -k --sequesterRsrc --keepParent "$app" "$output"
shasum -a 256 "$output"
