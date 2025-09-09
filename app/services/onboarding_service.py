from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status
from app.db.supabase_client import supabase_admin as supabase
from app.models.onboarding import OwnerOnboardingRequest, SubcontractorOnboardingRequest
from app.core.config import settings
import time
import re


def _get_user_type_id_by_key(key: str) -> Optional[int]:
    try:
        res = supabase.table("user_types").select("id,key").eq("key", key).limit(1).execute()
        data = getattr(res, "data", []) or ([] if not hasattr(res, "data") else res.data)
        if data:
            return data[0]["id"]
    except Exception:
        pass
    return None


def _get_app_user(user_id: str) -> Optional[dict]:
    res = supabase.table("app_users").select("*").eq("user_id", user_id).limit(1).execute()
    data = getattr(res, "data", [])
    return data[0] if data else None


def _upsert_app_user(user_id: str, profile: Dict[str, Any], type_key: Optional[str]) -> None:
    payload: Dict[str, Any] = {"user_id": user_id}
    # Carry over selected profile fields if present
    for k in [
        "first_name",
        "last_name",
        "phone",
        "country",
        "state",
        "city",
        "address",
        "postal_code",
    ]:
        if profile.get(k) is not None:
            payload[k] = profile[k]

    if type_key:
        type_id = _get_user_type_id_by_key(type_key)
        if type_id is not None:
            payload["type_id"] = type_id

    supabase.table("app_users").upsert(payload, on_conflict="user_id").execute()


def _ensure_user_profile(user_id: str, profile: Dict[str, Any]) -> None:
    # user_profiles requires first_name and last_name as NOT NULL per schema
    first_name = profile.get("first_name")
    last_name = profile.get("last_name")
    if not first_name or not last_name:
        raise HTTPException(status_code=422, detail="first_name and last_name are required")

    existing = supabase.table("user_profiles").select("id").eq("user_id", user_id).limit(1).execute()
    data = getattr(existing, "data", [])
    payload = {
        "user_id": user_id,
        "first_name": first_name,
        "last_name": last_name,
        "address": profile.get("address"),
        "city": profile.get("city"),
        "state": profile.get("state"),
        "postal_code": profile.get("postal_code"),
        "country": profile.get("country"),
    }
    if data:
        supabase.table("user_profiles").update(payload).eq("user_id", user_id).execute()
    else:
        supabase.table("user_profiles").insert(payload).execute()


def _mark_onboarding_completed(user_id: str) -> None:
    supabase.table("app_users").update({"onboarding_status": "completed"}).eq("user_id", user_id).execute()


def _owner_record_exists(user_id: str) -> bool:
    res = supabase.table("owners").select("id").eq("user_id", user_id).limit(1).execute()
    data = getattr(res, "data", [])
    return bool(data)


def _subcontractor_record_exists(user_id: str) -> Optional[str]:
    res = supabase.table("subcontractors").select("id").eq("user_id", user_id).limit(1).execute()
    data = getattr(res, "data", [])
    return data[0]["id"] if data else None


UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def _resolve_service_category_id(val: Optional[str]) -> Optional[str]:
    """Accepts a UUID, slug, or name and returns the UUID id for service_categories."""
    if not val:
        return None
    val = str(val).strip()
    if UUID_RE.match(val):
        return val
    # Try slug, then name
    res = (
        supabase.table("service_categories").select("id,slug,name").or_(f"slug.eq.{val},name.eq.{val}").limit(1).execute()
    )
    data = getattr(res, "data", [])
    if data:
        return data[0]["id"]
    raise HTTPException(status_code=422, detail=f"Unknown service category: '{val}'. Pass a valid UUID, slug, or name.")


