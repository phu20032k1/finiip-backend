"""Finiip Accounting AI Full Core (V85).

Backend-only accounting intelligence layer:
- Broad Vietnamese accounting transaction rules.
- Journal-entry suggestion with VAT split, payment-account inference, risk gates.
- Formula solvers for VAT, depreciation, prepaid allocation, COGS, profit, CIT, payroll, aging.
- Local knowledge-base search for accounting/RAG-style answers.

This module is deterministic and offline-first. It does not replace a licensed accountant;
it creates a draft + review checklist so users can verify before posting.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = ROOT_DIR / "knowledge_base"


ACCOUNT_NAMES: Dict[str, str] = {
    "111": "Tiền mặt",
    "112": "Tiền gửi ngân hàng",
    "121": "Chứng khoán kinh doanh",
    "128": "Đầu tư nắm giữ đến ngày đáo hạn",
    "131": "Phải thu khách hàng",
    "1331": "Thuế GTGT được khấu trừ của hàng hóa, dịch vụ",
    "1332": "Thuế GTGT được khấu trừ của tài sản cố định",
    "136": "Phải thu nội bộ",
    "138": "Phải thu khác",
    "141": "Tạm ứng",
    "151": "Hàng mua đang đi đường",
    "152": "Nguyên liệu, vật liệu",
    "153": "Công cụ, dụng cụ",
    "154": "Chi phí sản xuất, kinh doanh dở dang",
    "155": "Thành phẩm",
    "156": "Hàng hóa",
    "157": "Hàng gửi đi bán",
    "211": "Tài sản cố định hữu hình",
    "213": "Tài sản cố định vô hình",
    "214": "Hao mòn tài sản cố định",
    "217": "Bất động sản đầu tư",
    "228": "Đầu tư góp vốn vào đơn vị khác",
    "229": "Dự phòng tổn thất tài sản",
    "241": "Xây dựng cơ bản dở dang",
    "242": "Chi phí trả trước",
    "243": "Tài sản thuế thu nhập hoãn lại",
    "244": "Cầm cố, thế chấp, ký quỹ, ký cược",
    "331": "Phải trả người bán",
    "3331": "Thuế GTGT phải nộp",
    "3334": "Thuế thu nhập doanh nghiệp",
    "3335": "Thuế thu nhập cá nhân",
    "3338": "Thuế khác",
    "334": "Phải trả người lao động",
    "335": "Chi phí phải trả",
    "336": "Phải trả nội bộ",
    "338": "Phải trả, phải nộp khác",
    "3382": "Kinh phí công đoàn",
    "3383": "Bảo hiểm xã hội",
    "3384": "Bảo hiểm y tế",
    "3386": "Bảo hiểm thất nghiệp",
    "341": "Vay và nợ thuê tài chính",
    "343": "Trái phiếu phát hành",
    "344": "Nhận ký quỹ, ký cược",
    "352": "Dự phòng phải trả",
    "353": "Quỹ khen thưởng, phúc lợi",
    "411": "Vốn đầu tư của chủ sở hữu",
    "414": "Quỹ đầu tư phát triển",
    "421": "Lợi nhuận sau thuế chưa phân phối",
    "511": "Doanh thu bán hàng và cung cấp dịch vụ",
    "515": "Doanh thu hoạt động tài chính",
    "521": "Các khoản giảm trừ doanh thu",
    "611": "Mua hàng",
    "621": "Chi phí nguyên vật liệu trực tiếp",
    "622": "Chi phí nhân công trực tiếp",
    "623": "Chi phí sử dụng máy thi công",
    "627": "Chi phí sản xuất chung",
    "631": "Giá thành sản xuất",
    "632": "Giá vốn hàng bán",
    "635": "Chi phí tài chính",
    "641": "Chi phí bán hàng",
    "642": "Chi phí quản lý doanh nghiệp",
    "711": "Thu nhập khác",
    "811": "Chi phí khác",
    "821": "Chi phí thuế thu nhập doanh nghiệp",
    "911": "Xác định kết quả kinh doanh",
}


def _strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def norm(text: Any) -> str:
    value = str(text or "").replace("đ", "d").replace("Đ", "D")
    return re.sub(r"\s+", " ", _strip_accents(value).lower()).strip()


def format_vnd(amount: Optional[float]) -> str:
    if amount is None or (isinstance(amount, float) and math.isnan(amount)):
        return "0 đồng"
    return f"{float(amount):,.0f}".replace(",", ".") + " đồng"


def parse_money(text: Any) -> Optional[float]:
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    raw = str(text)
    q = norm(raw).replace("vnd", "").replace("dong", "").replace("đ", "")
    # 1.234.567, 1,234,567, 25tr, 25 triệu, 1.5 tỷ
    candidates = re.findall(r"(\d+(?:[\.,]\d+)*(?:\s*)?)(ty|ti|ti dong|tỷ|trieu|triệu|tr|nghin|nghìn|k|m)?", raw.lower())
    if not candidates:
        candidates = re.findall(r"(\d+(?:[\.,]\d+)*)(ty|trieu|tr|nghin|k|m)?", q)
    for number_text, unit in candidates:
        s = number_text.strip().replace(" ", "")
        if not s:
            continue
        # Thousand/decimal handling for Vietnamese money.
        if s.count(",") and s.count("."):
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        elif s.count(".") > 1:
            s = s.replace(".", "")
        elif s.count(",") > 1:
            s = s.replace(",", "")
        elif "," in s and len(s.split(",")[-1]) in {3, 6, 9}:
            s = s.replace(",", "")
        elif "." in s and len(s.split(".")[-1]) in {3, 6, 9}:
            s = s.replace(".", "")
        elif "," in s:
            s = s.replace(",", ".")
        try:
            value = float(s)
        except Exception:
            continue
        u = norm(unit)
        if u in {"ty", "ti", "ti dong", "tỷ"}:
            value *= 1_000_000_000
        elif u in {"trieu", "tr", "m", "triệu"}:
            value *= 1_000_000
        elif u in {"nghin", "k", "nghìn"}:
            value *= 1_000
        return value
    return None


def parse_percent(text: Any, default: Optional[float] = None) -> Optional[float]:
    m = re.search(r"(\d+(?:[\.,]\d+)?)\s*%", str(text or ""))
    if not m:
        return default
    return float(m.group(1).replace(",", ".")) / 100


@dataclass(frozen=True)
class AccountingRule:
    rule_id: str
    category: str
    transaction_type: str
    keywords: Tuple[str, ...]
    debit_account: str
    credit_account: str
    confidence: float = 0.78
    required_docs: Tuple[str, ...] = ()
    risk_flags: Tuple[str, ...] = ()
    missing_fields: Tuple[str, ...] = ()
    tax_notes: Tuple[str, ...] = ()
    alternative_debit_accounts: Tuple[str, ...] = ()
    alternative_credit_accounts: Tuple[str, ...] = ()
    department_hint: str = "general"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["debit_name"] = ACCOUNT_NAMES.get(self.debit_account, "")
        d["credit_name"] = ACCOUNT_NAMES.get(self.credit_account, "")
        return d


COMMON_DOCS = (
    "Hóa đơn/chứng từ hợp lệ nếu ghi nhận chi phí/thuế",
    "Hợp đồng/đề nghị thanh toán/phiếu nhập-xuất nếu có",
    "Chứng từ thanh toán: ủy nhiệm chi, sao kê ngân hàng hoặc phiếu thu/chi",
)


RULES: List[AccountingRule] = [
    # Revenue / sales
    AccountingRule("SALES_001", "Bán hàng thu tiền ngay", "income", ("ban hang", "ban san pham", "xuat hoa don ban hang", "thu tien ban hang"), "111", "511", 0.88, COMMON_DOCS, ("Cần tách VAT đầu ra nếu hóa đơn có thuế suất."), ("customer", "vat_rate"), ("Doanh thu thường ghi Có 511; VAT đầu ra ghi Có 3331."), alternative_debit_accounts=("112", "131")),
    AccountingRule("SALES_002", "Bán hàng chưa thu tiền", "income", ("ban chiu", "khach hang no", "cong no khach hang", "xuat hoa don chua thu tien"), "131", "511", 0.9, COMMON_DOCS, ("Cần theo dõi tuổi nợ và đối chiếu công nợ."), ("customer", "vat_rate"), ("Nếu có VAT, ghi Nợ 131 tổng thanh toán, Có 511 giá chưa thuế, Có 3331 VAT."), alternative_debit_accounts=("111", "112")),
    AccountingRule("SALES_003", "Khách hàng thanh toán công nợ", "income", ("khach thanh toan", "thu cong no", "khach hang chuyen tien", "thu tien khach no"), "112", "131", 0.91, ("Sao kê/phiếu thu", "Biên bản đối chiếu công nợ nếu cần"), ("Cần đối chiếu đúng khách hàng và hóa đơn được thanh toán."), ("customer",), (), alternative_debit_accounts=("111",)),
    AccountingRule("SALES_004", "Hàng bán bị trả lại/giảm trừ doanh thu", "expense", ("hang ban bi tra lai", "khach tra hang", "giam gia hang ban", "chiet khau thuong mai", "hoan tien khach"), "521", "131", 0.86, ("Biên bản trả hàng/điều chỉnh", "Hóa đơn điều chỉnh/thay thế nếu áp dụng"), ("Cần xử lý VAT điều chỉnh và nhập lại hàng nếu hàng quay về kho."), ("invoice", "customer", "vat_rate"), ("Giảm trừ doanh thu thường dùng 521; phần tiền hoàn/giảm công nợ tùy tình huống."), alternative_credit_accounts=("111", "112")),
    AccountingRule("SALES_005", "Giá vốn hàng bán", "expense", ("gia von", "xuat kho ban hang", "ket chuyen gia von", "cogs"), "632", "156", 0.87, ("Phiếu xuất kho", "Bảng tính giá vốn/FIFO/bình quân"), ("Cần nhất quán phương pháp tính giá xuất kho."), ("inventory_method",), (), alternative_credit_accounts=("155", "154")),

    # Purchases / vendors
    AccountingRule("PUR_001", "Mua hàng nhập kho trả tiền ngay", "expense", ("mua hang", "nhap kho", "mua hang hoa", "mua vat tu", "mua nguyen vat lieu"), "156", "112", 0.86, COMMON_DOCS, ("Nếu có VAT đầu vào đủ điều kiện, tách Nợ 1331."), ("supplier", "vat_rate", "payment_method"), ("Hàng hóa thường Nợ 156; nguyên vật liệu có thể Nợ 152."), alternative_debit_accounts=("152", "153", "611"), alternative_credit_accounts=("111", "331")),
    AccountingRule("PUR_002", "Mua hàng chưa thanh toán", "expense", ("mua chiu", "nhap hang chua thanh toan", "cong no nha cung cap", "mua hang no nha cung cap"), "156", "331", 0.89, COMMON_DOCS, ("Cần đối chiếu công nợ nhà cung cấp."), ("supplier", "vat_rate"), (), alternative_debit_accounts=("152", "153", "611")),
    AccountingRule("PUR_003", "Thanh toán nhà cung cấp", "expense", ("tra nha cung cap", "thanh toan cong no", "thanh toan ncc", "chuyen tien nha cung cap"), "331", "112", 0.92, ("Ủy nhiệm chi/sao kê", "Đối chiếu công nợ/hóa đơn thanh toán"), ("Cần đối chiếu đúng hóa đơn và công nợ."), ("supplier",), (), alternative_credit_accounts=("111",)),
    AccountingRule("PUR_004", "Ứng trước cho nhà cung cấp", "expense", ("ung truoc cho nha cung cap", "tam ung nha cung cap", "dat coc nha cung cap", "coc tien hang"), "331", "112", 0.86, ("Hợp đồng/đơn hàng", "Chứng từ chuyển tiền"), ("Theo dõi khoản ứng trước để bù trừ khi nhận hàng/hóa đơn."), ("supplier", "contract"), (), alternative_credit_accounts=("111",)),
    AccountingRule("PUR_005", "Nhà cung cấp hoàn tiền", "income", ("nha cung cap hoan tien", "refund nha cung cap", "duoc hoan tien mua hang"), "112", "331", 0.82, ("Biên bản hoàn tiền", "Sao kê"), ("Cần xác định hoàn tiền do giảm giá, trả hàng hay thanh toán thừa."), ("supplier", "reason"), (), alternative_debit_accounts=("111",)),

    # Cash, bank, internal transfers
    AccountingRule("CASH_001", "Rút tiền gửi ngân hàng nhập quỹ", "transfer", ("rut tien ngan hang", "rut tien ve quy", "rut tien mat tu ngan hang"), "111", "112", 0.9, ("Phiếu thu", "Sao kê/giấy báo nợ"), (), (), ()),
    AccountingRule("CASH_002", "Nộp tiền mặt vào ngân hàng", "transfer", ("nop tien vao ngan hang", "gui tien mat vao ngan hang", "nop tien mat"), "112", "111", 0.9, ("Phiếu chi", "Giấy nộp tiền/sao kê"), (), (), ()),
    AccountingRule("CASH_003", "Phí ngân hàng", "expense", ("phi ngan hang", "phi chuyen khoan", "bank fee", "phi duy tri tai khoan"), "642", "112", 0.88, ("Sao kê ngân hàng", "Chứng từ phí"), ("Có thể hạch toán 635 nếu là chi phí tài chính liên quan vay vốn."), (), (), alternative_debit_accounts=("635",)),
    AccountingRule("CASH_004", "Lãi tiền gửi ngân hàng", "income", ("lai tien gui", "lai ngan hang", "nhan lai tien gui"), "112", "515", 0.88, ("Sao kê/giấy báo có"), (), (), ()),

    # Expenses
    AccountingRule("EXP_001", "Chi phí điện nước", "expense", ("tien dien", "evn", "tien nuoc", "dien nuoc"), "642", "112", 0.88, COMMON_DOCS, ("Nếu dùng cho bán hàng/sản xuất có thể phân bổ 641/627."), ("department", "invoice"), (), alternative_debit_accounts=("641", "627"), alternative_credit_accounts=("111", "331")),
    AccountingRule("EXP_002", "Chi phí thuê văn phòng/nhà xưởng", "expense", ("thue van phong", "tien thue nha", "thue mat bang", "thue nha xuong"), "642", "112", 0.87, ("Hợp đồng thuê", "Hóa đơn/chứng từ", "Chứng từ thanh toán"), ("Nếu trả trước nhiều kỳ nên ghi Nợ 242 rồi phân bổ."), ("contract", "period", "invoice"), (), alternative_debit_accounts=("242", "641", "627"), alternative_credit_accounts=("111", "331")),
    AccountingRule("EXP_003", "Chi phí marketing/quảng cáo", "expense", ("facebook ads", "google ads", "tiktok ads", "quang cao", "marketing", "booking kols"), "641", "112", 0.87, ("Hóa đơn/chứng từ", "Hợp đồng/đơn đặt hàng", "Bằng chứng chạy quảng cáo"), ("Kiểm tra nhà cung cấp nước ngoài, thuế nhà thầu nếu có."), ("supplier", "invoice", "campaign"), (), alternative_debit_accounts=("642",), alternative_credit_accounts=("111", "331")),
    AccountingRule("EXP_004", "Chi phí tiếp khách/hội nghị", "expense", ("tiep khach", "an uong tiep khach", "hoi nghi", "khach san tiep khach"), "642", "112", 0.8, ("Hóa đơn", "Đề nghị thanh toán", "Danh sách/nội dung tiếp khách nếu nội bộ yêu cầu"), ("Rủi ro chi phí không được trừ nếu thiếu chứng từ hoặc không phục vụ hoạt động kinh doanh."), ("business_purpose", "invoice"), (), alternative_credit_accounts=("111", "331")),
    AccountingRule("EXP_005", "Công tác phí", "expense", ("cong tac phi", "di cong tac", "ve may bay", "khach san cong tac", "taxi cong tac"), "642", "112", 0.84, ("Quyết định/đề nghị công tác", "Hóa đơn/vé/bảng kê", "Chứng từ thanh toán"), ("Cần theo quy chế công tác phí nội bộ."), ("employee", "business_purpose"), (), alternative_debit_accounts=("641", "627"), alternative_credit_accounts=("111", "141")),
    AccountingRule("EXP_006", "Chi phí văn phòng phẩm", "expense", ("van phong pham", "muc in", "giay in", "do dung van phong"), "642", "111", 0.84, COMMON_DOCS, (), ("invoice",), (), alternative_credit_accounts=("112", "331")),
    AccountingRule("EXP_007", "Chi phí sửa chữa/bảo trì", "expense", ("sua chua", "bao tri", "bao duong", "sua may", "sua xe", "sua van phong"), "642", "112", 0.82, ("Hợp đồng/báo giá", "Biên bản nghiệm thu", "Hóa đơn"), ("Nếu làm tăng năng lực/thời gian sử dụng TSCĐ có thể phải ghi tăng nguyên giá."), ("asset", "invoice"), (), alternative_debit_accounts=("241", "627", "641"), alternative_credit_accounts=("111", "331")),
    AccountingRule("EXP_008", "Chi phí vận chuyển", "expense", ("van chuyen", "cuoc van chuyen", "phi ship", "logistics", "giao hang"), "641", "112", 0.82, COMMON_DOCS, ("Nếu liên quan mua hàng có thể cộng vào giá nhập kho."), ("purpose", "invoice"), (), alternative_debit_accounts=("156", "152", "642"), alternative_credit_accounts=("111", "331")),

    # Payroll / social insurance
    AccountingRule("PAY_001", "Ghi nhận lương phải trả", "expense", ("tinh luong", "trich luong", "ghi nhan luong", "luong phai tra", "bang luong"), "642", "334", 0.9, ("Bảng lương", "Hợp đồng lao động", "Bảng chấm công"), ("Cần tách bộ phận 622/627/641/642 nếu có."), ("department", "payroll_period"), (), alternative_debit_accounts=("622", "627", "641")),
    AccountingRule("PAY_002", "Thanh toán lương", "expense", ("tra luong", "thanh toan luong", "chuyen khoan luong", "chi luong"), "334", "112", 0.92, ("Bảng lương đã duyệt", "Sao kê/ủy nhiệm chi"), (), ("employee", "payroll_period"), (), alternative_credit_accounts=("111",)),
    AccountingRule("PAY_003", "Trích bảo hiểm phần doanh nghiệp", "expense", ("trich bhxh", "bao hiem xa hoi", "bhyt", "bhtn", "kinh phi cong doan"), "642", "338", 0.86, ("Bảng tính BHXH/BHYT/BHTN/KPCĐ", "Bảng lương"), ("Cần tách phần NLĐ khấu trừ vào 334 và phần DN tính vào chi phí."), ("rates", "payroll_period"), (), alternative_debit_accounts=("622", "627", "641")),
    AccountingRule("PAY_004", "Khấu trừ thuế TNCN", "liability", ("thue tncn", "thue thu nhap ca nhan", "khau tru thue ca nhan"), "334", "3335", 0.86, ("Bảng tính thuế TNCN", "Bảng lương"), ("Cần kiểm tra giảm trừ gia cảnh, cư trú và biểu thuế áp dụng."), ("employee", "payroll_period"), ()),
    AccountingRule("PAY_005", "Nộp bảo hiểm/thuế TNCN", "expense", ("nop bhxh", "nop bao hiem", "nop thue tncn", "thanh toan bao hiem"), "338", "112", 0.86, ("Giấy nộp tiền/sao kê", "Thông báo cơ quan BHXH/thuế"), ("Nếu nộp TNCN thì dùng Nợ 3335/Có 112."), ("payment_type",), (), alternative_debit_accounts=("3335",)),

    # Advance / employee
    AccountingRule("ADV_001", "Tạm ứng nhân viên", "asset", ("tam ung nhan vien", "ung tien cho nhan vien", "ung cong tac phi", "tam ung cong tac"), "141", "112", 0.88, ("Đề nghị tạm ứng", "Phiếu chi/ủy nhiệm chi"), ("Cần quyết toán/hoàn ứng đúng hạn."), ("employee", "purpose"), (), alternative_credit_accounts=("111",)),
    AccountingRule("ADV_002", "Hoàn ứng/quyết toán tạm ứng", "expense", ("hoan ung", "quyet toan tam ung", "nhan vien hoan ung", "thanh toan bang tam ung"), "642", "141", 0.84, ("Bảng quyết toán tạm ứng", "Hóa đơn/chứng từ liên quan"), ("Nếu nhân viên nộp lại tiền thừa: Nợ 111/112, Có 141."), ("employee", "invoice", "purpose"), (), alternative_debit_accounts=("111", "112", "641", "627")),

    # Assets / tools / prepaid
    AccountingRule("ASSET_001", "Mua tài sản cố định", "asset", ("mua tai san co dinh", "mua may moc", "mua oto", "mua xe", "mua laptop gia tri lon", "mua thiet bi gia tri lon"), "211", "112", 0.86, ("Hóa đơn", "Hợp đồng", "Biên bản bàn giao/nghiệm thu", "Hồ sơ tài sản"), ("Cần xác định đủ điều kiện ghi nhận TSCĐ và thời gian khấu hao."), ("asset_name", "useful_life", "department", "vat_rate"), ("VAT đầu vào của TSCĐ đủ điều kiện thường ghi Nợ 1332."), alternative_debit_accounts=("213", "241"), alternative_credit_accounts=("331", "111")),
    AccountingRule("ASSET_002", "Trích khấu hao TSCĐ", "expense", ("khau hao", "trich khau hao", "hao mon tai san"), "642", "214", 0.88, ("Bảng tính khấu hao", "Danh mục TSCĐ"), ("Cần phân bổ theo bộ phận sử dụng 627/641/642."), ("asset", "months", "department"), (), alternative_debit_accounts=("627", "641")),
    AccountingRule("ASSET_003", "Mua công cụ dụng cụ", "asset", ("mua cong cu dung cu", "mua ccdc", "mua thiet bi nho", "mua laptop", "mua ban ghe"), "153", "112", 0.82, COMMON_DOCS, ("Nếu dùng ngay/phân bổ nhiều kỳ có thể qua 242 hoặc chi phí trực tiếp."), ("asset_name", "allocation_months", "department", "vat_rate"), (), alternative_debit_accounts=("242", "642"), alternative_credit_accounts=("111", "331")),
    AccountingRule("ASSET_004", "Phân bổ công cụ dụng cụ/chi phí trả trước", "expense", ("phan bo ccdc", "phan bo chi phi tra truoc", "phan bo 242", "phan bo cong cu"), "642", "242", 0.88, ("Bảng phân bổ", "Hồ sơ CCDC/chi phí trả trước"), ("Cần nhất quán thời gian phân bổ."), ("allocation_months", "department"), (), alternative_debit_accounts=("627", "641")),
    AccountingRule("ASSET_005", "Thanh lý/nhượng bán tài sản", "mixed", ("thanh ly tai san", "ban tai san co dinh", "nhuong ban tai san"), "811", "211", 0.78, ("Quyết định thanh lý", "Biên bản thanh lý", "Hóa đơn bán tài sản", "Bảng khấu hao"), ("Nghiệp vụ nhiều bút toán: xóa nguyên giá, xóa hao mòn, ghi thu nhập, VAT nếu có."), ("asset", "accumulated_depreciation", "selling_price", "vat_rate"), ()),

    # Loans, capital, finance
    AccountingRule("FIN_001", "Nhận tiền vay", "liability", ("vay ngan hang", "nhan tien vay", "giai ngan khoan vay", "vay von"), "112", "341", 0.9, ("Hợp đồng tín dụng", "Sao kê/giấy báo có"), ("Theo dõi gốc vay, lãi vay và kỳ hạn."), ("loan_contract",), ()),
    AccountingRule("FIN_002", "Trả gốc vay", "expense", ("tra goc vay", "tra no vay", "thanh toan goc vay"), "341", "112", 0.9, ("Lịch trả nợ", "Sao kê/ủy nhiệm chi"), (), ("loan_contract",), ()),
    AccountingRule("FIN_003", "Chi phí lãi vay", "expense", ("lai vay", "tra lai vay", "chi phi lai vay"), "635", "112", 0.88, ("Bảng tính lãi", "Hợp đồng vay", "Chứng từ thanh toán"), ("Kiểm tra điều kiện khống chế/được trừ khi quyết toán thuế nếu áp dụng."), ("loan_contract", "interest_period"), (), alternative_credit_accounts=("335", "341")),
    AccountingRule("FIN_004", "Góp vốn chủ sở hữu", "equity", ("gop von", "chu so huu gop von", "co dong gop von", "nhan von gop"), "112", "411", 0.9, ("Hồ sơ góp vốn", "Sao kê/phiếu thu"), ("Cần theo dõi đúng thành viên/cổ đông và thời hạn góp vốn."), ("owner",), (), alternative_debit_accounts=("111",)),
    AccountingRule("FIN_005", "Rút/hoàn trả vốn góp", "equity", ("rut von", "hoan tra von gop", "tra von cho chu so huu"), "411", "112", 0.78, ("Nghị quyết/quyết định", "Hồ sơ pháp lý liên quan", "Chứng từ thanh toán"), ("Rủi ro pháp lý cao, cần kiểm tra điều kiện giảm vốn/hoàn vốn."), ("legal_approval",), (), alternative_credit_accounts=("111",)),
    AccountingRule("FIN_006", "Cổ tức/lợi nhuận phải trả", "equity", ("chia co tuc", "chia loi nhuan", "loi nhuan phai tra"), "421", "338", 0.78, ("Nghị quyết phân phối lợi nhuận", "Danh sách cổ đông/thành viên"), ("Cần kiểm tra thuế TNCN/khấu trừ nếu trả cho cá nhân."), ("approval", "recipient"), ()),

    # Taxes
    AccountingRule("TAX_001", "Nộp thuế GTGT", "expense", ("nop thue gtgt", "nop vat", "thanh toan thue gtgt"), "3331", "112", 0.9, ("Giấy nộp tiền", "Tờ khai VAT"), (), ("tax_period",), ()),
    AccountingRule("TAX_002", "Thuế TNDN tạm tính/phải nộp", "expense", ("thue tndn", "thue thu nhap doanh nghiep", "tndn tam tinh"), "821", "3334", 0.86, ("Tờ khai/tính thuế TNDN", "Bảng xác định thu nhập chịu thuế"), ("Cần phân biệt lợi nhuận kế toán và thu nhập tính thuế."), ("taxable_income", "tax_rate"), ()),
    AccountingRule("TAX_003", "Nộp thuế TNDN", "expense", ("nop thue tndn", "thanh toan thue tndn"), "3334", "112", 0.9, ("Giấy nộp tiền", "Tờ khai/quyết toán"), (), ("tax_period",), ()),
    AccountingRule("TAX_004", "Thuế môn bài/lệ phí môn bài", "expense", ("le phi mon bai", "thue mon bai", "nop mon bai"), "642", "3338", 0.82, ("Tờ khai/thông báo", "Giấy nộp tiền"), (), ("tax_period",), (), alternative_credit_accounts=("112",)),

    # Inventory / production
    AccountingRule("INV_001", "Xuất nguyên vật liệu sản xuất", "expense", ("xuat nguyen vat lieu", "xuat vat tu san xuat", "dua vao san xuat"), "621", "152", 0.86, ("Phiếu xuất kho", "Lệnh sản xuất/định mức"), ("Cần theo dõi định mức và sản phẩm/công trình."), ("product", "quantity"), ()),
    AccountingRule("INV_002", "Nhập kho thành phẩm", "asset", ("nhap kho thanh pham", "hoan thanh san xuat", "ket chuyen gia thanh"), "155", "154", 0.84, ("Phiếu nhập kho", "Bảng tính giá thành"), ("Cần tính đủ 621/622/627 vào giá thành."), ("product", "costing_period"), ()),
    AccountingRule("INV_003", "Kiểm kê thiếu/hư hỏng hàng tồn kho", "expense", ("thieu kho", "hao hut", "hang hong", "mat hang", "kiem ke thieu"), "632", "156", 0.78, ("Biên bản kiểm kê", "Quyết định xử lý"), ("Cần xác định trách nhiệm bồi thường hoặc chi phí khác."), ("reason", "approval"), (), alternative_debit_accounts=("138", "811"), alternative_credit_accounts=("152", "155")),
    AccountingRule("INV_004", "Kiểm kê thừa hàng tồn kho", "income", ("thua kho", "kiem ke thua", "phat hien thua hang"), "156", "711", 0.78, ("Biên bản kiểm kê", "Quyết định xử lý"), ("Cần xác định nguyên nhân và quyền sở hữu."), ("reason",), (), alternative_debit_accounts=("152", "155")),

    # Provisions / accruals / period close
    AccountingRule("CLOSE_001", "Trích trước chi phí", "liability", ("trich truoc chi phi", "chi phi phai tra", "accrual"), "642", "335", 0.82, ("Căn cứ ước tính", "Hợp đồng/nghĩa vụ phát sinh"), ("Cần hoàn nhập/điều chỉnh khi có hóa đơn thực tế."), ("basis", "period"), (), alternative_debit_accounts=("641", "627", "635")),
    AccountingRule("CLOSE_002", "Kết chuyển doanh thu", "closing", ("ket chuyen doanh thu", "ket chuyen 511", "cuoi ky doanh thu"), "511", "911", 0.9, ("Bảng tổng hợp doanh thu"), (), ("period",), ()),
    AccountingRule("CLOSE_003", "Kết chuyển chi phí", "closing", ("ket chuyen chi phi", "ket chuyen 632", "ket chuyen 641", "ket chuyen 642"), "911", "632", 0.86, ("Bảng tổng hợp chi phí"), ("Có nhiều bút toán cho 632/635/641/642/811/821."), ("period",), (), alternative_credit_accounts=("635", "641", "642", "811", "821")),
    AccountingRule("CLOSE_004", "Kết chuyển lãi/lỗ", "closing", ("ket chuyen lai lo", "xac dinh ket qua kinh doanh", "ket chuyen 911"), "911", "421", 0.84, ("Bảng xác định kết quả kinh doanh"), ("Nếu lỗ thì bút toán đảo chiều: Nợ 421/Có 911."), ("period", "profit_or_loss"), ()),
]


FIELD_QUESTIONS: Dict[str, str] = {
    "customer": "Khách hàng nào và hóa đơn/công nợ nào liên quan?",
    "supplier": "Nhà cung cấp nào và hóa đơn/công nợ nào liên quan?",
    "vat_rate": "Có VAT không, thuế suất 0%, 5%, 8% hay 10%; số tiền bạn nhập là đã gồm VAT hay chưa?",
    "payment_method": "Thanh toán bằng tiền mặt, chuyển khoản hay ghi công nợ?",
    "invoice": "Có hóa đơn/chứng từ hợp lệ không?",
    "contract": "Có hợp đồng/đơn đặt hàng/biên bản nghiệm thu không?",
    "department": "Chi phí dùng cho bộ phận nào: sản xuất, bán hàng hay quản lý?",
    "business_purpose": "Mục đích kinh doanh của khoản chi là gì?",
    "employee": "Nhân viên nào và thuộc kỳ/bộ phận nào?",
    "asset_name": "Tên tài sản/công cụ và ngày đưa vào sử dụng là gì?",
    "useful_life": "Thời gian khấu hao/phân bổ dự kiến bao nhiêu tháng?",
    "allocation_months": "Phân bổ trong bao nhiêu tháng?",
    "inventory_method": "Công ty dùng FIFO, bình quân gia quyền hay phương pháp khác?",
    "loan_contract": "Khoản vay theo hợp đồng nào, kỳ hạn và lãi suất bao nhiêu?",
    "tax_period": "Kỳ thuế/kỳ kế toán nào?",
    "period": "Kỳ kế toán cần xử lý là tháng/quý/năm nào?",
    "reason": "Lý do nghiệp vụ phát sinh là gì?",
}


PAYMENT_HINTS: List[Tuple[str, str]] = [
    ("tien mat", "111"), ("cash", "111"), ("phiếu chi", "111"), ("phieu chi", "111"),
    ("chuyen khoan", "112"), ("ngan hang", "112"), ("sao ke", "112"), ("uy nhiem chi", "112"),
    ("chua thanh toan", "331"), ("cong no nha cung cap", "331"), ("mua chiu", "331"),
    ("khach no", "131"), ("ban chiu", "131"), ("chua thu tien", "131"),
]


def infer_payment_account(text: str, default: str) -> str:
    q = norm(text)
    for keyword, account in PAYMENT_HINTS:
        if norm(keyword) in q:
            return account
    return default


def infer_debit_by_department(text: str, fallback: str) -> str:
    q = norm(text)
    if any(k in q for k in ["san xuat", "nha xuong", "phan xuong", "cong trinh"]):
        return "627" if fallback in {"641", "642"} else fallback
    if any(k in q for k in ["ban hang", "sale", "kinh doanh", "marketing", "cua hang"]):
        return "641" if fallback in {"627", "642"} else fallback
    if any(k in q for k in ["quan ly", "van phong", "hanh chinh", "admin"]):
        return "642" if fallback in {"627", "641"} else fallback
    return fallback


def find_best_rule(description: str) -> Dict[str, Any]:
    q = norm(description)
    scored: List[Tuple[float, AccountingRule, List[str]]] = []
    for rule in RULES:
        hits: List[str] = []
        score = 0.0
        for kw in rule.keywords:
            nkw = norm(kw)
            if not nkw:
                continue
            if nkw in q:
                hits.append(kw)
                score += 1.0 + min(len(nkw) / 35, 0.65)
            else:
                tokens = [t for t in nkw.split() if len(t) >= 3]
                if tokens:
                    matched = sum(1 for t in tokens if t in q)
                    if matched >= max(1, math.ceil(len(tokens) * 0.7)):
                        hits.append(kw)
                        score += matched / len(tokens) * 0.55
        if score > 0:
            scored.append((score, rule, hits))
    if not scored:
        return {
            "matched": False,
            "rule": None,
            "score": 0,
            "matched_keywords": [],
            "confidence": 0.35,
            "category": "Chưa phân loại",
        }
    scored.sort(key=lambda x: (x[0], x[1].confidence), reverse=True)
    score, rule, hits = scored[0]
    confidence = min(0.97, max(0.45, rule.confidence + min(score, 3.0) * 0.035))
    return {
        "matched": True,
        "rule": rule.to_dict(),
        "score": round(score, 3),
        "matched_keywords": hits,
        "confidence": round(confidence, 3),
        "category": rule.category,
    }


def split_vat_amount(amount: float, vat_rate: Optional[float], amount_includes_vat: bool = True) -> Dict[str, float]:
    rate = vat_rate if vat_rate is not None else 0.0
    if rate <= 0:
        return {"net_amount": float(amount), "vat_amount": 0.0, "gross_amount": float(amount), "vat_rate": rate}
    if amount_includes_vat:
        net = float(amount) / (1 + rate)
        vat = float(amount) - net
        gross = float(amount)
    else:
        net = float(amount)
        vat = net * rate
        gross = net + vat
    return {"net_amount": round(net, 2), "vat_amount": round(vat, 2), "gross_amount": round(gross, 2), "vat_rate": rate}


def build_journal_lines(
    description: str,
    amount: Optional[float],
    rule_dict: Optional[Dict[str, Any]],
    vat_rate: Optional[float] = None,
    amount_includes_vat: bool = True,
) -> List[Dict[str, Any]]:
    if amount is None or amount <= 0 or not rule_dict:
        return []
    debit = infer_debit_by_department(description, str(rule_dict.get("debit_account") or "642"))
    credit = infer_payment_account(description, str(rule_dict.get("credit_account") or "112"))
    category = str(rule_dict.get("category") or "")
    transaction_type = str(rule_dict.get("transaction_type") or "")
    vat = split_vat_amount(amount, vat_rate, amount_includes_vat)
    net, tax, gross = vat["net_amount"], vat["vat_amount"], vat["gross_amount"]

    # Sales/revenue: debit cash/bank/receivable total; credit revenue + output VAT.
    if credit == "511" or transaction_type == "income" and rule_dict.get("credit_account") in {"511", "515", "711"}:
        debit_account = infer_payment_account(description, str(rule_dict.get("debit_account") or "112"))
        lines = [{"side": "debit", "account_code": debit_account, "account_name": ACCOUNT_NAMES.get(debit_account, ""), "amount": gross, "note": "Thu tiền/ghi nhận phải thu"}]
        if tax > 0 and str(rule_dict.get("credit_account")) == "511":
            lines.append({"side": "credit", "account_code": "511", "account_name": ACCOUNT_NAMES["511"], "amount": net, "note": "Doanh thu chưa VAT"})
            lines.append({"side": "credit", "account_code": "3331", "account_name": ACCOUNT_NAMES["3331"], "amount": tax, "note": "VAT đầu ra"})
        else:
            lines.append({"side": "credit", "account_code": str(rule_dict.get("credit_account") or "511"), "account_name": ACCOUNT_NAMES.get(str(rule_dict.get("credit_account") or "511"), ""), "amount": gross, "note": category})
        return lines

    # Purchases/expenses/assets with VAT input split.
    if tax > 0 and debit not in {"3331", "3334", "3335", "334", "338", "341", "411", "421", "911"}:
        vat_account = "1332" if debit in {"211", "213", "217", "241"} else "1331"
        return [
            {"side": "debit", "account_code": debit, "account_name": ACCOUNT_NAMES.get(debit, ""), "amount": net, "note": category},
            {"side": "debit", "account_code": vat_account, "account_name": ACCOUNT_NAMES.get(vat_account, ""), "amount": tax, "note": "VAT đầu vào"},
            {"side": "credit", "account_code": credit, "account_name": ACCOUNT_NAMES.get(credit, ""), "amount": gross, "note": "Thanh toán/ghi công nợ"},
        ]

    return [
        {"side": "debit", "account_code": debit, "account_name": ACCOUNT_NAMES.get(debit, ""), "amount": round(float(amount), 2), "note": category},
        {"side": "credit", "account_code": credit, "account_name": ACCOUNT_NAMES.get(credit, ""), "amount": round(float(amount), 2), "note": "Đối ứng"},
    ]


def journal_totals(lines: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    debit = sum(float(x.get("amount") or 0) for x in lines if x.get("side") == "debit")
    credit = sum(float(x.get("amount") or 0) for x in lines if x.get("side") == "credit")
    diff = round(debit - credit, 2)
    return {"debit_total": round(debit, 2), "credit_total": round(credit, 2), "difference": diff, "is_balanced": abs(diff) < 1}


def risk_review(description: str, amount: Optional[float], rule_dict: Optional[Dict[str, Any]], has_invoice: Optional[bool] = None) -> Dict[str, Any]:
    q = norm(description)
    risks: List[str] = []
    blocks: List[str] = []
    warnings: List[str] = []
    if rule_dict:
        risks.extend(rule_dict.get("risk_flags") or [])
    if amount is not None:
        if amount <= 0:
            blocks.append("Số tiền phải lớn hơn 0.")
        if amount >= 5_000_000 and any(k in q for k in ["tien mat", "cash", "phiếu chi", "phieu chi"]):
            warnings.append("Thanh toán tiền mặt từ 5 triệu đồng trở lên: cần kiểm tra điều kiện chứng từ thanh toán không dùng tiền mặt theo quy định hiện hành về VAT và thuế TNDN.")
        if amount >= 30_000_000 and any(k in q for k in ["laptop", "may tinh", "thiet bi", "may moc", "tai san"]):
            warnings.append("Giá trị lớn: cần xem xét ghi nhận TSCĐ hoặc CCDC/242 thay vì chi phí ngay.")
    if has_invoice is False and rule_dict and any(a in {rule_dict.get("debit_account"), rule_dict.get("credit_account")} for a in ["1331", "1332", "156", "152", "153", "211", "641", "642", "627"]):
        warnings.append("Chưa có hóa đơn/chứng từ: không nên tự động ghi nhận VAT/chi phí được trừ.")
    if any(k in q for k in ["tiep khach", "qua tang", "bien tang", "ung ho", "tu thien"]):
        warnings.append("Khoản chi nhạy cảm thuế: cần kiểm tra mục đích kinh doanh, hồ sơ chứng từ và chính sách nội bộ.")
    if any(k in q for k in ["nuoc ngoai", "foreign", "google", "facebook", "meta", "aws", "microsoft", "stripe"]):
        warnings.append("Nhà cung cấp nước ngoài: cần kiểm tra hóa đơn, thuế nhà thầu/khấu trừ nếu áp dụng.")
    if not rule_dict:
        warnings.append("Chưa tìm thấy rule phù hợp; cần kế toán chọn tài khoản trước khi ghi sổ.")
    severity = "ok"
    if blocks:
        severity = "block"
    elif warnings or risks:
        severity = "review"
    return {"severity": severity, "risks": risks, "warnings": warnings, "blocks": blocks}


def missing_questions(rule_dict: Optional[Dict[str, Any]], provided: Optional[Dict[str, Any]] = None) -> List[str]:
    provided = provided or {}
    if not rule_dict:
        return [
            "Bạn mô tả rõ nghiệp vụ phát sinh là mua/bán/thu/chi/tài sản/lương/thuế hay công nợ?",
            "Số tiền, phương thức thanh toán và chứng từ kèm theo là gì?",
        ]
    questions = []
    for field in rule_dict.get("missing_fields") or []:
        if provided.get(field) in (None, "", False):
            questions.append(FIELD_QUESTIONS.get(field, f"Cần bổ sung thông tin: {field}"))
    return questions[:8]


def analyze_transaction(
    description: str,
    amount: Optional[float] = None,
    vat_rate: Optional[float] = None,
    amount_includes_vat: bool = True,
    has_invoice: Optional[bool] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    amount = amount if amount is not None else parse_money(description)
    vat_rate = vat_rate if vat_rate is not None else parse_percent(description)
    if vat_rate is not None and vat_rate > 1:
        vat_rate = vat_rate / 100
    match = find_best_rule(description)
    rule = match.get("rule")
    lines = build_journal_lines(description, amount, rule, vat_rate=vat_rate, amount_includes_vat=amount_includes_vat)
    totals = journal_totals(lines)
    risk = risk_review(description, amount, rule, has_invoice=has_invoice)
    questions = missing_questions(rule, {**(extra or {}), "vat_rate": vat_rate, "invoice": has_invoice})
    confidence = float(match.get("confidence") or 0.35)
    if risk["severity"] == "review":
        confidence = max(0.25, confidence - 0.08)
    if risk["severity"] == "block":
        confidence = min(confidence, 0.35)
    decision = "auto_draft_allowed" if totals.get("is_balanced") and risk["severity"] == "ok" and confidence >= 0.82 else "review_required"
    if risk["severity"] == "block":
        decision = "blocked"
    return {
        "version": "v85_accounting_ai_full",
        "description": description,
        "amount": amount,
        "vat_rate": vat_rate,
        "amount_includes_vat": amount_includes_vat,
        "matched_rule": match,
        "category": match.get("category"),
        "confidence": round(confidence, 3),
        "journal_lines": lines,
        "journal_check": totals,
        "risk_review": risk,
        "missing_questions": questions,
        "required_documents": (rule or {}).get("required_docs", []) if isinstance(rule, dict) else [],
        "tax_notes": (rule or {}).get("tax_notes", []) if isinstance(rule, dict) else [],
        "decision": decision,
        "next_actions": _next_actions(decision, risk, questions),
    }


def _next_actions(decision: str, risk: Dict[str, Any], questions: List[str]) -> List[str]:
    if decision == "blocked":
        return ["Không tự động ghi sổ.", "Bổ sung/sửa dữ liệu đầu vào.", "Kế toán kiểm tra lại rule và chứng từ."]
    actions = []
    if questions:
        actions.append("Bổ sung các thông tin còn thiếu trước khi ghi sổ chính thức.")
    if risk.get("warnings") or risk.get("risks"):
        actions.append("Đưa vào review queue để kế toán xác nhận chứng từ/rủi ro thuế.")
    if decision == "auto_draft_allowed":
        actions.append("Có thể tạo bút toán nháp, chưa nên auto-post nếu chưa có xác nhận người dùng.")
    else:
        actions.append("Chỉ nên tạo bản nháp và chờ duyệt.")
    return actions


# -----------------------------
# Formula solvers
# -----------------------------

def calc_vat(amount: float, rate: float = 0.10, amount_includes_vat: bool = False) -> Dict[str, Any]:
    return split_vat_amount(float(amount), float(rate), amount_includes_vat)


def calc_straight_line_depreciation(cost: float, months: int, residual_value: float = 0.0) -> Dict[str, Any]:
    if months <= 0:
        raise ValueError("Số tháng khấu hao/phân bổ phải lớn hơn 0")
    depreciable = max(0.0, float(cost) - float(residual_value or 0))
    monthly = depreciable / months
    return {"cost": cost, "residual_value": residual_value, "months": months, "monthly_amount": round(monthly, 2), "yearly_amount": round(monthly * 12, 2)}


def calc_prepaid_allocation(total_cost: float, months: int, used_months: int = 1) -> Dict[str, Any]:
    base = calc_straight_line_depreciation(total_cost, months)
    allocated = base["monthly_amount"] * max(0, used_months)
    return {**base, "used_months": used_months, "allocated_amount": round(allocated, 2), "remaining_amount": round(max(0, total_cost - allocated), 2)}


def calc_weighted_average(begin_qty: float, begin_value: float, import_qty: float, import_value: float, export_qty: Optional[float] = None) -> Dict[str, Any]:
    qty = float(begin_qty) + float(import_qty)
    value = float(begin_value) + float(import_value)
    if qty <= 0:
        raise ValueError("Tổng số lượng phải lớn hơn 0")
    unit = value / qty
    result = {"total_qty": qty, "total_value": value, "unit_cost": round(unit, 2)}
    if export_qty is not None:
        result["export_qty"] = float(export_qty)
        result["export_value"] = round(float(export_qty) * unit, 2)
        result["ending_qty"] = round(qty - float(export_qty), 2)
        result["ending_value"] = round(value - result["export_value"], 2)
    return result


def calc_fifo(layers: List[Dict[str, float]], export_qty: float) -> Dict[str, Any]:
    remain = float(export_qty)
    cogs = 0.0
    consumed = []
    ending = []
    for layer in layers:
        qty = float(layer.get("qty") or layer.get("quantity") or 0)
        unit_cost = float(layer.get("unit_cost") or layer.get("price") or 0)
        take = min(qty, remain)
        if take > 0:
            consumed.append({"qty": take, "unit_cost": unit_cost, "value": round(take * unit_cost, 2)})
            cogs += take * unit_cost
            qty -= take
            remain -= take
        if qty > 0:
            ending.append({"qty": qty, "unit_cost": unit_cost, "value": round(qty * unit_cost, 2)})
    if remain > 0:
        raise ValueError("Không đủ số lượng tồn kho để xuất theo FIFO")
    return {"export_qty": export_qty, "cogs": round(cogs, 2), "consumed_layers": consumed, "ending_layers": ending, "ending_value": round(sum(x["value"] for x in ending), 2)}


def calc_profit(revenue: float, cogs: float = 0.0, selling_expenses: float = 0.0, admin_expenses: float = 0.0, financial_expenses: float = 0.0, other_income: float = 0.0, other_expenses: float = 0.0) -> Dict[str, Any]:
    gross_profit = float(revenue) - float(cogs)
    operating_profit = gross_profit - float(selling_expenses) - float(admin_expenses) - float(financial_expenses)
    profit_before_tax = operating_profit + float(other_income) - float(other_expenses)
    return {"revenue": revenue, "cogs": cogs, "gross_profit": round(gross_profit, 2), "operating_profit": round(operating_profit, 2), "profit_before_tax": round(profit_before_tax, 2)}


def calc_cit(taxable_income: float, tax_rate: float = 0.20, prepaid_tax: float = 0.0) -> Dict[str, Any]:
    payable = max(0.0, float(taxable_income) * float(tax_rate))
    remaining = payable - float(prepaid_tax or 0)
    return {"taxable_income": taxable_income, "tax_rate": tax_rate, "tax_payable": round(payable, 2), "prepaid_tax": prepaid_tax, "remaining_payable": round(remaining, 2)}


def calc_payroll_basic(gross_salary: float, employee_insurance_rate: float = 0.105, employer_insurance_rate: float = 0.215, pit: float = 0.0) -> Dict[str, Any]:
    employee_ins = float(gross_salary) * employee_insurance_rate
    employer_ins = float(gross_salary) * employer_insurance_rate
    net_salary = float(gross_salary) - employee_ins - float(pit or 0)
    return {"gross_salary": gross_salary, "employee_insurance": round(employee_ins, 2), "employer_insurance": round(employer_ins, 2), "pit": pit, "net_salary": round(net_salary, 2), "total_company_cost": round(float(gross_salary) + employer_ins, 2)}


def aging_bucket(days_overdue: int) -> str:
    if days_overdue <= 0:
        return "chưa quá hạn"
    if days_overdue <= 30:
        return "1-30 ngày"
    if days_overdue <= 60:
        return "31-60 ngày"
    if days_overdue <= 90:
        return "61-90 ngày"
    return ">90 ngày"


def solve_formula(payload: Dict[str, Any]) -> Dict[str, Any]:
    formula = norm(payload.get("formula") or payload.get("type") or "")
    if formula in {"vat", "gtgt"}:
        amount = float(payload.get("amount") or 0)
        rate = float(payload.get("rate") if payload.get("rate") is not None else 0.10)
        if rate > 1:
            rate /= 100
        return {"formula": "vat", "result": calc_vat(amount, rate, bool(payload.get("amount_includes_vat", False)))}
    if formula in {"khau hao", "depreciation", "straight_line"}:
        return {"formula": "depreciation", "result": calc_straight_line_depreciation(float(payload.get("cost") or payload.get("amount") or 0), int(payload.get("months") or 1), float(payload.get("residual_value") or 0))}
    if formula in {"phan bo", "prepaid", "allocation"}:
        return {"formula": "prepaid_allocation", "result": calc_prepaid_allocation(float(payload.get("total_cost") or payload.get("amount") or 0), int(payload.get("months") or 1), int(payload.get("used_months") or 1))}
    if formula in {"binh quan", "weighted_average", "average_cost"}:
        return {"formula": "weighted_average", "result": calc_weighted_average(float(payload.get("begin_qty") or 0), float(payload.get("begin_value") or 0), float(payload.get("import_qty") or 0), float(payload.get("import_value") or 0), payload.get("export_qty"))}
    if formula in {"fifo"}:
        return {"formula": "fifo", "result": calc_fifo(payload.get("layers") or [], float(payload.get("export_qty") or 0))}
    if formula in {"profit", "loi nhuan", "gross_profit", "net_profit"}:
        return {"formula": "profit", "result": calc_profit(float(payload.get("revenue") or 0), float(payload.get("cogs") or 0), float(payload.get("selling_expenses") or 0), float(payload.get("admin_expenses") or 0), float(payload.get("financial_expenses") or 0), float(payload.get("other_income") or 0), float(payload.get("other_expenses") or 0))}
    if formula in {"cit", "tndn"}:
        rate = float(payload.get("tax_rate") if payload.get("tax_rate") is not None else 0.20)
        if rate > 1:
            rate /= 100
        return {"formula": "cit", "result": calc_cit(float(payload.get("taxable_income") or payload.get("profit_before_tax") or 0), rate, float(payload.get("prepaid_tax") or 0))}
    if formula in {"payroll", "luong"}:
        return {"formula": "payroll", "result": calc_payroll_basic(float(payload.get("gross_salary") or payload.get("amount") or 0), float(payload.get("employee_insurance_rate") or 0.105), float(payload.get("employer_insurance_rate") or 0.215), float(payload.get("pit") or 0))}
    raise ValueError("Chưa hỗ trợ công thức này. Hãy dùng: vat, depreciation, prepaid, weighted_average, fifo, profit, cit, payroll.")


def solve_text_question(question: str) -> Dict[str, Any]:
    q = norm(question)
    amount = parse_money(question)
    pct = parse_percent(question)
    if any(k in q for k in ["vat", "gtgt", "thue gia tri gia tang"]):
        rate = pct if pct is not None else 0.10
        includes = any(k in q for k in ["da gom", "bao gom", "tong thanh toan", "sau thue"])
        if amount is None:
            return {"answer": "Chưa đủ dữ liệu để tính VAT. Cần số tiền và thuế suất nếu khác 10%.", "need_more": ["Số tiền trước/sau thuế?", "Thuế suất?"]}
        r = calc_vat(amount, rate, includes)
        return {"answer": f"Giá chưa thuế: {format_vnd(r['net_amount'])}; VAT {rate*100:.0f}%: {format_vnd(r['vat_amount'])}; tổng thanh toán: {format_vnd(r['gross_amount'])}.", "result": r}
    if any(k in q for k in ["khau hao", "phan bo"]):
        months_match = re.search(r"(\d+)\s*(thang|tháng)", question.lower())
        months = int(months_match.group(1)) if months_match else None
        if amount is None or not months:
            return {"answer": "Chưa đủ dữ liệu. Cần nguyên giá/tổng chi phí và số tháng khấu hao/phân bổ.", "need_more": ["Nguyên giá/tổng chi phí?", "Số tháng?"]}
        r = calc_straight_line_depreciation(amount, months)
        return {"answer": f"Mức phân bổ/khấu hao mỗi tháng: {format_vnd(r['monthly_amount'])}; mỗi năm: {format_vnd(r['yearly_amount'])}.", "result": r}
    if any(k in q for k in ["hach toan", "dinh khoan", "but toan", "mua", "ban", "thanh toan", "thu tien", "chi tien"]):
        return analyze_transaction(question, amount=amount, vat_rate=pct)
    return {"answer": "Câu hỏi chưa rõ là tính toán hay định khoản. AI đã chuyển sang tra cứu knowledge base nếu có.", "need_more": ["Bạn muốn tính công thức, định khoản hay hỏi quy định/quy trình?"]}


# -----------------------------
# Local knowledge/RAG helper
# -----------------------------

def _iter_knowledge_files() -> Iterable[Path]:
    if not KNOWLEDGE_DIR.exists():
        return []
    return KNOWLEDGE_DIR.rglob("*.md")


def _chunks_from_text(text: str, size: int = 900, overlap: int = 120) -> List[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    step = max(1, size - overlap)
    return [text[i:i + size].strip() for i in range(0, len(text), step) if text[i:i + size].strip()]


def search_local_knowledge(question: str, limit: int = 5) -> Dict[str, Any]:
    qn = norm(question)
    q_tokens = {t for t in re.findall(r"\w+", qn) if len(t) >= 3}
    rows: List[Dict[str, Any]] = []
    for path in _iter_knowledge_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for idx, chunk in enumerate(_chunks_from_text(text)):
            cn = norm(chunk)
            c_tokens = set(re.findall(r"\w+", cn))
            overlap = len(q_tokens & c_tokens)
            phrase_boost = 2 if qn[:60] and qn[:60] in cn else 0
            score = overlap + phrase_boost
            if score > 0:
                rows.append({"source": str(path.relative_to(ROOT_DIR)), "chunk_index": idx, "score": score, "content": chunk[:1200]})
    rows.sort(key=lambda x: x["score"], reverse=True)
    return {"items": rows[:limit], "total_matches": len(rows)}


def ask_accounting_ai(question: str, limit: int = 5) -> Dict[str, Any]:
    solved = solve_text_question(question)
    knowledge = search_local_knowledge(question, limit=limit)
    if knowledge["items"]:
        source_summary = "\n".join([f"- {x['source']}: {x['content'][:240]}..." for x in knowledge["items"][:3]])
    else:
        source_summary = "Không tìm thấy nguồn nội bộ phù hợp trong knowledge_base."
    answer_parts = []
    if solved.get("answer"):
        answer_parts.append(str(solved["answer"]))
    elif solved.get("journal_lines"):
        answer_parts.append("AI đã tạo bút toán nháp và checklist review.")
    answer_parts.append("Nguồn nội bộ tham khảo:\n" + source_summary)
    return {"version": "v85_accounting_ai_full", "question": question, "answer": "\n\n".join(answer_parts), "solver": solved, "knowledge_sources": knowledge["items"], "disclaimer": "Kết quả là gợi ý nháp; cần kế toán xác nhận theo chứng từ và quy định hiện hành trước khi ghi sổ/quyết toán."}


def rule_catalog() -> Dict[str, Any]:
    grouped: Dict[str, int] = {}
    for rule in RULES:
        grouped[rule.transaction_type] = grouped.get(rule.transaction_type, 0) + 1
    return {"version": "v85_accounting_ai_full", "total_rules": len(RULES), "by_transaction_type": grouped, "rules": [r.to_dict() for r in RULES]}


def capability_matrix() -> Dict[str, Any]:
    return {
        "version": "v85_accounting_ai_full",
        "coverage": {
            "transactions": ["mua/bán hàng", "công nợ phải thu/phải trả", "tiền mặt/ngân hàng", "chi phí", "lương/BHXH/TNCN", "TSCĐ/CCDC/242", "kho/giá vốn", "vay/lãi vay/vốn", "VAT/TNDN", "khóa sổ/kết chuyển"],
            "formulas": ["VAT xuôi/ngược", "khấu hao đường thẳng", "phân bổ trả trước", "FIFO", "bình quân gia quyền", "lợi nhuận", "TNDN", "lương cơ bản", "tuổi nợ"],
            "risk_gates": ["thiếu hóa đơn", "tiền mặt từ 5 triệu đồng trở lên", "chi phí nhạy cảm thuế", "nhà cung cấp nước ngoài", "giá trị tài sản lớn", "bút toán không cân"],
            "api": ["/ai/accounting/full-capabilities", "/ai/accounting/analyze-transaction", "/ai/accounting/suggest-entry", "/ai/accounting/solve", "/ai/accounting/ask", "/ai/accounting/check-journal", "/ai/accounting/rules"],
        },
        "manual_inputs_still_required": ["văn bản pháp luật/thông tư cập nhật", "dữ liệu kế toán thật", "chính sách nội bộ", "mapping tài khoản theo doanh nghiệp", "duyệt cuối bởi kế toán"],
    }
