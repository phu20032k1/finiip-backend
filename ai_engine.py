# ai_engine.py
# Finiip AI Engine - Rule-based Accounting Knowledge
# Cấp 2: AI kế toán theo luật, keyword, nghiệp vụ cơ bản

import re
from typing import Dict, Any, List


ACCOUNTING_RULES: List[Dict[str, Any]] = [
        # =========================
    # GIẢM GIÁ / HOÀN TIỀN / HÀNG BÁN BỊ TRẢ LẠI
    # =========================
    {
        "keywords": [
            "giảm giá hàng bán", "chiết khấu bán hàng", "voucher cho khách",
            "mã giảm giá", "khuyến mãi cho khách", "discount cho khách"
        ],
        "category": "Giảm trừ doanh thu",
        "transaction_type": "expense",
        "debit_account": "511",
        "debit_account_name": "Doanh thu bán hàng",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.82
    },
    {
        "keywords": [
            "khách trả hàng", "hàng bán bị trả lại", "hoàn tiền khách",
            "refund khách", "trả tiền cho khách"
        ],
        "category": "Hàng bán bị trả lại",
        "transaction_type": "expense",
        "debit_account": "511",
        "debit_account_name": "Doanh thu bán hàng",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.84
    },
    {
        "keywords": [
            "nhà cung cấp hoàn tiền", "refund từ nhà cung cấp",
            "hoàn tiền mua hàng", "được hoàn tiền"
        ],
        "category": "Nhà cung cấp hoàn tiền",
        "transaction_type": "income",
        "debit_account": "111",
        "debit_account_name": "Tiền mặt",
        "credit_account": "156",
        "credit_account_name": "Hàng hóa",
        "confidence": 0.8
    },

    # =========================
    # ĐẶT CỌC / TẠM ỨNG / HOÀN ỨNG
    # =========================
    {
        "keywords": [
            "đặt cọc cho nhà cung cấp", "cọc tiền hàng", "ứng trước cho nhà cung cấp",
            "tạm ứng nhà cung cấp"
        ],
        "category": "Ứng trước cho nhà cung cấp",
        "transaction_type": "expense",
        "debit_account": "331",
        "debit_account_name": "Phải trả người bán",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.82
    },
    {
        "keywords": [
            "khách đặt cọc", "khách ứng trước", "nhận cọc khách hàng",
            "khách chuyển tiền cọc"
        ],
        "category": "Khách hàng ứng trước",
        "transaction_type": "income",
        "debit_account": "111",
        "debit_account_name": "Tiền mặt",
        "credit_account": "131",
        "credit_account_name": "Phải thu khách hàng",
        "confidence": 0.82
    },
    {
        "keywords": [
            "tạm ứng nhân viên", "ứng tiền cho nhân viên",
            "nhân viên tạm ứng", "ứng công tác phí"
        ],
        "category": "Tạm ứng nhân viên",
        "transaction_type": "expense",
        "debit_account": "141",
        "debit_account_name": "Tạm ứng",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.85
    },
    {
        "keywords": [
            "hoàn ứng", "nhân viên hoàn ứng", "thu lại tiền tạm ứng",
            "quyết toán tạm ứng"
        ],
        "category": "Hoàn ứng nhân viên",
        "transaction_type": "income",
        "debit_account": "111",
        "debit_account_name": "Tiền mặt",
        "credit_account": "141",
        "credit_account_name": "Tạm ứng",
        "confidence": 0.84
    },

    # =========================
    # VAY / GÓP VỐN / RÚT VỐN
    # =========================
    {
        "keywords": [
            "vay ngân hàng", "nhận tiền vay", "giải ngân khoản vay",
            "vay vốn", "nhận khoản vay"
        ],
        "category": "Nhận tiền vay",
        "transaction_type": "income",
        "debit_account": "112",
        "debit_account_name": "Tiền gửi ngân hàng",
        "credit_account": "341",
        "credit_account_name": "Vay và nợ thuê tài chính",
        "confidence": 0.86
    },
    {
        "keywords": [
            "trả nợ vay", "trả gốc vay", "thanh toán khoản vay",
            "trả tiền vay ngân hàng"
        ],
        "category": "Trả nợ gốc vay",
        "transaction_type": "expense",
        "debit_account": "341",
        "debit_account_name": "Vay và nợ thuê tài chính",
        "credit_account": "112",
        "credit_account_name": "Tiền gửi ngân hàng",
        "confidence": 0.86
    },
    {
        "keywords": [
            "góp vốn", "chủ sở hữu góp vốn", "nhận vốn góp",
            "thành viên góp vốn", "cổ đông góp vốn"
        ],
        "category": "Nhận vốn góp",
        "transaction_type": "income",
        "debit_account": "111",
        "debit_account_name": "Tiền mặt",
        "credit_account": "411",
        "credit_account_name": "Vốn chủ sở hữu",
        "confidence": 0.88
    },
    {
        "keywords": [
            "rút vốn", "hoàn trả vốn góp", "trả vốn cho chủ sở hữu"
        ],
        "category": "Hoàn trả vốn góp",
        "transaction_type": "expense",
        "debit_account": "411",
        "debit_account_name": "Vốn chủ sở hữu",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.8
    },

    # =========================
    # LƯƠNG CHI TIẾT HƠN
    # =========================
    {
        "keywords": [
            "trích lương", "ghi nhận lương", "hạch toán lương",
            "lương phải trả"
        ],
        "category": "Ghi nhận lương phải trả",
        "transaction_type": "expense",
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "334",
        "credit_account_name": "Phải trả người lao động",
        "confidence": 0.88
    },
    {
        "keywords": [
            "trả lương qua ngân hàng", "chuyển khoản lương",
            "thanh toán lương", "chi lương"
        ],
        "category": "Thanh toán lương nhân viên",
        "transaction_type": "expense",
        "debit_account": "334",
        "debit_account_name": "Phải trả người lao động",
        "credit_account": "112",
        "credit_account_name": "Tiền gửi ngân hàng",
        "confidence": 0.9
    },
    {
        "keywords": [
            "thuế tncn", "thuế thu nhập cá nhân", "khấu trừ thuế cá nhân"
        ],
        "category": "Thuế thu nhập cá nhân",
        "transaction_type": "expense",
        "debit_account": "334",
        "debit_account_name": "Phải trả người lao động",
        "credit_account": "3335",
        "credit_account_name": "Thuế thu nhập cá nhân",
        "confidence": 0.82
    },

    # =========================
    # KHO / HAO HỤT / KIỂM KÊ
    # =========================
    {
        "keywords": [
            "kiểm kê thiếu hàng", "hao hụt hàng hóa", "mất hàng",
            "thiếu kho", "hàng hỏng"
        ],
        "category": "Hao hụt hàng tồn kho",
        "transaction_type": "expense",
        "debit_account": "632",
        "debit_account_name": "Giá vốn hàng bán",
        "credit_account": "156",
        "credit_account_name": "Hàng hóa",
        "confidence": 0.82
    },
    {
        "keywords": [
            "kiểm kê thừa hàng", "thừa kho", "phát hiện thừa hàng"
        ],
        "category": "Thừa hàng tồn kho",
        "transaction_type": "income",
        "debit_account": "156",
        "debit_account_name": "Hàng hóa",
        "credit_account": "711",
        "credit_account_name": "Thu nhập khác",
        "confidence": 0.78
    },
    {
        "keywords": [
            "hủy hàng", "hàng hết hạn", "tiêu hủy hàng hóa",
            "hàng lỗi không bán được"
        ],
        "category": "Tiêu hủy hàng hóa",
        "transaction_type": "expense",
        "debit_account": "811",
        "debit_account_name": "Chi phí khác",
        "credit_account": "156",
        "credit_account_name": "Hàng hóa",
        "confidence": 0.8
    },

    # =========================
    # SỬA CHỮA / BẢO TRÌ / BẢO HÀNH
    # =========================
    {
        "keywords": [
            "sửa chữa", "bảo trì", "bảo dưỡng", "sửa máy",
            "sửa thiết bị", "sửa văn phòng", "sửa cửa hàng"
        ],
        "category": "Chi phí sửa chữa bảo trì",
        "transaction_type": "expense",
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.84
    },
    {
        "keywords": [
            "bảo hành cho khách", "chi phí bảo hành", "đổi hàng bảo hành",
            "sửa hàng bảo hành"
        ],
        "category": "Chi phí bảo hành",
        "transaction_type": "expense",
        "debit_account": "641",
        "debit_account_name": "Chi phí bán hàng",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.82
    },

    # =========================
    # ĐÀO TẠO / TUYỂN DỤNG / NHÂN SỰ
    # =========================
    {
        "keywords": [
            "tuyển dụng", "đăng tin tuyển dụng", "phí tuyển dụng",
            "headhunt", "headhunter"
        ],
        "category": "Chi phí tuyển dụng",
        "transaction_type": "expense",
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.84
    },
    {
        "keywords": [
            "đào tạo", "khóa học", "học phí nhân viên",
            "training", "đào tạo nhân sự"
        ],
        "category": "Chi phí đào tạo",
        "transaction_type": "expense",
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.84
    },
    {
        "keywords": [
            "đồng phục", "áo đồng phục", "bảng tên nhân viên",
            "thẻ nhân viên"
        ],
        "category": "Chi phí nhân sự khác",
        "transaction_type": "expense",
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.8
    },

    # =========================
    # E-COMMERCE / LIVESTREAM / AFFILIATE
    # =========================
    {
        "keywords": [
            "affiliate", "hoa hồng affiliate", "tiếp thị liên kết",
            "commission affiliate"
        ],
        "category": "Chi phí affiliate",
        "transaction_type": "expense",
        "debit_account": "641",
        "debit_account_name": "Chi phí bán hàng",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.88
    },
    {
        "keywords": [
            "livestream", "thuê livestream", "host live", "mc live",
            "chi phí live bán hàng"
        ],
        "category": "Chi phí livestream bán hàng",
        "transaction_type": "expense",
        "debit_account": "641",
        "debit_account_name": "Chi phí bán hàng",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.86
    },
    {
        "keywords": [
            "mẫu thử", "sample cho khách", "gửi mẫu", "sản phẩm mẫu",
            "quà tặng khách hàng"
        ],
        "category": "Chi phí hàng mẫu quà tặng",
        "transaction_type": "expense",
        "debit_account": "641",
        "debit_account_name": "Chi phí bán hàng",
        "credit_account": "156",
        "credit_account_name": "Hàng hóa",
        "confidence": 0.8
    },

    # =========================
    # LOGISTICS / KHO BÃI
    # =========================
    {
        "keywords": [
            "thuê kho", "phí kho", "lưu kho", "kho bãi",
            "fulfillment", "phí fulfillment"
        ],
        "category": "Chi phí kho bãi",
        "transaction_type": "expense",
        "debit_account": "641",
        "debit_account_name": "Chi phí bán hàng",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.86
    },
    {
        "keywords": [
            "bốc xếp", "đóng container", "phí container",
            "phí logistics", "phí vận tải"
        ],
        "category": "Chi phí logistics",
        "transaction_type": "expense",
        "debit_account": "641",
        "debit_account_name": "Chi phí bán hàng",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.84
    },

    # =========================
    # PHÍ DỊCH VỤ CHUYÊN MÔN
    # =========================
    {
        "keywords": [
            "dịch vụ kế toán", "thuê kế toán", "phí kế toán",
            "dịch vụ báo cáo thuế"
        ],
        "category": "Chi phí dịch vụ kế toán",
        "transaction_type": "expense",
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.86
    },
    {
        "keywords": [
            "dịch vụ pháp lý", "luật sư", "tư vấn pháp luật",
            "phí pháp lý"
        ],
        "category": "Chi phí pháp lý",
        "transaction_type": "expense",
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.84
    },
    {
        "keywords": [
            "tư vấn", "dịch vụ tư vấn", "phí tư vấn",
            "consulting"
        ],
        "category": "Chi phí tư vấn",
        "transaction_type": "expense",
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.8
    },

    # =========================
    # CHI PHÍ KHÁC THƯỜNG GẶP
    # =========================
    {
        "keywords": [
            "xăng xe", "đổ xăng", "nhiên liệu", "dầu xe",
            "gửi xe", "cầu đường"
        ],
        "category": "Chi phí xăng xe đi lại",
        "transaction_type": "expense",
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.84
    },
    {
        "keywords": [
            "vệ sinh", "dọn dẹp", "dịch vụ vệ sinh",
            "rác thải", "phí môi trường"
        ],
        "category": "Chi phí vệ sinh môi trường",
        "transaction_type": "expense",
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.82
    },
    {
        "keywords": [
            "bảo vệ", "dịch vụ bảo vệ", "an ninh"
        ],
        "category": "Chi phí bảo vệ an ninh",
        "transaction_type": "expense",
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.82
    },
    # =========================
    # DOANH THU
    # =========================
    {
        "keywords": [
            "bán hàng", "doanh thu", "thu tiền khách", "khách thanh toán",
            "tiền bán hàng", "bán sản phẩm", "bán dịch vụ", "xuất hóa đơn bán hàng"
        ],
        "category": "Doanh thu bán hàng",
        "transaction_type": "income",
        "debit_account": "111",
        "debit_account_name": "Tiền mặt",
        "credit_account": "511",
        "credit_account_name": "Doanh thu bán hàng",
        "confidence": 0.9
    },
    {
        "keywords": [
            "lãi ngân hàng", "tiền lãi", "lãi tiền gửi", "doanh thu tài chính"
        ],
        "category": "Doanh thu tài chính",
        "transaction_type": "income",
        "debit_account": "112",
        "debit_account_name": "Tiền gửi ngân hàng",
        "credit_account": "515",
        "credit_account_name": "Doanh thu hoạt động tài chính",
        "confidence": 0.88
    },
    {
        "keywords": [
            "thu nhập khác", "thanh lý tài sản", "bán tài sản cũ", "bồi thường nhận được"
        ],
        "category": "Thu nhập khác",
        "transaction_type": "income",
        "debit_account": "111",
        "debit_account_name": "Tiền mặt",
        "credit_account": "711",
        "credit_account_name": "Thu nhập khác",
        "confidence": 0.82
    },

    # =========================
    # CHI PHÍ BÁN HÀNG / MARKETING
    # =========================
    {
        "keywords": [
            "facebook", "facebook ads", "google ads", "tiktok ads", "zalo ads",
            "quảng cáo", "ads", "marketing", "chạy quảng cáo", "chiến dịch quảng cáo",
            "booking koc", "booking kol", "influencer", "seeding"
        ],
        "category": "Chi phí quảng cáo",
        "transaction_type": "expense",
        "debit_account": "641",
        "debit_account_name": "Chi phí bán hàng",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.95
    },
    {
        "keywords": [
            "phí sàn", "phí shopee", "phí tiktok shop", "phí lazada",
            "hoa hồng sàn", "chiết khấu sàn", "phí giao dịch sàn"
        ],
        "category": "Chi phí sàn thương mại điện tử",
        "transaction_type": "expense",
        "debit_account": "641",
        "debit_account_name": "Chi phí bán hàng",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.93
    },
    {
        "keywords": [
            "đóng gói", "bao bì", "hộp carton", "túi đóng hàng",
            "tem nhãn", "màng bọc", "băng keo"
        ],
        "category": "Chi phí bao bì đóng gói",
        "transaction_type": "expense",
        "debit_account": "641",
        "debit_account_name": "Chi phí bán hàng",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.9
    },
    {
        "keywords": [
            "vận chuyển", "ship hàng", "giao hàng", "phí ship",
            "ghn", "ghtk", "viettel post", "j&t", "ninja van"
        ],
        "category": "Chi phí vận chuyển bán hàng",
        "transaction_type": "expense",
        "debit_account": "641",
        "debit_account_name": "Chi phí bán hàng",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.9
    },

    # =========================
    # CHI PHÍ QUẢN LÝ DOANH NGHIỆP
    # =========================
    {
        "keywords": [
            "lương", "tiền lương", "trả lương", "nhân viên",
            "tiền công", "thưởng nhân viên", "phụ cấp"
        ],
        "category": "Chi phí lương nhân viên",
        "transaction_type": "expense",
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.94
    },
    {
        "keywords": [
            "bảo hiểm xã hội", "bhxh", "bảo hiểm y tế", "bhyt",
            "bảo hiểm thất nghiệp", "bhtn", "kinh phí công đoàn"
        ],
        "category": "Chi phí bảo hiểm nhân viên",
        "transaction_type": "expense",
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.88
    },
    {
        "keywords": [
            "tiền điện", "điện", "evn", "hóa đơn điện"
        ],
        "category": "Chi phí điện",
        "transaction_type": "expense",
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.9
    },
    {
        "keywords": [
            "tiền nước", "nước sinh hoạt", "hóa đơn nước", "cấp nước"
        ],
        "category": "Chi phí nước",
        "transaction_type": "expense",
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.9
    },
    {
        "keywords": [
            "internet", "wifi", "mạng", "cước mạng", "fpt", "viettel internet",
            "vnpt", "cáp quang"
        ],
        "category": "Chi phí internet",
        "transaction_type": "expense",
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.9
    },
    {
        "keywords": [
            "điện thoại", "cước điện thoại", "sim", "4g", "5g", "cước di động"
        ],
        "category": "Chi phí điện thoại",
        "transaction_type": "expense",
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.86
    },
    {
        "keywords": [
            "thuê văn phòng", "tiền thuê nhà", "thuê mặt bằng",
            "thuê cửa hàng", "thuê kho", "tiền thuê kho"
        ],
        "category": "Chi phí thuê mặt bằng",
        "transaction_type": "expense",
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.92
    },
    {
        "keywords": [
            "văn phòng phẩm", "giấy in", "bút", "mực in",
            "ghim", "sổ sách", "file tài liệu"
        ],
        "category": "Chi phí văn phòng phẩm",
        "transaction_type": "expense",
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.88
    },
    {
        "keywords": [
            "phần mềm", "software", "saas", "hosting", "domain",
            "tên miền", "server", "cloud", "google workspace",
            "microsoft 365", "canva", "chatgpt", "notion"
        ],
        "category": "Chi phí phần mềm dịch vụ",
        "transaction_type": "expense",
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.87
    },
    {
        "keywords": [
            "tiếp khách", "ăn uống", "cafe khách hàng", "nhà hàng",
            "chiêu đãi", "gặp khách"
        ],
        "category": "Chi phí tiếp khách",
        "transaction_type": "expense",
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.84
    },
    {
        "keywords": [
            "công tác", "vé máy bay", "khách sạn", "taxi",
            "grab", "xăng xe đi công tác", "chi phí đi lại"
        ],
        "category": "Chi phí công tác",
        "transaction_type": "expense",
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.84
    },

    # =========================
    # HÀNG HÓA / MUA HÀNG
    # =========================
    {
        "keywords": [
            "mua hàng", "nhập hàng", "mua sản phẩm", "mua hàng hóa",
            "nhập kho", "mua để bán", "hàng nhập"
        ],
        "category": "Mua hàng hóa",
        "transaction_type": "expense",
        "debit_account": "156",
        "debit_account_name": "Hàng hóa",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.92
    },
    {
        "keywords": [
            "nguyên vật liệu", "nguyên liệu", "vật liệu sản xuất",
            "mua nguyên liệu", "mua vật tư"
        ],
        "category": "Mua nguyên vật liệu",
        "transaction_type": "expense",
        "debit_account": "156",
        "debit_account_name": "Hàng hóa",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.86
    },
    {
        "keywords": [
            "giá vốn", "xuất kho", "giá vốn hàng bán"
        ],
        "category": "Giá vốn hàng bán",
        "transaction_type": "expense",
        "debit_account": "632",
        "debit_account_name": "Giá vốn hàng bán",
        "credit_account": "156",
        "credit_account_name": "Hàng hóa",
        "confidence": 0.9
    },

    # =========================
    # TÀI SẢN CỐ ĐỊNH / CÔNG CỤ
    # =========================
    {
        "keywords": [
            "mua máy tính", "laptop", "máy in", "máy móc",
            "thiết bị", "tài sản cố định", "mua xe", "camera"
        ],
        "category": "Mua tài sản cố định",
        "transaction_type": "expense",
        "debit_account": "211",
        "debit_account_name": "Tài sản cố định hữu hình",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.86
    },
    {
        "keywords": [
            "khấu hao", "trích khấu hao", "khấu hao tài sản"
        ],
        "category": "Chi phí khấu hao",
        "transaction_type": "expense",
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "211",
        "credit_account_name": "Tài sản cố định hữu hình",
        "confidence": 0.82
    },

    # =========================
    # THUẾ
    # =========================
    {
        "keywords": [
            "nộp thuế vat", "nộp thuế gtgt", "thuế giá trị gia tăng",
            "thuế gtgt phải nộp"
        ],
        "category": "Nộp thuế GTGT",
        "transaction_type": "expense",
        "debit_account": "3331",
        "debit_account_name": "Thuế GTGT phải nộp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.9
    },
    {
        "keywords": [
            "thuế môn bài", "lệ phí môn bài"
        ],
        "category": "Lệ phí môn bài",
        "transaction_type": "expense",
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.88
    },
    {
        "keywords": [
            "thuế tndn", "thuế thu nhập doanh nghiệp"
        ],
        "category": "Thuế thu nhập doanh nghiệp",
        "transaction_type": "expense",
        "debit_account": "811",
        "debit_account_name": "Chi phí khác",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.82
    },

    # =========================
    # NGÂN HÀNG / TÀI CHÍNH
    # =========================
    {
        "keywords": [
            "phí ngân hàng", "phí chuyển khoản", "phí duy trì tài khoản",
            "sms banking", "internet banking"
        ],
        "category": "Chi phí ngân hàng",
        "transaction_type": "expense",
        "debit_account": "635",
        "debit_account_name": "Chi phí tài chính",
        "credit_account": "112",
        "credit_account_name": "Tiền gửi ngân hàng",
        "confidence": 0.88
    },
    {
        "keywords": [
            "lãi vay", "trả lãi vay", "chi phí lãi vay"
        ],
        "category": "Chi phí lãi vay",
        "transaction_type": "expense",
        "debit_account": "635",
        "debit_account_name": "Chi phí tài chính",
        "credit_account": "112",
        "credit_account_name": "Tiền gửi ngân hàng",
        "confidence": 0.88
    },
    {
        "keywords": [
            "rút tiền ngân hàng", "rút tiền mặt", "rút tiền từ ngân hàng"
        ],
        "category": "Rút tiền ngân hàng về quỹ",
        "transaction_type": "transfer",
        "debit_account": "111",
        "debit_account_name": "Tiền mặt",
        "credit_account": "112",
        "credit_account_name": "Tiền gửi ngân hàng",
        "confidence": 0.88
    },
    {
        "keywords": [
            "nộp tiền vào ngân hàng", "gửi tiền vào ngân hàng", "nộp tiền mặt vào tài khoản"
        ],
        "category": "Nộp tiền mặt vào ngân hàng",
        "transaction_type": "transfer",
        "debit_account": "112",
        "debit_account_name": "Tiền gửi ngân hàng",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.88
    },

    # =========================
    # CÔNG NỢ
    # =========================
    {
        "keywords": [
            "khách nợ", "phải thu khách hàng", "bán chịu", "ghi nợ khách hàng"
        ],
        "category": "Phải thu khách hàng",
        "transaction_type": "income",
        "debit_account": "131",
        "debit_account_name": "Phải thu khách hàng",
        "credit_account": "511",
        "credit_account_name": "Doanh thu bán hàng",
        "confidence": 0.84
    },
    {
        "keywords": [
            "thu hồi công nợ", "khách trả nợ", "thu nợ khách hàng"
        ],
        "category": "Thu hồi công nợ khách hàng",
        "transaction_type": "income",
        "debit_account": "111",
        "debit_account_name": "Tiền mặt",
        "credit_account": "131",
        "credit_account_name": "Phải thu khách hàng",
        "confidence": 0.88
    },
    {
        "keywords": [
            "nợ nhà cung cấp", "phải trả người bán", "mua chịu", "ghi nợ nhà cung cấp"
        ],
        "category": "Phải trả nhà cung cấp",
        "transaction_type": "expense",
        "debit_account": "156",
        "debit_account_name": "Hàng hóa",
        "credit_account": "331",
        "credit_account_name": "Phải trả người bán",
        "confidence": 0.84
    },
    {
        "keywords": [
            "trả nợ nhà cung cấp", "thanh toán công nợ nhà cung cấp",
            "trả tiền nhà cung cấp"
        ],
        "category": "Thanh toán công nợ nhà cung cấp",
        "transaction_type": "expense",
        "debit_account": "331",
        "debit_account_name": "Phải trả người bán",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.88
    },

    # =========================
    # KHÁC
    # =========================
    {
        "keywords": [
            "phạt", "tiền phạt", "vi phạm", "bồi thường phải trả"
        ],
        "category": "Chi phí khác",
        "transaction_type": "expense",
        "debit_account": "811",
        "debit_account_name": "Chi phí khác",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.8
    },
]


