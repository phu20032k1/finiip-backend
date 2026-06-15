---
title: "FINIIP AI Kế toán V108 - Playbook nghiệp vụ tổng hợp"
doc_type: "accounting_playbook"
authority: "curated_internal"
status: "active"
verified_on: "2026-06-13"
source_completeness: "comprehensive_summary"
tags: [playbook, accounting, journal, tax_risk, workflow]
---

# FINIIP AI Kế toán V108 - Playbook nghiệp vụ tổng hợp

## Mẫu trả lời bắt buộc

1. **Kết luận nghiệp vụ**: bản chất và thời điểm ghi nhận.
2. **Bút toán nháp**: tài khoản, số tiền và diễn giải; nêu chế độ kế toán giả định.
3. **Thuế**: VAT/TNDN/TNCN hoặc thuế nhà thầu nếu liên quan.
4. **Chứng từ**: hồ sơ đã có và còn thiếu.
5. **Rủi ro**: kế toán, thuế, công nợ, kho, tài sản và hiệu lực văn bản.
6. **Dữ liệu cần hỏi thêm**: chỉ hỏi phần làm thay đổi kết luận.
7. **Trạng thái**: `draft`, `needs_information`, `needs_review` hoặc `blocked`.

## Mua hàng, dịch vụ và thanh toán

### Hàng hóa nhập kho, chưa thanh toán
- Nợ 156: giá chưa VAT.
- Nợ 1331: VAT đầu vào nếu đủ điều kiện.
- Có 331: tổng phải trả.

Thay 156 bằng 152 cho nguyên vật liệu, 153 cho CCDC, 211/213 cho TSCĐ đủ điều kiện, 242 cho khoản nhiều kỳ hoặc tài khoản chi phí phù hợp nếu dùng ngay.

### Dịch vụ đã hoàn thành nhưng chưa có hóa đơn
Có thể phải ghi nhận chi phí phải trả theo nguyên tắc dồn tích khi nghĩa vụ và giá trị ước tính đủ tin cậy. Không đồng nghĩa VAT được khấu trừ. Trạng thái tối thiểu là `needs_review`.

### Thanh toán nhà cung cấp
- Nợ 331/Có 111 hoặc 112.
- Đối chiếu hóa đơn, đối tượng công nợ, khoản ứng trước, hạn thanh toán và chênh lệch tỷ giá.
- Giao dịch có điều kiện thanh toán không dùng tiền mặt phải kiểm tra riêng cho VAT và TNDN theo ngày phát sinh.

## Bán hàng, doanh thu và công nợ

### Bán hàng chịu VAT
- Nợ 111/112/131: tổng thanh toán.
- Có 511: doanh thu chưa VAT.
- Có 3331: VAT đầu ra.

### Giá vốn
- Nợ 632/Có 156 hoặc 155.
- Dịch vụ phải có căn cứ tập hợp chi phí và thời điểm hoàn thành.

### Khách hàng thanh toán công nợ
- Nợ 111/112/Có 131.
- Không ghi Có 511 lần nữa.

### Nhận tiền trước/đặt cọc
Không tự ghi doanh thu. Cần kiểm tra hợp đồng, quyền hoàn trả, điều kiện giao hàng và nghĩa vụ còn lại.

### Trả lại, giảm giá, chiết khấu
Xử lý đồng thời hóa đơn, doanh thu, VAT, công nợ/tiền và hàng nhập lại nếu có. Không tạo bút toán một chiều chỉ giảm tiền.

## Tiền, ngân hàng và tạm ứng

- Rút tiền ngân hàng nhập quỹ: Nợ 111/Có 112.
- Nộp tiền mặt vào ngân hàng: Nợ 112/Có 111.
- Tạm ứng nhân viên: Nợ 141/Có 111/112.
- Quyết toán: Nợ tài sản/chi phí, Nợ 1331 nếu đủ điều kiện/Có 141.
- Hoàn tiền thừa: Nợ 111/112/Có 141.
- Chi vượt tạm ứng: ghi nhận phần phải trả/hoàn lại cho nhân viên theo hồ sơ và chính sách.

## Kho và sản xuất

