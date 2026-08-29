-- Cham lai nhung ai doa mat khau.
--
-- VI SAO CAN. Dia chi may chu nam san trong .exe va trong moi goi tin - no
-- khong bao gio la bi mat, va khong duoc coi no la bi mat. Thu thuc su chan
-- duoc mot cuoc do mat khau la: doan sai nhieu lan thi phai cho.
--
-- GHI CA LAN DUNG. Mot bang chi ghi lan sai tra loi duoc "ai dang do", nhung
-- khong tra loi duoc "co ai vao duoc khong". Hai cau hoi do luon di cung nhau
-- vao dung cai dem co chuyen.

CREATE TABLE IF NOT EXISTS login_attempts (
    id           BIGSERIAL PRIMARY KEY,
    email        TEXT        NOT NULL,
    source_ip    TEXT        NOT NULL DEFAULT '',
    succeeded    BOOLEAN     NOT NULL,
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Hai chi muc nay la thu khien phep dem chay duoc o moi lan dang nhap ma khong
-- quet ca bang. Khong co chung, chinh o khoa chong do lai la cho cham nhat.
CREATE INDEX IF NOT EXISTS login_attempts_email_time
    ON login_attempts (lower(email), attempted_at DESC);
CREATE INDEX IF NOT EXISTS login_attempts_ip_time
    ON login_attempts (source_ip, attempted_at DESC);
