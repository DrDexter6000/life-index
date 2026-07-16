"""Build the optional generic MCP projection from the canonical registry."""

from __future__ import annotations

import inspect
from dataclasses import MISSING, fields
from typing import Annotated, Any, Callable, cast, get_type_hints

from tools.host_agent_channel.dispatcher import dispatch
from tools.host_agent_channel.registry import (
    CAPABILITY_REGISTRY,
    CapabilityDefinition,
    projection_annotations,
)


class OptionalMcpDependencyError(RuntimeError):
    """Raised only when the optional projection entrypoint lacks its SDK."""


def _load_mcp_components() -> tuple[Any, Any]:
    """Import the optional SDK only when a projection is actually created."""
    try:
        from mcp.server.fastmcp import FastMCP
        from mcp.types import ToolAnnotations
    except ModuleNotFoundError as exc:
        raise OptionalMcpDependencyError(
            "The optional MCP projection requires mcp==1.27.2; "
            "install Life Index with the mcp extra."
        ) from exc
    return FastMCP, ToolAnnotations


def _registry_tool_callable(
    capability: CapabilityDefinition, field_factory: Callable[..., Any]
) -> Callable[..., dict[str, Any]]:
    """Create an SDK callable whose signature comes exclusively from the registry."""
    type_hints = get_type_hints(capability.params_type)
    signature_params: list[inspect.Parameter] = []
    annotated = cast(Any, Annotated)
    for definition in fields(capability.params_type):
        default = definition.default
        if default is MISSING:
            default = inspect.Parameter.empty
        annotation = annotated[
            type_hints[definition.name],
            field_factory(description=definition.metadata["description"]),
        ]
        signature_params.append(
            inspect.Parameter(
                definition.name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=default,
                annotation=annotation,
            )
        )

    def invoke(**params: Any) -> dict[str, Any]:
        return dispatch(
            capability.method_id,
            {name: value for name, value in params.items() if value is not None},
            emit_validation_trace=False,
        )

    invoke.__name__ = capability.method_id.replace(".", "_")
    invoke.__doc__ = capability.description
    invoke.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        parameters=signature_params,
        return_annotation=dict[str, Any],
    )
    return invoke


def create_mcp_server() -> Any:
    """Create a stdio-capable MCP server with exactly the registered tools."""
    FastMCP, ToolAnnotations = _load_mcp_components()
    from pydantic import Field

    server = FastMCP("Life Index Core Projection")
    for capability in CAPABILITY_REGISTRY.values():
        server.add_tool(
            _registry_tool_callable(capability, Field),
            name=capability.method_id,
            description=capability.description,
            annotations=ToolAnnotations(**projection_annotations(capability)),
            structured_output=False,
        )
    return server


def run_stdio() -> None:
    """Run the optional SDK-managed stdio projection."""
    create_mcp_server().run(transport="stdio")
