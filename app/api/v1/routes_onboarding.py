from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_active_user
from app.models.onboarding import (
    OnboardingRequest,
    OnboardingResponse,
    OnboardingStatusResponse,
)
from app.services.onboarding_service import (
    complete_first_time_onboarding,
    get_onboarding_status,
)

router = APIRouter()


@router.get(
    "",
    response_model=OnboardingStatusResponse,
    summary="Retrieve onboarding context",
)
async def read_onboarding_status(current_user=Depends(get_current_active_user)):
    """Return the current onboarding state for the authenticated user's company."""
    return get_onboarding_status(current_user.id)


@router.post(
    "",
    response_model=OnboardingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Complete first-time onboarding",
)
async def submit_onboarding(payload: OnboardingRequest, current_user=Depends(get_current_active_user)):
    """
    Persist the initial company configuration for an authenticated user.

    Raises 409 if onboarding was already completed for this user/company pair.
    """
    return complete_first_time_onboarding(current_user.id, payload, current_user.email)
