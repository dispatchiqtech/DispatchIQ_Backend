from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Tuple
import re

from fastapi import HTTPException, status

from app.core.config import settings
from app.db.supabase_client import supabase_admin
from app.models.onboarding import (
    OnboardingRequest,
    OnboardingResponse,
    OnboardingSummary,
    OnboardingStatusResponse,
    PropertySummary,
    TechnicianSummary,
    EmergencyVendorSummary,
)

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
PLACEHOLDER_VALUES = {"string", "null", "none", "undefined", "", "all"}

TIMEZONE_ALIASES = {
    "Eastern (Detroit)": "America/Detroit",
    "Central (Chicago)": "America/Chicago",
    "Mountain (Denver)": "America/Denver",
    "Pacific (LA)": "America/Los_Angeles",
}
REVERSE_TIMEZONE_ALIASES = {v: k for k, v in TIMEZONE_ALIASES.items()}


def _get_app_user(user_id: str) -> Optional[Dict]:
    res = (
        supabase_admin.table("app_users")
        .select("user_id, company_id, first_name, last_name")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    data = getattr(res, "data", []) or []
    return data[0] if data else None


def _normalize_time(value: str) -> str:
    """Ensure time values conform to HH:MM:SS for Postgres."""
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.strftime("%H:%M:%S")
        except ValueError:
            continue
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Invalid time value '{value}'. Expected HH:MM 24-hour format.",
    )


def _format_time_for_response(value: Optional[str]) -> str:
    if not value:
        return "00:00"
    try:
        parsed = datetime.strptime(value, "%H:%M:%S")
    except ValueError:
        try:
            parsed = datetime.strptime(value, "%H:%M")
        except ValueError:
            return value
    return parsed.strftime("%H:%M")


def _normalize_timezone(value: Optional[str], fallback: str) -> str:
    if not value:
        return fallback
    candidate = value.strip()
    if candidate in TIMEZONE_ALIASES:
        return TIMEZONE_ALIASES[candidate]
    if candidate in REVERSE_TIMEZONE_ALIASES:
        return candidate
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Unsupported timezone '{value}'.",
    )


def _property_belongs_to_company(property_id: str, company_id: str) -> bool:
    res = (
        supabase_admin.table("properties")
        .select("id")
        .eq("id", property_id)
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    data = getattr(res, "data", []) or []
    return bool(data)


def _get_company(company_id: str) -> Optional[Dict]:
    res = (
        supabase_admin.table("companies")
        .select("*")
        .eq("id", company_id)
        .limit(1)
        .execute()
    )
    data = getattr(res, "data", []) or []
    return data[0] if data else None


def _company_has_existing_records(company_id: str) -> bool:
    for table in ("properties", "technicians", "emergency_vendors"):
        res = (
            supabase_admin.table(table)
            .select("id")
            .eq("company_id", company_id)
            .limit(1)
            .execute()
        )
        data = getattr(res, "data", []) or []
        if data:
            return True
    return False


def _clean_optional_uuid(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    candidate = value.strip()
    if candidate.lower() in PLACEHOLDER_VALUES:
        return None
    if not UUID_RE.match(candidate):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid UUID value '{value}'.",
        )
    return candidate


def _resolve_property_identifier(
    identifier: Optional[str],
    company_id: str,
    newly_created: Dict[str, str],
) -> Optional[str]:
    if not identifier:
        return None

    candidate = identifier.strip()
    if candidate.lower() in PLACEHOLDER_VALUES:
        return None

    if UUID_RE.match(candidate):
        if not _property_belongs_to_company(candidate, company_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Property {candidate} does not belong to this company.",
            )
        return candidate

    mapped = newly_created.get(candidate.lower())
    if mapped:
        return mapped

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Unknown property reference '{identifier}'. Use an existing property UUID or the name from this request.",
    )


