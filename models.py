from datetime import date, datetime
from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, String, Text
from database import Base


class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    account_type = Column(String, nullable=False)


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    tax_code = Column(String, nullable=True)
    address = Column(Text, nullable=True)


class Supplier(Base, TimestampMixin):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    tax_code = Column(String, nullable=True)
    address = Column(Text, nullable=True)


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    transaction_date = Column(Date, default=date.today, nullable=False)
    description = Column(Text, nullable=False)
    amount = Column(Float, nullable=False)
    type = Column(String, nullable=False)  # income / expense / unknown
    category = Column(String, nullable=True)
    note = Column(Text, nullable=True)
    debit_account_code = Column(String, nullable=True)
    credit_account_code = Column(String, nullable=True)
    ai_confidence = Column(Float, nullable=True)
    status = Column(String, default="draft", nullable=False)  # draft / confirmed / cancelled
    confirmed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    accounting_period = Column(String, nullable=True, index=True)  # YYYY-MM


class JournalEntry(Base, TimestampMixin):
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, nullable=True, index=True)
    entry_date = Column(Date, default=date.today, nullable=False)
    description = Column(Text, nullable=False)
    debit_account_code = Column(String, nullable=False)
    debit_account_name = Column(String, nullable=False)
    credit_account_code = Column(String, nullable=False)
    credit_account_name = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    line_no = Column(Integer, default=1, nullable=False)
    status = Column(String, default="draft", nullable=False)  # draft / posted / cancelled
    accounting_period = Column(String, nullable=True, index=True)


class AccountingPeriod(Base, TimestampMixin):
    __tablename__ = "accounting_periods"

    id = Column(Integer, primary_key=True, index=True)
    period = Column(String, unique=True, index=True, nullable=False)  # YYYY-MM
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(String, default="open", nullable=False)  # open / closed
    closed_at = Column(DateTime, nullable=True)
    reopened_at = Column(DateTime, nullable=True)
    note = Column(Text, nullable=True)


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, nullable=False)
    entity_type = Column(String, nullable=False, index=True)
    entity_id = Column(Integer, nullable=True, index=True)
    old_value_json = Column(Text, nullable=True)
    new_value_json = Column(Text, nullable=True)
    note = Column(Text, nullable=True)
    actor = Column(String, default="system", nullable=False)


class SalesInvoice(Base, TimestampMixin):
    __tablename__ = "sales_invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_date = Column(Date, default=date.today, nullable=False)
    invoice_number = Column(String, nullable=False, index=True)
    customer_id = Column(Integer, nullable=True)
    customer_name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    subtotal = Column(Float, nullable=False)
    vat_rate = Column(Float, default=0, nullable=False)
    vat_amount = Column(Float, default=0, nullable=False)
    total_amount = Column(Float, nullable=False)
    status = Column(String, default="unpaid", nullable=False)


class PurchaseInvoice(Base, TimestampMixin):
    __tablename__ = "purchase_invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_date = Column(Date, default=date.today, nullable=False)
    invoice_number = Column(String, nullable=False, index=True)
    supplier_id = Column(Integer, nullable=True)
    supplier_name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    subtotal = Column(Float, nullable=False)
    vat_rate = Column(Float, default=0, nullable=False)
    vat_amount = Column(Float, default=0, nullable=False)
    total_amount = Column(Float, nullable=False)
    status = Column(String, default="unpaid", nullable=False)


class AILog(Base, TimestampMixin):
    __tablename__ = "ai_logs"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, nullable=True, index=True)
    action = Column(String, nullable=False)
    input_description = Column(Text, nullable=True)
    input_amount = Column(Float, nullable=True)
    predicted_category = Column(String, nullable=True)
    predicted_type = Column(String, nullable=True)
    debit_account_code = Column(String, nullable=True)
    credit_account_code = Column(String, nullable=True)
    ai_confidence = Column(Float, nullable=True)
    ai_result_json = Column(Text, nullable=True)


class AICorrection(Base, TimestampMixin):
    __tablename__ = "ai_corrections"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, nullable=True, index=True)
    original_description = Column(Text, nullable=False)
    original_amount = Column(Float, nullable=False)
    ai_category = Column(String, nullable=True)
    ai_type = Column(String, nullable=True)
    ai_debit_account_code = Column(String, nullable=True)
    ai_credit_account_code = Column(String, nullable=True)
    ai_confidence = Column(Float, nullable=True)
    user_category = Column(String, nullable=False)
    user_type = Column(String, nullable=False)
    user_debit_account_code = Column(String, nullable=False)
    user_credit_account_code = Column(String, nullable=False)
    note = Column(Text, nullable=True)


class AIReviewItem(Base, TimestampMixin):
    """V19 review queue: giao dịch AI chưa đủ chắc chắn để tự ghi sổ."""
    __tablename__ = "ai_review_items"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, nullable=True, index=True)
    source = Column(String, default="ai", nullable=False)
    description = Column(Text, nullable=False)
    amount = Column(Float, nullable=False)
    ai_category = Column(String, nullable=True)
    ai_type = Column(String, nullable=True)
    ai_debit_account_code = Column(String, nullable=True)
    ai_credit_account_code = Column(String, nullable=True)
    ai_confidence = Column(Float, nullable=True)
    ai_result_json = Column(Text, nullable=True)
    status = Column(String, default="pending", nullable=False)  # pending / approved / corrected / rejected
    priority = Column(String, default="medium", nullable=False)  # low / medium / high
    reason = Column(Text, nullable=True)
    reviewer_note = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)


# ============================================================
# Product chat models used by /api/v1/chat
# ============================================================

class ChatConversation(Base, TimestampMixin):
    __tablename__ = "chat_conversations"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(120), nullable=False, index=True)
    workspace_id = Column(String(120), default="default", nullable=False, index=True)
    title = Column(String(240), default="Cuộc trò chuyện mới", nullable=False)
    preview = Column(Text, nullable=True)
    is_archived = Column(Boolean, default=False, nullable=False)
    last_message_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class ChatMessage(Base, TimestampMixin):
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, index=True)
    conversation_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(120), nullable=False, index=True)
    workspace_id = Column(String(120), default="default", nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String(30), default="completed", nullable=False)
    metadata_json = Column(Text, nullable=True)
    citations_json = Column(Text, nullable=True)
    confidence = Column(String(120), nullable=True)


class ChatAttachment(Base, TimestampMixin):
    __tablename__ = "chat_attachments"

    id = Column(String(36), primary_key=True, index=True)
    conversation_id = Column(String(36), nullable=True, index=True)
    user_id = Column(String(120), nullable=False, index=True)
    workspace_id = Column(String(120), default="default", nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    mime_type = Column(String(150), nullable=True)
    size_bytes = Column(Integer, default=0, nullable=False)
    storage_path = Column(Text, nullable=True)
    extraction_status = Column(String(30), default="ready", nullable=False)
    extracted_text = Column(Text, nullable=True)
    extraction_method = Column(String(120), nullable=True)


class ChatFeedback(Base, TimestampMixin):
    __tablename__ = "chat_feedback"

    id = Column(String(36), primary_key=True, index=True)
    message_id = Column(String(36), nullable=False, index=True)
    conversation_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(120), nullable=False, index=True)
    rating = Column(String(20), nullable=False)
    reason = Column(String(240), nullable=True)
    comment = Column(Text, nullable=True)
