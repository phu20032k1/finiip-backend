"""Finiip V112 Accounting Suite: shared operational records for accounting modules.

This layer reuses the existing Finiip ledger and adds auditable CRUD/workflow for
modules that do not yet have dedicated tables. It does not replace the existing
specialized transaction/invoice APIs.
"""
from datetime import date, datetime
import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import Column, Date, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Account, AccountingPeriod, AuditLog, AIReviewItem, JournalEntry, PurchaseInvoice, SalesInvoice, Transaction

router = APIRouter(prefix="/api/v112/accounting", tags=["Finiip V112 Accounting Suite"])

MODULES = [
    {"key":"cash","name":"Quỹ","document_types":["receipt","payment","cash_count"],"masters":["cash_fund"]},
    {"key":"bank","name":"Ngân hàng","document_types":["bank_receipt","bank_payment","bank_statement","bank_reconciliation"],"masters":["bank_account"]},
    {"key":"purchase","name":"Mua hàng","document_types":["purchase_order","purchase_contract","purchase_receipt","purchase_invoice","purchase_return","purchase_discount","supplier_payment"],"masters":["supplier","payment_term"]},
    {"key":"sales","name":"Bán hàng","document_types":["quotation","sales_order","sales_contract","sales_invoice","sales_return","sales_discount","customer_receipt"],"masters":["customer","payment_term"]},
    {"key":"inventory","name":"Kho","document_types":["stock_receipt","stock_issue","stock_transfer","stock_count","stock_revaluation"],"masters":["item","warehouse","unit"]},
    {"key":"fixed-assets","name":"Tài sản cố định","document_types":["asset_increase","depreciation","asset_transfer","asset_revaluation","asset_decrease"],"masters":["fixed_asset","asset_category"]},
    {"key":"tools","name":"CCDC & chi phí trả trước","document_types":["tool_increase","tool_allocation","tool_transfer","tool_decrease","prepaid_expense"],"masters":["tool","allocation_rule"]},
    {"key":"payroll","name":"Tiền lương","document_types":["payroll_sheet","insurance","pit_withholding","salary_payment"],"masters":["employee","department","salary_component"]},
    {"key":"tax","name":"Thuế","document_types":["vat_declaration","cit_declaration","pit_declaration","tax_payment","invoice_reconciliation"],"masters":["tax_code","tax_period"]},
    {"key":"costing","name":"Giá thành","document_types":["cost_collection","cost_allocation","wip_evaluation","costing_sheet"],"masters":["cost_object","cost_center"]},
    {"key":"ledger","name":"Tổng hợp & Sổ cái","document_types":["general_voucher","closing_entry","opening_balance","adjustment"],"masters":["accounting_dimension"]},
    {"key":"invoice","name":"Hóa đơn điện tử","document_types":["outgoing_invoice","incoming_invoice","invoice_adjustment","invoice_replacement","invoice_cancellation"],"masters":["invoice_template"]},
    {"key":"reports","name":"Báo cáo","document_types":["report_snapshot"],"masters":["report_template"]},
    {"key":"ai-control","name":"AI & Đối chiếu","document_types":["reconciliation_case","ai_review_case"],"masters":["review_rule"]},
]
MODULE_MAP = {x["key"]: x for x in MODULES}