def _create_or_link_admin(
    company_id: str,
    admin_email: str,
    admin_password: str,
    first_name: Optional[str],
    last_name: Optional[str],
) -> Tuple[str, bool]:
    """Create a Supabase user for the admin if one does not already exist."""
    email = admin_email.strip().lower()
    fn = (first_name or "").strip() or "Company"
    ln = (last_name or "").strip() or "Admin"

    created = False
    user_id = None

    try:
        response = supabase_admin.auth.admin.create_user(
            {
                "email": email,
                "password": admin_password,
                "email_confirm": False,
                "user_metadata": {
                    "first_name": fn,
                    "last_name": ln,
                    "company_id": company_id,
                },
            }
        )
        if not getattr(response, "user", None):
            raise Exception("Supabase did not return user")
        user = response.user
        user_id = user.id
        created = True

        supabase_admin.auth.admin.generate_link(
            {
                "type": "signup",
                "email": email,
                "options": {
                    "redirect_to": f"{settings.FRONTEND_URL}/auth/callback"
                },
            }
        )
    except Exception as create_error:
        # If the user already exists, fetch their record
        try:
            existing = supabase_admin.auth.admin.list_users(per_page=200).users
            user = next((u for u in existing if (u.email or "").lower() == email), None)
            if not user:
                raise create_error
            user_id = user.id
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unable to create or link admin user: {create_error}",
            )

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to determine admin user id.",
        )

    profile_update = {
        "company_id": company_id,
        "first_name": fn,
        "last_name": ln,
        "is_active": True,
    }
    profile_res = (
        supabase_admin.table("app_users")
        .update(profile_update)
        .eq("user_id", user_id)
        .execute()
    )
    if not getattr(profile_res, "data", []) or not profile_res.data:
        profile_update["user_id"] = user_id
        supabase_admin.table("app_users").insert(profile_update).execute()

    return user_id, created


def complete_first_time_onboarding(user_id: str, payload: OnboardingRequest, acting_email: str) -> OnboardingResponse:
    """
    Persist initial company setup for the user's company. Onboarding only runs once.
    """
    app_user = _get_app_user(user_id)
    if not app_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile not found. Complete signup before onboarding.",
        )

    company_id = app_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company not provisioned. Complete signup first.",
        )

    company = _get_company(company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company record missing. Contact support.",
        )

    if _company_has_existing_records(company_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Onboarding already completed.",
        )

    company_name = payload.company_name.strip() if payload.company_name else company.get("name", "")
    timezone = _normalize_timezone(payload.timezone, company.get("timezone", "America/Detroit"))
    work_start = _normalize_time(payload.work_hours_start)
    work_end = _normalize_time(payload.work_hours_end)

    company_payload = {
        "name": company_name,
        "timezone": timezone,
        "work_hours_start": work_start,
        "work_hours_end": work_end,
        "auto_assign": payload.auto_assign,
        "intake": payload.intake_method or "manual",
        "collect_pte": payload.collect_pte,
        "collect_window": payload.collect_window,
        "on_call_enabled": payload.on_call_enabled,
        "on_call_rotation": payload.on_call_rotation,
    }

    supabase_admin.table("companies").update(company_payload).eq("id", company_id).execute()

    admin_created = False
    if payload.admin_account:
        admin_email = payload.admin_account.email.strip()
        if admin_email.lower() != acting_email.strip().lower():
            _, admin_created = _create_or_link_admin(
                company_id=company_id,
                admin_email=admin_email,
                admin_password=payload.admin_account.password,
                first_name=payload.admin_account.first_name,
                last_name=payload.admin_account.last_name,
            )

    property_ids: List[str] = []
    property_name_map: Dict[str, str] = {}
    if payload.properties:
        property_rows: List[Dict] = [
            {
                "company_id": company_id,
                "name": item.name,
                "address": item.address,
                "notes": item.notes,
            }
            for item in payload.properties
        ]
        properties_res = supabase_admin.table("properties").insert(property_rows).execute()
        property_data = getattr(properties_res, "data", []) or []
        property_ids = [row["id"] for row in property_data]
        for item, row in zip(payload.properties, property_data):
            property_name_map[item.name.strip().lower()] = row["id"]

    technician_ids: List[str] = []
    if payload.technicians:
        technician_rows: List[Dict] = []
        for tech in payload.technicians:
            row: Dict = {
                "company_id": company_id,
                "first_name": tech.first_name,
                "last_name": tech.last_name,
                "phone": tech.phone,
                "email": tech.email,
                "shift": tech.shift,
                "merit_percent": tech.merit_percent if tech.merit_percent is not None else 100,
            }
            user_uuid = _clean_optional_uuid(tech.user_id)
            if user_uuid:
                row["user_id"] = user_uuid

            resolved_property = _resolve_property_identifier(
                tech.default_property,
                company_id,
                property_name_map,
            )
            if resolved_property:
                row["default_property_id"] = resolved_property

            technician_rows.append(row)

        tech_res = supabase_admin.table("technicians").insert(technician_rows).execute()
        tech_data = getattr(tech_res, "data", []) or []
        technician_ids = [row["id"] for row in tech_data]

    emergency_vendor_ids: List[str] = []
    if payload.emergency_vendors:
        vendor_rows: List[Dict] = [
            {
                "company_id": company_id,
                "category": vendor.category,
                "name": vendor.name,
                "phone": vendor.phone,
            }
            for vendor in payload.emergency_vendors
        ]
        vendor_res = supabase_admin.table("emergency_vendors").insert(vendor_rows).execute()
        vendor_data = getattr(vendor_res, "data", []) or []
        emergency_vendor_ids = [row["id"] for row in vendor_data]

    summary = OnboardingSummary(
        company_name=company_name,
        timezone=timezone,
        work_hours_start=_format_time_for_response(work_start),
        work_hours_end=_format_time_for_response(work_end),
        auto_assign=payload.auto_assign,
        on_call_enabled=payload.on_call_enabled,
        on_call_rotation=payload.on_call_rotation,
        intake_method=payload.intake_method or "manual",
        collect_pte=payload.collect_pte,
        collect_window=payload.collect_window,
        properties_total=len(property_ids),
        technicians_total=len(technician_ids),
        emergency_vendors_total=len(emergency_vendor_ids),
        admin_user_created=admin_created,
    )

    return OnboardingResponse(
        success=True,
        company_id=company_id,
        summary=summary,
    )


