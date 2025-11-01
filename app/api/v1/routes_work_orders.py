from fastapi import APIRouter, Depends, status, Query
from typing import Optional

from app.api.deps import get_current_active_user
from app.models.work_orders import (
    WorkOrderCreate,
    WorkOrderOptionsResponse,
    WorkOrderResponse,
    WorkOrderListResponse,
    WorkOrderUpdate,
)
from app.services.work_order_service import (
    get_work_order_options,
    create_work_order,
    get_work_orders,
    update_work_order,
)

router = APIRouter()


@router.get(
    "",
    response_model=WorkOrderListResponse,
    summary="List work orders for the authenticated company",
)
async def list_work_orders(
    current_user=Depends(get_current_active_user),
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    limit: int = Query(20, ge=1, le=100, description="Limit number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    Retrieve work orders for the authenticated company with optional filtering.
    """
    return get_work_orders(
        current_user.id,
        status_filter=status,
        priority_filter=priority,
        limit=limit,
        offset=offset,
    )


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


@router.put(
    "/{work_order_id}",
    response_model=WorkOrderResponse,
    summary="Update a work order",
)
async def update_work_order_route(
    work_order_id: str,
    payload: WorkOrderUpdate,
    current_user=Depends(get_current_active_user),
):
    """
    Update a work order (e.g., assign technician, update status).
    """
    return update_work_order(current_user.id, work_order_id, payload)