class AccountingDocument(Base):
    __tablename__ = "v112_accounting_documents"
    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(String(120), default="personal", nullable=False, index=True)
    module = Column(String(60), nullable=False, index=True)
    document_type = Column(String(80), nullable=False, index=True)
    document_no = Column(String(120), nullable=False, index=True)
    document_date = Column(Date, default=date.today, nullable=False, index=True)
    partner = Column(String(240), nullable=True, index=True)
    description = Column(Text, nullable=True)
    amount = Column(Float, default=0, nullable=False)
    tax_amount = Column(Float, default=0, nullable=False)
    debit_account_code = Column(String(40), nullable=True)
    credit_account_code = Column(String(40), nullable=True)
    status = Column(String(30), default="draft", nullable=False, index=True)
    ledger_status = Column(String(30), default="not_posted", nullable=False, index=True)
    journal_transaction_id = Column(Integer, nullable=True, index=True)
    journal_entry_id = Column(Integer, nullable=True, index=True)
    metadata_json = Column(Text, nullable=True)
    created_by = Column(String(120), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AccountingMaster(Base):
    __tablename__ = "v112_accounting_masters"
    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(String(120), default="personal", nullable=False, index=True)
    entity_type = Column(String(80), nullable=False, index=True)
    code = Column(String(120), nullable=False, index=True)
    name = Column(String(240), nullable=False, index=True)
    status = Column(String(30), default="active", nullable=False, index=True)
    data_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


Base.metadata.create_all(bind=engine)


class DocumentCreate(BaseModel):
    module: str
    document_type: str
    document_no: Optional[str] = None
    document_date: Optional[date] = None
    partner: Optional[str] = None
    description: Optional[str] = None
    amount: float = Field(0, ge=0)
    tax_amount: float = Field(0, ge=0)
    debit_account_code: Optional[str] = None
    credit_account_code: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class DocumentUpdate(BaseModel):
    document_type: Optional[str] = None
    document_no: Optional[str] = None
    document_date: Optional[date] = None
    partner: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[float] = Field(None, ge=0)
    tax_amount: Optional[float] = Field(None, ge=0)
    debit_account_code: Optional[str] = None
    credit_account_code: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class PostRequest(BaseModel):
    post_to_ledger: bool = True
    transaction_type: Optional[str] = None
    category: Optional[str] = None
    note: Optional[str] = None

class MasterCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=120)
    name: str = Field(..., min_length=1, max_length=240)
    status: str = "active"
    data: Dict[str, Any] = Field(default_factory=dict)

class MasterUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    status: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


def ws(request: Request) -> str:
    return (request.headers.get("X-Workspace-ID") or "personal").strip() or "personal"

def actor(request: Request) -> str:
    return (request.headers.get("X-User-ID") or "v112-user").strip() or "v112-user"

def dumps(v: Any) -> str:
    return json.dumps(v or {}, ensure_ascii=False, default=str)

def loads(v: Optional[str]) -> Dict[str, Any]:
    try:
        x = json.loads(v or "{}")
        return x if isinstance(x, dict) else {"value": x}
    except Exception:
        return {}

def spec(module: str) -> Dict[str, Any]:
    if module not in MODULE_MAP:
        raise HTTPException(status_code=404, detail="Phân hệ V112 không tồn tại")
    return MODULE_MAP[module]

def doc_dict(x: AccountingDocument) -> Dict[str, Any]:
    return {"id":x.id,"workspace_id":x.workspace_id,"module":x.module,"document_type":x.document_type,"document_no":x.document_no,"document_date":str(x.document_date),"partner":x.partner,"description":x.description,"amount":float(x.amount or 0),"tax_amount":float(x.tax_amount or 0),"total_amount":float(x.amount or 0)+float(x.tax_amount or 0),"debit_account_code":x.debit_account_code,"credit_account_code":x.credit_account_code,"status":x.status,"ledger_status":x.ledger_status,"journal_transaction_id":x.journal_transaction_id,"journal_entry_id":x.journal_entry_id,"metadata":loads(x.metadata_json),"created_by":x.created_by,"created_at":x.created_at.isoformat() if x.created_at else None,"updated_at":x.updated_at.isoformat() if x.updated_at else None}

def master_dict(x: AccountingMaster) -> Dict[str, Any]:
    return {"id":x.id,"entity_type":x.entity_type,"code":x.code,"name":x.name,"status":x.status,"data":loads(x.data_json),"created_at":x.created_at.isoformat() if x.created_at else None,"updated_at":x.updated_at.isoformat() if x.updated_at else None}

def audit(db: Session, request: Request, action: str, entity_id: int, old=None, new=None, note: Optional[str]=None):
    db.add(AuditLog(action=f"v112_{action}",entity_type="v112_accounting_document",entity_id=entity_id,old_value_json=dumps(old) if old is not None else None,new_value_json=dumps(new) if new is not None else None,note=f"workspace={ws(request)}"+(f"; {note}" if note else ""),actor=actor(request)))

