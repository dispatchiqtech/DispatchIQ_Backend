from typing import List, Optional, Literal
from pydantic import BaseModel, Field, constr


class Address(BaseModel):
    address: str
    city: str
    state: str
    postal_code: Optional[str] = None
    country: Optional[str] = Field(default="USA")


class OwnerOnboardingRequest(BaseModel):
    # Profile basics
    first_name: constr(strip_whitespace=True, min_length=1)
    last_name: constr(strip_whitespace=True, min_length=1)
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = "USA"

    # Role within combined route
    role: Literal["owner", "property_manager"] = "owner"

    # Owner specific
    company_name: Optional[str] = None
    company_registration_number: Optional[str] = None
    billing_address: Optional[str] = None
    payment_terms: Optional[int] = Field(default=30, ge=0)
    has_pma: Optional[bool] = False
    pma_document_url: Optional[str] = None


class SubcontractorServiceItem(BaseModel):
    service_category_id: str
    hourly_rate: Optional[float] = Field(default=None, ge=0)
    flat_rate: Optional[float] = Field(default=None, ge=0)
    is_active: Optional[bool] = True


class SubcontractorLocationItem(Address):
    is_primary: Optional[bool] = False
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class SubcontractorOnboardingRequest(BaseModel):
    # Profile basics
    first_name: constr(strip_whitespace=True, min_length=1)
    last_name: constr(strip_whitespace=True, min_length=1)
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = "USA"

    # Business
    subcontractor_type: Literal["individual", "company"] = "individual"
    company_name: Optional[str] = None
    business_registration_number: Optional[str] = None
    service_radius_km: Optional[int] = Field(default=50, ge=0)
    primary_service_category_id: Optional[str] = None
    tin: Optional[str] = None
    website: Optional[str] = None
    company_size: Optional[str] = None

    # Collections
    locations: Optional[List[SubcontractorLocationItem]] = None
    services: Optional[List[SubcontractorServiceItem]] = None


class OnboardingResult(BaseModel):
    success: bool
    message: str
    user_id: str
    role: str
    created_ids: Optional[dict] = None


class DocumentUploadResponse(BaseModel):
    document_id: str
    path: str  # storage path in bucket
    url: str   # signed URL for temporary access
    doc_type: str = "pma"


class CategoryCreateRequest(BaseModel):
    name: constr(strip_whitespace=True, min_length=2)
    slug: Optional[constr(strip_whitespace=True, min_length=2)] = None
    description: Optional[str] = None
    icon: Optional[str] = None


class CategoryResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    icon: Optional[str] = None
    is_active: bool
