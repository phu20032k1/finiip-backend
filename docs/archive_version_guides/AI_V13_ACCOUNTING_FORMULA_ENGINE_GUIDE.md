# Finiip V13 - Accounting Formula Engine

Bản V13 bổ sung bộ công thức kế toán lõi để AI không chỉ phân loại/đọc hóa đơn mà còn biết tính toán theo công thức rõ ràng.

## Chạy project

```bash
cd copy
pip install -r requirements.txt
python scripts/seed_and_train_ai.py
uvicorn main:app --reload
```

## API mới

### 1. Danh sách công thức

```bash
curl http://127.0.0.1:8000/formulas/catalog
```

### 2. Tính VAT

```bash
curl -X POST http://127.0.0.1:8000/formulas/vat \
  -H "Content-Type: application/json" \
  -d '{"subtotal":2000000,"vat_rate":10}'
```

Kết quả chính:

```json
{
  "vat_amount": 200000,
  "total": 2200000,
  "balanced": true
}
```

### 3. Khấu hao tài sản cố định

```bash
curl -X POST http://127.0.0.1:8000/formulas/depreciation \
  -H "Content-Type: application/json" \
  -d '{"cost":36000000,"salvage_value":0,"useful_life_months":36,"months_used":6}'
```

Công thức:

```text
monthly_depreciation = (cost - salvage_value) / useful_life_months
```

### 4. Phân bổ chi phí trả trước

```bash
curl -X POST http://127.0.0.1:8000/formulas/prepaid-allocation \
  -H "Content-Type: application/json" \
  -d '{"total_amount":12000000,"allocation_months":12,"months_allocated":3}'
```

### 5. Tính lợi nhuận thuần

```bash
curl -X POST http://127.0.0.1:8000/formulas/profit/net \
  -H "Content-Type: application/json" \
  -d '{"revenue":100000000,"cogs":45000000,"operating_expenses":25000000,"tax_expense":6000000}'
```

### 6. Tính thuế TNDN cơ bản

```bash
curl -X POST http://127.0.0.1:8000/formulas/tax/cit \
  -H "Content-Type: application/json" \
  -d '{"profit_before_tax":30000000,"tax_rate":20}'
```

### 7. Kiểm tra bút toán cân bằng Nợ/Có

```bash
curl -X POST http://127.0.0.1:8000/formulas/journal/check-balance \
  -H "Content-Type: application/json" \
  -d '{
    "lines": [
      {"side":"debit","account_code":"642","amount":2000000},
      {"side":"debit","account_code":"1331","amount":200000},
      {"side":"credit","account_code":"112","amount":2200000}
    ]
  }'
```

### 8. Tỷ số tài chính

```bash
curl -X POST http://127.0.0.1:8000/formulas/ratios \
  -H "Content-Type: application/json" \
  -d '{"current_assets":50000000,"current_liabilities":25000000,"total_assets":100000000,"total_liabilities":40000000,"equity":60000000,"revenue":100000000,"net_profit":20000000}'
```

### 9. Điểm hòa vốn

```bash
curl -X POST http://127.0.0.1:8000/formulas/break-even \
  -H "Content-Type: application/json" \
  -d '{"fixed_costs":30000000,"selling_price_per_unit":500000,"variable_cost_per_unit":300000}'
```

### 10. Tính lợi nhuận từ dữ liệu giao dịch trong hệ thống

```bash
curl http://127.0.0.1:8000/formulas/ledger/profit-loss
```

Hoặc theo kỳ:

```bash
curl "http://127.0.0.1:8000/formulas/ledger/profit-loss?period=2026-05"
```

### 11. Kiểm tra cân đối từ sổ bút toán

```bash
curl http://127.0.0.1:8000/formulas/ledger/trial-balance-check
```

## Trạng thái cấp độ

Sau V13, Finiip đang ở:

```text
Cấp 4 nhẹ + bắt đầu chạm Cấp 5
```

Vì hệ thống đã có:

```text
AI học từ dữ liệu
Feedback loop
Evaluation
OCR hóa đơn
Công thức kế toán lõi
Kiểm tra Nợ/Có
Tính VAT, khấu hao, phân bổ, lợi nhuận, thuế TNDN, tỷ số tài chính
```

## Bước tiếp theo đề xuất

V14 nên là một trong hai hướng:

```text
1. XML hóa đơn điện tử Việt Nam
2. AI tự sinh bút toán nâng cao từ công thức + OCR + ML
```
