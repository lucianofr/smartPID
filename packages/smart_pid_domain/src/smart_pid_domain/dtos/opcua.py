"""OPC-UA request/response DTOs."""
from __future__ import annotations

from pydantic import BaseModel

from smart_pid_domain.enums import ConnectionState  # noqa: TC001


class OPCUAStatusResponse(BaseModel):
    state: ConnectionState
    endpoint: str


class OPCUANodeInfo(BaseModel):
    node_id: str
    display_name: str
    node_class: str


class OPCUABrowseResponse(BaseModel):
    parent_node_id: str
    children: list[OPCUANodeInfo]


class OPCUASearchResponse(BaseModel):
    query: str
    results: list[OPCUANodeInfo]