def normalize_text(text: str) -> str:
    """
    Chuẩn hóa mô tả giao dịch để AI dễ nhận diện hơn.
    """
    if not text:
        return ""

    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)

    return text


def detect_payment_account(text: str, default_credit_account: str, default_credit_name: str):
    """
    Tự nhận diện thanh toán bằng tiền mặt hay ngân hàng.
    """
    bank_keywords = [
        "chuyển khoản", "ngân hàng", "bank", "stk", "tài khoản ngân hàng",
        "mb bank", "vietcombank", "vcb", "techcombank", "tcb",
        "bidv", "vietinbank", "agribank", "momo", "zalopay"
    ]

    cash_keywords = [
        "tiền mặt", "cash", "trả tiền mặt", "thu tiền mặt"
    ]

    for keyword in bank_keywords:
        if keyword in text:
            return "112", "Tiền gửi ngân hàng"

    for keyword in cash_keywords:
        if keyword in text:
            return "111", "Tiền mặt"

    return default_credit_account, default_credit_name


def classify_transaction(description: str) -> Dict[str, Any]:
    """
    Phân loại giao dịch kế toán dựa trên mô tả.
    Đây là AI rule-based, chưa phải machine learning.
    """
    text = normalize_text(description)

    best_match = None
    best_score = 0

    for rule in ACCOUNTING_RULES:
        score = 0

        for keyword in rule["keywords"]:
            if keyword in text:
                score += len(keyword)

        if score > best_score:
            best_score = score
            best_match = rule

    if not best_match:
        return {
            "category": "Chưa phân loại",
            "transaction_type": "unknown",
            "debit_account": None,
            "debit_account_name": None,
            "credit_account": None,
            "credit_account_name": None,
            "confidence": 0.0,
            "suggestion": "Cần kế toán kiểm tra thủ công"
        }

    debit_account = best_match["debit_account"]
    debit_account_name = best_match["debit_account_name"]
    credit_account = best_match["credit_account"]
    credit_account_name = best_match["credit_account_name"]

    # Nếu giao dịch đang Có 111 hoặc 112 thì thử nhận diện lại phương thức thanh toán
    if credit_account in ["111", "112"]:
        credit_account, credit_account_name = detect_payment_account(
            text,
            credit_account,
            credit_account_name
        )

    return {
        "category": best_match["category"],
        "transaction_type": best_match["transaction_type"],
        "debit_account": debit_account,
        "debit_account_name": debit_account_name,
        "credit_account": credit_account,
        "credit_account_name": credit_account_name,
        "confidence": best_match["confidence"],
        "suggestion": "AI đã phân loại theo rule, nên kiểm tra lại trước khi ghi sổ chính thức"
    }


def suggest_journal_entry(description: str, amount: float) -> Dict[str, Any]:
    """
    Gợi ý bút toán từ mô tả và số tiền.
    Hàm này dùng cho bước nâng cấp tiếp theo.
    """
    result = classify_transaction(description)

    return {
        "description": description,
        "amount": amount,
        "category": result["category"],
        "debit_account_code": result["debit_account"],
        "debit_account_name": result["debit_account_name"],
        "credit_account_code": result["credit_account"],
        "credit_account_name": result["credit_account_name"],
        "confidence": result["confidence"],
        "suggestion": result["suggestion"]
    }


def add_custom_rule(
    keywords: List[str],
    category: str,
    transaction_type: str,
    debit_account: str,
    debit_account_name: str,
    credit_account: str,
    credit_account_name: str,
    confidence: float = 0.8
):
    """
    Thêm rule mới khi app đang chạy.
    Bản hiện tại chỉ thêm tạm thời trong RAM.
    Sau này có thể lưu rule vào database.
    """
    ACCOUNTING_RULES.append({
        "keywords": keywords,
        "category": category,
        "transaction_type": transaction_type,
        "debit_account": debit_account,
        "debit_account_name": debit_account_name,
        "credit_account": credit_account,
        "credit_account_name": credit_account_name,
        "confidence": confidence
    })

    return {
        "message": "Đã thêm kiến thức mới cho AI",
        "category": category,
        "keywords": keywords
    }
    
    
    
    # ============================================================
# FINIIP AI ENGINE - BẢN HOÀN CHỈNH CẤP 2
# ============================================================

import unicodedata


def remove_vietnamese_accents(text: str) -> str:
    """
    Bỏ dấu tiếng Việt để AI nhận diện tốt hơn.
    Ví dụ: 'tiền điện' -> 'tien dien'
    """
    if not text:
        return ""

    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D")
    return text


