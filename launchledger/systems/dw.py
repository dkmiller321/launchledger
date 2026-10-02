"""Data-warehouse rollups (PRD S8), rebuilt from ERP and MES rows."""

from collections import defaultdict
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from launchledger.db import models as m


def rebuild_dw(session: Session, on: date = date(2026, 10, 1)) -> None:
    """Recompute supplier on-time rates and work-order cycle times."""
    session.execute(delete(m.SupplierOnTime))
    session.execute(delete(m.WoCycleTime))

    names = {s.supplier_id: s.name for s in session.scalars(select(m.Supplier))}
    received: dict[str, int] = defaultdict(int)
    on_time: dict[str, int] = defaultdict(int)
    open_late: dict[str, int] = defaultdict(int)
    for po in session.scalars(select(m.PurchaseOrder)):
        if po.status == "RECEIVED" and po.received_on is not None:
            received[po.supplier_id] += 1
            if po.received_on <= po.due_date:
                on_time[po.supplier_id] += 1
        elif po.status == "OPEN" and (po.promised_date > po.due_date or po.due_date < on):
            open_late[po.supplier_id] += 1
    for sid, name in names.items():
        got = received[sid]
        session.add(
            m.SupplierOnTime(
                supplier_id=sid,
                name=name,
                pos_received=got,
                pos_on_time=on_time[sid],
                on_time_rate=round(on_time[sid] / got, 3) if got else 0.0,
                open_late_pos=open_late[sid],
            )
        )

    part_of = {s.serial_number: s.part_number for s in session.scalars(select(m.Serial))}
    cycles: dict[str, list[tuple[date, int]]] = defaultdict(list)
    for wo in session.scalars(select(m.WorkOrder).where(m.WorkOrder.closed_on.is_not(None))):
        assert wo.closed_on is not None
        part = part_of.get(wo.serial_number)
        if part:
            cycles[part].append((wo.closed_on, (wo.closed_on - wo.opened_on).days))
    for part, items in cycles.items():
        items.sort()
        days = [d for _, d in items]
        session.add(
            m.WoCycleTime(
                part_number=part,
                closed_wos=len(days),
                avg_cycle_days=round(sum(days) / len(days), 1),
                last_cycle_days=float(days[-1]),
            )
        )