def next_no(db: Session, workspace: str, module: str, d: date) -> str:
    prefixes={"cash":"QUY","bank":"NH","purchase":"MH","sales":"BH","inventory":"KHO","fixed-assets":"TSCD","tools":"CCDC","payroll":"LUONG","tax":"THUE","costing":"GT","ledger":"TH","invoice":"HD","reports":"BC","ai-control":"AI"}
    n=db.query(AccountingDocument).filter(AccountingDocument.workspace_id==workspace,AccountingDocument.module==module,AccountingDocument.document_date==d).count()+1
    return f"{prefixes.get(module,'CT')}-{d.strftime('%Y%m%d')}-{n:04d}"

def open_period(db: Session, d: date):
    p=db.query(AccountingPeriod).filter(AccountingPeriod.period==d.strftime("%Y-%m")).first()
    if p and p.status=="closed":
        raise HTTPException(status_code=409, detail=f"Kỳ kế toán {p.period} đã khóa")

def get_account(db: Session, code: Optional[str]) -> Account:
    if not code:
        raise HTTPException(status_code=400, detail="Thiếu tài khoản Nợ/Có để ghi sổ")
    a=db.query(Account).filter(Account.code==code).first()
    if not a:
        raise HTTPException(status_code=400, detail=f"Tài khoản {code} chưa tồn tại")
    return a


@router.get("/modules")
def modules():
    return {"version":"112.0","modules":MODULES}

@router.get("/dashboard")
def dashboard(request: Request, db: Session=Depends(get_db)):
    q=db.query(AccountingDocument).filter(AccountingDocument.workspace_id==ws(request))
    statuses={s:q.filter(AccountingDocument.status==s).count() for s in ["draft","approved","posted","cancelled"]}
    return {"version":"112.0","workspace_id":ws(request),"v112_documents":q.count(),"by_status":statuses,"by_module":{m["key"]:q.filter(AccountingDocument.module==m["key"]).count() for m in MODULES},"v112_document_value":float(q.with_entities(func.coalesce(func.sum(AccountingDocument.amount+AccountingDocument.tax_amount),0)).scalar() or 0),"core":{"accounts":db.query(Account).count(),"transactions":db.query(Transaction).count(),"journal_entries":db.query(JournalEntry).count(),"pending_ai_review":db.query(AIReviewItem).filter(AIReviewItem.status=="pending").count(),"sales_invoice_total":float(db.query(func.coalesce(func.sum(SalesInvoice.total_amount),0)).scalar() or 0),"purchase_invoice_total":float(db.query(func.coalesce(func.sum(PurchaseInvoice.total_amount),0)).scalar() or 0),"unpaid_sales":db.query(SalesInvoice).filter(SalesInvoice.status=="unpaid").count(),"unpaid_purchases":db.query(PurchaseInvoice).filter(PurchaseInvoice.status=="unpaid").count()},"action_required":statuses["draft"]+statuses["approved"]+db.query(AIReviewItem).filter(AIReviewItem.status=="pending").count()}

@router.get("/documents")
def list_documents(request: Request, db: Session=Depends(get_db), module: Optional[str]=None, document_type: Optional[str]=None, status: Optional[str]=None, q: Optional[str]=None, limit: int=Query(100,ge=1,le=500), offset: int=Query(0,ge=0)):
    query=db.query(AccountingDocument).filter(AccountingDocument.workspace_id==ws(request))
    if module: spec(module); query=query.filter(AccountingDocument.module==module)
    if document_type: query=query.filter(AccountingDocument.document_type==document_type)
    if status: query=query.filter(AccountingDocument.status==status)
    if q:
        like=f"%{q}%"; query=query.filter(AccountingDocument.document_no.ilike(like)|AccountingDocument.partner.ilike(like)|AccountingDocument.description.ilike(like))
    total=query.count(); items=query.order_by(AccountingDocument.document_date.desc(),AccountingDocument.id.desc()).offset(offset).limit(limit).all()
    return {"items":[doc_dict(x) for x in items],"total":total,"limit":limit,"offset":offset}

