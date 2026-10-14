"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { smartHomeApi, type CameraDevice } from "@/lib/smart-home-api";

interface CameraModalProps {
  camera: CameraDevice | null;
  onClose: () => void;
}

export function CameraModal({ camera, onClose }: CameraModalProps) {
  return (
    <Dialog open={!!camera} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[640px] border-border bg-card">
        <DialogHeader>
          <DialogTitle className="text-foreground">{camera?.name}</DialogTitle>
        </DialogHeader>
        <div className="relative flex aspect-video w-full items-center justify-center overflow-hidden rounded-lg border border-border bg-black">
          {camera && (
            <>
              <div className="absolute left-4 top-4 z-10 flex items-center gap-2 rounded-full bg-black/50 px-2.5 py-1 backdrop-blur-sm">
                <span className="relative flex h-2.5 w-2.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
                  <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-red-500" />
                </span>
                <span className="text-[11px] font-bold uppercase tracking-wider text-white">
                  Live • {camera.metadata}
                </span>
              </div>
              <img
                src={smartHomeApi.getStreamUrl(camera.name)}
                alt={`${camera.name} Feed`}
                className="h-full w-full object-cover"
              />
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
