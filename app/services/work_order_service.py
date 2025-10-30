from __future__ import annotations

from typing import Dict, List, Optional
import uuid

from fastapi import HTTPException, status

from app.db.supabase_client import supabase_admin as supabase
from app.models.work_orders import (
    PropertyOption,
    PropertyUnitOption,
    WorkOrderCreate,
    WorkOrderOptionsResponse,
    WorkOrderResponse,
)


def _get_app_user(user_id: str) -> Optional[Dict]:
    res = (
        supabase.table("app_users")
        .select("user_id, company_id, first_name, last_name")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    data = getattr(res, "data", []) or []
    return data[0] if data else None


def _get_company(company_id: str) -> Optional[Dict]:
    res = (
        supabase.table("companies")
        .select("*")
        .eq("id", company_id)
        .limit(1)
        .execute()
    )
    data = getattr(res, "data", []) or []
    return data[0] if data else None


def get_work_order_options(user_id: str) -> WorkOrderOptionsResponse:
    app_user = _get_app_user(user_id)
    if not app_user or not app_user.get("company_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with a company.",
        )

    company_id = app_user["company_id"]

    properties_res = (
        supabase.table("properties")
        .select("id,name,address,notes")
        .eq("company_id", company_id)
        .order("name")
        .execute()
    )
    properties_data = getattr(properties_res, "data", []) or []
    property_ids = [row["id"] for row in properties_data]

    units_map: Dict[str, List[PropertyUnitOption]] = {}
    if property_ids:
        units_res = (
            supabase.table("property_units")
            .select("id,property_id,label,notes,is_active")
            .in_("property_id", property_ids)
            .order("label")
            .execute()
        )
        units_data = getattr(units_res, "data", []) or []
        for row in units_data:
            option = PropertyUnitOption(
                id=row["id"],
                label=row["label"],
                notes=row.get("notes"),
                is_active=bool(row.get("is_active", True)),
            )
            units_map.setdefault(row["property_id"], []).append(option)

    properties = [
        PropertyOption(
            id=row["id"],
            name=row.get("name", ""),
            address=row.get("address"),
            notes=row.get("notes"),
            units=units_map.get(row["id"], []),
        )
        for row in properties_data
    ]

    return WorkOrderOptionsResponse(company_id=company_id, properties=properties)


def _ensure_property(company_id: str, property_id: str) -> Dict:
    res = (
        supabase.table("properties")
        .select("id,name")
        .eq("id", property_id)
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    data = getattr(res, "data", []) or []
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found for this company.",
        )
    return data[0]


def _get_unit(record_id: str) -> Optional[Dict]:
    res = (
        supabase.table("property_units")
        .select("id,label,property_id,company_id,is_active")
        .eq("id", record_id)
        .limit(1)
        .execute()
    )
    data = getattr(res, "data", []) or []
    return data[0] if data else None


def _find_unit_by_label(property_id: str, label: str) -> Optional[Dict]:
    res = (
        supabase.table("property_units")
        .select("id,label,property_id,company_id,is_active")
        .eq("property_id", property_id)
        .eq("label", label)
        .limit(1)
        .execute()
    )
    data = getattr(res, "data", []) or []
    return data[0] if data else None


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid UUID for {field}.",
        )


def _upsert_unit(company_id: str, property_id: str, request: WorkOrderCreate) -> tuple[Optional[str], Optional[str]]:
    label = (request.unit_label or "").strip() if request.unit_label else None
    unit_id = (request.unit_id or "").strip() if request.unit_id else None

    if unit_id:
        normalized_unit_id = _normalize_uuid(unit_id, "unit_id")
        unit = _get_unit(normalized_unit_id)
        if not unit or unit.get("company_id") != company_id or unit.get("property_id") != property_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Unit does not belong to the selected property.",
            )
        return unit["id"], unit.get("label")

    if label:
        existing = _find_unit_by_label(property_id, label)
        if existing:
            return existing["id"], existing.get("label")

        insert_res = (
            supabase.table("property_units")
            .insert(
                {
                    "company_id": company_id,
                    "property_id": property_id,
                    "label": label,
                    "is_active": True,
                }
            )
            .execute()
        )
        insert_data = getattr(insert_res, "data", []) or []
        if not insert_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create unit for property.",
            )
        unit = insert_data[0]
        return unit["id"], unit.get("label")

    return None, None


def create_work_order(user_id: str, request: WorkOrderCreate) -> WorkOrderResponse:
    app_user = _get_app_user(user_id)
    if not app_user or not app_user.get("company_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with a company.",
        )

    company_id = app_user["company_id"]

    property_record = _ensure_property(company_id, request.property_id)
    property_name = property_record.get("name", "")

    unit_id, unit_label = _upsert_unit(company_id, request.property_id, request)

    assigned_technician_id = None
    if request.assigned_technician_id:
        normalized_tech_id = _normalize_uuid(request.assigned_technician_id, "assigned_technician_id")
        tech_res = (
            supabase.table("technicians")
            .select("id")
            .eq("id", normalized_tech_id)
            .eq("company_id", company_id)
            .limit(1)
            .execute()
        )
        tech_data = getattr(tech_res, "data", []) or []
        if not tech_data:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Technician does not belong to this company.",
            )
        assigned_technician_id = tech_data[0]["id"]

    work_order_payload: Dict[str, Optional[str]] = {
        "company_id": company_id,
        "property_id": request.property_id,
        "unit_id": unit_id,
        "unit": unit_label,
        "issue": request.issue,
        "priority": request.priority,
        "pte": request.pte,
        "preferred_window": request.preferred_window,
        "tenant_name": request.tenant_name,
        "tenant_phone": request.tenant_phone,
        "assigned_technician_id": assigned_technician_id,
    }

    insert_res = supabase.table("work_orders").insert(work_order_payload).execute()
    data = getattr(insert_res, "data", []) or []
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create work order.",
        )
    record = data[0]

    return WorkOrderResponse(
        id=record["id"],
        company_id=company_id,
        property_id=record["property_id"],
        property_name=property_name,
        unit_id=record.get("unit_id"),
        unit_label=record.get("unit"),
        issue=record.get("issue", ""),
        priority=record.get("priority", ""),
        status=record.get("status", ""),
        pte=record.get("pte"),
        preferred_window=record.get("preferred_window"),
        tenant_name=record.get("tenant_name"),
        tenant_phone=record.get("tenant_phone"),
        assigned_technician_id=record.get("assigned_technician_id"),
        created_at=record.get("created_at"),
    )
