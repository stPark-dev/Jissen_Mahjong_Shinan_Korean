#!/bin/sh
# Build the patched snes9x libretro core used for headless tracing/verification.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
rev=1bcc369e89f08243e0a462882fb1f3e42e51de3a
mkdir -p "$root/.ext"
cd "$root/.ext"
[ -d snes9x ] || git clone https://github.com/snes9xgit/snes9x.git
cd snes9x
git fetch --depth 1 origin "$rev" 2>/dev/null || true
git checkout -q "$rev"
git apply --check "$here/snes9x-kr-trace.patch" 2>/dev/null && git apply "$here/snes9x-kr-trace.patch"
make -C libretro -j"$(nproc)"
