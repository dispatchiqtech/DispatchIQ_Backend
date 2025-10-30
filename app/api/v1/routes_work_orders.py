from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_active_user
from app.models.work_orders import WorkOrderCreate, WorkOrderOptionsResponse, WorkOrderResponse
from app.services.work_order_service import get_work_order_options, create_work_order

router = APIRouter()


@router.get(
    "/options",
    response_model=WorkOrderOptionsResponse,
    summary="List properties and units for work order creation",
)
async def read_work_order_options(current_user=Depends(get_current_active_user)):
    """
    Retrieve properties and unit options for the authenticated company.
    """
    return get_work_order_options(current_user.id)


@router.post(
    "",
    response_model=WorkOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new work order",
)
async def create_work_order_route(
    payload: WorkOrderCreate,
    current_user=Depends(get_current_active_user),
):
    """
    Create a work order scoped to the authenticated user's company.
    """
    return create_work_order(current_user.id, payload)
