-- Tai khoan PacOs soi guong vao bang users (28-08-2026).
--
-- Khi AUTH_MODE=pacos, mat khau do PacOs kiem tra; may chu nay chi giu MOT
-- dong cho moi nguoi de created_by van tro vao dau do. Dong soi guong khong co
-- mat khau local, nen password_hash phai duoc phep rong.
ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS pacos_user_id TEXT;
-- Quyen PacOs cap luc dang nhap gan nhat, de sau nay cau noi sang PacOs biet
-- nguoi nay duoc tao bao gia hay khong ma khong phai hoi lai.
ALTER TABLE users ADD COLUMN IF NOT EXISTS permissions JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;
