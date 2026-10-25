export function plotBounds(points: number[][], padding = 0.5): number[] {
  const bounds = points.reduce(
    (box, point) => [
      Math.min(box[0], point[0]),
      Math.min(box[1], point[1]),
      Math.max(box[2], point[0]),
      Math.max(box[3], point[1]),
    ],
    [Infinity, Infinity, -Infinity, -Infinity],
  );
  return [bounds[0] - padding, bounds[1] - padding, bounds[2] + padding, bounds[3] + padding];
}
