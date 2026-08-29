# meta.json — sinh từ máy chủ, không gõ tay

Fixture này là ảnh chụp của `/api/meta`, sinh TỪ chính `server/api/screen.py` +
`server/core/calculator.py` — nên chữ Thái trong các bài test là chữ của máy
chủ, không phải bản chép tay thứ hai (luật P1).

Khi `screen.py` đổi, sinh lại bằng (chạy từ `D:\ThaiPlasticPricing`):

```powershell
.\server\.venv\Scripts\python.exe -c "import sys, json; sys.path.insert(0, r'server\core'); sys.path.insert(0, r'server\api'); import calculator as c; from screen import screen_labels, VERSION_LABEL; meta = {'version': 'fixture', 'version_label': VERSION_LABEL, 'products': c.PRODUCTS, 'length_references': c.LENGTH_REFERENCES, 'dimension_units': list(c.DIMENSION_FACTORS_TO_CM), 'thickness_units': list(c.THICKNESS_FACTORS_TO_MM), 'default_weight_formulas': c.DEFAULT_WEIGHT_FORMULAS, 'default_price_formula': c.DEFAULT_PRICE_FORMULA, 'formula_variables': c.FORMULA_VARIABLES, 'formula_help_text': 'fixture', 'sign_in_with': 'local', 'pacos_bridge': False, 'labels': screen_labels()}; open(r'pantongone-frontend\src\test-fixtures\meta.json', 'w', encoding='utf-8').write(json.dumps(meta, ensure_ascii=False, indent=1))"
```
