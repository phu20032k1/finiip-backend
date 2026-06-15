from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ORMModel(BaseModel):
    class Config:
        from_attributes = True


class AccountCreate(BaseModel):
    code: str
    name: str
    account_type: str


class AccountResponse(AccountCreate, ORMModel):
    id: int
    created_at: datetime


class CustomerCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    tax_code: Optional[str] = None
    address: Optional[str] = None


class CustomerResponse(CustomerCreate, ORMModel):
    id: int
    created_at: datetime


class SupplierCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    tax_code: Optional[str] = None
    address: Optional[str] = None


class SupplierResponse(SupplierCreate, ORMModel):
    id: int
    created_at: datetime


class TransactionCreate(BaseModel):
    transaction_date: Optional[date] = None
    description: str
    amount: float = Field(gt=0)
    type: str = "unknown"
    category: Optional[str] = None
    note: Optional[str] = None


class TransactionUpdate(BaseModel):
    transaction_date: Optional[date] = None
    description: Optional[str] = None
    amount: Optional[float] = Field(default=None, gt=0)
    type: Optional[str] = None
    category: Optional[str] = None
    note: Optional[str] = None
    debit_account_code: Optional[str] = None
    credit_account_code: Optional[str] = None
    ai_confidence: Optional[float] = None
    status: Optional[str] = "draft"


class TransactionResponse(ORMModel):
    id: int
    transaction_date: date
    description: str
    amount: float
    type: str
    category: Optional[str]
    note: Optional[str]
    debit_account_code: Optional[str]
    credit_account_code: Optional[str]
    ai_confidence: Optional[float]
    status: str
    confirmed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    accounting_period: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class JournalEntryCreate(BaseModel):
    transaction_id: Optional[int] = None
    entry_date: Optional[date] = None
    description: str
    debit_account_code: str
    credit_account_code: str
    amount: float = Field(gt=0)
    status: Optional[str] = "draft"


class JournalEntryResponse(ORMModel):
    id: int
    transaction_id: Optional[int]
    entry_date: date
    description: str
    debit_account_code: str
    debit_account_name: str
    credit_account_code: str
    credit_account_name: str
    amount: float
    line_no: int
    status: str
    accounting_period: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AccountingPeriodCreate(BaseModel):
    period: str = Field(pattern=r"^\d{4}-\d{2}$")
    note: Optional[str] = None


class AccountingPeriodResponse(ORMModel):
    id: int
    period: str
    start_date: date
    end_date: date
    status: str
    closed_at: Optional[datetime] = None
    reopened_at: Optional[datetime] = None
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ClosePeriodRequest(BaseModel):
    period: str = Field(pattern=r"^\d{4}-\d{2}$")
    note: Optional[str] = None


class AuditLogResponse(ORMModel):
    id: int
    action: str
    entity_type: str
    entity_id: Optional[int]
    old_value_json: Optional[str]
    new_value_json: Optional[str]
    note: Optional[str]
    actor: str
    created_at: datetime
    updated_at: datetime


class ImportPreviewItem(BaseModel):
    row: int
    transaction_date: date
    description: str
    amount: float
    ai_result: Dict[str, Any]


class ImportExcelResponse(BaseModel):
    imported: int
    status: str
    items: List[Dict[str, Any]]


class SalesInvoiceCreate(BaseModel):
    invoice_date: Optional[date] = None
    invoice_number: str
    customer_id: Optional[int] = None
    customer_name: str
    description: Optional[str] = None
    subtotal: float = Field(gt=0)
    vat_rate: float = 0
    status: str = "unpaid"


class SalesInvoiceResponse(ORMModel):
    id: int
    invoice_date: date
    invoice_number: str
    customer_id: Optional[int]
    customer_name: str
    description: Optional[str]
    subtotal: float
    vat_rate: float
    vat_amount: float
    total_amount: float
    status: str
    created_at: datetime


class PurchaseInvoiceCreate(BaseModel):
    invoice_date: Optional[date] = None
    invoice_number: str
    supplier_id: Optional[int] = None
    supplier_name: str
    description: Optional[str] = None
    subtotal: float = Field(gt=0)
    vat_rate: float = 0
    status: str = "unpaid"