def get_onboarding_status(user_id: str) -> OnboardingStatusResponse:
    app_user = _get_app_user(user_id)
    if not app_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile not found.",
        )

    company_id = app_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company not provisioned.",
        )

    company = _get_company(company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company record missing.",
        )

    properties_res = (
        supabase_admin.table("properties")
        .select("id,name,address,notes")
        .eq("company_id", company_id)
        .execute()
    )
    properties_data = getattr(properties_res, "data", []) or []
    property_map = {row["id"]: row for row in properties_data}

    technicians_res = (
        supabase_admin.table("technicians")
        .select("id,first_name,last_name,email,phone,shift,default_property_id")
        .eq("company_id", company_id)
        .execute()
    )
    technicians_data = getattr(technicians_res, "data", []) or []

    vendors_res = (
        supabase_admin.table("emergency_vendors")
        .select("id,category,name,phone")
        .eq("company_id", company_id)
        .execute()
    )
    vendors_data = getattr(vendors_res, "data", []) or []

    properties = [
        PropertySummary(
            id=row["id"],
            name=row.get("name", ""),
            address=row.get("address"),
            notes=row.get("notes"),
        )
        for row in properties_data
    ]

    technicians = [
        TechnicianSummary(
            id=row["id"],
            first_name=row.get("first_name"),
            last_name=row.get("last_name"),
            email=row.get("email"),
            phone=row.get("phone"),
            shift=row.get("shift"),
            default_property_id=row.get("default_property_id"),
            default_property_name=property_map.get(row.get("default_property_id"), {}).get("name"),
        )
        for row in technicians_data
    ]

    vendors = [
        EmergencyVendorSummary(
            id=row["id"],
            category=row.get("category"),
            name=row.get("name", ""),
            phone=row.get("phone"),
        )
        for row in vendors_data
    ]

    timezone = company.get("timezone", "America/Detroit")
    timezone_label = REVERSE_TIMEZONE_ALIASES.get(timezone, timezone)

    return OnboardingStatusResponse(
        company_id=company_id,
        company_name=company.get("name", ""),
        timezone=timezone,
        timezone_label=timezone_label,
        work_hours_start=_format_time_for_response(company.get("work_hours_start")),
        work_hours_end=_format_time_for_response(company.get("work_hours_end")),
        auto_assign=bool(company.get("auto_assign", True)),
        on_call_enabled=bool(company.get("on_call_enabled", False)),
        on_call_rotation=company.get("on_call_rotation", "weekly"),
        intake_method=company.get("intake", "manual"),
        collect_pte=bool(company.get("collect_pte", True)),
        collect_window=bool(company.get("collect_window", True)),
        properties=properties,
        technicians=technicians,
        emergency_vendors=vendors,
        onboarding_completed=bool(properties or technicians or vendors),
    )