- Mua hàng: 151/152/153/156 tùy trạng thái và bản chất.
- Xuất NVL trực tiếp: Nợ 621/Có 152.
- Lương trực tiếp: Nợ 622/Có 334.
- Chi phí sản xuất chung: Nợ 627/Có tài khoản liên quan.
- Tập hợp dở dang: Nợ 154/Có 621/622/627 theo phương pháp áp dụng.
- Nhập thành phẩm: Nợ 155/Có 154.
- Xuất bán: Nợ 632/Có 155/156.

Kiểm tra âm kho, đơn vị tính, lô/hạn dùng, phương pháp tính giá xuất kho, chi phí mua và hàng đi đường.

## Chi phí hoạt động

- 641: phục vụ bán hàng, marketing, giao hàng, cửa hàng, nhân viên bán hàng.
- 642: quản lý chung, văn phòng, tư vấn, hành chính.
- 627: chi phí chung tại bộ phận sản xuất.
- 635: lãi vay, lỗ tỷ giá và chi phí tài chính theo điều kiện.
- 242: khoản liên quan nhiều kỳ; phân bổ có căn cứ, thời gian và phương pháp nhất quán.

Không đồng nhất chi phí kế toán với chi phí được trừ thuế TNDN.

## TSCĐ, CCDC và chi phí trả trước

- TSCĐ: Nợ 211/213, Nợ 1332 nếu đủ điều kiện/Có 111/112/331.
- CCDC nhập kho: Nợ 153, Nợ 1331/Có 111/112/331.
- Xuất CCDC phân bổ: Nợ 242/Có 153.
- Phân bổ: Nợ 627/641/642/Có 242.
- Khấu hao: Nợ 627/641/642/Có 214.
- Thanh lý: xử lý nguyên giá, hao mòn, tiền thu, VAT và chi phí thanh lý; luôn `needs_review`.

## Lương, bảo hiểm và TNCN

- Lương phải trả: Nợ 622/627/641/642/Có 334.
- Phần doanh nghiệp chịu: Nợ chi phí/Có 338.
- Phần người lao động chịu: Nợ 334/Có 338.
- Khấu trừ TNCN: Nợ 334/Có 3335.
- Trả lương: Nợ 334/Có 111/112.
- Nộp bảo hiểm/thuế: Nợ 338/3335/Có 112.

Tỷ lệ, mức lương đóng, giảm trừ và tình trạng cư trú phải lấy từ bảng chính sách còn hiệu lực và hồ sơ nhân sự; không đoán.

## Vay, ngoại tệ và vốn

- Nhận vay: Nợ 111/112/Có 341.
- Trả gốc: Nợ 341/Có 111/112.
- Lãi: Nợ 635 hoặc vốn hóa khi đủ điều kiện/Có 111/112/335.
- Góp vốn: Nợ tài sản nhận góp/Có 411.
- Ngoại tệ: ghi nhận theo tỷ giá áp dụng, theo dõi nguyên tệ và đánh giá cuối kỳ theo chế độ.

## Thuế TNDN, khóa sổ và kết chuyển

- Thuế TNDN hiện hành: Nợ 821/Có 3334.
- Nộp thuế: Nợ 3334/Có 112.
- Kết chuyển doanh thu: Nợ 511/515/711/Có 911.
- Kết chuyển chi phí: Nợ 911/Có 632/635/641/642/811/821.
- Lãi: Nợ 911/Có 421; lỗ: Nợ 421/Có 911.

Trước khóa sổ phải đối chiếu tiền, công nợ, kho, tài sản, thuế, lương, chi phí dồn tích, doanh thu chưa thực hiện và giao dịch ngoại tệ.

## Quality gate

Chặn hoặc yêu cầu review khi có một trong các dấu hiệu:

- Thiếu ngày nghiệp vụ, bản chất, số tiền, đối tượng hoặc phương thức thanh toán.
- Hóa đơn và giao nhận/nghiệm thu không khớp.
- Bút toán không cân hoặc làm âm kho bất hợp lý.
- Giao dịch từ ngưỡng pháp luật yêu cầu thanh toán không dùng tiền mặt nhưng chứng từ thanh toán chưa phù hợp.
- Tài sản giá trị lớn chưa rõ thời gian sử dụng, nguyên giá hoặc bộ phận dùng.
- Nhà cung cấp nước ngoài, bên liên kết, ngoại tệ, góp vốn, chia lợi nhuận, thanh lý hoặc điều chỉnh kỳ trước.
- Nguồn RAG có trạng thái `future_effective`, `superseded` hoặc không trả lời đúng điều kiện của câu hỏi.
