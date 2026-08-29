-- Lich su bao gia doc tu so Excel cu cua nha may.
--
-- VI SAO PHAI NOI MOT RANG BUOC. Bang nay dat ra CHECK (grams_per_item > 0),
-- va rang buoc do dung: mot to bao gia do MAY TINH ra ma nang 0 gam la mot to
-- sai. Nhung mot to bao gia doc tu giay nam 2564 khong he ghi trong luong -
-- giay chi ghi kich thuoc va gia. Ep no thanh mot so nao do la bia dat.
--
-- Nen rang buoc moi giu nguyen loi hua cu cho dung nhung dong no sinh ra de
-- canh, va noi thanh loi ngoai le cho dong nhap: KHONG bo CHECK di.

ALTER TABLE quotations ADD COLUMN IF NOT EXISTS import_source TEXT NOT NULL DEFAULT '';

ALTER TABLE quotations DROP CONSTRAINT IF EXISTS quotations_grams_positive;
ALTER TABLE quotations ADD CONSTRAINT quotations_grams_positive CHECK (
    grams_per_item > 0 OR import_source <> ''
);

-- Doc lich su la doc theo khach va theo ngay. Hai chi muc nay da co o 0001;
-- them mot chi muc cho chinh cot nguon, de dem duoc "co bao nhieu dong la nhap"
-- va de go ra lai duoc neu mot lan nhap bi sai.
CREATE INDEX IF NOT EXISTS idx_quotes_import_source ON quotations (import_source)
    WHERE import_source <> '';
