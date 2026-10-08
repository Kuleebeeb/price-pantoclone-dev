#!/usr/bin/env bash
# Dua may chu tinh gia len may that. Chay TU thu muc server/.
#
# Nam trong git (luat H6): script roi tren VPS nghia la VPS chet thi mat luon
# quy trinh deploy. Dung lai ngay khi mot buoc hong - khong bao gio di tiep.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

BACKUP_DIR="${BACKUP_DIR:-$HERE/../backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"

if [[ ! -f .env ]]; then
    echo "KHONG THAY .env - chep tu .env.example roi dien POSTGRES_PASSWORD va AUTH_SECRET" >&2
    exit 1
fi
set -a; source .env; set +a
PORT="${API_PORT:-8100}"
REV="$(awk 'NR==1 {print $1}' CANDIDATE_REV 2>/dev/null || true)"
if [[ ! "$REV" =~ ^[0-9a-f]{40}$ ]]; then
    REV="$(git rev-parse HEAD)"
fi

echo "==> 1/6  pg_dump TRUOC khi lam bat cu gi"
mkdir -p "$BACKUP_DIR"
RUNNING_SERVICES="$(docker compose ps --status running --services)"
if grep -qx postgres <<< "$RUNNING_SERVICES"; then
    DUMP="$BACKUP_DIR/pricing-$STAMP.sql.gz"
    docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-pricing}" -d "${POSTGRES_DB:-pricing}" \
        | gzip > "$DUMP"
    echo "    backup: $DUMP ($(du -h "$DUMP" | cut -f1))"
else
    echo "HONG: Postgres khong chay; khong the backup. Dung update, khong coi day la cai moi." >&2
    exit 1
fi
gzip -t "$DUMP"
PREVIOUS_IMAGE="$(docker compose images -q api | head -n 1)"
if [[ -n "$PREVIOUS_IMAGE" ]]; then
    docker image tag "$PREVIOUS_IMAGE" "thaiplastic-api:before-$STAMP"
    printf '%s\n' "thaiplastic-api:before-$STAMP" > "$BACKUP_DIR/image-before-$STAMP.txt"
fi

echo "==> 2/6  nguon"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git pull --ff-only
    REV="$(git rev-parse HEAD)"
else
    # Khong phai git checkout: deploy/ship.sh da bung goi tar cua mot commit len
    # day va ghi ten commit vao CANDIDATE_REV. Khong co gi de pull.
    echo "    khong phai git checkout - nguon do deploy/ship.sh dua len: $REV"
fi

echo "==> 3/6  build image"
docker compose build --build-arg "SOURCE_REV=$REV"
NEW_IMAGE="$(docker image inspect thaiplastic-api:latest --format '{{.Id}}')"
docker image tag "$NEW_IMAGE" "thaiplastic-api:$REV"

echo "==> 4/6  test doi chieu voi ban desktop cua CEO"
# Lech mot so la dung deploy. Cong thuc trong core/ la ban sao tung byte cua
# chuong trinh CEO dang dung; no thoi khop la san pham noi doi.
# </dev/null: docker compose run nuot stdin, va khi script nay duoc bom qua ssh
# thi phan con lai cua script chinh la stdin do.
docker compose run --rm --no-deps --entrypoint python api tests/test_parity.py </dev/null

echo "==> 5/6  khoi dong lai"
docker compose up -d

echo "==> 6/6  cho health that (ping Postgres), toi da 60 giay"
for i in $(seq 1 30); do
    if curl -fsS -m 3 "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1; then
        RUNNING_IMAGE="$(docker inspect --format '{{.Image}}' "$(docker compose ps -q api)")"
        if [[ "$RUNNING_IMAGE" != "$NEW_IMAGE" ]]; then
            echo "HONG: API khong chay image vua build; khong ghi DEPLOYED_REV." >&2
            exit 1
        fi
        echo "    OK sau $((i * 2)) giay"
        curl -s "http://127.0.0.1:${PORT}/api/health"; echo
        printf '%s %s\n' "$REV" "$STAMP" > DEPLOYED_REV
        printf '%s\n' "$NEW_IMAGE" > DEPLOYED_IMAGE
        rm -f CANDIDATE_REV
        echo
        echo "Ban cai dat dang phuc vu:"
        curl -s "http://127.0.0.1:${PORT}/api/version"; echo
        exit 0
    fi
    sleep 2
done

echo "HONG: /api/health khong tra 200 sau 60 giay. Log 40 dong cuoi:" >&2
docker compose logs --tail 40 api >&2
exit 1