def onboard_owner_or_pm(user_id: str, payload: OwnerOnboardingRequest) -> Dict[str, Any]:
    # Prevent duplicate onboarding
    if _owner_record_exists(user_id):
        raise HTTPException(status_code=409, detail="User already onboarded as owner/pm")

    # Ensure user profile and app_users
    profile_dict = payload.model_dump()
    _ensure_user_profile(user_id, profile_dict)
    # Map role key for user_types: assume keys: 'owner', 'property_manager', 'subcontractor'
    _upsert_app_user(user_id, profile_dict, type_key=(payload.role or "owner"))

    # If role is property_manager, require a PMA document URL to be provided or uploaded separately
    pma_url = payload.pma_document_url
    if payload.role == "property_manager":
        if not pma_url or not str(pma_url).strip():
            raise HTTPException(
                status_code=422,
                detail="PMA document is required for property managers. Upload it first and pass pma_document_url."
            )

    # Create owner row
    owner_row = {
        "user_id": user_id,
        "company_name": payload.company_name,
        "company_registration_number": payload.company_registration_number,
        "billing_address": payload.billing_address,
        "payment_terms": payload.payment_terms,
        # For owners, PMA is not required; for PM, enforce above and set accordingly
        "has_pma": bool(pma_url) if payload.role == "property_manager" else False,
        "pma_document_url": pma_url if pma_url else None,
    }
    insert_res = supabase.table("owners").insert(owner_row).execute()
    data = getattr(insert_res, "data", [])
    if not data:
        raise HTTPException(status_code=400, detail="Failed to create owner record")
    owner_id = data[0]["id"]

    _mark_onboarding_completed(user_id)

    return {
        "success": True,
        "message": "Onboarding completed for owner/pm",
        "user_id": user_id,
        "role": payload.role,
        "created_ids": {"owner_id": owner_id},
    }


def onboard_subcontractor(user_id: str, payload: SubcontractorOnboardingRequest) -> Dict[str, Any]:
    # Prevent duplicate onboarding
    if _subcontractor_record_exists(user_id):
        raise HTTPException(status_code=409, detail="User already onboarded as subcontractor")

    profile_dict = payload.model_dump()
    _ensure_user_profile(user_id, profile_dict)
    _upsert_app_user(user_id, profile_dict, type_key="subcontractor")

    # Create subcontractor row
    subcontractor_row = {
        "user_id": user_id,
        "company_name": payload.company_name,
        "business_registration_number": payload.business_registration_number,
        "subcontractor_type": payload.subcontractor_type,
        "service_radius_km": payload.service_radius_km,
        "tin": payload.tin,
        "website": payload.website,
        "company_size": payload.company_size,
        "primary_service_category_id": _resolve_service_category_id(payload.primary_service_category_id),
    }
    sub_insert = supabase.table("subcontractors").insert(subcontractor_row).execute()
    sub_data = getattr(sub_insert, "data", [])
    if not sub_data:
        raise HTTPException(status_code=400, detail="Failed to create subcontractor record")
    subcontractor_id = sub_data[0]["id"]

    # Optional: insert locations
    if payload.locations:
        loc_rows: List[Dict[str, Any]] = []
        for loc in payload.locations:
            loc_rows.append(
                {
                    "subcontractor_id": subcontractor_id,
                    "address": loc.address,
                    "city": loc.city,
                    "state": loc.state,
                    "postal_code": loc.postal_code,
                    "latitude": loc.latitude,
                    "longitude": loc.longitude,
                    "is_primary": bool(loc.is_primary),
                }
            )
        if loc_rows:
            supabase.table("subcontractor_locations").insert(loc_rows).execute()

    # Optional: insert services
    if payload.services:
        svc_rows: List[Dict[str, Any]] = []
        for svc in payload.services:
            svc_rows.append(
                {
                    "subcontractor_id": subcontractor_id,
                    "service_category_id": _resolve_service_category_id(svc.service_category_id),
                    "hourly_rate": svc.hourly_rate,
                    "flat_rate": svc.flat_rate,
                    "is_active": svc.is_active if svc.is_active is not None else True,
                }
            )
        if svc_rows:
            supabase.table("subcontractor_services").insert(svc_rows).execute()

    _mark_onboarding_completed(user_id)

    return {
        "success": True,
        "message": "Onboarding completed for subcontractor",
        "user_id": user_id,
        "role": "subcontractor",
        "created_ids": {"subcontractor_id": subcontractor_id},
    }