def normalize_text(text: str) -> str:
    """
    Chuẩn hóa mô tả giao dịch.
    """
    if not text:
        return ""

    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_for_match(text: str) -> str:
    """
    Chuẩn hóa nâng cao để so khớp keyword:
    - viết thường
    - bỏ dấu tiếng Việt
    - bỏ khoảng trắng thừa
    """
    text = normalize_text(text)
    text = remove_vietnamese_accents(text)
    text = re.sub(r"[^a-z0-9\s%]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def detect_payment_account(text: str, default_account: str = "111", default_name: str = "Tiền mặt"):
    """
    Nhận diện tài khoản thanh toán:
    - 111: tiền mặt
    - 112: ngân hàng
    """
    raw_text = normalize_text(text)
    clean_text = normalize_for_match(text)

    bank_keywords = [
        "chuyển khoản", "chuyen khoan",
        "ngân hàng", "ngan hang",
        "bank", "internet banking", "mobile banking",
        "stk", "số tài khoản", "so tai khoan",
        "vietcombank", "vcb",
        "techcombank", "tcb",
        "mb bank", "mbbank",
        "bidv", "vietinbank", "agribank",
        "momo", "zalopay", "ví điện tử", "vi dien tu"
    ]

    cash_keywords = [
        "tiền mặt", "tien mat",
        "cash",
        "trả tiền mặt", "tra tien mat",
        "thu tiền mặt", "thu tien mat"
    ]

    for keyword in bank_keywords:
        if normalize_for_match(keyword) in clean_text or keyword in raw_text:
            return "112", "Tiền gửi ngân hàng", "bank"

    for keyword in cash_keywords:
        if normalize_for_match(keyword) in clean_text or keyword in raw_text:
            return "111", "Tiền mặt", "cash"

    if default_account == "112":
        return "112", "Tiền gửi ngân hàng", "bank"

    return default_account, default_name, "unknown"


def detect_vat_rate(description: str) -> float:
    """
    Nhận diện VAT trong mô tả.
    Nếu có VAT nhưng không ghi rõ %, mặc định 10%.
    """
    text = normalize_for_match(description)

    if "khong vat" in text or "khong thue" in text or "vat 0" in text:
        return 0.0

    patterns = [
        r"vat\s*(\d+)",
        r"gtgt\s*(\d+)",
        r"thue\s*(\d+)",
        r"(\d+)\s*%"
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            number = float(match.group(1))
            if 0 <= number <= 20:
                return number / 100

    vat_keywords = ["vat", "gtgt", "thuế", "thue", "hóa đơn", "hoa don"]
    for keyword in vat_keywords:
        if normalize_for_match(keyword) in text:
            return 0.10

    return 0.0


def detect_amount_level(amount: float) -> str:
    """
    Phân loại mức tiền để cảnh báo.
    """
    if amount >= 100_000_000:
        return "very_high"
    if amount >= 20_000_000:
        return "high"
    if amount >= 5_000_000:
        return "medium"
    return "normal"


def confidence_label(confidence: float) -> str:
    """
    Đổi confidence dạng số sang chữ dễ hiểu.
    """
    if confidence >= 0.9:
        return "Rất cao"
    if confidence >= 0.8:
        return "Cao"
    if confidence >= 0.65:
        return "Trung bình"
    if confidence > 0:
        return "Thấp"
    return "Không xác định"


def find_best_rule(description: str):
    """
    Tìm rule phù hợp nhất.
    Cải tiến so với bản cũ:
    - so khớp cả tiếng Việt có dấu và không dấu
    - keyword dài được ưu tiên hơn
    - nhiều keyword trùng thì điểm cao hơn
    """
    raw_text = normalize_text(description)
    clean_text = normalize_for_match(description)

    best_match = None
    best_score = 0
    matched_keywords = []

    for rule in ACCOUNTING_RULES:
        score = 0
        current_matched_keywords = []

        for keyword in rule.get("keywords", []):
            raw_keyword = normalize_text(keyword)
            clean_keyword = normalize_for_match(keyword)

            if raw_keyword and raw_keyword in raw_text:
                score += len(raw_keyword) * 3
                current_matched_keywords.append(keyword)

            elif clean_keyword and clean_keyword in clean_text:
                score += len(clean_keyword) * 2
                current_matched_keywords.append(keyword)

            else:
                # So khớp từng từ quan trọng nếu không trùng nguyên cụm
                words = [w for w in clean_keyword.split() if len(w) >= 4]
                word_hits = sum(1 for w in words if w in clean_text)

                if words and word_hits >= max(1, len(words) // 2):
                    score += word_hits * 4
                    current_matched_keywords.append(keyword)

        if score > best_score:
            best_score = score
            best_match = rule
            matched_keywords = current_matched_keywords

    return best_match, best_score, matched_keywords


def generate_warnings(
    description: str,
    amount: float,
    category: str,
    transaction_type: str,
    debit_account: str,
    credit_account: str,
    confidence: float,
    payment_method: str,
    vat_rate: float
):
    """
    Sinh cảnh báo kế toán/thuế cơ bản.
    Đây là phần làm sản phẩm trông thông minh hơn.
    """
    warnings = []
    text = normalize_for_match(description)

    if not description or len(description.strip()) < 8:
        warnings.append({
            "level": "medium",
            "type": "short_description",
            "message": "Mô tả giao dịch quá ngắn, AI có thể phân loại chưa chính xác."
        })

    if category == "Chưa phân loại" or confidence == 0:
        warnings.append({
            "level": "high",
            "type": "unknown_transaction",
            "message": "AI chưa nhận diện được nghiệp vụ. Cần kế toán kiểm tra và chọn tài khoản thủ công."
        })

    if 0 < confidence < 0.75:
        warnings.append({
            "level": "medium",
            "type": "low_confidence",
            "message": "Độ tin cậy chưa cao. Nên kiểm tra lại tài khoản Nợ/Có trước khi ghi sổ."
        })

    if amount >= 5_000_000 and payment_method == "cash":
        warnings.append({
            "level": "high",
            "type": "large_cash_payment",
            "message": "Giao dịch từ 5 triệu đồng trở lên thanh toán bằng tiền mặt có rủi ro về điều kiện khấu trừ VAT và chi phí được trừ. Cần kiểm tra chứng từ thanh toán không dùng tiền mặt."
        })

    if amount >= 100_000_000:
        warnings.append({
            "level": "medium",
            "type": "very_large_transaction",
            "message": "Giao dịch có giá trị lớn. Nên kiểm tra hợp đồng, hóa đơn và chứng từ đi kèm."
        })

    expense_accounts = ["641", "642", "627", "632", "635", "811", "211", "156", "152", "153"]
    if transaction_type == "expense" and debit_account in expense_accounts and amount >= 2_000_000:
        warnings.append({
            "level": "low",
            "type": "invoice_required",
            "message": "Khoản chi phí từ 2 triệu trở lên nên có hóa đơn/chứng từ hợp lệ để phục vụ quyết toán thuế."
        })

    if vat_rate > 0 and transaction_type == "expense":
        warnings.append({
            "level": "low",
            "type": "purchase_vat",
            "message": f"AI phát hiện VAT {int(vat_rate * 100)}%. Có thể cần tách thuế GTGT đầu vào vào TK 1331."
        })

    if vat_rate > 0 and transaction_type == "income":
        warnings.append({
            "level": "low",
            "type": "sales_vat",
            "message": f"AI phát hiện VAT {int(vat_rate * 100)}%. Có thể cần ghi nhận thuế GTGT đầu ra vào TK 3331."
        })

    if "khong hoa don" in text or "khong co hoa don" in text:
        warnings.append({
            "level": "medium",
            "type": "missing_invoice",
            "message": "Mô tả có dấu hiệu không có hóa đơn. Cần cân nhắc trước khi ghi nhận là chi phí hợp lệ."
        })

    if "tam ung" in text or "ung truoc" in text:
        warnings.append({
            "level": "low",
            "type": "advance_tracking",
            "message": "Đây có thể là nghiệp vụ tạm ứng/ứng trước. Cần theo dõi hoàn ứng hoặc đối trừ công nợ sau này."
        })

    if not warnings:
        warnings.append({
            "level": "ok",
            "type": "normal",
            "message": "Chưa phát hiện rủi ro lớn. Vẫn nên kiểm tra lại trước khi ghi sổ chính thức."
        })

    return warnings


def build_vat_journal_lines(
    description: str,
    amount: float,
    transaction_type: str,
    debit_account: str,
    debit_account_name: str,
    credit_account: str,
    credit_account_name: str,
    vat_rate: float
):
    """
    Tạo bút toán nhiều dòng nếu có VAT.
    Nếu không có VAT thì trả về bút toán 2 dòng cơ bản.
    """
    text = normalize_for_match(description)

    if vat_rate <= 0:
        return {
            "has_vat": False,
            "subtotal": amount,
            "vat_amount": 0,
            "total_amount": amount,
            "journal_lines": [
                {
                    "side": "debit",
                    "account_code": debit_account,
                    "account_name": debit_account_name,
                    "amount": amount
                },
                {
                    "side": "credit",
                    "account_code": credit_account,
                    "account_name": credit_account_name,
                    "amount": amount
                }
            ]
        }

    # Nếu ghi "chưa VAT" thì amount là tiền chưa thuế
    amount_is_before_vat = (
        "chua vat" in text
        or "chua thue" in text
        or "truoc vat" in text
        or "truoc thue" in text
    )

    if amount_is_before_vat:
        subtotal = amount
        vat_amount = round(amount * vat_rate, 2)
        total_amount = round(subtotal + vat_amount, 2)
    else:
        # Mặc định coi amount là tổng đã gồm VAT
        total_amount = amount
        subtotal = round(total_amount / (1 + vat_rate), 2)
        vat_amount = round(total_amount - subtotal, 2)

    # Bán hàng có VAT:
    # Nợ 111/112/131
    # Có 511
    # Có 3331
    if transaction_type == "income" and credit_account == "511":
        return {
            "has_vat": True,
            "subtotal": subtotal,
            "vat_amount": vat_amount,
            "total_amount": total_amount,
            "journal_lines": [
                {
                    "side": "debit",
                    "account_code": debit_account,
                    "account_name": debit_account_name,
                    "amount": total_amount
                },
                {
                    "side": "credit",
                    "account_code": "511",
                    "account_name": "Doanh thu bán hàng và cung cấp dịch vụ",
                    "amount": subtotal
                },
                {
                    "side": "credit",
                    "account_code": "3331",
                    "account_name": "Thuế GTGT phải nộp",
                    "amount": vat_amount
                }
            ]
        }

    # Mua hàng / chi phí có VAT:
    # Nợ chi phí/tài sản
    # Nợ 1331
    # Có 111/112/331
    if transaction_type == "expense":
        return {
            "has_vat": True,
            "subtotal": subtotal,
            "vat_amount": vat_amount,
            "total_amount": total_amount,
            "journal_lines": [
                {
                    "side": "debit",
                    "account_code": debit_account,
                    "account_name": debit_account_name,
                    "amount": subtotal
                },
                {
                    "side": "debit",
                    "account_code": "1331",
                    "account_name": "Thuế GTGT được khấu trừ của hàng hóa, dịch vụ",
                    "amount": vat_amount
                },
                {
                    "side": "credit",
                    "account_code": credit_account,
                    "account_name": credit_account_name,
                    "amount": total_amount
                }
            ]
        }

    return {
        "has_vat": False,
        "subtotal": amount,
        "vat_amount": 0,
        "total_amount": amount,
        "journal_lines": [
            {
                "side": "debit",
                "account_code": debit_account,
                "account_name": debit_account_name,
                "amount": amount
            },
            {
                "side": "credit",
                "account_code": credit_account,
                "account_name": credit_account_name,
                "amount": amount
            }
        ]
    }


def classify_transaction(description: str) -> Dict[str, Any]:
    """
    AI phân loại giao dịch bản hoàn chỉnh.
    """
    text = normalize_text(description)
    best_match, best_score, matched_keywords = find_best_rule(description)

    if not best_match:
        return {
            "category": "Chưa phân loại",
            "transaction_type": "unknown",
            "debit_account": None,
            "debit_account_name": None,
            "credit_account": None,
            "credit_account_name": None,
            "confidence": 0.0,
            "confidence_label": "Không xác định",
            "matched_keywords": [],
            "payment_method": "unknown",
            "vat_rate": detect_vat_rate(description),
            "warnings": [
                {
                    "level": "high",
                    "type": "unknown_transaction",
                    "message": "AI chưa nhận diện được nghiệp vụ. Cần kế toán kiểm tra thủ công."
                }
            ],
            "suggestion": "Cần kế toán kiểm tra và bổ sung rule mới cho trường hợp này."
        }

    debit_account = best_match["debit_account"]
    debit_account_name = best_match["debit_account_name"]
    credit_account = best_match["credit_account"]
    credit_account_name = best_match["credit_account_name"]

    payment_method = "unknown"

    # Nếu tài khoản Có là tiền thì nhận diện lại 111/112
    if credit_account in ["111", "112"]:
        credit_account, credit_account_name, payment_method = detect_payment_account(
            text,
            credit_account,
            credit_account_name
        )

    # Nếu tài khoản Nợ là tiền trong giao dịch doanh thu thì cũng nhận diện 111/112
    if debit_account in ["111", "112"]:
        debit_account, debit_account_name, payment_method = detect_payment_account(
            text,
            debit_account,
            debit_account_name
        )

    base_confidence = float(best_match.get("confidence", 0.75))

    # Tăng nhẹ confidence nếu match nhiều keyword
    if len(matched_keywords) >= 2:
        confidence = min(0.98, base_confidence + 0.05)
    else:
        confidence = base_confidence

    vat_rate = detect_vat_rate(description)

    warnings = generate_warnings(
        description=description,
        amount=0,
        category=best_match["category"],
        transaction_type=best_match["transaction_type"],
        debit_account=debit_account,
        credit_account=credit_account,
        confidence=confidence,
        payment_method=payment_method,
        vat_rate=vat_rate
    )

    return {
        "category": best_match["category"],
        "transaction_type": best_match["transaction_type"],
        "debit_account": debit_account,
        "debit_account_name": debit_account_name,
        "credit_account": credit_account,
        "credit_account_name": credit_account_name,
        "confidence": confidence,
        "confidence_label": confidence_label(confidence),
        "matched_keywords": matched_keywords,
        "payment_method": payment_method,
        "vat_rate": vat_rate,
        "warnings": warnings,
        "suggestion": "AI đã phân loại theo rule-based. Nên kiểm tra lại trước khi ghi sổ chính thức."
    }


def suggest_journal_entry(description: str, amount: float) -> Dict[str, Any]:
    """
    Gợi ý bút toán hoàn chỉnh:
    - Có phân loại
    - Có tài khoản Nợ/Có
    - Có VAT nếu phát hiện
    - Có cảnh báo
    - Có nhiều dòng bút toán để demo đẹp hơn
    """
    result = classify_transaction(description)

    if amount <= 0:
        return {
            "error": True,
            "message": "Số tiền phải lớn hơn 0"
        }

    if result["transaction_type"] == "unknown":
        return {
            "description": description,
            "amount": amount,
            "category": result["category"],
            "transaction_type": result["transaction_type"],
            "debit_account_code": None,
            "debit_account_name": None,
            "credit_account_code": None,
            "credit_account_name": None,
            "confidence": 0.0,
            "confidence_label": "Không xác định",
            "payment_method": "unknown",
            "vat_rate": result.get("vat_rate", 0),
            "amount_level": detect_amount_level(amount),
            "warnings": result["warnings"],
            "journal_lines": [],
            "suggestion": "Chưa thể gợi ý bút toán. Cần kế toán kiểm tra thủ công."
        }

    vat_data = build_vat_journal_lines(
        description=description,
        amount=amount,
        transaction_type=result["transaction_type"],
        debit_account=result["debit_account"],
        debit_account_name=result["debit_account_name"],
        credit_account=result["credit_account"],
        credit_account_name=result["credit_account_name"],
        vat_rate=result["vat_rate"]
    )

    warnings = generate_warnings(
        description=description,
        amount=amount,
        category=result["category"],
        transaction_type=result["transaction_type"],
        debit_account=result["debit_account"],
        credit_account=result["credit_account"],
        confidence=result["confidence"],
        payment_method=result["payment_method"],
        vat_rate=result["vat_rate"]
    )

    return {
        "description": description,
        "amount": amount,
        "category": result["category"],
        "transaction_type": result["transaction_type"],

        "debit_account_code": result["debit_account"],
        "debit_account_name": result["debit_account_name"],
        "credit_account_code": result["credit_account"],
        "credit_account_name": result["credit_account_name"],

        "confidence": result["confidence"],
        "confidence_label": result["confidence_label"],
        "matched_keywords": result["matched_keywords"],
        "payment_method": result["payment_method"],

        "vat_rate": result["vat_rate"],
        "has_vat": vat_data["has_vat"],
        "subtotal": vat_data["subtotal"],
        "vat_amount": vat_data["vat_amount"],
        "total_amount": vat_data["total_amount"],

        "amount_level": detect_amount_level(amount),
        "warnings": warnings,
        "journal_lines": vat_data["journal_lines"],

        "suggestion": "Đây là bút toán AI gợi ý. Kế toán nên kiểm tra trước khi ghi sổ chính thức."
    }


def demo_ai_cases():
    """
    Dữ liệu demo dùng để thuyết trình.
    """
    examples = [
        {
            "description": "Thanh toán tiền điện EVN tháng 5 bằng chuyển khoản",
            "amount": 2500000
        },
        {
            "description": "Trả lương nhân viên qua ngân hàng tháng 5",
            "amount": 35000000
        },
        {
            "description": "Mua laptop văn phòng 22 triệu chưa VAT 10% thanh toán tiền mặt",
            "amount": 22000000
        },
        {
            "description": "Chạy quảng cáo Facebook Ads tháng 5 có VAT 10%",
            "amount": 5500000
        },
        {
            "description": "Khách hàng thanh toán tiền mua hàng qua Vietcombank có VAT 10%",
            "amount": 11000000
        },
        {
            "description": "Tạm ứng nhân viên đi công tác",
            "amount": 3000000
        }
    ]

    results = []

    for item in examples:
        results.append(
            suggest_journal_entry(
                description=item["description"],
                amount=item["amount"]
            )
        )

    return results



# ============================================================
# 3
# 
# ============================================================

EXTRA_ACCOUNTING_RULES = [
    # ========================================================
    # 1. DOANH THU - BÁN HÀNG
    # ========================================================
    {
        "category": "Doanh thu bán hàng",
        "transaction_type": "income",
        "keywords": [
            "bán hàng", "ban hang",
            "doanh thu", "thu tiền bán hàng", "thu tien ban hang",
            "khách thanh toán", "khach thanh toan",
            "khách hàng trả tiền", "khach hang tra tien",
            "xuất hóa đơn bán hàng", "xuat hoa don ban hang",
            "bán sản phẩm", "ban san pham",
            "bán dịch vụ", "ban dich vu"
        ],
        "debit_account": "111",
        "debit_account_name": "Tiền mặt",
        "credit_account": "511",
        "credit_account_name": "Doanh thu bán hàng và cung cấp dịch vụ",
        "confidence": 0.90
    },
    {
        "category": "Doanh thu cung cấp dịch vụ",
        "transaction_type": "income",
        "keywords": [
            "cung cấp dịch vụ", "cung cap dich vu",
            "phí dịch vụ", "phi dich vu",
            "doanh thu dịch vụ", "doanh thu dich vu",
            "thu phí tư vấn", "thu phi tu van",
            "dịch vụ tư vấn", "dich vu tu van",
            "dịch vụ thiết kế", "dich vu thiet ke",
            "dịch vụ phần mềm", "dich vu phan mem"
        ],
        "debit_account": "111",
        "debit_account_name": "Tiền mặt",
        "credit_account": "511",
        "credit_account_name": "Doanh thu bán hàng và cung cấp dịch vụ",
        "confidence": 0.88
    },
    {
        "category": "Doanh thu chưa thu tiền",
        "transaction_type": "income",
        "keywords": [
            "bán chịu", "ban chiu",
            "khách nợ", "khach no",
            "chưa thu tiền khách hàng", "chua thu tien khach hang",
            "ghi nhận công nợ khách hàng", "ghi nhan cong no khach hang",
            "phải thu khách hàng", "phai thu khach hang"
        ],
        "debit_account": "131",
        "debit_account_name": "Phải thu của khách hàng",
        "credit_account": "511",
        "credit_account_name": "Doanh thu bán hàng và cung cấp dịch vụ",
        "confidence": 0.87
    },

    # ========================================================
    # 2. GIÁ VỐN - HÀNG TỒN KHO
    # ========================================================
    {
        "category": "Mua hàng hóa nhập kho",
        "transaction_type": "expense",
        "keywords": [
            "mua hàng hóa", "mua hang hoa",
            "nhập kho hàng hóa", "nhap kho hang hoa",
            "mua hàng nhập kho", "mua hang nhap kho",
            "mua sản phẩm để bán", "mua san pham de ban",
            "mua hàng tồn kho", "mua hang ton kho"
        ],
        "debit_account": "156",
        "debit_account_name": "Hàng hóa",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.88
    },
    {
        "category": "Mua nguyên vật liệu",
        "transaction_type": "expense",
        "keywords": [
            "mua nguyên vật liệu", "mua nguyen vat lieu",
            "nhập kho nguyên liệu", "nhap kho nguyen lieu",
            "mua vật liệu", "mua vat lieu",
            "nguyên liệu sản xuất", "nguyen lieu san xuat"
        ],
        "debit_account": "152",
        "debit_account_name": "Nguyên liệu, vật liệu",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.88
    },
    {
        "category": "Giá vốn hàng bán",
        "transaction_type": "expense",
        "keywords": [
            "giá vốn", "gia von",
            "xuất kho bán hàng", "xuat kho ban hang",
            "kết chuyển giá vốn", "ket chuyen gia von",
            "giá vốn hàng bán", "gia von hang ban"
        ],
        "debit_account": "632",
        "debit_account_name": "Giá vốn hàng bán",
        "credit_account": "156",
        "credit_account_name": "Hàng hóa",
        "confidence": 0.86
    },

    # ========================================================
    # 3. CHI PHÍ BÁN HÀNG - MARKETING
    # ========================================================
    {
        "category": "Chi phí quảng cáo",
        "transaction_type": "expense",
        "keywords": [
            "quảng cáo", "quang cao",
            "facebook ads", "facebook",
            "google ads", "google",
            "tiktok ads", "tiktok",
            "zalo ads", "zalo",
            "marketing", "ads",
            "chạy quảng cáo", "chay quang cao",
            "chi phí truyền thông", "chi phi truyen thong"
        ],
        "debit_account": "641",
        "debit_account_name": "Chi phí bán hàng",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.92
    },
    {
        "category": "Chi phí vận chuyển bán hàng",
        "transaction_type": "expense",
        "keywords": [
            "phí vận chuyển", "phi van chuyen",
            "ship hàng", "ship hang",
            "giao hàng", "giao hang",
            "chuyển phát", "chuyen phat",
            "ghn", "ghtk", "viettel post",
            "phí giao hàng", "phi giao hang",
            "vận chuyển cho khách", "van chuyen cho khach"
        ],
        "debit_account": "641",
        "debit_account_name": "Chi phí bán hàng",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.86
    },
    {
        "category": "Chi phí hoa hồng bán hàng",
        "transaction_type": "expense",
        "keywords": [
            "hoa hồng", "hoa hong",
            "chiết khấu đại lý", "chiet khau dai ly",
            "thưởng doanh số", "thuong doanh so",
            "commission", "affiliate"
        ],
        "debit_account": "641",
        "debit_account_name": "Chi phí bán hàng",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.84
    },

    # ========================================================
    # 4. CHI PHÍ QUẢN LÝ DOANH NGHIỆP
    # ========================================================
    {
        "category": "Chi phí điện nước",
        "transaction_type": "expense",
        "keywords": [
            "tiền điện", "tien dien",
            "evn", "điện lực", "dien luc",
            "tiền nước", "tien nuoc",
            "cấp nước", "cap nuoc",
            "hóa đơn điện", "hoa don dien",
            "hóa đơn nước", "hoa don nuoc"
        ],
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.93
    },
    {
        "category": "Chi phí thuê văn phòng",
        "transaction_type": "expense",
        "keywords": [
            "thuê văn phòng", "thue van phong",
            "tiền thuê nhà", "tien thue nha",
            "thuê mặt bằng", "thue mat bang",
            "thuê cửa hàng", "thue cua hang",
            "thuê kho", "thue kho",
            "tiền thuê kho", "tien thue kho"
        ],
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.90
    },
    {
        "category": "Chi phí internet điện thoại",
        "transaction_type": "expense",
        "keywords": [
            "internet", "wifi",
            "cước điện thoại", "cuoc dien thoai",
            "viettel", "vnpt", "fpt telecom",
            "sim công ty", "sim cong ty",
            "cước viễn thông", "cuoc vien thong"
        ],
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.88
    },
    {
        "category": "Chi phí văn phòng phẩm",
        "transaction_type": "expense",
        "keywords": [
            "văn phòng phẩm", "van phong pham",
            "mua giấy", "mua giay",
            "mua bút", "mua but",
            "mực in", "muc in",
            "giấy in", "giay in",
            "đồ dùng văn phòng", "do dung van phong"
        ],
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.87
    },
    {
        "category": "Chi phí tiếp khách",
        "transaction_type": "expense",
        "keywords": [
            "tiếp khách", "tiep khach",
            "ăn uống tiếp khách", "an uong tiep khach",
            "nhà hàng tiếp khách", "nha hang tiep khach",
            "cafe khách hàng", "cafe khach hang",
            "chi phí tiếp đối tác", "chi phi tiep doi tac"
        ],
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.82
    },
    {
        "category": "Chi phí công tác",
        "transaction_type": "expense",
        "keywords": [
            "công tác", "cong tac",
            "vé máy bay", "ve may bay",
            "khách sạn", "khach san",
            "taxi công tác", "taxi cong tac",
            "grab công tác", "grab cong tac",
            "chi phí đi lại", "chi phi di lai",
            "phụ cấp công tác", "phu cap cong tac"
        ],
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.84
    },

    # ========================================================
    # 5. NHÂN SỰ - LƯƠNG - BẢO HIỂM
    # ========================================================
    {
        "category": "Chi phí lương nhân viên",
        "transaction_type": "expense",
        "keywords": [
            "lương", "luong",
            "trả lương", "tra luong",
            "lương nhân viên", "luong nhan vien",
            "tiền lương", "tien luong",
            "bảng lương", "bang luong",
            "lương tháng", "luong thang",
            "thưởng nhân viên", "thuong nhan vien"
        ],
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "334",
        "credit_account_name": "Phải trả người lao động",
        "confidence": 0.91
    },
    {
        "category": "Thanh toán lương",
        "transaction_type": "expense",
        "keywords": [
            "thanh toán lương", "thanh toan luong",
            "chi lương", "chi luong",
            "trả lương qua ngân hàng", "tra luong qua ngan hang",
            "chuyển lương", "chuyen luong"
        ],
        "debit_account": "334",
        "debit_account_name": "Phải trả người lao động",
        "credit_account": "112",
        "credit_account_name": "Tiền gửi ngân hàng",
        "confidence": 0.90
    },
    {
        "category": "Bảo hiểm xã hội",
        "transaction_type": "expense",
        "keywords": [
            "bảo hiểm xã hội", "bao hiem xa hoi",
            "bhxh", "bhyt", "bhtn",
            "nộp bảo hiểm", "nop bao hiem",
            "bảo hiểm nhân viên", "bao hiem nhan vien"
        ],
        "debit_account": "338",
        "debit_account_name": "Phải trả, phải nộp khác",
        "credit_account": "112",
        "credit_account_name": "Tiền gửi ngân hàng",
        "confidence": 0.89
    },

    # ========================================================
    # 6. TẠM ỨNG - HOÀN ỨNG - CÔNG NỢ
    # ========================================================
    {
        "category": "Tạm ứng nhân viên",
        "transaction_type": "expense",
        "keywords": [
            "tạm ứng", "tam ung",
            "ứng trước", "ung truoc",
            "tạm ứng công tác", "tam ung cong tac",
            "tạm ứng nhân viên", "tam ung nhan vien"
        ],
        "debit_account": "141",
        "debit_account_name": "Tạm ứng",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.89
    },
    {
        "category": "Hoàn ứng nhân viên",
        "transaction_type": "income",
        "keywords": [
            "hoàn ứng", "hoan ung",
            "thu hồi tạm ứng", "thu hoi tam ung",
            "nhân viên hoàn ứng", "nhan vien hoan ung",
            "nộp lại tạm ứng", "nop lai tam ung"
        ],
        "debit_account": "111",
        "debit_account_name": "Tiền mặt",
        "credit_account": "141",
        "credit_account_name": "Tạm ứng",
        "confidence": 0.88
    },
    {
        "category": "Thanh toán cho nhà cung cấp",
        "transaction_type": "expense",
        "keywords": [
            "trả nhà cung cấp", "tra nha cung cap",
            "thanh toán nhà cung cấp", "thanh toan nha cung cap",
            "trả công nợ", "tra cong no",
            "thanh toán công nợ", "thanh toan cong no",
            "trả tiền hàng cho nhà cung cấp", "tra tien hang cho nha cung cap"
        ],
        "debit_account": "331",
        "debit_account_name": "Phải trả cho người bán",
        "credit_account": "112",
        "credit_account_name": "Tiền gửi ngân hàng",
        "confidence": 0.88
    },
    {
        "category": "Thu công nợ khách hàng",
        "transaction_type": "income",
        "keywords": [
            "thu công nợ", "thu cong no",
            "khách trả nợ", "khach tra no",
            "thu tiền khách nợ", "thu tien khach no",
            "khách thanh toán công nợ", "khach thanh toan cong no"
        ],
        "debit_account": "112",
        "debit_account_name": "Tiền gửi ngân hàng",
        "credit_account": "131",
        "credit_account_name": "Phải thu của khách hàng",
        "confidence": 0.88
    },

    # ========================================================
    # 7. TÀI SẢN CỐ ĐỊNH - CÔNG CỤ DỤNG CỤ
    # ========================================================
    {
        "category": "Mua tài sản cố định",
        "transaction_type": "expense",
        "keywords": [
            "mua laptop", "mua máy tính", "mua may tinh",
            "mua xe", "mua ô tô", "mua oto",
            "mua máy móc", "mua may moc",
            "thiết bị văn phòng", "thiet bi van phong",
            "tài sản cố định", "tai san co dinh",
            "máy in", "may in",
            "máy photocopy", "may photocopy"
        ],
        "debit_account": "211",
        "debit_account_name": "Tài sản cố định hữu hình",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.90
    },
    {
        "category": "Mua công cụ dụng cụ",
        "transaction_type": "expense",
        "keywords": [
            "công cụ dụng cụ", "cong cu dung cu",
            "mua công cụ", "mua cong cu",
            "mua ghế", "mua ghe",
            "mua bàn", "mua ban",
            "mua kệ", "mua ke",
            "dụng cụ văn phòng", "dung cu van phong"
        ],
        "debit_account": "153",
        "debit_account_name": "Công cụ, dụng cụ",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.85
    },
    {
        "category": "Khấu hao tài sản cố định",
        "transaction_type": "expense",
        "keywords": [
            "khấu hao", "khau hao",
            "trích khấu hao", "trich khau hao",
            "khấu hao tài sản", "khau hao tai san",
            "khấu hao tháng", "khau hao thang"
        ],
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "214",
        "credit_account_name": "Hao mòn tài sản cố định",
        "confidence": 0.90
    },

    # ========================================================
    # 8. THUẾ
    # ========================================================
    {
        "category": "Nộp thuế GTGT",
        "transaction_type": "expense",
        "keywords": [
            "nộp thuế gtgt", "nop thue gtgt",
            "nộp vat", "nop vat",
            "thuế giá trị gia tăng", "thue gia tri gia tang",
            "nộp thuế vat", "nop thue vat"
        ],
        "debit_account": "3331",
        "debit_account_name": "Thuế GTGT phải nộp",
        "credit_account": "112",
        "credit_account_name": "Tiền gửi ngân hàng",
        "confidence": 0.91
    },
    {
        "category": "Nộp thuế thu nhập doanh nghiệp",
        "transaction_type": "expense",
        "keywords": [
            "thuế thu nhập doanh nghiệp", "thue thu nhap doanh nghiep",
            "thuế tndn", "thue tndn",
            "nộp tndn", "nop tndn",
            "nộp thuế doanh nghiệp", "nop thue doanh nghiep"
        ],
        "debit_account": "3334",
        "debit_account_name": "Thuế thu nhập doanh nghiệp",
        "credit_account": "112",
        "credit_account_name": "Tiền gửi ngân hàng",
        "confidence": 0.90
    },
    {
        "category": "Nộp thuế thu nhập cá nhân",
        "transaction_type": "expense",
        "keywords": [
            "thuế thu nhập cá nhân", "thue thu nhap ca nhan",
            "thuế tncn", "thue tncn",
            "nộp tncn", "nop tncn",
            "khấu trừ thuế cá nhân", "khau tru thue ca nhan"
        ],
        "debit_account": "3335",
        "debit_account_name": "Thuế thu nhập cá nhân",
        "credit_account": "112",
        "credit_account_name": "Tiền gửi ngân hàng",
        "confidence": 0.90
    },

    # ========================================================
    # 9. NGÂN HÀNG - VAY - LÃI VAY
    # ========================================================
    {
        "category": "Vay ngân hàng",
        "transaction_type": "income",
        "keywords": [
            "vay ngân hàng", "vay ngan hang",
            "nhận tiền vay", "nhan tien vay",
            "giải ngân khoản vay", "giai ngan khoan vay",
            "khoản vay", "khoan vay"
        ],
        "debit_account": "112",
        "debit_account_name": "Tiền gửi ngân hàng",
        "credit_account": "341",
        "credit_account_name": "Vay và nợ thuê tài chính",
        "confidence": 0.88
    },
    {
        "category": "Trả nợ vay",
        "transaction_type": "expense",
        "keywords": [
            "trả nợ vay", "tra no vay",
            "thanh toán khoản vay", "thanh toan khoan vay",
            "trả gốc vay", "tra goc vay",
            "trả ngân hàng", "tra ngan hang"
        ],
        "debit_account": "341",
        "debit_account_name": "Vay và nợ thuê tài chính",
        "credit_account": "112",
        "credit_account_name": "Tiền gửi ngân hàng",
        "confidence": 0.87
    },
    {
        "category": "Chi phí lãi vay",
        "transaction_type": "expense",
        "keywords": [
            "lãi vay", "lai vay",
            "trả lãi vay", "tra lai vay",
            "chi phí lãi vay", "chi phi lai vay",
            "lãi ngân hàng", "lai ngan hang"
        ],
        "debit_account": "635",
        "debit_account_name": "Chi phí tài chính",
        "credit_account": "112",
        "credit_account_name": "Tiền gửi ngân hàng",
        "confidence": 0.88
    },
    {
        "category": "Lãi tiền gửi ngân hàng",
        "transaction_type": "income",
        "keywords": [
            "lãi tiền gửi", "lai tien gui",
            "lãi ngân hàng", "lai ngan hang",
            "thu lãi tiền gửi", "thu lai tien gui",
            "tiền lãi ngân hàng", "tien lai ngan hang"
        ],
        "debit_account": "112",
        "debit_account_name": "Tiền gửi ngân hàng",
        "credit_account": "515",
        "credit_account_name": "Doanh thu hoạt động tài chính",
        "confidence": 0.86
    },

    # ========================================================
    # 10. CHI PHÍ KHÁC
    # ========================================================
    {
        "category": "Phí ngân hàng",
        "transaction_type": "expense",
        "keywords": [
            "phí ngân hàng", "phi ngan hang",
            "phí chuyển khoản", "phi chuyen khoan",
            "phí duy trì tài khoản", "phi duy tri tai khoan",
            "phí sms banking", "phi sms banking",
            "phí giao dịch ngân hàng", "phi giao dich ngan hang"
        ],
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "112",
        "credit_account_name": "Tiền gửi ngân hàng",
        "confidence": 0.86
    },
    {
        "category": "Chi phí phạt vi phạm",
        "transaction_type": "expense",
        "keywords": [
            "tiền phạt", "tien phat",
            "phạt vi phạm", "phat vi pham",
            "phạt hợp đồng", "phat hop dong",
            "phạt chậm nộp", "phat cham nop",
            "phạt thuế", "phat thue"
        ],
        "debit_account": "811",
        "debit_account_name": "Chi phí khác",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.84
    },
    {
        "category": "Chi phí sửa chữa",
        "transaction_type": "expense",
        "keywords": [
            "sửa chữa", "sua chua",
            "bảo trì", "bao tri",
            "bảo dưỡng", "bao duong",
            "sửa máy", "sua may",
            "sửa thiết bị", "sua thiet bi",
            "sửa văn phòng", "sua van phong"
        ],
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.84
    },
    {
        "category": "Chi phí phần mềm",
        "transaction_type": "expense",
        "keywords": [
            "mua phần mềm", "mua phan mem",
            "thuê phần mềm", "thue phan mem",
            "phí phần mềm", "phi phan mem",
            "subscription", "saas",
            "chatgpt", "notion", "canva",
            "microsoft 365", "google workspace"
        ],
        "debit_account": "642",
        "debit_account_name": "Chi phí quản lý doanh nghiệp",
        "credit_account": "111",
        "credit_account_name": "Tiền mặt",
        "confidence": 0.86
    },
]


def extend_accounting_rules():
    """
    Thêm rule mở rộng vào ACCOUNTING_RULES.
    Hàm này tránh thêm trùng rule nhiều lần khi server reload.
    """
    global ACCOUNTING_RULES

    existing_keys = set()

    for rule in ACCOUNTING_RULES:
        key = (
            rule.get("category"),
            rule.get("debit_account"),
            rule.get("credit_account")
        )
        existing_keys.add(key)

    added_count = 0

    for rule in EXTRA_ACCOUNTING_RULES:
        key = (
            rule.get("category"),
            rule.get("debit_account"),
            rule.get("credit_account")
        )

        if key not in existing_keys:
            ACCOUNTING_RULES.append(rule)
            existing_keys.add(key)
            added_count += 1

    return added_count


# Tự động nạp kiến thức mở rộng khi import file ai_engine.py
EXTENDED_RULES_ADDED = extend_accounting_rules()

# ============================================================
# FINIIP AI ENGINE - UPGRADE V3.0
# Ghi chú: Các hàm bên dưới override phiên bản cũ ở phía trên file.
# Mục tiêu: rule mạnh hơn, matching không dấu, VAT rõ hơn, cảnh báo tốt hơn,
# batch test và dữ liệu demo cho backend/frontend sau này.
# ============================================================

from collections import defaultdict

V3_CORE_RULES: List[Dict[str, Any]] = [
    # Doanh thu
    {"category":"Doanh thu bán hàng","transaction_type":"income","keywords":["doanh thu bán hàng","thu tiền bán hàng","bán hàng","khách thanh toán tiền mua hàng","khách hàng thanh toán","nhận chuyển khoản doanh thu","thu tiền khách hàng","xuất hóa đơn bán hàng","bán sản phẩm","bán hàng online","doanh thu shopee","doanh thu tiktok shop","doanh thu cửa hàng"],"debit_account":"111","debit_account_name":"Tiền mặt","credit_account":"511","credit_account_name":"Doanh thu bán hàng và cung cấp dịch vụ","confidence":0.92},
    {"category":"Doanh thu dịch vụ","transaction_type":"income","keywords":["doanh thu dịch vụ","phí dịch vụ","cung cấp dịch vụ","thu phí tư vấn","dịch vụ phần mềm","dịch vụ thiết kế","dịch vụ marketing","dịch vụ kế toán"],"debit_account":"111","debit_account_name":"Tiền mặt","credit_account":"511","credit_account_name":"Doanh thu bán hàng và cung cấp dịch vụ","confidence":0.90},
    {"category":"Thu hồi công nợ khách hàng","transaction_type":"income","keywords":["thu hồi công nợ","khách trả nợ","thu nợ khách hàng","khách hàng thanh toán công nợ","thu tiền công nợ","khách chuyển khoản trả nợ"],"debit_account":"111","debit_account_name":"Tiền mặt","credit_account":"131","credit_account_name":"Phải thu khách hàng","confidence":0.91},
    {"category":"Khách hàng ứng trước","transaction_type":"income","keywords":["khách đặt cọc","khách ứng trước","nhận cọc khách hàng","khách chuyển tiền cọc","nhận tiền đặt cọc"],"debit_account":"111","debit_account_name":"Tiền mặt","credit_account":"131","credit_account_name":"Phải thu khách hàng","confidence":0.88},

    # Chi phí vận hành
    {"category":"Chi phí điện nước","transaction_type":"expense","keywords":["tiền điện","thanh toán tiền điện","evn","điện lực","tiền nước","thanh toán tiền nước","nước sạch","hóa đơn điện","hóa đơn nước","điện nước văn phòng"],"debit_account":"642","debit_account_name":"Chi phí quản lý doanh nghiệp","credit_account":"111","credit_account_name":"Tiền mặt","confidence":0.93},
    {"category":"Chi phí internet viễn thông","transaction_type":"expense","keywords":["internet","wifi","cước internet","tiền mạng","vnpt","viettel","fpt telecom","cước điện thoại","sim công ty","viễn thông"],"debit_account":"642","debit_account_name":"Chi phí quản lý doanh nghiệp","credit_account":"111","credit_account_name":"Tiền mặt","confidence":0.90},
    {"category":"Chi phí thuê văn phòng","transaction_type":"expense","keywords":["thuê văn phòng","tiền thuê văn phòng","thuê mặt bằng","tiền thuê mặt bằng","thuê cửa hàng","tiền thuê nhà","thuê kho","thuê địa điểm"],"debit_account":"642","debit_account_name":"Chi phí quản lý doanh nghiệp","credit_account":"111","credit_account_name":"Tiền mặt","confidence":0.91},
    {"category":"Chi phí văn phòng phẩm","transaction_type":"expense","keywords":["văn phòng phẩm","mua giấy in","mua bút","mực in","đồ dùng văn phòng","dụng cụ văn phòng","mua sổ sách","ghim kẹp"],"debit_account":"642","debit_account_name":"Chi phí quản lý doanh nghiệp","credit_account":"111","credit_account_name":"Tiền mặt","confidence":0.89},
    {"category":"Chi phí quảng cáo marketing","transaction_type":"expense","keywords":["quảng cáo facebook","facebook ads","meta ads","quảng cáo tiktok","tiktok ads","google ads","quảng cáo google","chi phí quảng cáo","chạy ads","marketing online","quảng cáo zalo","seo","booking koc","booking kol"],"debit_account":"641","debit_account_name":"Chi phí bán hàng","credit_account":"111","credit_account_name":"Tiền mặt","confidence":0.93},
    {"category":"Chi phí tiếp khách","transaction_type":"expense","keywords":["tiếp khách","ăn uống tiếp khách","chi phí tiếp khách","mời khách hàng","cafe gặp khách","nhà hàng tiếp khách","chiêu đãi khách hàng"],"debit_account":"642","debit_account_name":"Chi phí quản lý doanh nghiệp","credit_account":"111","credit_account_name":"Tiền mặt","confidence":0.87},
    {"category":"Chi phí công tác","transaction_type":"expense","keywords":["công tác phí","vé máy bay công tác","khách sạn công tác","taxi công tác","phụ cấp công tác","đi công tác","chi phí đi lại"],"debit_account":"642","debit_account_name":"Chi phí quản lý doanh nghiệp","credit_account":"111","credit_account_name":"Tiền mặt","confidence":0.86},
    {"category":"Chi phí phần mềm","transaction_type":"expense","keywords":["mua phần mềm","thuê phần mềm","phí phần mềm","subscription","saas","chatgpt","canva","notion","microsoft 365","google workspace","hosting","domain","tên miền","server","cloud"],"debit_account":"642","debit_account_name":"Chi phí quản lý doanh nghiệp","credit_account":"111","credit_account_name":"Tiền mặt","confidence":0.88},
    {"category":"Phí ngân hàng","transaction_type":"expense","keywords":["phí ngân hàng","phí chuyển khoản","phí duy trì tài khoản","phí sms banking","phí internet banking","vietcombank thu phí","bidv thu phí","techcombank thu phí","phí giao dịch ngân hàng"],"debit_account":"642","debit_account_name":"Chi phí quản lý doanh nghiệp","credit_account":"112","credit_account_name":"Tiền gửi ngân hàng","confidence":0.91},

    # Nhân sự
    {"category":"Ghi nhận lương phải trả","transaction_type":"expense","keywords":["ghi nhận lương","trích lương","lương phải trả","hạch toán lương","tính lương nhân viên","bảng lương tháng"],"debit_account":"642","debit_account_name":"Chi phí quản lý doanh nghiệp","credit_account":"334","credit_account_name":"Phải trả người lao động","confidence":0.90},
    {"category":"Thanh toán lương nhân viên","transaction_type":"expense","keywords":["trả lương","thanh toán lương","chuyển khoản lương","chi lương","trả lương nhân viên","lương nhân viên tháng","trả lương qua ngân hàng"],"debit_account":"334","debit_account_name":"Phải trả người lao động","credit_account":"112","credit_account_name":"Tiền gửi ngân hàng","confidence":0.94},
    {"category":"Bảo hiểm bắt buộc","transaction_type":"expense","keywords":["bảo hiểm xã hội","bhxh","bảo hiểm y tế","bhyt","bhtn","nộp bảo hiểm","bảo hiểm nhân viên"],"debit_account":"338","debit_account_name":"Phải trả, phải nộp khác","credit_account":"112","credit_account_name":"Tiền gửi ngân hàng","confidence":0.88},
    {"category":"Thuế thu nhập cá nhân","transaction_type":"expense","keywords":["thuế tncn","thuế thu nhập cá nhân","nộp thuế cá nhân","khấu trừ thuế cá nhân"],"debit_account":"3335","debit_account_name":"Thuế thu nhập cá nhân","credit_account":"112","credit_account_name":"Tiền gửi ngân hàng","confidence":0.88},

    # Mua hàng, tài sản, kho
    {"category":"Mua hàng hóa nhập kho","transaction_type":"expense","keywords":["mua hàng hóa nhập kho","nhập kho hàng hóa","mua hàng nhập kho","mua hàng hóa","nhập hàng","mua nguyên vật liệu","mua sản phẩm để bán"],"debit_account":"156","debit_account_name":"Hàng hóa","credit_account":"111","credit_account_name":"Tiền mặt","confidence":0.91},
    {"category":"Mua công cụ dụng cụ","transaction_type":"expense","keywords":["mua công cụ dụng cụ","công cụ dụng cụ","mua bàn ghế","mua thiết bị nhỏ","mua máy in","mua điện thoại văn phòng"],"debit_account":"153","debit_account_name":"Công cụ dụng cụ","credit_account":"111","credit_account_name":"Tiền mặt","confidence":0.86},
    {"category":"Mua tài sản cố định","transaction_type":"expense","keywords":["mua máy tính","mua laptop","mua ô tô","mua xe","mua máy móc","mua thiết bị văn phòng giá trị lớn","mua tài sản cố định","mua tscđ"],"debit_account":"211","debit_account_name":"Tài sản cố định hữu hình","credit_account":"111","credit_account_name":"Tiền mặt","confidence":0.90},
    {"category":"Giá vốn hàng bán","transaction_type":"expense","keywords":["ghi nhận giá vốn","giá vốn hàng bán","xuất kho bán hàng","kết chuyển giá vốn"],"debit_account":"632","debit_account_name":"Giá vốn hàng bán","credit_account":"156","credit_account_name":"Hàng hóa","confidence":0.86},

    # Tiền, ngân hàng, công nợ
    {"category":"Rút tiền mặt từ ngân hàng","transaction_type":"transfer","keywords":["rút tiền mặt từ ngân hàng","rút tiền ngân hàng","rút tiền mặt","rút tiền từ tài khoản","withdraw tiền mặt"],"debit_account":"111","debit_account_name":"Tiền mặt","credit_account":"112","credit_account_name":"Tiền gửi ngân hàng","confidence":0.94},
    {"category":"Nộp tiền mặt vào ngân hàng","transaction_type":"transfer","keywords":["nộp tiền mặt vào ngân hàng","nộp tiền vào tài khoản","nộp tiền ngân hàng","gửi tiền mặt vào ngân hàng"],"debit_account":"112","debit_account_name":"Tiền gửi ngân hàng","credit_account":"111","credit_account_name":"Tiền mặt","confidence":0.94},
    {"category":"Tạm ứng nhân viên","transaction_type":"expense","keywords":["tạm ứng nhân viên","ứng tiền cho nhân viên","nhân viên tạm ứng","ứng công tác phí","tạm ứng công tác"],"debit_account":"141","debit_account_name":"Tạm ứng","credit_account":"111","credit_account_name":"Tiền mặt","confidence":0.91},
    {"category":"Hoàn ứng nhân viên","transaction_type":"income","keywords":["hoàn ứng","nhân viên hoàn ứng","thu lại tiền tạm ứng","quyết toán tạm ứng","hoàn trả tạm ứng"],"debit_account":"111","debit_account_name":"Tiền mặt","credit_account":"141","credit_account_name":"Tạm ứng","confidence":0.90},
    {"category":"Thanh toán công nợ nhà cung cấp","transaction_type":"expense","keywords":["trả nhà cung cấp","trả tiền nhà cung cấp","thanh toán nhà cung cấp","thanh toán công nợ nhà cung cấp","trả nợ nhà cung cấp","trả tiền hàng cho nhà cung cấp"],"debit_account":"331","debit_account_name":"Phải trả người bán","credit_account":"111","credit_account_name":"Tiền mặt","confidence":0.91},
    {"category":"Mua chịu nhà cung cấp","transaction_type":"expense","keywords":["mua chịu","ghi nợ nhà cung cấp","phải trả người bán","nhận hóa đơn chưa thanh toán","mua hàng chưa thanh toán"],"debit_account":"156","debit_account_name":"Hàng hóa","credit_account":"331","credit_account_name":"Phải trả người bán","confidence":0.87},

    # Thuế, vốn, vay
    {"category":"Nộp thuế VAT","transaction_type":"expense","keywords":["nộp thuế vat","nộp thuế gtgt","thuế giá trị gia tăng phải nộp","thanh toán thuế vat"],"debit_account":"3331","debit_account_name":"Thuế GTGT phải nộp","credit_account":"112","credit_account_name":"Tiền gửi ngân hàng","confidence":0.90},
    {"category":"Nhận vốn góp","transaction_type":"income","keywords":["nhận vốn góp","góp vốn","chủ sở hữu góp vốn","thành viên góp vốn","cổ đông góp vốn","bổ sung vốn điều lệ"],"debit_account":"111","debit_account_name":"Tiền mặt","credit_account":"411","credit_account_name":"Vốn chủ sở hữu","confidence":0.92},
    {"category":"Nhận tiền vay","transaction_type":"income","keywords":["vay ngân hàng","nhận tiền vay","giải ngân khoản vay","vay vốn","nhận khoản vay"],"debit_account":"112","debit_account_name":"Tiền gửi ngân hàng","credit_account":"341","credit_account_name":"Vay và nợ thuê tài chính","confidence":0.90},
    {"category":"Trả nợ vay","transaction_type":"expense","keywords":["trả nợ vay","trả gốc vay","thanh toán khoản vay","trả tiền vay ngân hàng"],"debit_account":"341","debit_account_name":"Vay và nợ thuê tài chính","credit_account":"112","credit_account_name":"Tiền gửi ngân hàng","confidence":0.90},
]


def _v3_extend_rules() -> int:
    existing = set()
    for r in ACCOUNTING_RULES:
        existing.add((r.get("category"), tuple(sorted([remove_vietnamese_accents(k.lower()) for k in r.get("keywords", [])[:3]]))))
    added = 0
    for r in V3_CORE_RULES:
        key = (r.get("category"), tuple(sorted([remove_vietnamese_accents(k.lower()) for k in r.get("keywords", [])[:3]])))
        if key not in existing:
            ACCOUNTING_RULES.append(r)
            existing.add(key)
            added += 1
    return added

V3_RULES_ADDED = _v3_extend_rules()


def normalize_for_match(text: str) -> str:
    text = normalize_text(text or "")
    text = remove_vietnamese_accents(text)
    text = re.sub(r"[^a-z0-9% ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _keyword_variants(keyword: str) -> List[str]:
    raw = normalize_text(keyword)
    no_acc = normalize_for_match(keyword)
    return list({raw, no_acc})


def detect_payment_account(text: str, default_account: str, default_name: str):
    raw = normalize_text(text)
    norm = normalize_for_match(text)
    bank_keywords = [
        "chuyen khoan", "ngan hang", "bank", "stk", "tai khoan", "vietcombank", "vcb", "techcombank", "tcb", "bidv", "vietinbank", "agribank", "mb bank", "mbbank", "acb", "vpbank", "tpbank", "momo", "zalopay", "visa", "mastercard", "quet the", "pos"
    ]
    cash_keywords = ["tien mat", "cash", "tra tien mat", "thu tien mat"]
    receivable_keywords = ["ban chiu", "khach no", "chua thu tien", "cong no khach", "phai thu"]
    payable_keywords = ["mua chiu", "chua thanh toan", "ghi no nha cung cap", "phai tra nguoi ban"]
    if any(k in norm for k in receivable_keywords):
        return "131", "Phải thu khách hàng", "receivable"
    if any(k in norm for k in payable_keywords):
        return "331", "Phải trả người bán", "payable"
    if any(k in norm for k in bank_keywords):
        return "112", "Tiền gửi ngân hàng", "bank"
    if any(k in norm for k in cash_keywords):
        return "111", "Tiền mặt", "cash"
    if default_account == "112":
        return default_account, default_name, "bank"
    if default_account == "111":
        return default_account, default_name, "cash"
    return default_account, default_name, "unknown"


def detect_vat_rate(description: str) -> float:
    norm = normalize_for_match(description)
    if any(k in norm for k in ["khong vat", "khong co vat", "khong thue", "mien thue"]):
        return 0.0
    patterns = [
        (r"vat\s*(\d{1,2})\s*%", 1),
        (r"gtgt\s*(\d{1,2})\s*%", 1),
        (r"thue\s*(\d{1,2})\s*%", 1),
        (r"(\d{1,2})\s*%\s*vat", 1),
    ]
    for pattern, group in patterns:
        m = re.search(pattern, norm)
        if m:
            value = float(m.group(group))
            if value in [0, 5, 8, 10]:
                return value
            return value
    if any(k in norm for k in ["co vat", "hoa don vat", "hoa don do", "thue gtgt"]):
        return 10.0
    return 0.0


def detect_amount_level(amount: float) -> str:
    if amount >= 100_000_000:
        return "very_high"
    if amount >= 20_000_000:
        return "high"
    if amount >= 5_000_000:
        return "medium"
    return "low"


def confidence_label(value: float) -> str:
    if value >= 0.9:
        return "Rất cao"
    if value >= 0.75:
        return "Cao"
    if value >= 0.55:
        return "Trung bình"
    if value > 0:
        return "Thấp"
    return "Không xác định"


def find_best_rule(description: str):
    raw = normalize_text(description)
    norm = normalize_for_match(description)
    best_match = None
    best_score = 0.0
    best_keywords: List[str] = []

    for rule in ACCOUNTING_RULES:
        score = 0.0
        matched: List[str] = []
        for kw in rule.get("keywords", []):
            variants = _keyword_variants(kw)
            matched_this = False
            for v in variants:
                if v and (v in raw or v in norm):
                    score += max(2.0, len(v.split()) * 4.0 + len(v) / 10.0)
                    matched_this = True
                    break
            if matched_this:
                matched.append(kw)
        # Ưu tiên rule có keyword dài/chính xác và confidence cao
        if matched:
            score += float(rule.get("confidence", 0.75)) * 5
            if len(matched) >= 2:
                score += 4
        if score > best_score:
            best_score = score
            best_match = rule
            best_keywords = matched

    return best_match, best_score, best_keywords


def generate_warnings(description: str, amount: float, category: str, transaction_type: str, debit_account: str, credit_account: str, confidence: float, payment_method: str, vat_rate: float) -> List[Dict[str, Any]]:
    warnings: List[Dict[str, Any]] = []
    norm = normalize_for_match(description)
    if confidence < 0.7:
        warnings.append({"level":"medium","type":"low_confidence","message":"Độ tin cậy AI chưa cao, nên kiểm tra thủ công trước khi ghi sổ."})
    if amount and amount >= 5_000_000 and payment_method == "cash":
        warnings.append({"level":"high","type":"cash_over_5m","message":"Giao dịch tiền mặt từ 5 triệu đồng trở lên có thể rủi ro về chứng từ/thuế. Cần kiểm tra quy định hiện hành và chứng từ thanh toán không dùng tiền mặt."})
    if amount and amount >= 100_000_000:
        warnings.append({"level":"medium","type":"large_amount","message":"Giao dịch giá trị lớn, nên kiểm tra hợp đồng, hóa đơn và phê duyệt nội bộ."})
    if vat_rate > 0 and transaction_type == "expense" and credit_account == "111" and amount >= 5_000_000:
        warnings.append({"level":"high","type":"vat_cash_payment","message":"Chi phí có VAT và giá trị lớn thanh toán tiền mặt có thể không tối ưu khi khấu trừ thuế. Nên kiểm tra chứng từ thanh toán."})
    if any(k in norm for k in ["hoa don", "vat", "gtgt"]) and vat_rate == 0:
        warnings.append({"level":"low","type":"vat_rate_missing","message":"Mô tả nhắc đến hóa đơn/VAT nhưng chưa thấy thuế suất. Nên bổ sung 5%, 8% hoặc 10% nếu có."})
    if transaction_type == "unknown":
        warnings.append({"level":"high","type":"unknown_transaction","message":"AI chưa nhận diện được nghiệp vụ. Cần kế toán kiểm tra thủ công."})
    return warnings


def build_vat_journal_lines(description: str, amount: float, transaction_type: str, debit_account: str, debit_account_name: str, credit_account: str, credit_account_name: str, vat_rate: float) -> Dict[str, Any]:
    if vat_rate <= 0 or transaction_type not in ["income", "expense"]:
        return {
            "has_vat": False,
            "subtotal": amount,
            "vat_amount": 0,
            "total_amount": amount,
            "journal_lines": [
                {"side":"debit","account_code":debit_account,"account_name":debit_account_name,"amount":amount},
                {"side":"credit","account_code":credit_account,"account_name":credit_account_name,"amount":amount},
            ] if debit_account and credit_account else []
        }
    # Giả định amount là tổng đã gồm VAT khi mô tả có VAT.
    subtotal = round(amount / (1 + vat_rate / 100), 2)
    vat_amount = round(amount - subtotal, 2)
    if transaction_type == "expense":
        lines = [
            {"side":"debit","account_code":debit_account,"account_name":debit_account_name,"amount":subtotal},
            {"side":"debit","account_code":"1331","account_name":"Thuế GTGT được khấu trừ","amount":vat_amount},
            {"side":"credit","account_code":credit_account,"account_name":credit_account_name,"amount":amount},
        ]
    else:
        lines = [
            {"side":"debit","account_code":debit_account,"account_name":debit_account_name,"amount":amount},
            {"side":"credit","account_code":credit_account,"account_name":credit_account_name,"amount":subtotal},
            {"side":"credit","account_code":"3331","account_name":"Thuế GTGT phải nộp","amount":vat_amount},
        ]
    return {"has_vat": True, "subtotal": subtotal, "vat_amount": vat_amount, "total_amount": amount, "journal_lines": lines}


def classify_transaction(description: str) -> Dict[str, Any]:
    best_match, best_score, matched_keywords = find_best_rule(description)
    vat_rate = detect_vat_rate(description)
    if not best_match:
        warnings = generate_warnings(description, 0, "Chưa phân loại", "unknown", None, None, 0.0, "unknown", vat_rate)
        return {
            "category":"Chưa phân loại", "transaction_type":"unknown",
            "debit_account":None, "debit_account_name":None, "credit_account":None, "credit_account_name":None,
            "confidence":0.0, "confidence_label":"Không xác định", "matched_keywords":[], "payment_method":"unknown", "vat_rate":vat_rate,
            "warnings":warnings, "suggestion":"Cần kế toán kiểm tra và bổ sung rule mới cho trường hợp này."
        }
    debit_account = best_match.get("debit_account")
    debit_name = best_match.get("debit_account_name")
    credit_account = best_match.get("credit_account")
    credit_name = best_match.get("credit_account_name")
    payment_method = "unknown"
    if credit_account in ["111", "112", "331"]:
        credit_account, credit_name, payment_method = detect_payment_account(description, credit_account, credit_name)
    if debit_account in ["111", "112", "131"]:
        debit_account, debit_name, payment_method = detect_payment_account(description, debit_account, debit_name)
    base_confidence = float(best_match.get("confidence", 0.75))
    confidence = min(0.98, base_confidence + (0.03 if len(matched_keywords) >= 2 else 0) + (0.02 if best_score > 25 else 0))
    warnings = generate_warnings(description, 0, best_match.get("category"), best_match.get("transaction_type"), debit_account, credit_account, confidence, payment_method, vat_rate)
    return {
        "category":best_match.get("category"), "transaction_type":best_match.get("transaction_type"),
        "debit_account":debit_account, "debit_account_name":debit_name,
        "credit_account":credit_account, "credit_account_name":credit_name,
        "confidence":round(confidence, 3), "confidence_label":confidence_label(confidence),
        "matched_keywords":matched_keywords, "payment_method":payment_method, "vat_rate":vat_rate,
        "warnings":warnings, "suggestion":"AI đã phân loại theo rule-based. Nên kiểm tra trước khi ghi sổ chính thức."
    }


def suggest_journal_entry(description: str, amount: float) -> Dict[str, Any]:
    result = classify_transaction(description)
    if amount <= 0:
        return {"error": True, "message": "Số tiền phải lớn hơn 0"}
    if result["transaction_type"] == "unknown":
        return {
            "description": description, "amount": amount, "category": result["category"], "transaction_type": "unknown",
            "debit_account_code": None, "debit_account_name": None, "credit_account_code": None, "credit_account_name": None,
            "confidence": 0.0, "confidence_label": "Không xác định", "matched_keywords": [], "payment_method": "unknown",
            "vat_rate": result.get("vat_rate", 0), "has_vat": False, "subtotal": amount, "vat_amount": 0, "total_amount": amount,
            "amount_level": detect_amount_level(amount), "warnings": result["warnings"], "journal_lines": [],
            "suggestion": "Chưa thể gợi ý bút toán. Cần kế toán kiểm tra thủ công."
        }
    vat_data = build_vat_journal_lines(description, amount, result["transaction_type"], result["debit_account"], result["debit_account_name"], result["credit_account"], result["credit_account_name"], result["vat_rate"])
    warnings = generate_warnings(description, amount, result["category"], result["transaction_type"], result["debit_account"], result["credit_account"], result["confidence"], result["payment_method"], result["vat_rate"])
    return {
        "description": description, "amount": amount, "category": result["category"], "transaction_type": result["transaction_type"],
        "debit_account_code": result["debit_account"], "debit_account_name": result["debit_account_name"],
        "credit_account_code": result["credit_account"], "credit_account_name": result["credit_account_name"],
        "confidence": result["confidence"], "confidence_label": result["confidence_label"], "matched_keywords": result["matched_keywords"], "payment_method": result["payment_method"],
        "vat_rate": result["vat_rate"], "has_vat": vat_data["has_vat"], "subtotal": vat_data["subtotal"], "vat_amount": vat_data["vat_amount"], "total_amount": vat_data["total_amount"],
        "amount_level": detect_amount_level(amount), "warnings": warnings, "journal_lines": vat_data["journal_lines"],
        "suggestion": "Đây là bút toán AI gợi ý. Kế toán nên kiểm tra trước khi ghi sổ chính thức."
    }


def demo_ai_cases():
    examples = [
        {"description":"Thanh toán tiền điện EVN tháng 5 bằng chuyển khoản", "amount":2500000},
        {"description":"Thanh toán tiền nước văn phòng tháng 5", "amount":900000},
        {"description":"Trả lương nhân viên tháng 5 qua Vietcombank", "amount":35000000},
        {"description":"Mua máy tính văn phòng 22 triệu có VAT 10% thanh toán chuyển khoản", "amount":22000000},
        {"description":"Chi phí quảng cáo TikTok Ads có VAT 10%", "amount":8800000},
        {"description":"Nhận chuyển khoản doanh thu bán hàng có VAT 10%", "amount":11000000},
        {"description":"Mua văn phòng phẩm thanh toán tiền mặt", "amount":1200000},
        {"description":"Phí ngân hàng Vietcombank", "amount":55000},
        {"description":"Rút tiền mặt từ ngân hàng", "amount":10000000},
        {"description":"Nộp tiền mặt vào tài khoản ngân hàng", "amount":15000000},
        {"description":"Tạm ứng nhân viên đi công tác", "amount":3000000},
        {"description":"Hoàn ứng nhân viên", "amount":500000},
        {"description":"Trả tiền nhà cung cấp bằng chuyển khoản", "amount":45000000},
        {"description":"Nhận vốn góp của chủ sở hữu", "amount":200000000},
    ]
    return [suggest_journal_entry(x["description"], x["amount"]) for x in examples]


def benchmark_ai_cases(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    results = []
    recognized = 0
    high_confidence = 0
    warnings_count = 0
    categories = defaultdict(int)
    for case in cases:
        description = case.get("description", "")
        amount = float(case.get("amount", 0) or 0)
        result = suggest_journal_entry(description, amount)
        ok = result.get("transaction_type") != "unknown"
        recognized += 1 if ok else 0
        high_confidence += 1 if result.get("confidence", 0) >= 0.85 else 0
        warnings_count += len(result.get("warnings", []))
        categories[result.get("category") or "Chưa phân loại"] += 1
        results.append({"input": case, "ai_result": result})
    total = len(cases)
    return {
        "total": total,
        "recognized": recognized,
        "unknown": total - recognized,
        "recognized_rate": round(recognized / total * 100, 2) if total else 0,
        "high_confidence": high_confidence,
        "high_confidence_rate": round(high_confidence / total * 100, 2) if total else 0,
        "warnings_count": warnings_count,
        "category_distribution": dict(categories),
        "results": results,
    }

# ============================================================
# FINIIP AI ENGINE - V3.1 FIX TRANSFER ACCOUNTS
# ============================================================

def classify_transaction(description: str) -> Dict[str, Any]:
    best_match, best_score, matched_keywords = find_best_rule(description)
    vat_rate = detect_vat_rate(description)
    if not best_match:
        warnings = generate_warnings(description, 0, "Chưa phân loại", "unknown", None, None, 0.0, "unknown", vat_rate)
        return {
            "category":"Chưa phân loại", "transaction_type":"unknown",
            "debit_account":None, "debit_account_name":None, "credit_account":None, "credit_account_name":None,
            "confidence":0.0, "confidence_label":"Không xác định", "matched_keywords":[], "payment_method":"unknown", "vat_rate":vat_rate,
            "warnings":warnings, "suggestion":"Cần kế toán kiểm tra và bổ sung rule mới cho trường hợp này."
        }
    category = best_match.get("category")
    tx_type = best_match.get("transaction_type")
    debit_account = best_match.get("debit_account")
    debit_name = best_match.get("debit_account_name")
    credit_account = best_match.get("credit_account")
    credit_name = best_match.get("credit_account_name")
    payment_method = "transfer" if tx_type == "transfer" else "unknown"

    # Với giao dịch chuyển nội bộ 111 <-> 112, giữ nguyên Nợ/Có theo rule.
    if tx_type != "transfer":
        if credit_account in ["111", "112", "331"]:
            credit_account, credit_name, payment_method = detect_payment_account(description, credit_account, credit_name)
        if debit_account in ["111", "112", "131"]:
            debit_account, debit_name, payment_method = detect_payment_account(description, debit_account, debit_name)

    base_confidence = float(best_match.get("confidence", 0.75))
    confidence = min(0.98, base_confidence + (0.03 if len(matched_keywords) >= 2 else 0) + (0.02 if best_score > 25 else 0))
    warnings = generate_warnings(description, 0, category, tx_type, debit_account, credit_account, confidence, payment_method, vat_rate)
    return {
        "category":category, "transaction_type":tx_type,
        "debit_account":debit_account, "debit_account_name":debit_name,
        "credit_account":credit_account, "credit_account_name":credit_name,
        "confidence":round(confidence, 3), "confidence_label":confidence_label(confidence),
        "matched_keywords":matched_keywords, "payment_method":payment_method, "vat_rate":vat_rate,
        "warnings":warnings, "suggestion":"AI đã phân loại theo rule-based. Nên kiểm tra trước khi ghi sổ chính thức."
    }


# ============================================================
# FINIIP AI ENGINE - V7 KNOWLEDGE PACK
# Thêm kiến thức kế toán thường gặp cho SME/e-commerce.
# ============================================================

EXTRA_ACCOUNTING_KNOWLEDGE_RULES = [
    {"keywords": ["khau hao tai san co dinh", "trich khau hao", "khấu hao tài sản cố định", "trích khấu hao"], "category": "Chi phí khấu hao TSCĐ", "transaction_type": "expense", "debit_account": "642", "debit_account_name": "Chi phí quản lý doanh nghiệp", "credit_account": "214", "credit_account_name": "Hao mòn tài sản cố định", "confidence": 0.9},
    {"keywords": ["mua cong cu dung cu", "mua ccdc", "công cụ dụng cụ", "mua công cụ dụng cụ"], "category": "Mua công cụ dụng cụ", "transaction_type": "expense", "debit_account": "153", "debit_account_name": "Công cụ dụng cụ", "credit_account": "111", "credit_account_name": "Tiền mặt", "confidence": 0.86},
    {"keywords": ["phan bo cong cu dung cu", "phân bổ công cụ dụng cụ", "phan bo ccdc", "phân bổ ccdc"], "category": "Phân bổ công cụ dụng cụ", "transaction_type": "expense", "debit_account": "642", "debit_account_name": "Chi phí quản lý doanh nghiệp", "credit_account": "242", "credit_account_name": "Chi phí trả trước", "confidence": 0.88},
    {"keywords": ["tra truoc tien thue van phong", "trả trước tiền thuê văn phòng", "chi phi tra truoc", "chi phí trả trước"], "category": "Chi phí trả trước", "transaction_type": "expense", "debit_account": "242", "debit_account_name": "Chi phí trả trước", "credit_account": "111", "credit_account_name": "Tiền mặt", "confidence": 0.86},
    {"keywords": ["lai vay ngan hang", "lãi vay ngân hàng", "chi phi lai vay", "chi phí lãi vay"], "category": "Chi phí lãi vay", "transaction_type": "expense", "debit_account": "635", "debit_account_name": "Chi phí tài chính", "credit_account": "112", "credit_account_name": "Tiền gửi ngân hàng", "confidence": 0.88},
    {"keywords": ["nop thue gtgt", "nộp thuế gtgt", "nop thue vat", "nộp thuế vat"], "category": "Nộp thuế GTGT", "transaction_type": "expense", "debit_account": "3331", "debit_account_name": "Thuế GTGT phải nộp", "credit_account": "112", "credit_account_name": "Tiền gửi ngân hàng", "confidence": 0.9},
    {"keywords": ["nop thue tndn", "nộp thuế tndn", "thue thu nhap doanh nghiep", "thuế thu nhập doanh nghiệp"], "category": "Nộp thuế TNDN", "transaction_type": "expense", "debit_account": "3334", "debit_account_name": "Thuế thu nhập doanh nghiệp", "credit_account": "112", "credit_account_name": "Tiền gửi ngân hàng", "confidence": 0.88},
    {"keywords": ["nop bao hiem xa hoi", "nộp bảo hiểm xã hội", "bhxh", "bhyt", "bhtn"], "category": "Nộp bảo hiểm", "transaction_type": "expense", "debit_account": "338", "debit_account_name": "Phải trả phải nộp khác", "credit_account": "112", "credit_account_name": "Tiền gửi ngân hàng", "confidence": 0.88},
    {"keywords": ["gia von hang ban", "giá vốn hàng bán", "xuat kho ban hang", "xuất kho bán hàng"], "category": "Giá vốn hàng bán", "transaction_type": "expense", "debit_account": "632", "debit_account_name": "Giá vốn hàng bán", "credit_account": "156", "credit_account_name": "Hàng hóa", "confidence": 0.9},
    {"keywords": ["phi san shopee", "phí sàn shopee", "phi san tiktok shop", "phí sàn tiktok shop", "phi san lazada", "phí sàn lazada"], "category": "Chi phí sàn thương mại điện tử", "transaction_type": "expense", "debit_account": "641", "debit_account_name": "Chi phí bán hàng", "credit_account": "112", "credit_account_name": "Tiền gửi ngân hàng", "confidence": 0.9},
    {"keywords": ["doi soat shopee", "đối soát shopee", "doi soat tiktok shop", "đối soát tiktok shop", "san thu ho", "sàn thu hộ"], "category": "Sàn TMĐT thu hộ khách hàng", "transaction_type": "income", "debit_account": "112", "debit_account_name": "Tiền gửi ngân hàng", "credit_account": "131", "credit_account_name": "Phải thu khách hàng", "confidence": 0.86},
    {"keywords": ["hoan tien shopee", "hoàn tiền shopee", "hoan tien tiktok shop", "hoàn tiền tiktok shop", "khach hoan hang san", "khách hoàn hàng sàn"], "category": "Hoàn tiền/hoàn hàng TMĐT", "transaction_type": "expense", "debit_account": "521", "debit_account_name": "Các khoản giảm trừ doanh thu", "credit_account": "131", "credit_account_name": "Phải thu khách hàng", "confidence": 0.84},
    {"keywords": ["phi cod", "phí cod", "phi thu ho", "phí thu hộ", "phi van chuyen cod", "phí vận chuyển cod"], "category": "Chi phí COD/vận chuyển thu hộ", "transaction_type": "expense", "debit_account": "641", "debit_account_name": "Chi phí bán hàng", "credit_account": "112", "credit_account_name": "Tiền gửi ngân hàng", "confidence": 0.86},
    {"keywords": ["chi ho khach hang", "chi hộ khách hàng", "thu ho khach hang", "thu hộ khách hàng"], "category": "Thu hộ/chi hộ", "transaction_type": "other", "debit_account": "138", "debit_account_name": "Phải thu khác", "credit_account": "111", "credit_account_name": "Tiền mặt", "confidence": 0.78},
    {"keywords": ["nhan tien khach no", "nhận tiền khách nợ", "thu cong no khach hang", "thu công nợ khách hàng"], "category": "Thu công nợ khách hàng", "transaction_type": "income", "debit_account": "111", "debit_account_name": "Tiền mặt", "credit_account": "131", "credit_account_name": "Phải thu khách hàng", "confidence": 0.9},
    {"keywords": ["tra cong no nha cung cap", "trả công nợ nhà cung cấp", "thanh toan cong no nha cung cap", "thanh toán công nợ nhà cung cấp"], "category": "Trả công nợ nhà cung cấp", "transaction_type": "expense", "debit_account": "331", "debit_account_name": "Phải trả người bán", "credit_account": "111", "credit_account_name": "Tiền mặt", "confidence": 0.9},
]

_existing_rule_keys = {
    (tuple(normalize_for_match(k) for k in rule.get("keywords", [])), rule.get("category"), rule.get("debit_account"), rule.get("credit_account"))
    for rule in ACCOUNTING_RULES
}
for _rule in EXTRA_ACCOUNTING_KNOWLEDGE_RULES:
    _key = (tuple(normalize_for_match(k) for k in _rule.get("keywords", [])), _rule.get("category"), _rule.get("debit_account"), _rule.get("credit_account"))
    if _key not in _existing_rule_keys:
        ACCOUNTING_RULES.append(_rule)
        _existing_rule_keys.add(_key)

# ============================================================
# FINIIP AI ENGINE - V8 INTELLIGENCE LAYER
# Nâng cấp: explanation, confidence gate, risk score, expected accuracy test,
# và chuẩn hóa journal_entry để tiến gần Cấp 5.
# ============================================================

V8_KNOWLEDGE_DOMAINS = [
    {
        "domain": "thuế",
        "description": "Quy tắc cơ bản về VAT, TNDN, TNCN và thanh toán không tiền mặt.",
        "priority": "high",
        "examples": ["VAT đầu vào", "nộp thuế GTGT", "thuế TNDN", "thuế TNCN"],
    },
    {
        "domain": "bút toán",
        "description": "Gợi ý Nợ/Có theo nghiệp vụ kế toán SME và thương mại điện tử.",
        "priority": "high",
        "examples": ["doanh thu bán hàng", "giá vốn", "chi phí quảng cáo", "thu công nợ"],
    },
    {
        "domain": "sàn TMĐT",
        "description": "Phí sàn, COD, hoàn hàng, đối soát Shopee/TikTok Shop/Lazada.",
        "priority": "high",
        "examples": ["phí sàn Shopee", "đối soát TikTok Shop", "hoàn hàng", "COD"],
    },
    {
        "domain": "ngân hàng và tiền mặt",
        "description": "Phân biệt thanh toán tiền mặt, chuyển khoản, rút/nộp tiền nội bộ.",
        "priority": "medium",
        "examples": ["chuyển khoản", "tiền mặt", "rút tiền", "nộp tiền"],
    },
    {
        "domain": "tài sản và phân bổ",
        "description": "TSCĐ, CCDC, chi phí trả trước, khấu hao và phân bổ.",
        "priority": "medium",
        "examples": ["mua máy tính", "khấu hao", "phân bổ CCDC", "chi phí trả trước"],
    },
]

V8_EXPECTED_TEST_CASES = [
    {"description": "Thanh toán tiền điện EVN tháng 5 bằng chuyển khoản", "amount": 2500000, "expected_category": "Chi phí điện nước", "expected_debit": "642", "expected_credit": "112"},
    {"description": "Chạy quảng cáo Facebook Ads có VAT 10% thanh toán chuyển khoản", "amount": 11000000, "expected_category": "Chi phí quảng cáo", "expected_debit": "641", "expected_credit": "112"},
    {"description": "Nhận chuyển khoản doanh thu bán hàng có VAT 10%", "amount": 22000000, "expected_category": "Doanh thu bán hàng", "expected_debit": "112", "expected_credit": "511"},
    {"description": "Mua hàng hóa nhập kho từ nhà cung cấp bằng chuyển khoản", "amount": 45000000, "expected_category": "Mua hàng hóa", "expected_debit": "156", "expected_credit": "112"},
    {"description": "Xuất kho bán hàng ghi nhận giá vốn", "amount": 12000000, "expected_category": "Giá vốn hàng bán", "expected_debit": "632", "expected_credit": "156"},
    {"description": "Phí sàn Shopee tháng 5", "amount": 1800000, "expected_category": "Chi phí sàn thương mại điện tử", "expected_debit": "641", "expected_credit": "112"},
    {"description": "Đối soát TikTok Shop sàn chuyển tiền về ngân hàng", "amount": 30500000, "expected_category": "Sàn TMĐT thu hộ khách hàng", "expected_debit": "112", "expected_credit": "131"},
    {"description": "Nộp thuế GTGT quý này qua ngân hàng", "amount": 9000000, "expected_category": "Nộp thuế GTGT", "expected_debit": "3331", "expected_credit": "112"},
    {"description": "Trích khấu hao tài sản cố định tháng 5", "amount": 3000000, "expected_category": "Chi phí khấu hao TSCĐ", "expected_debit": "642", "expected_credit": "214"},
    {"description": "Trả lương nhân viên tháng 5 qua ngân hàng", "amount": 35000000, "expected_category": "Thanh toán lương nhân viên", "expected_debit": "334", "expected_credit": "112"},
    {"description": "Thu công nợ khách hàng bằng chuyển khoản", "amount": 16000000, "expected_category": "Thu công nợ khách hàng", "expected_debit": "112", "expected_credit": "131"},
    {"description": "Trả công nợ nhà cung cấp bằng chuyển khoản", "amount": 21000000, "expected_category": "Trả công nợ nhà cung cấp", "expected_debit": "331", "expected_credit": "112"},
]


def v8_confidence_status(confidence: float) -> Dict[str, Any]:
    confidence = float(confidence or 0)
    if confidence >= 0.9:
        return {"level": "very_high", "label": "Rất chắc", "needs_review": False, "action": "Có thể đề xuất ghi sổ sau khi người dùng xác nhận."}
    if confidence >= 0.75:
        return {"level": "high", "label": "Khá chắc", "needs_review": False, "action": "Nên kiểm tra nhanh trước khi ghi sổ."}
    if confidence >= 0.55:
        return {"level": "medium", "label": "Chưa thật chắc", "needs_review": True, "action": "Cần người dùng/kế toán kiểm tra."}
    return {"level": "low", "label": "Không chắc", "needs_review": True, "action": "Không nên tự động ghi sổ."}


def v8_explain_result(description: str, amount: float, result: Dict[str, Any]) -> str:
    category = result.get("category") or "Chưa phân loại"
    debit = result.get("debit_account_code") or result.get("debit_account")
    credit = result.get("credit_account_code") or result.get("credit_account")
    matched = result.get("matched_keywords") or []
    vat_rate = result.get("vat_rate", 0) or 0
    payment_method = result.get("payment_method") or "unknown"
    parts = []
    if matched:
        parts.append(f"AI nhận diện các từ khóa/ngữ cảnh: {', '.join(matched[:5])}.")
    else:
        parts.append("AI chưa tìm thấy từ khóa đủ mạnh, nên kết quả cần được kiểm tra kỹ.")
    parts.append(f"Nghiệp vụ được xếp vào '{category}' với bút toán Nợ {debit or '?'} / Có {credit or '?'}.")
    if vat_rate:
        parts.append(f"Mô tả có VAT {vat_rate}%, nên AI tách phần thuế vào tài khoản VAT phù hợp nếu là nghiệp vụ mua/bán.")
    if payment_method != "unknown":
        parts.append(f"Phương thức thanh toán được suy luận là {payment_method}.")
    if amount >= 5_000_000:
        parts.append("Số tiền từ 5 triệu đồng trở lên cần kiểm tra chứng từ và phương thức thanh toán không dùng tiền mặt để giảm rủi ro thuế.")
    return " ".join(parts)


def v8_tax_risk_check(description: str, amount: float, result: Dict[str, Any]) -> Dict[str, Any]:
    norm = normalize_for_match(description)
    warnings = list(result.get("warnings") or [])
    risk_score = 0
    reasons = []

    if result.get("transaction_type") == "unknown":
        risk_score += 40
        reasons.append("AI chưa nhận diện được nghiệp vụ.")
    if float(result.get("confidence") or 0) < 0.7:
        risk_score += 20
        reasons.append("Độ tin cậy AI thấp hơn 0.7.")
    if amount >= 5_000_000 and any(k in norm for k in ["tien mat", "tiền mặt", "cash"]):
        risk_score += 30
        reasons.append("Giao dịch từ 5 triệu đồng trở lên thanh toán tiền mặt có rủi ro chứng từ/thuế.")
    if any(k in norm for k in ["hoa don", "hóa đơn", "vat", "gtgt"]) and not result.get("vat_rate"):
        risk_score += 15
        reasons.append("Có nhắc hóa đơn/VAT nhưng chưa rõ thuế suất.")
    if any(k in norm for k in ["phat", "phạt", "khong hoa don", "không hóa đơn"]):
        risk_score += 25
        reasons.append("Mô tả có dấu hiệu phạt hoặc thiếu hóa đơn.")
    risk_score = min(100, risk_score)
    if risk_score >= 70:
        level = "high"
    elif risk_score >= 35:
        level = "medium"
    elif risk_score > 0:
        level = "low"
    else:
        level = "safe"
    return {"risk_score": risk_score, "risk_level": level, "reasons": reasons, "warnings": warnings}


def v8_normalize_journal_entry(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    lines = result.get("journal_lines") or []
    journal_entry = []
    for line in lines:
        journal_entry.append({
            "side": line.get("side"),
            "account_code": line.get("account_code"),
            "account_name": line.get("account_name"),
            "amount": line.get("amount"),
        })
    if not journal_entry and result.get("debit_account_code") and result.get("credit_account_code"):
        journal_entry = [
            {"side": "debit", "account_code": result.get("debit_account_code"), "account_name": result.get("debit_account_name"), "amount": result.get("amount")},
            {"side": "credit", "account_code": result.get("credit_account_code"), "account_name": result.get("credit_account_name"), "amount": result.get("amount")},
        ]
    return journal_entry


def v8_enrich_ai_result(description: str, amount: float, result: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(result)
    confidence_status = v8_confidence_status(float(enriched.get("confidence") or 0))
    enriched["confidence_status"] = confidence_status
    enriched["needs_review"] = confidence_status["needs_review"]
    enriched["explanation"] = v8_explain_result(description, amount, enriched)
    enriched["journal_entry"] = v8_normalize_journal_entry(enriched)
    enriched["tax_risk"] = v8_tax_risk_check(description, amount, enriched)
    enriched["ai_stage"] = "V8 - Rule-based + learning memory + explanation + confidence gate + tax risk + journal suggestion"
    return enriched


_v8_base_suggest_journal_entry = suggest_journal_entry


def suggest_journal_entry(description: str, amount: float) -> Dict[str, Any]:  # type: ignore[no-redef]
    base = _v8_base_suggest_journal_entry(description, amount)
    if base.get("error"):
        return base
    return v8_enrich_ai_result(description, amount, base)


def v8_run_expected_accuracy_test(cases: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    cases = cases or V8_EXPECTED_TEST_CASES
    passed = 0
    results = []
    for case in cases:
        result = suggest_journal_entry(case["description"], float(case.get("amount") or 0))
        checks = {
            "category": result.get("category") == case.get("expected_category"),
            "debit": result.get("debit_account_code") == case.get("expected_debit"),
            "credit": result.get("credit_account_code") == case.get("expected_credit"),
        }
        ok = all(checks.values())
        passed += 1 if ok else 0
        results.append({"input": case, "ai_result": result, "checks": checks, "passed": ok})
    total = len(cases)
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy_percent": round(passed / total * 100, 2) if total else 0,
        "target": "Mục tiêu ngắn hạn: >= 80%; mục tiêu tốt: >= 90% trên bộ test thật của doanh nghiệp.",
        "results": results,
    }

# ============================================================
# FINIIP AI ENGINE - V8.1 SME ACCOUNTING OVERRIDES
# Sửa một số nghiệp vụ hay bị lẫn do keyword chung quá mạnh.
# ============================================================

_v81_prev_suggest_journal_entry = suggest_journal_entry


def v81_apply_business_overrides(description: str, amount: float, result: Dict[str, Any]) -> Dict[str, Any]:
    norm = normalize_for_match(description)
    updated = dict(result)

    # Chuẩn hóa tên category để test/analytics nhất quán hơn.
    category_alias = {
        "Mua hàng hóa nhập kho": "Mua hàng hóa",
        "Khấu hao tài sản cố định": "Chi phí khấu hao TSCĐ",
    }
    if updated.get("category") in category_alias:
        updated["category"] = category_alias[updated.get("category")]

    # Thanh toán lương: phân biệt với ghi nhận lương phải trả.
    if any(k in norm for k in ["tra luong", "thanh toan luong", "chuyen khoan luong", "chi luong"]):
        credit_code, credit_name, payment_method = detect_payment_account(description, "111", "Tiền mặt")
        updated.update({
            "category": "Thanh toán lương nhân viên",
            "transaction_type": "expense",
            "debit_account_code": "334",
            "debit_account_name": "Phải trả người lao động",
            "credit_account_code": credit_code,
            "credit_account_name": credit_name,
            "payment_method": payment_method,
            "confidence": max(float(updated.get("confidence") or 0), 0.93),
        })

    # Thu công nợ khách hàng: Nợ tiền / Có 131, không được đổi Nợ thành 131.
    if any(k in norm for k in ["thu cong no khach hang", "nhan tien khach no", "khach thanh toan cong no", "thu no khach hang"]):
        debit_code, debit_name, payment_method = detect_payment_account(description, "111", "Tiền mặt")
        updated.update({
            "category": "Thu công nợ khách hàng",
            "transaction_type": "income",
            "debit_account_code": debit_code,
            "debit_account_name": debit_name,
            "credit_account_code": "131",
            "credit_account_name": "Phải thu khách hàng",
            "payment_method": payment_method,
            "confidence": max(float(updated.get("confidence") or 0), 0.92),
        })

    # Trả công nợ nhà cung cấp: Nợ 331 / Có tiền.
    if any(k in norm for k in ["tra cong no nha cung cap", "thanh toan cong no nha cung cap", "tra no nha cung cap"]):
        credit_code, credit_name, payment_method = detect_payment_account(description, "111", "Tiền mặt")
        updated.update({
            "category": "Trả công nợ nhà cung cấp",
            "transaction_type": "expense",
            "debit_account_code": "331",
            "debit_account_name": "Phải trả người bán",
            "credit_account_code": credit_code,
            "credit_account_name": credit_name,
            "payment_method": payment_method,
            "confidence": max(float(updated.get("confidence") or 0), 0.92),
        })

    # Rebuild journal lines nếu đã override Nợ/Có.
    if updated.get("debit_account_code") and updated.get("credit_account_code") and not updated.get("has_vat"):
        updated["journal_lines"] = [
            {"side": "debit", "account_code": updated.get("debit_account_code"), "account_name": updated.get("debit_account_name"), "amount": amount},
            {"side": "credit", "account_code": updated.get("credit_account_code"), "account_name": updated.get("credit_account_name"), "amount": amount},
        ]
    updated = v8_enrich_ai_result(description, amount, updated)
    return updated


def suggest_journal_entry(description: str, amount: float) -> Dict[str, Any]:  # type: ignore[no-redef]
    base = _v81_prev_suggest_journal_entry(description, amount)
    if base.get("error"):
        return base
    return v81_apply_business_overrides(description, amount, base)

# V8.2: fix thu công nợ khách hàng payment detection ưu tiên ngân hàng/tiền mặt trước receivable.
_v82_prev_suggest_journal_entry = suggest_journal_entry


def v82_money_account_from_text(description: str, default_code: str = "111"):
    norm = normalize_for_match(description)
    if any(k in norm for k in ["chuyen khoan", "ngan hang", "bank", "vietcombank", "vcb", "techcombank", "bidv", "momo", "zalopay"]):
        return "112", "Tiền gửi ngân hàng", "bank"
    if any(k in norm for k in ["tien mat", "cash"]):
        return "111", "Tiền mặt", "cash"
    return ("112", "Tiền gửi ngân hàng", "bank") if default_code == "112" else ("111", "Tiền mặt", "cash")


def suggest_journal_entry(description: str, amount: float) -> Dict[str, Any]:  # type: ignore[no-redef]
    result = _v82_prev_suggest_journal_entry(description, amount)
    if result.get("error"):
        return result
    norm = normalize_for_match(description)
    if any(k in norm for k in ["thu cong no khach hang", "nhan tien khach no", "khach thanh toan cong no", "thu no khach hang"]):
        debit_code, debit_name, payment_method = v82_money_account_from_text(description, "111")
        result.update({
            "category": "Thu công nợ khách hàng",
            "transaction_type": "income",
            "debit_account_code": debit_code,
            "debit_account_name": debit_name,
            "credit_account_code": "131",
            "credit_account_name": "Phải thu khách hàng",
            "payment_method": payment_method,
            "confidence": max(float(result.get("confidence") or 0), 0.92),
            "journal_lines": [
                {"side": "debit", "account_code": debit_code, "account_name": debit_name, "amount": amount},
                {"side": "credit", "account_code": "131", "account_name": "Phải thu khách hàng", "amount": amount},
            ],
        })
        result = v8_enrich_ai_result(description, amount, result)
    return result
