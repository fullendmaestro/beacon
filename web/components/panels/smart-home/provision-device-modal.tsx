"use client";

import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  smartHomeApi,
  type ProvisionDevicePayload,
} from "@/lib/smart-home-api";
import { useBeaconSocket } from "@/lib/use-beacon-socket";

interface ProvisionDeviceModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const DOMAIN_PRESETS: Record<
  ProvisionDevicePayload["domain"],
  { proto_type: string; defaultZ: number }
> = {
  light: { proto_type: "CeilingLight", defaultZ: 2.4 },
  door: { proto_type: "Door", defaultZ: 0.0 },
  blind: { proto_type: "MotorizedBlind", defaultZ: 1.25 },
  climate: { proto_type: "Radiator", defaultZ: 0.36 },
  appliance: { proto_type: "WallPlug", defaultZ: 0.15 },
  sensor: { proto_type: "DistanceSensor", defaultZ: 1.2 },
  camera: { proto_type: "Camera", defaultZ: 2.15 },
};

export function ProvisionDeviceModal({
  open,
  onOpenChange,
}: ProvisionDeviceModalProps) {
  const { rooms, devices, refresh } = useBeaconSocket();
  const [wbtName, setWbtName] = useState("");
  const [domain, setDomain] =
    useState<ProvisionDevicePayload["domain"]>("light");
  const [protoType, setProtoType] = useState("CeilingLight");
  const [roomId, setRoomId] = useState("kitchen");
  const [posX, setPosX] = useState("-2.5");
  const [posY, setPosY] = useState("-2.5");
  const [posZ, setPosZ] = useState("2.4");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleDomainChange = (newDomain: ProvisionDevicePayload["domain"]) => {
    setDomain(newDomain);
    const preset = DOMAIN_PRESETS[newDomain];
    setProtoType(preset.proto_type);
    setPosZ(String(preset.defaultZ));
  };

  const handleProvision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!wbtName.trim()) {
      setErrorMsg("Please enter an exact Webots device name (wbt_name).");
      return;
    }
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      await smartHomeApi.provisionDevice({
        wbt_name: wbtName.trim(),
        domain,
        proto_type: protoType.trim() || DOMAIN_PRESETS[domain].proto_type,
        room_id: roomId || undefined,
        translation: [
          Number(posX) || 0,
          Number(posY) || 0,
          Number(posZ) || 0,
        ],
        initial_state:
          domain === "light"
            ? { power_state: "on", brightness: 100, color: "#fae6cc" }
            : {},
      });
      setWbtName("");
      await refresh();
      onOpenChange(false);
    } catch (err: any) {
      setErrorMsg(err?.message || "Failed to provision device.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRemoveDevice = async (id: string) => {
    try {
      await smartHomeApi.removeDevice(id);
      await refresh();
    } catch {
      // Ignore
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md rounded-3xl">
        <DialogHeader>
          <DialogTitle>Provision Dynamic IoT Device</DialogTitle>
          <DialogDescription>
            Spawns a new VRML device node into SQLite WAL &amp; Webots{" "}
            <code>DYNAMIC_DEVICES</code> via the Event Broker.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleProvision} className="flex flex-col gap-3.5 pt-2">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-foreground">
              Exact Webots Name (<code>wbt_name</code>)
            </label>
            <Input
              placeholder="e.g. Kitchen Island Pendant Light"
              value={wbtName}
              onChange={(e) => setWbtName(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-foreground">
                Domain
              </label>
              <select
                value={domain}
                onChange={(e) =>
                  handleDomainChange(
                    e.target.value as ProvisionDevicePayload["domain"],
                  )
                }
                className="h-9 rounded-md border border-input bg-background px-3 text-xs"
              >
                <option value="light">light</option>
                <option value="door">door</option>
                <option value="blind">blind</option>
                <option value="climate">climate</option>
                <option value="appliance">appliance</option>
                <option value="sensor">sensor</option>
                <option value="camera">camera</option>
              </select>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-foreground">
                Webots PROTO Type
              </label>
              <Input
                value={protoType}
                onChange={(e) => setProtoType(e.target.value)}
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-foreground">
              Room Assignment (or auto-inferred from 2D polygon)
            </label>
            <select
              value={roomId}
              onChange={(e) => setRoomId(e.target.value)}
              className="h-9 rounded-md border border-input bg-background px-3 text-xs"
            >
              <option value="">Auto-infer from (X, Y) coordinates</option>
              {rooms.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name} ({r.id})
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div className="flex flex-col gap-1">
              <label className="text-[11px] text-muted-foreground">
                World X (m)
              </label>
              <Input
                type="number"
                step="0.1"
                value={posX}
                onChange={(e) => setPosX(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[11px] text-muted-foreground">
                World Y (m)
              </label>
              <Input
                type="number"
                step="0.1"
                value={posY}
                onChange={(e) => setPosY(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[11px] text-muted-foreground">
                World Z (m)
              </label>
              <Input
                type="number"
                step="0.1"
                value={posZ}
                onChange={(e) => setPosZ(e.target.value)}
              />
            </div>
          </div>

          {errorMsg && (
            <p className="text-xs font-medium text-destructive">{errorMsg}</p>
          )}

          <Button
            type="submit"
            disabled={isSubmitting}
            className="mt-1 gap-1.5 rounded-xl"
          >
            <Plus className="size-4" />
            {isSubmitting ? "Spawning Node..." : "Spawn Device in Twin"}
          </Button>
        </form>

        {devices.length > 0 && (
          <div className="mt-2 border-t border-border/60 pt-3">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Registered SQLite Devices ({devices.length})
            </span>
            <div className="mt-2 flex max-h-36 flex-col gap-1.5 overflow-y-auto pr-1">
              {devices.slice(-8).reverse().map((d) => (
                <div
                  key={d.id}
                  className="flex items-center justify-between rounded-xl border border-border/50 bg-muted/30 px-2.5 py-1.5 text-xs"
                >
                  <div className="flex flex-col min-w-0">
                    <span className="truncate font-medium text-foreground">
                      {d.wbt_name}
                    </span>
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {d.id} • {d.domain}
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-7 text-muted-foreground hover:text-destructive"
                    onClick={() => handleRemoveDevice(d.id)}
                    title="Remove device"
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </div>
              ))}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
