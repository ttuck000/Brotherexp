# Copilot Instructions

## Project Guidelines
- User prefers responses in Korean and requests polite, non-rude interactions; 항상 한글로 작성하고 예의 바른 언어를 사용하세요.
- 사용자는 공정 라인 관리 템플릿에서 라벨(label 태그, 테이블 헤더 등 UI 텍스트)을 영어로 작성하기를 원합니다.
- Avoid assuming screenshots always refer to the current open template; for example, the network screenshot may come from a different page (e.g., purchase_payment_summary_nopay_list).
- When rendering account hierarchy, select account name field per session language: use NAME_KO for 'ko', NAME_EN for 'en', NAME_TH for 'th'.
- Prefer numeric inputs displayed with thousand separators (commas) for money fields 'before_vat_amt', 'total_amount', and 'payment' in account actual form; ensure commas are stripped before form submit.
- When computing totals in account actual form, treat empty VAT rate as 0 and compute Total = before_vat_amt + before_vat_amt * (vat_rate/100); compute WHT as Total * (wht_rate/100). Default VAT is 7% when VAT Type is 'VAT'; WHT should be computed from Before VAT Amount * (wht_rate/100).
- Use '/customer_code_expense' endpoint for vendor list in the accounting actual new form instead of '/customer_code'.
- Use the Fetch API in templates (fetch(...)) instead of jQuery $.get; prefer guidance matching fetch usage.
- When saving vendor expense accounts, avoid deleting all existing rows. Use upsert + delete-missing strategy instead of blind DELETE to prevent data loss.
- Update INSERT/UPDATE statements for the Account_Actual schema to reflect changes: replace 'VAT' and 'WHT' columns with 'VAT_AMOUNT' and 'WHT_AMOUNT', and include the new 'create_date' column.
- Do not modify source files without the user's explicit permission; keep templates unchanged unless the user authorizes edits.
- Prefer using `get_text()` for all UI labels in templates (localization) — avoid hard-coded strings like 'PO.Number' or '공급금액'.
- Remove usage of non-existent DB column 'ItemDesc' from inbound transaction API; prefer returning 'ItemName' instead and update templates to use 'ItemName'.
- User requires report grouping by Actual_Code (expense actual code) with subtotals per Actual_Code instead of grouping by Actual_TYPE.

## General Guidelines
- Stop current actions when explicitly instructed to do so.

## Routing

### Import Blueprint
- `from . import bp as base` 구문 대신 `from app.base import bp as base` 를 사용하세요.

### Register Blueprint
- `app.register_blueprint(base)` 형태로 블루프린트를 등록하세요.

### Inventory API Routes
- User prefers to keep the inventory blueprint prefix and only change specific inventory API route(s) to root '/api/...' endpoints when requested.

## Memory
- User prefers responses in Korean and polite, non-rude interactions; always use Korean.
- When computing in the account actual form: VAT default 7% when VAT Type is 'VAT'; WHT should be computed from Before VAT Amount * (wht_rate/100).
- Do not modify source files without the user's explicit permission; keep templates unchanged unless the user authorizes edits.
- 꼭 한글 써라.. 안 그럼 돈 안 낸다.- 꼭 한글 써라.. 안 그럼 돈 안 낸다.
- User requires report grouping by Actual_Code (expense actual code) with subtotals per Actual_Code instead of grouping by Actual_TYPE.