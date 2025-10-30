from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field, constr, EmailStr, ConfigDict, AliasChoices, field_validator


PriorityLiteral = Literal["routine", "emergency"]


class PropertyUnitOption(BaseModel):
    id: str
    label: str
    notes: Optional[str] = None
    is_active: bool = True


class PropertyOption(BaseModel):
    id: str
    name: str
    address: Optional[str] = None
    notes: Optional[str] = None
    units: List[PropertyUnitOption] = Field(default_factory=list)


class WorkOrderOptionsResponse(BaseModel):
    company_id: str
    properties: List[PropertyOption] = Field(default_factory=list)


class WorkOrderCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    property_id: constr(strip_whitespace=True, min_length=1) = Field(
        validation_alias=AliasChoices("property_id", "propertyId"),
        serialization_alias="propertyId",
    )
    unit_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("unit_id", "unitId"),
        serialization_alias="unitId",
    )
    unit_label: Optional[constr(strip_whitespace=True, min_length=1)] = Field(
        default=None,
        validation_alias=AliasChoices("unit_label", "unitLabel"),
        serialization_alias="unitLabel",
    )
    issue: constr(strip_whitespace=True, min_length=3)
    priority: PriorityLiteral = "routine"
    pte: Optional[bool] = None
    preferred_window: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("preferred_window", "preferredWindow"),
        serialization_alias="preferredWindow",
    )
    tenant_name: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("tenant_name", "tenantName"),
        serialization_alias="tenantName",
    )
    tenant_phone: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("tenant_phone", "tenantPhone"),
        serialization_alias="tenantPhone",
    )
    assigned_technician_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("assigned_technician_id", "assignedTechnicianId"),
        serialization_alias="assignedTechnicianId",
    )

    @field_validator("priority")
    @classmethod
    def priority_lower(cls, value: str) -> str:
        return value.lower()


class WorkOrderResponse(BaseModel):
    id: str
    company_id: str
    property_id: str
    property_name: Optional[str] = None
    unit_id: Optional[str] = None
    unit_label: Optional[str] = None
    issue: str
    priority: str
    status: str
    pte: Optional[bool] = None
    preferred_window: Optional[str] = None
    tenant_name: Optional[str] = None
    tenant_phone: Optional[str] = None
    assigned_technician_id: Optional[str] = None
    created_at: datetime