@router.post("/documents")
def create_document(payload: DocumentCreate, request: Request, db: Session=Depends(get_db)):
    s=spec(payload.module)
    if payload.document_type not in s["document_types"]: raise HTTPException(status_code=400,detail=f"Loại chứng từ không hợp lệ cho {s['name']}")
    d=payload.document_date or date.today(); workspace=ws(request)
    x=AccountingDocument(workspace_id=workspace,module=payload.module,document_type=payload.document_type,document_no=payload.document_no or next_no(db,workspace,payload.module,d),document_date=d,partner=payload.partner,description=payload.description,amount=payload.amount,tax_amount=payload.tax_amount,debit_account_code=payload.debit_account_code,credit_account_code=payload.credit_account_code,metadata_json=dumps(payload.metadata),created_by=actor(request))
    db.add(x); db.flush(); audit(db,request,"create",x.id,new=doc_dict(x)); db.commit(); db.refresh(x); return {"document":doc_dict(x)}

@router.get("/documents/{document_id}")
def get_document(document_id:int, request:Request, db:Session=Depends(get_db)):
    x=db.query(AccountingDocument).filter(AccountingDocument.id==document_id,AccountingDocument.workspace_id==ws(request)).first()
    if not x: raise HTTPException(status_code=404,detail="Không tìm thấy chứng từ V112")
    return {"document":doc_dict(x)}

@router.put("/documents/{document_id}")
def update_document(document_id:int,payload:DocumentUpdate,request:Request,db:Session=Depends(get_db)):
    x=db.query(AccountingDocument).filter(AccountingDocument.id==document_id,AccountingDocument.workspace_id==ws(request)).first()
    if not x: raise HTTPException(status_code=404,detail="Không tìm thấy chứng từ V112")
    if x.status in {"posted","cancelled"}: raise HTTPException(status_code=409,detail="Chứng từ đã ghi sổ/hủy, không thể sửa")
    old=doc_dict(x); data=payload.model_dump(exclude_unset=True); meta=data.pop("metadata",None)
    if data.get("document_type") and data["document_type"] not in spec(x.module)["document_types"]: raise HTTPException(status_code=400,detail="Loại chứng từ không hợp lệ")
    for k,v in data.items(): setattr(x,k,v)
    if meta is not None: x.metadata_json=dumps(meta)
    x.updated_at=datetime.utcnow(); audit(db,request,"update",x.id,old=old,new=doc_dict(x)); db.commit(); db.refresh(x); return {"document":doc_dict(x)}

@router.delete("/documents/{document_id}")
def delete_document(document_id:int,request:Request,db:Session=Depends(get_db)):
    x=db.query(AccountingDocument).filter(AccountingDocument.id==document_id,AccountingDocument.workspace_id==ws(request)).first()
    if not x: raise HTTPException(status_code=404,detail="Không tìm thấy chứng từ V112")
    if x.status=="posted": raise HTTPException(status_code=409,detail="Không xóa chứng từ đã ghi sổ")
    old=doc_dict(x); audit(db,request,"delete",x.id,old=old); db.delete(x); db.commit(); return {"ok":True,"deleted_id":document_id}

@router.post("/documents/{document_id}/approve")
def approve(document_id:int,request:Request,db:Session=Depends(get_db)):
    x=db.query(AccountingDocument).filter(AccountingDocument.id==document_id,AccountingDocument.workspace_id==ws(request)).first()
    if not x: raise HTTPException(status_code=404,detail="Không tìm thấy chứng từ V112")
    if x.status!="draft": raise HTTPException(status_code=409,detail="Chỉ chứng từ nháp mới được duyệt")
    old=doc_dict(x); x.status="approved"; audit(db,request,"approve",x.id,old=old,new=doc_dict(x)); db.commit(); db.refresh(x); return {"document":doc_dict(x)}