def upload_pma_document(user_id: str, filename: str, file_bytes: bytes) -> Dict[str, Any]:
    """Upload a PMA document to Supabase Storage and create user_documents row.

    Returns: { document_id, url }
    """
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    bucket = settings.SUPABASE_STORAGE_BUCKET
    # Path: pma/{user_id}/{timestamp}_{filename}
    ts = int(time.time())
    safe_name = filename.replace("\\", "/").split("/")[-1]
    path = f"pma/{user_id}/{ts}_{safe_name}"

    try:
        # Prefer service key for private buckets
        from supabase import create_client
        storage_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_KEY)
        storage = storage_client.storage.from_(bucket)
        # Upload. If overwrite not desired, rely on unique timestamped path
        storage.upload(path, file_bytes)
        # Create a short-lived signed URL for immediate use
        signed_resp = storage.create_signed_url(path, 3600)
        signed_url = None
        if isinstance(signed_resp, dict):
            signed_url = (
                signed_resp.get("signedURL")
                or signed_resp.get("signed_url")
                or (signed_resp.get("data") or {}).get("signedUrl")
                or (signed_resp.get("data") or {}).get("signedURL")
                or (signed_resp.get("data") or {}).get("signed_url")
            )
        else:
            signed_url = str(signed_resp)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to upload PMA: {str(e)}")

    # Insert into user_documents with doc_type 'pma'
    try:
        # Store storage path in url column (for private buckets)
        doc = {
            "user_id": user_id,
            "doc_type": "pma",
            "url": path,
            "title": safe_name,
            "status": "pending",
        }
        res = supabase.table("user_documents").insert(doc).execute()
        data = getattr(res, "data", [])
        if not data:
            raise Exception("Failed to record document")
        document_id = data[0]["id"]
        return {"document_id": document_id, "path": path, "url": signed_url or ""}
    except Exception as e:
        # Best effort cleanup is omitted; path is unique and harmless if left orphaned
        raise HTTPException(status_code=400, detail=f"Failed to save document record: {str(e)}")


def create_signed_url_for_path(path: str, expires_in: int = 3600) -> str:
    """Create a signed URL for a file path in the configured bucket."""
    if not path:
        raise HTTPException(status_code=400, detail="path is required")
    try:
        from supabase import create_client
        storage_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_KEY)
        storage = storage_client.storage.from_(settings.SUPABASE_STORAGE_BUCKET)
        signed_resp = storage.create_signed_url(path, expires_in)
        if isinstance(signed_resp, dict):
            url = (
                signed_resp.get("signedURL")
                or signed_resp.get("signed_url")
                or (signed_resp.get("data") or {}).get("signedUrl")
                or (signed_resp.get("data") or {}).get("signedURL")
                or (signed_resp.get("data") or {}).get("signed_url")
            )
        else:
            url = str(signed_resp)
        if not url:
            raise Exception("Failed to create signed URL")
        return url
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not create signed URL: {str(e)}")


# -------- Service categories (list/create) --------
_SLUG_SAFE_RE = re.compile(r"[^a-z0-9-]+")


def _slugify(s: str) -> str:
    s = (s or "").strip().lower().replace(" ", "-")
    s = _SLUG_SAFE_RE.sub("", s)
    return s or "cat"


def list_service_categories() -> List[Dict[str, Any]]:
    qb = supabase.table("service_categories").select("id,name,slug,description,icon,is_active,sort_order")
    res = qb.order("sort_order").order("name").execute()
    return getattr(res, "data", []) or []


def create_service_category(name: str, slug: Optional[str] = None, description: Optional[str] = None, icon: Optional[str] = None) -> Dict[str, Any]:
    if not name or not name.strip():
        raise HTTPException(status_code=422, detail="name is required")

    name = name.strip()
    slug = (slug or _slugify(name))

    # Check existing by slug or name to keep unique constraints happy
    existing = (
        supabase.table("service_categories").select("id,name,slug,is_active").or_(f"slug.eq.{slug},name.eq.{name}").limit(1).execute()
    )
    data = getattr(existing, "data", [])
    if data:
        return data[0]

    payload = {
        "name": name,
        "slug": slug,
        "description": description,
        "icon": icon,
        "is_active": True,  # open taxonomy: immediately usable
        "sort_order": 0,
    }
    inserted = supabase.table("service_categories").insert(payload).execute()
    ins = getattr(inserted, "data", [])
    if not ins:
        raise HTTPException(status_code=400, detail="Failed to create service category")
    return ins[0]
