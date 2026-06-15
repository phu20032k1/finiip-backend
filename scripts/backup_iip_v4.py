"""Lightweight JSON backup for IIP V4 tables."""
import json
from datetime import datetime, date
from database import SessionLocal
from iip_steel_platform import row_to_dict, IIPDealer, IIPOrder, IIPOrderItem, IIPDebt, IIPPayment, IIPOutputInvoice, IIPWarehouseSlip, IIPDelivery, IIPOrderProfitSnapshot, IIPApprovalRequest, IIPInvoiceXMLFile, IIPSupplierBonusProgram, IIPBonusTier, IIPDeliveryLocation, IIPDeliveryEvent, IIPDealerCreditScoreHistory

TABLES = {
    'dealers': IIPDealer,
    'orders': IIPOrder,
    'order_items': IIPOrderItem,
    'debts': IIPDebt,
    'payments': IIPPayment,
    'invoices': IIPOutputInvoice,
    'warehouse_slips': IIPWarehouseSlip,
    'deliveries': IIPDelivery,
    'profit_snapshots': IIPOrderProfitSnapshot,
    'approval_requests': IIPApprovalRequest,
    'invoice_xml_files': IIPInvoiceXMLFile,
    'bonus_programs': IIPSupplierBonusProgram,
    'bonus_tiers': IIPBonusTier,
    'delivery_locations': IIPDeliveryLocation,
    'delivery_events': IIPDeliveryEvent,
    'credit_score_history': IIPDealerCreditScoreHistory,
}

def main():
    db = SessionLocal()
    try:
        payload = {'exported_at': datetime.utcnow().isoformat()}
        for name, model in TABLES.items():
            payload[name] = [row_to_dict(x) for x in db.query(model).all()]
        out = f'iip_v4_backup_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.json'
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, default=str, indent=2)
        print(out)
    finally:
        db.close()

if __name__ == '__main__':
    main()
