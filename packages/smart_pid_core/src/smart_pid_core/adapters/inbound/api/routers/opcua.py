"""OPC-UA browse and status router."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_current_user,
    get_opcua_adapter,
)
from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter  # noqa: TC001
from smart_pid_domain.dtos.auth import UserClaims  # noqa: TC001
from smart_pid_domain.dtos.opcua import (
    OPCUABrowseResponse,
    OPCUANodeInfo,
    OPCUASearchResponse,
    OPCUAStatusResponse,
)

router = APIRouter()


@router.get("/status", response_model=OPCUAStatusResponse)
async def get_status(
    _user: Annotated[UserClaims, Depends(get_current_user)],
    adapter: Annotated[OPCUAAdapter, Depends(get_opcua_adapter)],
) -> OPCUAStatusResponse:
    return OPCUAStatusResponse(state=adapter.state, endpoint=adapter.endpoint)


@router.get("/browse/{node_id:path}", response_model=OPCUABrowseResponse)
async def browse_children(
    node_id: str,
    _user: Annotated[UserClaims, Depends(get_current_user)],
    adapter: Annotated[OPCUAAdapter, Depends(get_opcua_adapter)],
) -> OPCUABrowseResponse:
    try:
        children = adapter.browse_children(node_id)
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    return OPCUABrowseResponse(
        parent_node_id=node_id,
        children=[OPCUANodeInfo(**c) for c in children],
    )


@router.get("/search", response_model=OPCUASearchResponse)
async def search_tags(
    q: Annotated[str, Query(min_length=1, max_length=200)],
    _user: Annotated[UserClaims, Depends(get_current_user)],
    adapter: Annotated[OPCUAAdapter, Depends(get_opcua_adapter)],
) -> OPCUASearchResponse:
    try:
        results = adapter.search(q)
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    return OPCUASearchResponse(
        query=q,
        results=[OPCUANodeInfo(**r) for r in results],
    )


@router.post("/connect")
async def force_reconnect(
    _user: Annotated[UserClaims, Depends(get_current_user)],
    adapter: Annotated[OPCUAAdapter, Depends(get_opcua_adapter)],
) -> dict[str, str]:
    adapter.stop()
    adapter.start()
    return {"detail": "Reconnection initiated"}
