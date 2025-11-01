from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel

from app.api.deps import get_current_active_user
from app.db.supabase_client import supabase_admin
from app.services.work_order_service import _get_app_user

router = APIRouter()


class PropertyCreate(BaseModel):
    name: str
    address: str
    notes: Optional[str] = None


class PropertyUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class PropertyResponse(BaseModel):
    id: str
    company_id: str
    name: str
    address: str
    notes: Optional[str] = None


class UnitCreate(BaseModel):
    property_id: str
    label: str
    notes: Optional[str] = None
    is_active: bool = True


class UnitUpdate(BaseModel):
    label: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class UnitResponse(BaseModel):
    id: str
    property_id: str
    label: str
    notes: Optional[str] = None
    is_active: bool


@router.get("/properties", response_model=List[PropertyResponse])
async def get_properties(current_user=Depends(get_current_active_user)):
    """Get all properties for the current user's company."""
    app_user = _get_app_user(current_user.id)
    if not app_user or not app_user.get("company_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with a company.",
        )
    
    company_id = app_user["company_id"]
    
    res = (
        supabase_admin.table("properties")
        .select("id,company_id,name,address,notes")
        .eq("company_id", company_id)
        .order("name")
        .execute()
    )
    
    data = getattr(res, "data", []) or []
    return [PropertyResponse(**row) for row in data]


@router.post("/properties", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_property(
    property_data: PropertyCreate,
    current_user=Depends(get_current_active_user)
):
    """Create a new property."""
    app_user = _get_app_user(current_user.id)
    if not app_user or not app_user.get("company_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with a company.",
        )
    
    company_id = app_user["company_id"]
    
    res = (
        supabase_admin.table("properties")
        .insert({
            "company_id": company_id,
            "name": property_data.name,
            "address": property_data.address,
            "notes": property_data.notes,
        })
        .execute()
    )
    
    data = getattr(res, "data", []) or []
    if not data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create property",
        )
    
    return PropertyResponse(**data[0])


@router.put("/properties/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: str,
    property_data: PropertyUpdate,
    current_user=Depends(get_current_active_user)
):
    """Update a property."""
    app_user = _get_app_user(current_user.id)
    if not app_user or not app_user.get("company_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with a company.",
        )
    
    company_id = app_user["company_id"]
    
    # Verify property belongs to company
    check_res = (
        supabase_admin.table("properties")
        .select("id")
        .eq("id", property_id)
        .eq("company_id", company_id)
        .execute()
    )
    
    check_data = getattr(check_res, "data", []) or []
    if not check_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )
    
    # Build update dict
    update_dict = {}
    if property_data.name is not None:
        update_dict["name"] = property_data.name
    if property_data.address is not None:
        update_dict["address"] = property_data.address
    if property_data.notes is not None:
        update_dict["notes"] = property_data.notes
    
    if not update_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    
    res = (
        supabase_admin.table("properties")
        .update(update_dict)
        .eq("id", property_id)
        .eq("company_id", company_id)
        .execute()
    )
    
    data = getattr(res, "data", []) or []
    if not data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update property",
        )
    
    return PropertyResponse(**data[0])


@router.delete("/properties/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(
    property_id: str,
    current_user=Depends(get_current_active_user)
):
    """Delete a property."""
    app_user = _get_app_user(current_user.id)
    if not app_user or not app_user.get("company_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with a company.",
        )
    
    company_id = app_user["company_id"]
    
    # Verify property belongs to company
    check_res = (
        supabase_admin.table("properties")
        .select("id")
        .eq("id", property_id)
        .eq("company_id", company_id)
        .execute()
    )
    
    check_data = getattr(check_res, "data", []) or []
    if not check_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )
    
    # Delete property (cascade will handle units)
    supabase_admin.table("properties").delete().eq("id", property_id).eq("company_id", company_id).execute()
    
    return None


