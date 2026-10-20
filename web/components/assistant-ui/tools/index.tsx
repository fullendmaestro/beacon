"use client";

import {
  GetLightsToolUI,
  GetLightStateToolUI,
  SetPowerStateToolUI,
  SetBrightnessToolUI,
  SetColorToolUI,
} from "./light-tool-ui";
import {
  GetDoorsToolUI,
  SetDoorStateToolUI,
  SetDoorLockToolUI,
  GetBlindsToolUI,
  SetBlindPositionToolUI,
} from "./access-blind-tool-ui";
import {
  GetClimateZonesToolUI,
  SetClimateStateToolUI,
  GetAppliancesToolUI,
  SetApplianceStateToolUI,
} from "./climate-appliance-tool-ui";
import {
  GetHomeSummaryToolUI,
  GetSensorsToolUI,
  GetCamerasToolUI,
  TriggerSceneToolUI,
  SetEnvironmentToolUI,
  CalculatorToolUI,
  UtcNowToolUI,
} from "./home-scene-sensor-tool-ui";
import {
  GetTiagoTelemetryToolUI,
  PlanTiagoRouteToolUI,
  NavigateTiagoToRoomToolUI,
  NavigateTiagoToPoseToolUI,
  SetTiagoArmPoseToolUI,
  SetTiagoGripperToolUI,
  PickObjectToolUI,
  PlaceObjectToolUI,
  InspectSceneVisuallyToolUI,
  DeliverItemToolUI,
  FetchItemToolUI,
  PatrolHomeToolUI,
  StopTiagoToolUI,
  GetHumansToolUI,
  ProposeAiTaskToolUI,
} from "./tiago-tool-ui";

export function SmartHomeToolUIs() {
  return (
    <>
      {/* Lights */}
      <GetLightsToolUI />
      <GetLightStateToolUI />
      <SetPowerStateToolUI />
      <SetBrightnessToolUI />
      <SetColorToolUI />

      {/* Doors, Locks, Garage, Gate & Window Blinds */}
      <GetDoorsToolUI />
      <SetDoorStateToolUI />
      <SetDoorLockToolUI />
      <GetBlindsToolUI />
      <SetBlindPositionToolUI />

      {/* Climate & Appliances */}
      <GetClimateZonesToolUI />
      <SetClimateStateToolUI />
      <GetAppliancesToolUI />
      <SetApplianceStateToolUI />

      {/* Summary, Sensors, Cameras, Scenes & Utilities */}
      <GetHomeSummaryToolUI />
      <GetSensorsToolUI />
      <GetCamerasToolUI />
      <TriggerSceneToolUI />
      <SetEnvironmentToolUI />
      <CalculatorToolUI />
      <UtcNowToolUI />

      {/* PAL Robotics TIAGo, Humans & AI Tasks */}
      <GetTiagoTelemetryToolUI />
      <PlanTiagoRouteToolUI />
      <NavigateTiagoToRoomToolUI />
      <NavigateTiagoToPoseToolUI />
      <SetTiagoArmPoseToolUI />
      <SetTiagoGripperToolUI />
      <PickObjectToolUI />
      <PlaceObjectToolUI />
      <InspectSceneVisuallyToolUI />
      <DeliverItemToolUI />
      <FetchItemToolUI />
      <PatrolHomeToolUI />
      <StopTiagoToolUI />
      <GetHumansToolUI />
      <ProposeAiTaskToolUI />
    </>
  );
}
