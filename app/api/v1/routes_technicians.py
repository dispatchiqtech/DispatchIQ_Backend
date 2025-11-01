from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel, EmailStr

from app.api.deps import get_current_active_user
from app.db.supabase_client import supabase_admin
from app.services.work_order_service import _get_app_user

router = APIRouter()


class TechnicianCreate(BaseModel):
    first_name: str
    last_name: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    default_property_id: Optional[str] = None
    shift: Optional[str] = None
    merit_percent: int = 100
    availability: str = "available"


class TechnicianUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    default_property_id: Optional[str] = None
    shift: Optional[str] = None
    merit_percent: Optional[int] = None
    availability: Optional[str] = None


class TechnicianResponse(BaseModel):
    id: str
    company_id: str
    user_id: Optional[str] = None
    first_name: str
    last_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    default_property_id: Optional[str] = None
    default_property_name: Optional[str] = None
    shift: Optional[str] = None
    merit_percent: int
    availability: str


@router.get("/technicians", response_model=List[TechnicianResponse])
async def get_technicians(current_user=Depends(get_current_active_user)):
    """Get all technicians for the current user's company."""
    app_user = _get_app_user(current_user.id)
    if not app_user or not app_user.get("company_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with a company.",
        )
    
    company_id = app_user["company_id"]
    
    # Get technicians with property name join
    res = (
        supabase_admin.table("technicians")
        .select(
            "id,company_id,user_id,first_name,last_name,phone,email,default_property_id,shift,merit_percent,availability"
        )
        .eq("company_id", company_id)
        .order("last_name,first_name")
        .execute()
    )
    
    data = getattr(res, "data", []) or []
    
    # Get property names for technicians with default_property_id
    property_ids = [row["default_property_id"] for row in data if row.get("default_property_id")]
    property_names = {}
    if property_ids:
        prop_res = (
            supabase_admin.table("properties")
            .select("id,name")
            .in_("id", property_ids)
            .execute()
        )
        prop_data = getattr(prop_res, "data", []) or []
        property_names = {row["id"]: row["name"] for row in prop_data}
    
    # Build response with property names
    technicians = []
    for row in data:
        tech = TechnicianResponse(
            id=row["id"],
            company_id=row["company_id"],
            user_id=row.get("user_id"),
            first_name=row["first_name"],
            last_name=row["last_name"],
            phone=row.get("phone"),
            email=row.get("email"),
            default_property_id=row.get("default_property_id"),
            default_property_name=property_names.get(row.get("default_property_id")) if row.get("default_property_id") else None,
            shift=row.get("shift"),
            merit_percent=row.get("merit_percent", 100),
            availability=row.get("availability", "available"),
        )
        technicians.append(tech)
    
    return technicians


@router.post("/technicians", response_model=TechnicianResponse, status_code=status.HTTP_201_CREATED)
async def create_technician(
    tech_data: TechnicianCreate,
    current_user=Depends(get_current_active_user)
):
    """Create a new technician."""
    app_user = _get_app_user(current_user.id)
    if not app_user or not app_user.get("company_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with a company.",
        )
    
    company_id = app_user["company_id"]
    
    # Verify default_property_id belongs to company if provided
    if tech_data.default_property_id:
        prop_res = (
            supabase_admin.table("properties")
            .select("id")
            .eq("id", tech_data.default_property_id)
            .eq("company_id", company_id)
            .execute()
        )
        prop_data = getattr(prop_res, "data", []) or []
        if not prop_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Property not found or does not belong to your company",
            )
    
    insert_data = {
        "company_id": company_id,
        "first_name": tech_data.first_name,
        "last_name": tech_data.last_name,
        "phone": tech_data.phone,
        "email": tech_data.email,
        "default_property_id": tech_data.default_property_id,
        "shift": tech_data.shift,
        "merit_percent": tech_data.merit_percent,
        "availability": tech_data.availability,
    }
    
    res = (
        supabase_admin.table("technicians")
        .insert(insert_data)
        .execute()
    )
    
    data = getattr(res, "data", []) or []
    if not data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create technician",
        )
    
    row = data[0]
    # Get property name if exists
    property_name = None
    if row.get("default_property_id"):
        prop_res = (
            supabase_admin.table("properties")
            .select("name")
            .eq("id", row["default_property_id"])
            .execute()
        )
        prop_data = getattr(prop_res, "data", []) or []
        if prop_data:
            property_name = prop_data[0]["name"]
    
    return TechnicianResponse(
        id=row["id"],
        company_id=row["company_id"],
        user_id=row.get("user_id"),
        first_name=row["first_name"],
        last_name=row["last_name"],
        phone=row.get("phone"),
        email=row.get("email"),
        default_property_id=row.get("default_property_id"),
        default_property_name=property_name,
        shift=row.get("shift"),
        merit_percent=row.get("merit_percent", 100),
        availability=row.get("availability", "available"),
    )


