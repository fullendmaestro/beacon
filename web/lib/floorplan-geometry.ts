/**
 * Coordinate Transformation Pipeline (Webots 3D -> SVG 2D)
 *
 * Estate bounds in `beacon_home.wbt`:
 * - World X: -12.6m (West Patio/Dining) to +4.4m (East Garage/Forecourt) -> Width = 17.0m
 * - World Y: -13.3m (South Bedrooms/Bathrooms) to +0.2m (North Living/Garage wall) -> Height = 13.5m
 *
 * Scale: 50 px = 1 meter -> viewBox = "0 0 850 675"
 */

export const FLOORPLAN_VIEWBOX_WIDTH = 850;
export const FLOORPLAN_VIEWBOX_HEIGHT = 675;
export const FLOORPLAN_SCALE = 50;
export const WORLD_MIN_X = -12.6;
export const WORLD_MAX_Y = 0.2;

export interface SvgPoint {
  x: number;
  y: number;
}

export function worldToSvg(x: number, y: number): SvgPoint {
  return {
    x: Number(((x - WORLD_MIN_X) * FLOORPLAN_SCALE).toFixed(2)),
    y: Number(((WORLD_MAX_Y - y) * FLOORPLAN_SCALE).toFixed(2)),
  };
}

export function svgToWorld(svgX: number, svgY: number): { x: number; y: number } {
  return {
    x: Number((svgX / FLOORPLAN_SCALE + WORLD_MIN_X).toFixed(2)),
    y: Number((WORLD_MAX_Y - svgY / FLOORPLAN_SCALE).toFixed(2)),
  };
}

export function polygonToSvgPoints(polygon2d: number[][]): string {
  return polygon2d
    .map(([wx, wy]) => {
      const pt = worldToSvg(wx, wy);
      return `${pt.x},${pt.y}`;
    })
    .join(" ");
}

export function polygonCentroidSvg(polygon2d: number[][]): SvgPoint {
  if (!polygon2d || polygon2d.length === 0) {
    return { x: 425, y: 337 };
  }
  const sum = polygon2d.reduce(
    (acc, [wx, wy]) => {
      const pt = worldToSvg(wx, wy);
      return { x: acc.x + pt.x, y: acc.y + pt.y };
    },
    { x: 0, y: 0 },
  );
  return {
    x: Number((sum.x / polygon2d.length).toFixed(1)),
    y: Number((sum.y / polygon2d.length).toFixed(1)),
  };
}

export function buildManhattanPolyline(
  waypoints: Array<{ x: number; y: number }>,
  origin?: { x: number; y: number },
): string {
  const pts: Array<{ x: number; y: number }> = [];
  if (origin) {
    pts.push(origin);
  }
  for (const wp of waypoints) {
    if (typeof wp.x === "number" && typeof wp.y === "number") {
      pts.push({ x: wp.x, y: wp.y });
    }
  }
  return pts
    .map((p) => {
      const s = worldToSvg(p.x, p.y);
      return `${s.x},${s.y}`;
    })
    .join(" ");
}
