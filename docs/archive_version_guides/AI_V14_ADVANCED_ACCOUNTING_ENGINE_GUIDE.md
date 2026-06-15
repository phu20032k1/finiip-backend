# Finiip V14 - Advanced Accounting Engine

Bản V14 mở rộng Formula Engine từ V13 lên nhóm nghiệp vụ kế toán nâng cao hơn.

## Trạng thái

- Cấp hiện tại: Cấp 4 nhẹ + chạm Cấp 5 rõ hơn
- Test: 17 passed
- Mục tiêu: giúp AI/backend không chỉ đọc hóa đơn, mà còn tính giá vốn, tồn kho, lương, công nợ, kết chuyển và BCTC cơ bản.

## API mới

### 1. FIFO tồn kho và giá vốn

```bash
curl -X POST http://127.0.0.1:8000/formulas/inventory/fifo \
  -H "Content-Type: application/json" \
  -d '{
    "beginning_layers": [
      {"quantity": 10, "unit_cost": 100000, "label": "old"},
      {"quantity": 5, "unit_cost": 120000, "label": "new"}
    ],
    "purchases": [
      {"quantity": 10, "unit_cost": 150000, "label": "purchase_may"}
    ],
    "sales_quantity": 12
  }'
```

### 2. Bình quân gia quyền

```bash
curl -X POST http://127.0.0.1:8000/formulas/inventory/weighted-average \
  -H "Content-Type: application/json" \
  -d '{
    "beginning_quantity": 10,
    "beginning_value": 1000000,
    "purchases": [{"quantity": 10, "amount": 1500000}],
    "sales_quantity": 8
  }'
```

### 3. Lương, bảo hiểm, thuế TNCN cơ bản

```bash
curl -X POST http://127.0.0.1:8000/formulas/payroll/basic \
  -H "Content-Type: application/json" \
  -d '{
    "gross_salary": 10000000,
    "personal_income_tax": 500000
  }'
```

### 4. Tuổi công nợ

```bash
curl -X POST http://127.0.0.1:8000/formulas/accounts/aging \
  -H "Content-Type: application/json" \
  -d '{
    "as_of": "2026-05-27",
    "items": [
      {"name": "Customer A", "amount": 1000000, "due_date": "2026-05-20"},
      {"name": "Customer B", "amount": 2000000, "due_date": "2026-02-01"},
      {"name": "Customer C", "amount": 3000000, "due_date": "2026-06-01"}
    ]
  }'
```

### 5. Kết chuyển cuối kỳ

```bash
curl -X POST http://127.0.0.1:8000/formulas/closing/period \
  -H "Content-Type: application/json" \
  -d '{
    "revenue": 100000000,
    "cogs": 45000000,
    "selling_expenses": 10000000,
    "admin_expenses": 15000000,
    "tax_expense": 6000000
  }'
```

### 6. Báo cáo tài chính cơ bản

```bash
curl -X POST http://127.0.0.1:8000/formulas/statements/basic \
  -H "Content-Type: application/json" \
  -d '{
    "cash": 20000000,
    "receivables": 10000000,
    "inventory": 15000000,
    "fixed_assets": 50000000,
    "accumulated_depreciation": 5000000,
    "payables": 10000000,
    "loans": 20000000,
    "owner_equity": 40000000,
    "revenue": 100000000,
    "cogs": 45000000,
    "operating_expenses": 25000000,
    "tax_expense": 6000000
  }'
```

## API cũ vẫn giữ

- `/formulas/vat`
- `/formulas/depreciation`
- `/formulas/prepaid-allocation`
- `/formulas/profit/gross`
- `/formulas/profit/net`
- `/formulas/tax/cit`
- `/formulas/journal/check-balance`
- `/formulas/ratios`
- `/formulas/break-even`
- `/formulas/ledger/profit-loss`
- `/formulas/ledger/trial-balance-check`

## Lưu ý

Các công thức lương, bảo hiểm, thuế trong bản này là công thức tổng quát để backend tính thử và demo nghiệp vụ. Khi dùng thực tế cần cập nhật theo luật hiện hành, vùng lương, trần đóng bảo hiểm, giảm trừ gia cảnh và quy định thuế mới nhất.