class PurchaseInvoiceResponse(ORMModel):
    id: int
    invoice_date: date
    invoice_number: str
    supplier_id: Optional[int]
    supplier_name: str
    description: Optional[str]
    subtotal: float
    vat_rate: float
    vat_amount: float
    total_amount: float
    status: str
    created_at: datetime


class AIAnalyzeRequest(BaseModel):
    description: str
    amount: float = Field(gt=0)


class AICreateTransactionRequest(AIAnalyzeRequest):
    transaction_date: Optional[date] = None
    note: Optional[str] = None
    auto_create_journal: bool = False


class AICorrectionCreate(BaseModel):
    user_category: str
    user_type: str
    user_debit_account_code: str
    user_credit_account_code: str
    note: Optional[str] = None




class AITeachExampleCreate(BaseModel):
    description: str
    amount: float = Field(gt=0)
    user_category: str
    user_type: str = "expense"
    user_debit_account_code: str
    user_credit_account_code: str
    note: Optional[str] = None


class AITeachBatchRequest(BaseModel):
    items: List[AITeachExampleCreate]



class AITrainingExampleUpdate(BaseModel):
    description: Optional[str] = None
    amount: Optional[float] = Field(default=None, gt=0)
    user_category: Optional[str] = None
    user_type: Optional[str] = None
    user_debit_account_code: Optional[str] = None
    user_credit_account_code: Optional[str] = None
    note: Optional[str] = None


class AIFeedbackRequest(BaseModel):
    description: str
    amount: float = Field(gt=0)
    ai_category: Optional[str] = None
    ai_type: Optional[str] = None
    ai_debit_account_code: Optional[str] = None
    ai_credit_account_code: Optional[str] = None
    ai_confidence: Optional[float] = None
    correct_category: str
    correct_type: str = "expense"
    correct_debit_account_code: str
    correct_credit_account_code: str
    note: Optional[str] = None
    train_after: bool = False


class AIMLEvaluateRequest(BaseModel):
    test_ratio: float = Field(default=0.2, gt=0, lt=0.8)
    min_examples: int = Field(default=10, ge=2)


class AIMLTrainRequest(BaseModel):
    min_examples: int = Field(default=1, ge=1)
    include_corrections: bool = True


class AIMLPredictRequest(AIAnalyzeRequest):
    min_confidence: float = Field(default=0.55, ge=0, le=1)


class AILogResponse(ORMModel):
    id: int
    transaction_id: Optional[int]
    action: str
    input_description: Optional[str]
    input_amount: Optional[float]
    predicted_category: Optional[str]
    predicted_type: Optional[str]
    debit_account_code: Optional[str]
    credit_account_code: Optional[str]
    ai_confidence: Optional[float]
    ai_result_json: Optional[str]
    created_at: datetime


class AICorrectionResponse(ORMModel):
    id: int
    transaction_id: Optional[int]
    original_description: str
    original_amount: float
    ai_category: Optional[str]
    ai_type: Optional[str]
    ai_debit_account_code: Optional[str]
    ai_credit_account_code: Optional[str]
    ai_confidence: Optional[float]
    user_category: str
    user_type: str
    user_debit_account_code: str
    user_credit_account_code: str
    note: Optional[str]
    created_at: datetime


class AIBatchItem(BaseModel):
    description: str
    amount: float = Field(gt=0)


class AIBatchAnalyzeRequest(BaseModel):
    items: List[AIBatchItem]


class AICustomRuleCreate(BaseModel):
    keywords: List[str]
    category: str
    transaction_type: str = "expense"
    debit_account: str
    debit_account_name: str
    credit_account: str
    credit_account_name: str
    confidence: float = Field(default=0.8, ge=0, le=1)


class JournalLineResponse(BaseModel):
    side: str
    account_code: str
    account_name: str
    amount: float


class MessageResponse(BaseModel):
    message: str


class DashboardResponse(BaseModel):
    totals: Dict[str, Any]
    ai: Dict[str, Any]
    reports: Dict[str, Any]
    warnings: List[Dict[str, Any]]


