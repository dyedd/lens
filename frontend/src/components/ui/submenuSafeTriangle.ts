export type Point = {
  x: number;
  y: number;
};

export type RectLike = {
  left: number;
  right: number;
  top: number;
  bottom: number;
};

function crossProductSign(p1: Point, p2: Point, p3: Point) {
  return (p1.x - p3.x) * (p2.y - p3.y) - (p2.x - p3.x) * (p1.y - p3.y);
}

/** Determine whether a 2D point falls inside or on the edges of a triangle. */
export function isPointInTriangle(
  point: Point,
  v1: Point,
  v2: Point,
  v3: Point,
) {
  const area = Math.abs(crossProductSign(v1, v2, v3));
  if (area < 0.001) return false;
  const d1 = crossProductSign(point, v1, v2);
  const d2 = crossProductSign(point, v2, v3);
  const d3 = crossProductSign(point, v3, v1);
  const hasNeg = d1 < 0 || d2 < 0 || d3 < 0;
  const hasPos = d1 > 0 || d2 > 0 || d3 > 0;
  return !(hasNeg && hasPos);
}

/**
 * Build the safe-aim triangle connecting the cursor origin on the parent item
 * to the top and bottom corners of the submenu's facing edge.
 */
export function getSubmenuTriangle(
  origin: Point,
  submenuRect: RectLike,
  triggerRect?: RectLike | null,
  paddingPx = 8,
): [Point, Point, Point] | null {
  let edgeX: number | null = null;
  if (triggerRect) {
    const triggerCenterX = (triggerRect.left + triggerRect.right) / 2;
    if (submenuRect.left >= triggerCenterX) {
      edgeX = submenuRect.left;
    } else if (submenuRect.right <= triggerCenterX) {
      edgeX = submenuRect.right;
    }
  }
  if (edgeX === null) {
    if (origin.x <= submenuRect.left) edgeX = submenuRect.left;
    else if (origin.x >= submenuRect.right) edgeX = submenuRect.right;
    else return null;
  }
  return [
    origin,
    { x: edgeX, y: submenuRect.top - paddingPx },
    { x: edgeX, y: submenuRect.bottom + paddingPx },
  ];
}

/** Check whether the pointer is moving within the safe triangle toward a submenu. */
export function isPointerInSubmenuSafeTriangle(
  cursor: Point,
  origin: Point,
  submenuRect: RectLike,
  triggerRect?: RectLike | null,
  paddingPx = 8,
) {
  const triangle = getSubmenuTriangle(
    origin,
    submenuRect,
    triggerRect,
    paddingPx,
  );
  if (!triangle) return false;
  return isPointInTriangle(cursor, triangle[0], triangle[1], triangle[2]);
}
