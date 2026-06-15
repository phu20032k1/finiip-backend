from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import io
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple


MONEY_RE = re.compile(r"(?<!\d)(\d{1,3}(?:[\.,\s]\d{3})+(?:[\.,]\d{1,2})?|\d+(?:[\.,]\d{1,2})?)(?!\d)")
DATE_RE = re.compile(r"(?P<d>\d{1,2})[\-/\.](?P<m>\d{1,2})[\-/\.](?P<y>\d{2,4})|(?P<y2>\d{4})[\-/\.](?P<m2>\d{1,2})[\-/\.](?P<d2>\d{1,2})")
TAX_CODE_RE = re.compile(r"(?:mã\s*số\s*thuế|mst|tax\s*code|vat\s*code)\s*[:：]?\s*([0-9\-]{8,20})", re.IGNORECASE)
INVOICE_NO_RE = re.compile(r"(?:số\s*(?:hóa\s*đơn|hoá\s*đơn)|invoice\s*(?:no|number)|no\.?|số)\s*[:：#]?\s*([A-Z0-9\-_/]{3,30})", re.IGNORECASE)
VAT_RATE_RE = re.compile(r"(?:thuế\s*suất|vat\s*rate|vat)\s*[:：]?\s*(\d{1,2})(?:\s*%)", re.IGNORECASE)


