#!/usr/bin/env bash
# Dong goi cay nguon HIEN TAI va dua len may that, roi chay remote-install.sh o do.
# Chay tu bat ky dau:  server/deploy/ship.sh [ssh-alias] [thu-muc-tren-may-chu]
#
# Nam trong git (luat H6). Ba dieu no KHONG bao gio lam:
#   - mang .env di theo: 28-08-2026 mot goi tar mang .env dev de len .env prod,
#     API roi vao crash-loop "password authentication failed", site sap ~1 gio
#   - ship cay chua commit: thu dang chay tren may chu phai la mot commit tim lai duoc
#   - bo qua mot buoc hong: set -e, dung ngay
set -euo pipefail

HOST="${1:-pacos-prod}"
REMOTE="${2:-/srv/thaiplastic}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
PKG="/tmp/thaiplastic-$STAMP.tgz"

cd "$ROOT"
if [[ -n "$(git status --porcelain -- server pantongone-frontend)" ]]; then
    echo "HONG: server/ hoac pantongone-frontend/ con thay doi chua commit - commit truoc roi ship" >&2
    git status --short -- server pantongone-frontend >&2
    exit 1
fi
REV="$(git rev-parse --short HEAD)"

echo "==> 1/3  dong goi (khong .env, node_modules, dist, releases, web, .venv, log)"
tar czf "$PKG" \
    --exclude='.env' --exclude='node_modules' --exclude='dist' --exclude='releases' \
    --exclude='web' --exclude='__pycache__' --exclude='.venv' --exclude='*.log' \
    --exclude='tsconfig.tsbuildinfo' \
    server pantongone-frontend
if tar tzf "$PKG" | grep -qE '(^|/)\.env$'; then
    echo "HONG: goi tar co .env - khong ship" >&2
    exit 1
fi
echo "    $PKG ($(du -h "$PKG" | cut -f1)) tu commit $REV"

echo "==> 2/3  copy len $HOST"
scp -q "$PKG" "$HOST:/tmp/"

# Cac buoc tren may chu: giu nguon dang chay, bung goi moi de len, ghi ten commit,
# roi giao cho deploy/deploy.sh (pg_dump -> build -> test -> up -> health).
# deploy.sh duoc goi tu FILE tren may chu, khong bom qua stdin: docker compose
# nuot stdin, va phan con lai cua mot script bom qua ssh chinh la stdin do.
echo "==> 3/3  cai tren may chu"
ssh "$HOST" "set -euo pipefail
cd '$REMOTE'
mkdir -p backups
tar czf 'backups/src-before-$STAMP.tgz' --exclude='.env' --exclude='node_modules' --exclude='dist' \
    --exclude='releases' --exclude='web' --exclude='__pycache__' --exclude='.venv' --exclude='*.log' \
    server pantongone-frontend
tar xzf '$PKG' -C '$REMOTE'
printf '%s %s\n' '$REV' '$STAMP' > server/DEPLOYED_REV
rm -f '$PKG'
cd server && bash deploy/deploy.sh"