class InvoiceOCRTextRequest(BaseModel):
    raw_text: str
    create_purchase_invoice: bool = False
    create_transaction: bool = False
    auto_create_journal: bool = False

# =========================
# V13 Accounting Formula Engine schemas
# =========================

class VATFormulaRequest(BaseModel):
    subtotal: Optional[float] = Field(default=None, ge=0)
    vat_rate: float = Field(default=10, ge=0)
    vat_amount: Optional[float] = Field(default=None, ge=0)
    total: Optional[float] = Field(default=None, ge=0)


class DepreciationFormulaRequest(BaseModel):
    cost: float = Field(gt=0)
    salvage_value: float = Field(default=0, ge=0)
    useful_life_months: int = Field(default=36, gt=0)
    months_used: Optional[int] = Field(default=None, ge=0)


class PrepaidAllocationRequest(BaseModel):
    total_amount: float = Field(gt=0)
    allocation_months: int = Field(gt=0)
    months_allocated: int = Field(default=1, ge=0)


class GrossProfitRequest(BaseModel):
    revenue: float = Field(ge=0)
    cogs: float = Field(ge=0)


class NetProfitRequest(BaseModel):
    revenue: float = Field(ge=0)
    cogs: float = Field(default=0, ge=0)
    operating_expenses: float = Field(default=0, ge=0)
    other_income: float = Field(default=0, ge=0)
    other_expenses: float = Field(default=0, ge=0)
    tax_expense: float = Field(default=0, ge=0)


class CorporateIncomeTaxRequest(BaseModel):
    profit_before_tax: float
    tax_rate: float = Field(default=20, ge=0)
    non_deductible_expenses: float = Field(default=0, ge=0)
    tax_exempt_income: float = Field(default=0, ge=0)


class JournalCheckLine(BaseModel):
    side: str
    account_code: Optional[str] = None
    account_name: Optional[str] = None
    amount: float = Field(ge=0)


class JournalCheckRequest(BaseModel):
    lines: List[JournalCheckLine]


class FinancialRatiosRequest(BaseModel):
    current_assets: float = Field(default=0, ge=0)
    current_liabilities: float = Field(default=0, ge=0)
    total_assets: float = Field(default=0, ge=0)
    total_liabilities: float = Field(default=0, ge=0)
    equity: float = 0
    revenue: float = Field(default=0, ge=0)
    net_profit: float = 0
    inventory: float = Field(default=0, ge=0)
    cash: float = Field(default=0, ge=0)


class BreakEvenRequest(BaseModel):
    fixed_costs: float = Field(gt=0)
    selling_price_per_unit: float = Field(gt=0)
    variable_cost_per_unit: float = Field(ge=0)

# =========================
# V14 Advanced Accounting Engine schemas
# =========================

class InventoryLayer(BaseModel):
    quantity: float = Field(ge=0)
    unit_cost: float = Field(ge=0)
    label: Optional[str] = None


class InventoryPurchase(BaseModel):
    quantity: float = Field(ge=0)
    unit_cost: Optional[float] = Field(default=None, ge=0)
    amount: Optional[float] = Field(default=None, ge=0)
    label: Optional[str] = None


class FIFOInventoryRequest(BaseModel):
    beginning_layers: List[InventoryLayer] = []
    purchases: List[InventoryLayer] = []
    sales_quantity: float = Field(ge=0)


class WeightedAverageInventoryRequest(BaseModel):
    beginning_quantity: float = Field(default=0, ge=0)
    beginning_value: float = Field(default=0, ge=0)
    purchases: List[InventoryPurchase] = []
    sales_quantity: float = Field(default=0, ge=0)


class PayrollBasicRequest(BaseModel):
    gross_salary: float = Field(ge=0)
    employee_social_rate: float = Field(default=8, ge=0)
    employee_health_rate: float = Field(default=1.5, ge=0)
    employee_unemployment_rate: float = Field(default=1, ge=0)
    personal_income_tax: float = Field(default=0, ge=0)
    employer_social_rate: float = Field(default=17.5, ge=0)
    employer_health_rate: float = Field(default=3, ge=0)
    employer_unemployment_rate: float = Field(default=1, ge=0)


