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
    WorkOrderListResponse,
    WorkOrderUpdate,
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


def get_work_orders(
    user_id: str,
    status_filter: Optional[str] = None,
    priority_filter: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> WorkOrderListResponse:
    app_user = _get_app_user(user_id)
    if not app_user or not app_user.get("company_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with a company.",
        )

    company_id = app_user["company_id"]

    # Build query
    query = (
        supabase.table("work_orders")
        .select("id,company_id,property_id,unit_id,unit,issue,priority,status,pte,preferred_window,tenant_name,tenant_phone,assigned_technician_id,created_at")
        .eq("company_id", company_id)
    )

    if status_filter:
        query = query.eq("status", status_filter)
    if priority_filter:
        query = query.eq("priority", priority_filter)

    # Get total count - use a simpler approach
    count_query = supabase.table("work_orders").select("id").eq("company_id", company_id)
    if status_filter:
        count_query = count_query.eq("status", status_filter)
    if priority_filter:
        count_query = count_query.eq("priority", priority_filter)
    
    count_res = count_query.execute()
    total = len(getattr(count_res, "data", []) or [])

    # Get work orders with pagination
    query = query.order("created_at", desc=True).limit(limit).offset(offset)
    res = query.execute()
    data = getattr(res, "data", []) or []

    # Get property names
    property_ids = [row["property_id"] for row in data if row.get("property_id")]
    property_names = {}
    if property_ids:
        prop_res = (
            supabase.table("properties")
            .select("id,name")
            .in_("id", property_ids)
            .execute()
        )
        prop_data = getattr(prop_res, "data", []) or []
        property_names = {row["id"]: row["name"] for row in prop_data}

    # Build response
    work_orders = []
    for row in data:
        wo = WorkOrderResponse(
            id=row["id"],
            company_id=row["company_id"],
            property_id=row["property_id"],
            property_name=property_names.get(row["property_id"]),
            unit_id=row.get("unit_id"),
            unit_label=row.get("unit"),
            issue=row.get("issue", ""),
            priority=row.get("priority", "routine"),
            status=row.get("status", "open"),
            pte=row.get("pte"),
            preferred_window=row.get("preferred_window"),
            tenant_name=row.get("tenant_name"),
            tenant_phone=row.get("tenant_phone"),
            assigned_technician_id=row.get("assigned_technician_id"),
            created_at=row.get("created_at"),
        )
        work_orders.append(wo)

    return WorkOrderListResponse(work_orders=work_orders, total=total)


def update_work_order(user_id: str, work_order_id: str, update_data: WorkOrderUpdate) -> WorkOrderResponse:
    app_user = _get_app_user(user_id)
    if not app_user or not app_user.get("company_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with a company.",
        )

    company_id = app_user["company_id"]

    # Verify work order belongs to company
    check_res = (
        supabase.table("work_orders")
        .select("id,property_id")
        .eq("id", work_order_id)
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    check_data = getattr(check_res, "data", []) or []
    if not check_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Work order not found",
        )

    # Build update dict
    update_dict = {}
    
    # Handle technician assignment
    if update_data.assigned_technician_id is not None:
        if update_data.assigned_technician_id:
            normalized_tech_id = _normalize_uuid(update_data.assigned_technician_id, "assigned_technician_id")
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
            update_dict["assigned_technician_id"] = tech_data[0]["id"]
        else:
            update_dict["assigned_technician_id"] = None
    
    # Handle status update
    if update_data.status is not None:
        update_dict["status"] = update_data.status

    if not update_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    # Update work order
    res = (
        supabase.table("work_orders")
        .update(update_dict)
        .eq("id", work_order_id)
        .eq("company_id", company_id)
        .execute()
    )
    
    data = getattr(res, "data", []) or []
    if not data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update work order",
        )
    
    record = data[0]
    
    # Get property name
    property_id = record.get("property_id") or check_data[0].get("property_id")
    property_name = None
    if property_id:
        prop_res = (
            supabase.table("properties")
            .select("name")
            .eq("id", property_id)
            .limit(1)
            .execute()
        )
        prop_data = getattr(prop_res, "data", []) or []
        if prop_data:
            property_name = prop_data[0]["name"]

    return WorkOrderResponse(
        id=record["id"],
        company_id=company_id,
        property_id=record["property_id"],
        property_name=property_name,
        unit_id=record.get("unit_id"),
        unit_label=record.get("unit"),
        issue=record.get("issue", ""),
        priority=record.get("priority", "routine"),
        status=record.get("status", "open"),
        pte=record.get("pte"),
        preferred_window=record.get("preferred_window"),
        tenant_name=record.get("tenant_name"),
        tenant_phone=record.get("tenant_phone"),
        assigned_technician_id=record.get("assigned_technician_id"),
        created_at=record.get("created_at"),
    )
