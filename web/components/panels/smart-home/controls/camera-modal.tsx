"use client";

import { useState, useEffect } from "react";
import { useAui } from "@assistant-ui/react";
import { Camera, Download, Sparkles, RefreshCw } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { smartHomeApi, type CameraDevice } from "@/lib/smart-home-api";

interface CameraModalProps {
  camera: CameraDevice | null;
  onClose: () => void;
}

export function CameraModal({ camera, onClose }: CameraModalProps) {
  const aui = useAui();
  const [streamNonce, setStreamNonce] = useState(0);
  const [isCapturing, setIsCapturing] = useState(false);

  useEffect(() => {
    setStreamNonce((n) => n + 1);
  }, [camera?.name]);

  const handleDownloadSnapshot = async () => {
    if (!camera) return;
    setIsCapturing(true);
    try {
      const data = await smartHomeApi.getFrameData(camera.name);
      const link = document.createElement("a");
      link.href = `data:${data.mime_type};base64,${data.jpeg_base64}`;
      link.download = `${camera.name.toLowerCase().replace(/\s+/g, "_")}_snapshot.jpg`;
      link.click();
    } finally {
      setIsCapturing(false);
    }
  };

  const handleAskBeacon = () => {
    if (!camera) return;
    aui.thread.append({
      role: "user",
      content: [
        {
          type: "text",
          text: `Inspect the live feed from '${camera.name}' using inspect_camera_feed and tell me what you see in detail.`,
        },
      ],
    });
    onClose();
  };

  return (
    <Dialog open={!!camera} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[680px] border-border bg-card rounded-3xl">
        <DialogHeader className="flex flex-row items-center justify-between pr-6">
          <DialogTitle className="flex items-center gap-2 text-foreground">
            <Camera className="size-5 text-teal-500" />
            <span>{camera?.name}</span>
          </DialogTitle>
        </DialogHeader>

        <div className="relative flex aspect-video w-full items-center justify-center overflow-hidden rounded-2xl border border-border bg-black">
          {camera && (
            <>
              <div className="absolute left-3.5 top-3.5 z-10 flex items-center gap-2 rounded-full bg-black/65 px-3 py-1 backdrop-blur-md">
                <span className="relative flex size-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
                  <span className="relative inline-flex size-2 rounded-full bg-red-500" />
                </span>
                <span className="text-[11px] font-bold uppercase tracking-wider text-white">
                  Live • {camera.metadata}
                </span>
              </div>

              <img
                src={`${smartHomeApi.getStreamUrl(camera.name)}?t=${streamNonce}`}
                alt={`${camera.name} Feed`}
                className="h-full w-full object-cover"
              />
            </>
          )}
        </div>

        {camera && (
          <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                className="h-9 gap-1.5 rounded-xl text-xs"
                onClick={() => setStreamNonce((n) => n + 1)}
              >
                <RefreshCw className="size-3.5" />
                Reconnect Stream
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={isCapturing}
                className="h-9 gap-1.5 rounded-xl text-xs"
                onClick={handleDownloadSnapshot}
              >
                <Download className="size-3.5" />
                {isCapturing ? "Saving..." : "Save Snapshot"}
              </Button>
            </div>

            <Button
              size="sm"
              className="h-9 gap-1.5 rounded-xl bg-teal-600 text-xs font-semibold text-white hover:bg-teal-700"
              onClick={handleAskBeacon}
            >
              <Sparkles className="size-3.5" />
              Ask Beacon to Inspect Feed
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