class AgingItem(BaseModel):
    name: Optional[str] = None
    party: Optional[str] = None
    amount: float = Field(ge=0)
    due_date: date


class AccountsAgingRequest(BaseModel):
    items: List[AgingItem]
    as_of: Optional[date] = None


class PeriodClosingRequest(BaseModel):
    revenue: float = Field(default=0, ge=0)
    cogs: float = Field(default=0, ge=0)
    selling_expenses: float = Field(default=0, ge=0)
    admin_expenses: float = Field(default=0, ge=0)
    financial_expenses: float = Field(default=0, ge=0)
    other_expenses: float = Field(default=0, ge=0)
    tax_expense: float = Field(default=0, ge=0)


class BasicFinancialStatementsRequest(BaseModel):
    cash: float = Field(default=0, ge=0)
    receivables: float = Field(default=0, ge=0)
    inventory: float = Field(default=0, ge=0)
    fixed_assets: float = Field(default=0, ge=0)
    accumulated_depreciation: float = Field(default=0, ge=0)
    payables: float = Field(default=0, ge=0)
    loans: float = Field(default=0, ge=0)
    owner_equity: float = Field(default=0)
    revenue: float = Field(default=0, ge=0)
    cogs: float = Field(default=0, ge=0)
    operating_expenses: float = Field(default=0, ge=0)
    tax_expense: float = Field(default=0, ge=0)


# =========================
# V15 Backend API Pack schemas
# =========================

class FrontendTransactionPreviewRequest(BaseModel):
    description: str
    amount: float = Field(gt=0)
    transaction_date: Optional[date] = None
    min_confidence: float = Field(default=0.55, ge=0, le=1)


class FrontendInvoiceTextPreviewRequest(BaseModel):
    raw_text: str
    create_drafts: bool = False


class BulkReanalyzeTransactionsRequest(BaseModel):
    transaction_ids: List[int]
    update_transactions: bool = False
    min_confidence: float = Field(default=0.55, ge=0, le=1)


# =========================
# V18-V22 Self-made AI upgrade schemas
# =========================

class AIV18FeedbackLearningRequest(BaseModel):
    description: str
    amount: float = Field(gt=0)
    ai_category: Optional[str] = None
    ai_type: Optional[str] = None
    ai_debit_account_code: Optional[str] = None
    ai_credit_account_code: Optional[str] = None
    ai_confidence: Optional[float] = None
    correct_category: str
    correct_type: str = "expense"
    correct_debit_account_code: str
    correct_credit_account_code: str
    note: Optional[str] = None
    train_after: bool = False
    create_review_item: bool = True


class AIV19ReviewDecisionRequest(BaseModel):
    action: str = Field(pattern=r"^(approve|correct|reject)$")
    correct_category: Optional[str] = None
    correct_type: Optional[str] = None
    correct_debit_account_code: Optional[str] = None
    correct_credit_account_code: Optional[str] = None
    note: Optional[str] = None
    train_after_correction: bool = False
    create_journal: bool = False


class AIV20RetrainFeedbackRequest(BaseModel):
    min_examples: int = Field(default=1, ge=1)
    evaluate_after: bool = True
    test_ratio: float = Field(default=0.2, gt=0, lt=0.8)


class AIV21OCRImproveTextRequest(BaseModel):
    raw_text: str
    create_purchase_invoice: bool = False
    create_transaction: bool = False
    auto_create_journal: bool = False
    auto_push_review_queue: bool = True


class AIV22DoubleEntryRequest(BaseModel):
    description: str
    amount: float = Field(gt=0)
    subtotal: Optional[float] = Field(default=None, ge=0)
    vat_rate: float = Field(default=10, ge=0)
    vat_amount: Optional[float] = Field(default=None, ge=0)
    transaction_id: Optional[int] = None
    transaction_date: Optional[date] = None
    mode: str = Field(default="auto", pattern=r"^(auto|purchase|sales|expense|asset)$")
    cash_account_code: str = "111"
    payable_account_code: str = "331"
    receivable_account_code: str = "131"
    auto_create_journal: bool = False
    status: str = "draft"