def normalize_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[\t ]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_accents(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn").lower()


def parse_money(raw: str) -> Optional[float]:
    if not raw:
        return None
    cleaned = raw.strip().replace(" ", "")
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        parts = cleaned.split(",")
        if len(parts[-1]) in (1, 2):
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "." in cleaned:
        parts = cleaned.split(".")
        if len(parts[-1]) in (1, 2) and len(parts) == 2:
            pass
        else:
            cleaned = cleaned.replace(".", "")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    return float(value)


def parse_invoice_date(text: str) -> Optional[str]:
    match = DATE_RE.search(text)
    if not match:
        return None
    if match.group("y"):
        d, m, y = int(match.group("d")), int(match.group("m")), int(match.group("y"))
    else:
        d, m, y = int(match.group("d2")), int(match.group("m2")), int(match.group("y2"))
    if y < 100:
        y += 2000
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def _first_capture(patterns: List[str], text: str) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            value = match.group(1).strip(" :-–—\t")
            value = re.sub(r"\s{2,}", " ", value)
            if value:
                return value[:160]
    return None


def extract_party_names(text: str) -> Tuple[Optional[str], Optional[str]]:
    supplier = _first_capture([
        r"(?:đơn\s*vị\s*bán\s*hàng|người\s*bán|seller|supplier)\s*[:：]\s*(.+)",
        r"(?:tên\s*đơn\s*vị\s*bán|tên\s*người\s*bán)\s*[:：]\s*(.+)",
    ], text)
    buyer = _first_capture([
        r"(?:đơn\s*vị\s*mua\s*hàng|người\s*mua|buyer|customer)\s*[:：]\s*(.+)",
        r"(?:tên\s*đơn\s*vị\s*mua|tên\s*người\s*mua)\s*[:：]\s*(.+)",
    ], text)
    return supplier, buyer


def _money_near_labels(text: str, labels: List[str]) -> Optional[float]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    normalized_labels = [_strip_accents(label) for label in labels]
    candidates: List[float] = []
    for line in lines:
        nline = _strip_accents(line)
        if any(label in nline for label in normalized_labels):
            values = [parse_money(m.group(1)) for m in MONEY_RE.finditer(line)]
            values = [v for v in values if v is not None]
            if values:
                candidates.append(max(values))
    return max(candidates) if candidates else None


def extract_amounts(text: str) -> Dict[str, Optional[float]]:
    subtotal = _money_near_labels(text, [
        "cộng tiền hàng", "tiền hàng", "subtotal", "amount before tax", "chưa thuế", "trước thuế"
    ])
    vat_amount = _money_near_labels(text, [
        "tiền thuế gtgt", "thuế gtgt", "tiền vat", "vat amount", "tax amount"
    ])
    total = _money_near_labels(text, [
        "tổng cộng thanh toán", "tổng thanh toán", "tổng tiền thanh toán", "total payment", "grand total", "total amount", "thành tiền"
    ])
    vat_rate = None
    match = VAT_RATE_RE.search(text)
    if match:
        try:
            vat_rate = float(match.group(1))
        except ValueError:
            vat_rate = None
    if total is None:
        money_values = [parse_money(m.group(1)) for m in MONEY_RE.finditer(text)]
        money_values = [v for v in money_values if v is not None and v >= 1000]
        if money_values:
            total = max(money_values)
    if subtotal is None and total is not None and vat_amount is not None:
        subtotal = max(total - vat_amount, 0)
    if vat_amount is None and subtotal is not None and total is not None and total >= subtotal:
        diff = round(total - subtotal, 2)
        if diff > 0:
            vat_amount = diff
    if vat_rate is None and subtotal and vat_amount:
        vat_rate = round(vat_amount / subtotal * 100, 2)
    return {
        "subtotal": subtotal,
        "vat_rate": vat_rate,
        "vat_amount": vat_amount,
        "total_amount": total,
    }


def extract_invoice_number(text: str) -> Optional[str]:
    match = INVOICE_NO_RE.search(text)
    if match:
        value = match.group(1).strip()
        if not re.fullmatch(r"\d{1,2}", value):
            return value
    return None


def extract_tax_codes(text: str) -> List[str]:
    codes = []
    for match in TAX_CODE_RE.finditer(text):
        code = match.group(1).strip(" -")
        if code not in codes:
            codes.append(code)
    return codes


def guess_description(text: str, supplier_name: Optional[str]) -> str:
    ntext = _strip_accents(text)
    mapping = [
        ("facebook", "Chi phí quảng cáo Facebook"),
        ("google", "Chi phí quảng cáo Google"),
        ("tiktok", "Chi phí quảng cáo TikTok"),
        ("zalo", "Chi phí quảng cáo Zalo"),
        ("evn", "Thanh toán tiền điện"),
        ("dien", "Thanh toán tiền điện"),
        ("nuoc", "Thanh toán tiền nước"),
        ("internet", "Thanh toán tiền internet"),
        ("fpt", "Thanh toán tiền internet FPT"),
        ("van phong pham", "Mua văn phòng phẩm"),
        ("may tinh", "Mua máy tính văn phòng"),
        ("laptop", "Mua máy tính văn phòng"),
        ("hang hoa", "Mua hàng hóa nhập kho"),
        ("thue van phong", "Trả tiền thuê văn phòng"),
    ]
    for key, desc in mapping:
        if key in ntext:
            return desc
    if supplier_name:
        return f"Hóa đơn mua hàng từ {supplier_name}"
    return "Hóa đơn mua hàng"


def parse_invoice_text(text: str) -> Dict[str, Any]:
    text = normalize_text(text)
    supplier, buyer = extract_party_names(text)
    amounts = extract_amounts(text)
    tax_codes = extract_tax_codes(text)
    lower = _strip_accents(text)
    invoice_type = "purchase"
    if any(k in lower for k in ["hoa don ban ra", "ban hang cho khach", "sales invoice"]):
        invoice_type = "sales"
    confidence = 0.25
    confidence += 0.15 if extract_invoice_number(text) else 0
    confidence += 0.15 if parse_invoice_date(text) else 0
    confidence += 0.15 if supplier or buyer else 0
    confidence += 0.20 if amounts.get("total_amount") else 0
    confidence += 0.10 if amounts.get("vat_amount") is not None or amounts.get("vat_rate") is not None else 0
    return {
        "invoice_type": invoice_type,
        "invoice_number": extract_invoice_number(text),
        "invoice_date": parse_invoice_date(text),
        "supplier_name": supplier,
        "buyer_name": buyer,
        "tax_codes": tax_codes,
        "description": guess_description(text, supplier),
        **amounts,
        "currency": "VND",
        "confidence": round(min(confidence, 0.98), 2),
        "raw_text": text,
    }


def read_text_from_upload(filename: str, content: bytes) -> Dict[str, Any]:
    suffix = (filename or "").lower().rsplit(".", 1)[-1]
    if suffix in {"txt", "csv", "json", "xml"}:
        for enc in ("utf-8-sig", "utf-8", "cp1258", "latin-1"):
            try:
                return {"text": content.decode(enc), "method": f"text_decode_{enc}"}
            except UnicodeDecodeError:
                continue
        return {"text": content.decode("utf-8", errors="ignore"), "method": "text_decode_fallback"}
    if suffix == "pdf":
        try:
            from pypdf import PdfReader  # type: ignore
            reader = PdfReader(io.BytesIO(content))
            pages = [(page.extract_text() or "") for page in reader.pages]
            return {"text": "\n".join(pages), "method": "pypdf_text_layer"}
        except Exception as exc:
            return {"text": "", "method": "pdf_failed", "warning": f"Không đọc được PDF text-layer: {exc}"}
    if suffix in {"png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff"}:
        try:
            from PIL import Image  # type: ignore
            import pytesseract  # type: ignore
            image = Image.open(io.BytesIO(content))
            text = pytesseract.image_to_string(image, lang="vie+eng")
            return {"text": text, "method": "tesseract_ocr"}
        except Exception as exc:
            return {"text": "", "method": "image_ocr_failed", "warning": f"Chưa OCR được ảnh. Cài Tesseract OCR và gói ngôn ngữ vie/eng, hoặc upload PDF có text. Chi tiết: {exc}"}
    return {"text": content.decode("utf-8", errors="ignore"), "method": "unknown_decode_fallback"}
