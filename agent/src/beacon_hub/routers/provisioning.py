"""Dynamic device and navigation node provisioning endpoints (/api/v2/devices, /api/v2/nav-nodes)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..broker import get_broker
from ..database.connection import get_db
from ..database.models import DeviceProvisionRequest, NavNodeProvisionRequest

router = APIRouter(prefix="/api/v2", tags=["provisioning"])


@router.post("/devices")
async def provision_device(req: DeviceProvisionRequest) -> dict[str, Any]:
    db = get_db()
    broker = get_broker()
    existing = db.strict_lookup(req.wbt_name)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Device with wbt_name '{req.wbt_name}' already exists (id='{existing['id']}').",
        )
    rec = db.provision_device(req)
    db.log_event("device.lifecycle.provisioned", rec)
    await broker.publish("device.lifecycle.provisioned", rec)
    return {"success": True, "device": rec}


@router.delete("/devices/{identifier}")
async def delete_device(identifier: str) -> dict[str, Any]:
    db = get_db()
    broker = get_broker()
    removed = db.remove_device(identifier)
    if not removed:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "error_code": "DEVICE_NOT_FOUND_STRICT",
                "message": f"No device matched exact id or wbt_name '{identifier}'.",
            },
        )
    payload = {
        "device_id": removed["id"],
        "wbt_name": removed["wbt_name"],
        "wbt_def": removed.get("wbt_def"),
        "domain": removed["domain"],
    }
    db.log_event("device.lifecycle.removed", payload)
    await broker.publish("device.lifecycle.removed", payload)
    return {"success": True, **payload}


@router.post("/nav-nodes")
async def provision_nav_node(req: NavNodeProvisionRequest) -> dict[str, Any]:
    db = get_db()
    broker = get_broker()
    node = db.add_nav_node(req)
    await broker.publish("nav.node.provisioned", node)
    return {"success": True, "node": node}