@router.put("/technicians/{technician_id}", response_model=TechnicianResponse)
async def update_technician(
    technician_id: str,
    tech_data: TechnicianUpdate,
    current_user=Depends(get_current_active_user)
):
    """Update a technician."""
    app_user = _get_app_user(current_user.id)
    if not app_user or not app_user.get("company_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with a company.",
        )
    
    company_id = app_user["company_id"]
    
    # Verify technician belongs to company
    check_res = (
        supabase_admin.table("technicians")
        .select("id")
        .eq("id", technician_id)
        .eq("company_id", company_id)
        .execute()
    )
    
    check_data = getattr(check_res, "data", []) or []
    if not check_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Technician not found",
        )
    
    # Verify default_property_id belongs to company if provided
    if tech_data.default_property_id:
        prop_res = (
            supabase_admin.table("properties")
            .select("id")
            .eq("id", tech_data.default_property_id)
            .eq("company_id", company_id)
            .execute()
        )
        prop_data = getattr(prop_res, "data", []) or []
        if not prop_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Property not found or does not belong to your company",
            )
    
    # Build update dict
    update_dict = {}
    if tech_data.first_name is not None:
        update_dict["first_name"] = tech_data.first_name
    if tech_data.last_name is not None:
        update_dict["last_name"] = tech_data.last_name
    if tech_data.phone is not None:
        update_dict["phone"] = tech_data.phone
    if tech_data.email is not None:
        update_dict["email"] = tech_data.email
    if tech_data.default_property_id is not None:
        update_dict["default_property_id"] = tech_data.default_property_id
    if tech_data.shift is not None:
        update_dict["shift"] = tech_data.shift
    if tech_data.merit_percent is not None:
        update_dict["merit_percent"] = tech_data.merit_percent
    if tech_data.availability is not None:
        update_dict["availability"] = tech_data.availability
    
    if not update_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    
    res = (
        supabase_admin.table("technicians")
        .update(update_dict)
        .eq("id", technician_id)
        .eq("company_id", company_id)
        .execute()
    )
    
    data = getattr(res, "data", []) or []
    if not data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update technician",
        )
    
    row = data[0]
    # Get property name if exists
    property_name = None
    if row.get("default_property_id"):
        prop_res = (
            supabase_admin.table("properties")
            .select("name")
            .eq("id", row["default_property_id"])
            .execute()
        )
        prop_data = getattr(prop_res, "data", []) or []
        if prop_data:
            property_name = prop_data[0]["name"]
    
    return TechnicianResponse(
        id=row["id"],
        company_id=row["company_id"],
        user_id=row.get("user_id"),
        first_name=row["first_name"],
        last_name=row["last_name"],
        phone=row.get("phone"),
        email=row.get("email"),
        default_property_id=row.get("default_property_id"),
        default_property_name=property_name,
        shift=row.get("shift"),
        merit_percent=row.get("merit_percent", 100),
        availability=row.get("availability", "available"),
    )


@router.delete("/technicians/{technician_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_technician(
    technician_id: str,
    current_user=Depends(get_current_active_user)
):
    """Delete a technician."""
    app_user = _get_app_user(current_user.id)
    if not app_user or not app_user.get("company_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with a company.",
        )
    
    company_id = app_user["company_id"]
    
    # Verify technician belongs to company
    check_res = (
        supabase_admin.table("technicians")
        .select("id")
        .eq("id", technician_id)
        .eq("company_id", company_id)
        .execute()
    )
    
    check_data = getattr(check_res, "data", []) or []
    if not check_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Technician not found",
        )
    
    supabase_admin.table("technicians").delete().eq("id", technician_id).eq("company_id", company_id).execute()
    
    return None

