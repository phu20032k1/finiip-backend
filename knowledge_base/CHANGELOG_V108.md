# Changelog V108

## Đã sửa

- Giữ nguyên tên các file cũ để tránh gãy đường dẫn code.
- Bổ sung TK 133 và quy tắc chọn tài khoản theo bản chất.
- Cập nhật chuỗi VAT: NĐ 181/2025 → NĐ 359/2025; tách NĐ 144/2026 thành `future_effective` đến 20/06/2026.
- Cập nhật nền tảng TNDN theo Luật 67/2025, NĐ 320/2025 và TT 20/2026; bỏ nội dung cũ chỉ dùng ngưỡng 20 triệu.
- Tách rõ ghi nhận kế toán, khấu trừ VAT và chi phí được trừ TNDN.
- Nâng playbook nghiệp vụ, quality gate, workflow và policy RAG.

## Đã thêm

- `global/legal/chi_phi_duoc_tru.md`
- `global/legal/tai_san_co_dinh.md`
- `global/accounting/cong_cu_dung_cu.md`
- `global/accounting/thong_tu_58_2026_dnsn.md`
- `global/accounting/luong_bao_hiem_tncn.md`
- `global/accounting/kho_gia_von_san_xuat.md`
- `global/accounting/mua_ban_cong_no.md`
- `global/accounting/vay_von_chu_so_huu_tai_chinh.md`
- `global/accounting/khoa_so_bao_cao.md`
- `policies/rag_retrieval_policy.md`
- `sources/legal_source_registry.md`
- `tests/rag_eval_questions.jsonl`

## Lưu ý triển khai

Cần re-index toàn bộ knowledge base để metadata mới có hiệu lực. Nếu code đang whitelist tên file, thêm các file mới; không đổi đường dẫn của các file cũ.