@router.get("/properties/{property_id}/units", response_model=List[UnitResponse])
async def get_units(
    property_id: str,
    current_user=Depends(get_current_active_user)
):
    """Get all units for a property."""
    app_user = _get_app_user(current_user.id)
    if not app_user or not app_user.get("company_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with a company.",
        )
    
    company_id = app_user["company_id"]
    
    # Verify property belongs to company
    check_res = (
        supabase_admin.table("properties")
        .select("id")
        .eq("id", property_id)
        .eq("company_id", company_id)
        .execute()
    )
    
    check_data = getattr(check_res, "data", []) or []
    if not check_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )
    
    res = (
        supabase_admin.table("property_units")
        .select("id,property_id,label,notes,is_active")
        .eq("property_id", property_id)
        .eq("company_id", company_id)
        .order("label")
        .execute()
    )
    
    data = getattr(res, "data", []) or []
    return [UnitResponse(**row) for row in data]


@router.post("/units", response_model=UnitResponse, status_code=status.HTTP_201_CREATED)
async def create_unit(
    unit_data: UnitCreate,
    current_user=Depends(get_current_active_user)
):
    """Create a new unit for a property."""
    app_user = _get_app_user(current_user.id)
    if not app_user or not app_user.get("company_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with a company.",
        )
    
    company_id = app_user["company_id"]
    
    # Verify property belongs to company
    check_res = (
        supabase_admin.table("properties")
        .select("id")
        .eq("id", unit_data.property_id)
        .eq("company_id", company_id)
        .execute()
    )
    
    check_data = getattr(check_res, "data", []) or []
    if not check_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )
    
    res = (
        supabase_admin.table("property_units")
        .insert({
            "company_id": company_id,
            "property_id": unit_data.property_id,
            "label": unit_data.label,
            "notes": unit_data.notes,
            "is_active": unit_data.is_active,
        })
        .execute()
    )
    
    data = getattr(res, "data", []) or []
    if not data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create unit",
        )
    
    return UnitResponse(**data[0])


@router.put("/units/{unit_id}", response_model=UnitResponse)
async def update_unit(
    unit_id: str,
    unit_data: UnitUpdate,
    current_user=Depends(get_current_active_user)
):
    """Update a unit."""
    app_user = _get_app_user(current_user.id)
    if not app_user or not app_user.get("company_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with a company.",
        )
    
    company_id = app_user["company_id"]
    
    # Verify unit belongs to company
    check_res = (
        supabase_admin.table("property_units")
        .select("id")
        .eq("id", unit_id)
        .eq("company_id", company_id)
        .execute()
    )
    
    check_data = getattr(check_res, "data", []) or []
    if not check_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unit not found",
        )
    
    # Build update dict
    update_dict = {}
    if unit_data.label is not None:
        update_dict["label"] = unit_data.label
    if unit_data.notes is not None:
        update_dict["notes"] = unit_data.notes
    if unit_data.is_active is not None:
        update_dict["is_active"] = unit_data.is_active
    
    if not update_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    
    res = (
        supabase_admin.table("property_units")
        .update(update_dict)
        .eq("id", unit_id)
        .eq("company_id", company_id)
        .execute()
    )
    
    data = getattr(res, "data", []) or []
    if not data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update unit",
        )
    
    return UnitResponse(**data[0])


@router.delete("/units/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_unit(
    unit_id: str,
    current_user=Depends(get_current_active_user)
):
    """Delete a unit."""
    app_user = _get_app_user(current_user.id)
    if not app_user or not app_user.get("company_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with a company.",
        )
    
    company_id = app_user["company_id"]
    
    # Verify unit belongs to company
    check_res = (
        supabase_admin.table("property_units")
        .select("id")
        .eq("id", unit_id)
        .eq("company_id", company_id)
        .execute()
    )
    
    check_data = getattr(check_res, "data", []) or []
    if not check_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unit not found",
        )
    
    supabase_admin.table("property_units").delete().eq("id", unit_id).eq("company_id", company_id).execute()
    
    return None


