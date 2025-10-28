from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field, EmailStr, constr, field_validator, AliasChoices, ConfigDict

HourString = constr(pattern=r"^\d{2}:\d{2}$")
VendorCategory = Literal["hvac", "plumbing", "electrical", "general"]
IntakeMethod = Literal["email", "manual"]
OnCallRotation = Literal["weekly", "custom"]


class AdminAccount(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: EmailStr
    password: constr(min_length=8, max_length=64)
    first_name: Optional[constr(strip_whitespace=True, min_length=1)] = Field(
        default=None,
        validation_alias=AliasChoices("first_name", "firstName"),
        serialization_alias="firstName",
    )
    last_name: Optional[constr(strip_whitespace=True, min_length=1)] = Field(
        default=None,
        validation_alias=AliasChoices("last_name", "lastName"),
        serialization_alias="lastName",
    )


class PropertyCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: constr(strip_whitespace=True, min_length=1)
    address: constr(strip_whitespace=True, min_length=1)
    notes: Optional[str] = None


class TechnicianCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    first_name: constr(strip_whitespace=True, min_length=1) = Field(
        validation_alias=AliasChoices("first_name", "firstName"),
        serialization_alias="firstName",
    )
    last_name: constr(strip_whitespace=True, min_length=1) = Field(
        validation_alias=AliasChoices("last_name", "lastName"),
        serialization_alias="lastName",
    )
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    shift: Optional[str] = None
    default_property: Optional[str] = Field(
        default=None,
        description="Property reference by UUID or name, or 'all' for all properties.",
        validation_alias=AliasChoices("default_property", "defaultProperty"),
        serialization_alias="defaultProperty",
    )
    user_id: Optional[str] = Field(
        default=None,
        description="Optional Supabase auth user id if this technician has login access.",
        validation_alias=AliasChoices("user_id", "userId"),
        serialization_alias="userId",
    )
    merit_percent: Optional[int] = Field(
        default=100,
        ge=0,
        validation_alias=AliasChoices("merit_percent", "meritPercent"),
        serialization_alias="meritPercent",
    )


class EmergencyVendorCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    category: VendorCategory
    name: constr(strip_whitespace=True, min_length=1)
    phone: Optional[str] = None


class OnboardingRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    company_name: Optional[constr(strip_whitespace=True, min_length=1)] = Field(
        default=None,
        validation_alias=AliasChoices("company_name", "companyName"),
        serialization_alias="companyName",
    )
    timezone: Optional[constr(strip_whitespace=True, min_length=1)] = None
    work_hours_start: HourString = Field(
        validation_alias=AliasChoices("work_hours_start", "workHoursStart"),
        serialization_alias="workHoursStart",
    )
    work_hours_end: HourString = Field(
        validation_alias=AliasChoices("work_hours_end", "workHoursEnd"),
        serialization_alias="workHoursEnd",
    )
    auto_assign: bool = Field(
        default=True,
        validation_alias=AliasChoices("auto_assign", "autoAssign"),
        serialization_alias="autoAssign",
    )
    on_call_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("on_call_enabled", "onCallEnabled"),
        serialization_alias="onCallEnabled",
    )
    on_call_rotation: OnCallRotation = Field(
        default="weekly",
        validation_alias=AliasChoices("on_call_rotation", "onCallRotation"),
        serialization_alias="onCallRotation",
    )
    intake_method: IntakeMethod = Field(
        default="manual",
        validation_alias=AliasChoices("intake_method", "intakeMethod"),
        serialization_alias="intakeMethod",
    )
    collect_pte: bool = Field(
        default=True,
        validation_alias=AliasChoices("collect_pte", "collectPte"),
        serialization_alias="collectPte",
    )
    collect_window: bool = Field(
        default=True,
        validation_alias=AliasChoices("collect_window", "collectWindow"),
        serialization_alias="collectWindow",
    )
    admin_account: Optional[AdminAccount] = Field(
        default=None,
        validation_alias=AliasChoices("admin_account", "adminAccount"),
        serialization_alias="adminAccount",
    )
    properties: List[PropertyCreate] = Field(default_factory=list)
    technicians: List[TechnicianCreate] = Field(default_factory=list)
    emergency_vendors: List[EmergencyVendorCreate] = Field(
        default_factory=list,
        validation_alias=AliasChoices("emergency_vendors", "emergencyVendors"),
        serialization_alias="emergencyVendors",
    )

    @field_validator("work_hours_start", "work_hours_end")
    @classmethod
    def validate_work_hours(cls, value: str) -> str:
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError:
            raise ValueError("work hours must use HH:MM 24-hour format (00-23:00-59)")
        return value


class PropertySummary(BaseModel):
    id: str
    name: str
    address: Optional[str] = None
    notes: Optional[str] = None


class TechnicianSummary(BaseModel):
    id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    shift: Optional[str] = None
    default_property_id: Optional[str] = None
    default_property_name: Optional[str] = None


class EmergencyVendorSummary(BaseModel):
    id: str
    category: VendorCategory
    name: str
    phone: Optional[str] = None


class OnboardingSummary(BaseModel):
    company_name: str
    timezone: str
    work_hours_start: str
    work_hours_end: str
    auto_assign: bool
    on_call_enabled: bool
    on_call_rotation: OnCallRotation
    intake_method: IntakeMethod
    collect_pte: bool
    collect_window: bool
    properties_total: int
    technicians_total: int
    emergency_vendors_total: int
    admin_user_created: bool


class OnboardingResponse(BaseModel):
    success: bool
    company_id: str
    summary: OnboardingSummary


class OnboardingStatusResponse(BaseModel):
    company_id: str
    company_name: str
    timezone: str
    timezone_label: str
    work_hours_start: str
    work_hours_end: str
    auto_assign: bool
    on_call_enabled: bool
    on_call_rotation: OnCallRotation
    intake_method: IntakeMethod
    collect_pte: bool
    collect_window: bool
    properties: List[PropertySummary] = Field(default_factory=list)
    technicians: List[TechnicianSummary] = Field(default_factory=list)
    emergency_vendors: List[EmergencyVendorSummary] = Field(default_factory=list)
    onboarding_completed: bool
