from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File
from app.api.deps import get_current_active_user, limiter
from app.models.onboarding import (
    OwnerOnboardingRequest,
    SubcontractorOnboardingRequest,
    OnboardingResult,
    DocumentUploadResponse,
    CategoryCreateRequest,
    CategoryResponse,
)
from app.services.onboarding_service import (
    onboard_owner_or_pm,
    onboard_subcontractor,
    upload_pma_document,
    create_signed_url_for_path,
    list_service_categories,
    create_service_category,
)

router = APIRouter()

@router.post(
    "/owner",
    response_model=OnboardingResult,
    status_code=status.HTTP_201_CREATED,
    summary="Onboard owner/property manager",
)
@limiter.limit("5/minute")
async def onboard_owner_pm(
    request: Request,
    payload: OwnerOnboardingRequest,
    current_user = Depends(get_current_active_user),
):
    """Create owner/PM profile. PMs must upload PMA first and pass the storage path in `pma_document_url`."""
    try:
        result = onboard_owner_or_pm(current_user.id, payload)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/subcontractor",
    response_model=OnboardingResult,
    status_code=status.HTTP_201_CREATED,
    summary="Onboard subcontractor",
)
@limiter.limit("5/minute")
async def onboard_subcontractor_route(
    request: Request,
    payload: SubcontractorOnboardingRequest,
    current_user = Depends(get_current_active_user),
):
    """Create subcontractor profile. Optional locations/services can be provided."""
    try:
        result = onboard_subcontractor(current_user.id, payload)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/owner/pma",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload PMA document",
)
@limiter.limit("5/minute")
async def upload_owner_pma(
    request: Request,
    file: UploadFile = File(...),
    current_user = Depends(get_current_active_user),
):
    """Upload PMA to private storage. Returns `document_id`, `path` (store in onboarding), and 1h signed `url`."""
    try:
        content = await file.read()
        result = upload_pma_document(current_user.id, file.filename, content)
        return {
            "document_id": result["document_id"],
            "path": result.get("path", ""),
            "url": result.get("url", ""),
            "doc_type": "pma",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/file/signed-url",
    summary="Create signed URL for stored file",
)
@limiter.limit("15/minute")
async def get_signed_url(request: Request, path: str, expires_in: int = 3600, current_user = Depends(get_current_active_user)):
    """Generate a short-lived signed URL for a storage `path` in the PMA bucket."""
    try:
        url = create_signed_url_for_path(path, expires_in)
        return {"url": url, "expires_in": expires_in}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/categories",
    response_model=list[CategoryResponse],
    summary="List service categories",
)
@limiter.limit("30/minute")
async def get_categories(request: Request, current_user = Depends(get_current_active_user)):
    """List all service categories (active and inactive)."""
    items = list_service_categories()
    return items


@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new service category",
)
@limiter.limit("10/minute")
async def post_category(request: Request, payload: CategoryCreateRequest, current_user = Depends(get_current_active_user)):
    """Create a new service category. Immediately available for selection."""
    created = create_service_category(payload.name, payload.slug, payload.description, payload.icon)
    return created

