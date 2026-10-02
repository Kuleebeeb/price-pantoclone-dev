-- Mot quyen cho moi man hinh (02-10-2026, xem permissions.py).
--
-- Quyen cua mot nguoi duoc chep tu PacOs MOI LAN dang nhap. Nguoi dang nhap
-- truoc ban nay chi mang pricing.sign_in, nen ngay ban nay len ho se bi tu choi
-- moi tab cho toi lan dang nhap sau (token song 12 gio). PacOs migration 0138
-- cap DU tam quyen moi cho moi vai dang giu pricing.sign_in, nen o day lam
-- dung dieu PacOs se tra loi o lan dang nhap ke tiep - khong hon, khong kem.
UPDATE users
   SET permissions = permissions || '["pricing.calculate", "pricing.save", "pricing.history",
                                      "pricing.delete", "pricing.drawing", "pricing.sample_inspection",
                                      "pricing.planning", "pricing.coa"]'::jsonb
 WHERE permissions ? 'pricing.sign_in'
   AND NOT permissions ?| ARRAY['pricing.calculate', 'pricing.save', 'pricing.history',
                               'pricing.delete', 'pricing.drawing', 'pricing.sample_inspection',
                               'pricing.planning', 'pricing.coa'];
