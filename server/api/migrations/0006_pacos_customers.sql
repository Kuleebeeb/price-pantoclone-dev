-- Danh sach khach hang cua PacOs, soi guong sang day (28-08-2026).
--
-- VI SAO. Bee: "Dong bo ten khach hang 2 ben truoc de khi day qua 2 ben deu
-- hieu day la khach hang nao". PacOs la noi giu ho so khach (bao gia phai tro
-- vao mot customer_id that); ben nay chi co ten go tay tren 17.000 dong lich
-- su, va chi 3 dong co ma. Nen PacOs la chu, bang nay la ban sao: MA cua PacOs
-- la can cuoc chung, ghi vao quotations.customer_code khi tinh gia va khi
-- khop duoc ten cu.
--
-- Khong co FOREIGN KEY tu quotations sang day: mot ma PacOs bo di khong duoc
-- lam mat dong lich su.
CREATE TABLE IF NOT EXISTS pacos_customers (
    pacos_id   TEXT        PRIMARY KEY,
    code       TEXT        NOT NULL,
    name       TEXT        NOT NULL,
    name_th    TEXT        NOT NULL DEFAULT '',
    is_active  BOOLEAN     NOT NULL DEFAULT TRUE,
    synced_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS pacos_customers_code ON pacos_customers (upper(code));
CREATE INDEX IF NOT EXISTS idx_quotes_customer_code ON quotations (customer_code) WHERE customer_code <> '';
