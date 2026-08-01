"""OPC-UA browse and status router."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_opcua_adapter,
    get_repo,
    require_admin,
    require_user,
)
from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter  # noqa: TC001
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository  # noqa: TC001
from smart_pid_domain.dtos.auth import UserClaims  # noqa: TC001
from smart_pid_domain.dtos.opcua import (
    OPCUABrowseResponse,
    OPCUAConnectRequest,
    OPCUAEndpointRequest,
    OPCUANodeInfo,
    OPCUASearchResponse,
    OPCUAStatusResponse,
)
from smart_pid_domain.enums import ConnectionState

router = APIRouter()


@router.get("/status", response_model=OPCUAStatusResponse)
async def get_status(
    _user: Annotated[UserClaims, Depends(require_user)],
    adapter: Annotated[OPCUAAdapter, Depends(get_opcua_adapter)],
) -> OPCUAStatusResponse:
    return OPCUAStatusResponse(state=adapter.state, endpoint=adapter.endpoint)


@router.get("/browse/{node_id:path}", response_model=OPCUABrowseResponse)
async def browse_children(
    node_id: str,
    _user: Annotated[UserClaims, Depends(require_admin)],
    adapter: Annotated[OPCUAAdapter, Depends(get_opcua_adapter)],
) -> OPCUABrowseResponse:
    try:
        children = adapter.browse_children(node_id)
    except ConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e),
        ) from e
    except TimeoutError as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(e),
        ) from e
    return OPCUABrowseResponse(
        parent_node_id=node_id,
        children=[OPCUANodeInfo(**c) for c in children],
    )


@router.get("/search", response_model=OPCUASearchResponse)
async def search_tags(
    q: Annotated[str, Query(min_length=1, max_length=200)],
    _user: Annotated[UserClaims, Depends(require_admin)],
    adapter: Annotated[OPCUAAdapter, Depends(get_opcua_adapter)],
) -> OPCUASearchResponse:
    try:
        results = adapter.search(q)
    except ConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e),
        ) from e
    except TimeoutError as e:
        # A recursive address-space walk can outlast the adapter budget on a
        # large server; that is a slow upstream, not an internal failure.
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(e),
        ) from e
    return OPCUASearchResponse(
        query=q,
        results=[OPCUANodeInfo(**r) for r in results],
    )


@router.put("/endpoint", response_model=OPCUAStatusResponse)
async def save_endpoint(
    body: OPCUAEndpointRequest,
    _user: Annotated[UserClaims, Depends(require_admin)],
    adapter: Annotated[OPCUAAdapter, Depends(get_opcua_adapter)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
) -> OPCUAStatusResponse:
    if not body.endpoint.startswith("opc.tcp://"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Endpoint must start with opc.tcp://",
        )
    await repo.set_meta("opcua_endpoint", body.endpoint)
    adapter.set_endpoint(body.endpoint)
    return OPCUAStatusResponse(state=adapter.state, endpoint=adapter.endpoint)


@router.post("/connect")
async def force_connect(
    _user: Annotated[UserClaims, Depends(require_admin)],
    adapter: Annotated[OPCUAAdapter, Depends(get_opcua_adapter)],
    body: OPCUAConnectRequest | None = None,
) -> OPCUAStatusResponse:
    if body and body.endpoint:
        adapter.set_endpoint(body.endpoint)
    adapter.stop()
    adapter.start()
    connected = adapter.wait_connected(timeout_s=5.0)
    return OPCUAStatusResponse(
        state=ConnectionState.ONLINE if connected else adapter.state,
        endpoint=adapter.endpoint,
    )


@router.post("/disconnect")
async def force_disconnect(
    _user: Annotated[UserClaims, Depends(require_admin)],
    adapter: Annotated[OPCUAAdapter, Depends(get_opcua_adapter)],
) -> OPCUAStatusResponse:
    adapter.stop()
    return OPCUAStatusResponse(state=adapter.state, endpoint=adapter.endpoint)
