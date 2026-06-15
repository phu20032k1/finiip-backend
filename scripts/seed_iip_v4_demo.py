"""Seed IIP Steel V4 demo data from command line."""
from fastapi import Request
from database import SessionLocal
from iip_steel_platform import seed_iip_demo_v2, IIPFinanceCostRule, IIPCostPrice, IIPSupplierBonusProgram, IIPBonusTier, IIPVehicle, IIPAuthUser, hash_password, upsert_by_key
from datetime import date


def main():
    db = SessionLocal()
    try:
        seed_iip_demo_v2(db)
        if not db.query(IIPFinanceCostRule).filter(IIPFinanceCostRule.name == 'default_12pct').first():
            db.add(IIPFinanceCostRule(name='default_12pct', annual_rate_pct=12, is_default=1))
        for product_code, cost in [('VAS-D10', 14500000), ('VAS-D12', 14600000), ('HP-D10', 14300000)]:
            if not db.query(IIPCostPrice).filter(IIPCostPrice.product_code == product_code).first():
                db.add(IIPCostPrice(product_code=product_code, province='ALL', cost_price=cost, supplier='demo'))
        if not db.query(IIPSupplierBonusProgram).filter(IIPSupplierBonusProgram.program_code == 'VAS-2026').first():
            db.add(IIPSupplierBonusProgram(program_code='VAS-2026', supplier='VAS', year=2026, product_brand='VAS', start_date=date(2026,1,1), end_date=date(2026,12,31)))
            db.add(IIPBonusTier(program_code='VAS-2026', tier_name='Bạc', target_ton=30000, bonus_amount=800_000_000))
            db.add(IIPBonusTier(program_code='VAS-2026', tier_name='Vàng', target_ton=40000, bonus_amount=1_500_000_000))
            db.add(IIPBonusTier(program_code='VAS-2026', tier_name='Kim cương', target_ton=50000, bonus_amount=3_000_000_000))
        upsert_by_key(db, IIPVehicle, 'vehicle_code', {'vehicle_code': 'TRUCK-01', 'plate_number': '29H-12345', 'max_ton': 25, 'driver_name': 'Tài xế Demo', 'driver_phone': '0900000000', 'status': 'active'})
        if not db.query(IIPAuthUser).filter(IIPAuthUser.username == 'dealer_sonla').first():
            db.add(IIPAuthUser(username='dealer_sonla', full_name='Đại lý Sơn La Demo', role='dealer', dealer_code='DL_SONLA', password_hash=hash_password('dealer123'), is_active=True))
        db.commit()
        print('Seeded IIP Steel V4 demo data.')
    finally:
        db.close()

if __name__ == '__main__':
    main()