@router.post("/documents/{document_id}/cancel")
def cancel(document_id:int,request:Request,db:Session=Depends(get_db)):
    x=db.query(AccountingDocument).filter(AccountingDocument.id==document_id,AccountingDocument.workspace_id==ws(request)).first()
    if not x: raise HTTPException(status_code=404,detail="Không tìm thấy chứng từ V112")
    if x.status=="posted": raise HTTPException(status_code=409,detail="Chứng từ đã ghi sổ cần lập điều chỉnh/đảo")
    old=doc_dict(x); x.status="cancelled"; audit(db,request,"cancel",x.id,old=old,new=doc_dict(x)); db.commit(); db.refresh(x); return {"document":doc_dict(x)}

@router.post("/documents/{document_id}/post")
def post(document_id:int,payload:PostRequest,request:Request,db:Session=Depends(get_db)):
    x=db.query(AccountingDocument).filter(AccountingDocument.id==document_id,AccountingDocument.workspace_id==ws(request)).first()
    if not x: raise HTTPException(status_code=404,detail="Không tìm thấy chứng từ V112")
    if x.status=="cancelled": raise HTTPException(status_code=409,detail="Chứng từ đã hủy")
    if x.status=="posted": return {"document":doc_dict(x),"already_posted":True}
    old=doc_dict(x); open_period(db,x.document_date); tx=entry=None
    if payload.post_to_ledger:
        total=float(x.amount or 0)+float(x.tax_amount or 0)
        if total<=0: raise HTTPException(status_code=400,detail="Số tiền phải lớn hơn 0 để ghi sổ")
        debit=get_account(db,x.debit_account_code); credit=get_account(db,x.credit_account_code)
        if debit.code==credit.code: raise HTTPException(status_code=400,detail="Tài khoản Nợ và Có không được trùng nhau")
        description=x.description or f"{spec(x.module)['name']} {x.document_no}"; tx_type=payload.transaction_type or ("income" if x.module=="sales" or x.document_type in {"receipt","bank_receipt","customer_receipt"} else "expense")
        tx=Transaction(transaction_date=x.document_date,description=description,amount=total,type=tx_type,category=payload.category or f"v112:{x.module}:{x.document_type}",note=f"V112 {x.document_no}"+(f"; {payload.note}" if payload.note else ""),debit_account_code=debit.code,credit_account_code=credit.code,status="confirmed",confirmed_at=datetime.utcnow(),accounting_period=x.document_date.strftime("%Y-%m")); db.add(tx); db.flush()
        entry=JournalEntry(transaction_id=tx.id,entry_date=x.document_date,description=description,debit_account_code=debit.code,debit_account_name=debit.name,credit_account_code=credit.code,credit_account_name=credit.name,amount=total,line_no=1,status="posted",accounting_period=x.document_date.strftime("%Y-%m")); db.add(entry); db.flush(); x.journal_transaction_id=tx.id; x.journal_entry_id=entry.id; x.ledger_status="posted"
    else: x.ledger_status="not_required"
    x.status="posted"; audit(db,request,"post",x.id,old=old,new=doc_dict(x),note=payload.note); db.commit(); db.refresh(x); return {"document":doc_dict(x),"transaction_id":tx.id if tx else None,"journal_entry_id":entry.id if entry else None}

@router.get("/masters/{entity_type}")
def list_masters(entity_type:str,request:Request,db:Session=Depends(get_db),q:Optional[str]=None,status:Optional[str]="active",limit:int=Query(200,le=500)):
    query=db.query(AccountingMaster).filter(AccountingMaster.workspace_id==ws(request),AccountingMaster.entity_type==entity_type)
    if status: query=query.filter(AccountingMaster.status==status)
    if q:
        like=f"%{q}%"; query=query.filter(AccountingMaster.code.ilike(like)|AccountingMaster.name.ilike(like))
    items=query.order_by(AccountingMaster.name).limit(limit).all(); return {"items":[master_dict(x) for x in items],"total":len(items)}

@router.post("/masters/{entity_type}")
def create_master(entity_type:str,payload:MasterCreate,request:Request,db:Session=Depends(get_db)):
    workspace=ws(request)
    if db.query(AccountingMaster).filter(AccountingMaster.workspace_id==workspace,AccountingMaster.entity_type==entity_type,AccountingMaster.code==payload.code).first(): raise HTTPException(status_code=400,detail="Mã danh mục đã tồn tại")
    x=AccountingMaster(workspace_id=workspace,entity_type=entity_type,code=payload.code,name=payload.name,status=payload.status,data_json=dumps(payload.data)); db.add(x); db.commit(); db.refresh(x); return {"item":master_dict(x)}

@router.put("/masters/{entity_type}/{item_id}")
def update_master(entity_type:str,item_id:int,payload:MasterUpdate,request:Request,db:Session=Depends(get_db)):
    x=db.query(AccountingMaster).filter(AccountingMaster.id==item_id,AccountingMaster.workspace_id==ws(request),AccountingMaster.entity_type==entity_type).first()
    if not x: raise HTTPException(status_code=404,detail="Không tìm thấy danh mục")
    data=payload.model_dump(exclude_unset=True); extra=data.pop("data",None)
    for k,v in data.items(): setattr(x,k,v)
    if extra is not None: x.data_json=dumps(extra)
    db.commit(); db.refresh(x); return {"item":master_dict(x)}

@router.delete("/masters/{entity_type}/{item_id}")
def delete_master(entity_type:str,item_id:int,request:Request,db:Session=Depends(get_db)):
    x=db.query(AccountingMaster).filter(AccountingMaster.id==item_id,AccountingMaster.workspace_id==ws(request),AccountingMaster.entity_type==entity_type).first()
    if not x: raise HTTPException(status_code=404,detail="Không tìm thấy danh mục")
    db.delete(x); db.commit(); return {"ok":True,"deleted_id":item_id}

@router.get("/reconciliation")
def reconcile(request:Request,db:Session=Depends(get_db)):
    q=db.query(AccountingDocument).filter(AccountingDocument.workspace_id==ws(request)); draft=q.filter(AccountingDocument.status=="draft").count(); approved=q.filter(AccountingDocument.status=="approved").count(); low=db.query(Transaction).filter(Transaction.ai_confidence.isnot(None),Transaction.ai_confidence<0.7,Transaction.status!="cancelled").count(); missing=db.query(Transaction).filter(((Transaction.debit_account_code.is_(None))|(Transaction.credit_account_code.is_(None))),Transaction.status!="cancelled").count(); ai=db.query(AIReviewItem).filter(AIReviewItem.status=="pending").count()
    checks=[{"key":"draft_documents","severity":"warning" if draft else "ok","count":draft,"label":"Chứng từ V112 còn nháp"},{"key":"approved_not_posted","severity":"warning" if approved else "ok","count":approved,"label":"Chứng từ đã duyệt chưa ghi sổ"},{"key":"low_ai_confidence","severity":"warning" if low else "ok","count":low,"label":"Giao dịch AI độ tin cậy thấp"},{"key":"missing_accounts","severity":"danger" if missing else "ok","count":missing,"label":"Giao dịch thiếu tài khoản Nợ/Có"},{"key":"unpaid_sales","severity":"info","count":db.query(SalesInvoice).filter(SalesInvoice.status=="unpaid").count(),"label":"Hóa đơn bán chưa thu"},{"key":"unpaid_purchases","severity":"info","count":db.query(PurchaseInvoice).filter(PurchaseInvoice.status=="unpaid").count(),"label":"Hóa đơn mua chưa trả"},{"key":"pending_ai_review","severity":"warning" if ai else "ok","count":ai,"label":"Hàng đợi AI cần duyệt"}]
    issues=sum(int(x["count"]) for x in checks if x["severity"] in {"warning","danger"}); return {"workspace_id":ws(request),"checked_at":datetime.utcnow().isoformat()+"Z","checks":checks,"issues":issues,"status":"attention" if issues else "ok"}
