/**
 * 3D point with x, y, z coordinates.
 */
export interface Point3D {
  x: number;
  y: number;
  z: number;
}

/**
 * Converts a Point3D to a list of coordinates.
 * @param p - Point3D to convert
 * @returns Array of [x, y, z] coordinates
 */
export function point3DToList(p: Point3D): [number, number, number] {
  return [p.x, p.y, p.z];
}

/**
 * Creates a Point3D from an array of coordinates.
 * @param coords - Array of [x, y, z] coordinates
 * @returns Point3D object
 */
export function point3DFromList(coords: number[]): Point3D {
  return { x: coords[0], y: coords[1], z: coords[2] };
}

/**
 * 3D axis-aligned bounding box.
 */
export interface BoundingBox3D {
  minPoint: Point3D;
  maxPoint: Point3D;
}

/**
 * Calculates the center point of a bounding box.
 * @param box - Bounding box
 * @returns Center point
 */
export function boundingBoxCenter(box: BoundingBox3D): Point3D {
  return {
    x: (box.minPoint.x + box.maxPoint.x) / 2,
    y: (box.minPoint.y + box.maxPoint.y) / 2,
    z: (box.minPoint.z + box.maxPoint.z) / 2,
  };
}

/**
 * Calculates the size of a bounding box.
 * @param box - Bounding box
 * @returns Size as a Point3D
 */
export function boundingBoxSize(box: BoundingBox3D): Point3D {
  return {
    x: box.maxPoint.x - box.minPoint.x,
    y: box.maxPoint.y - box.minPoint.y,
    z: box.maxPoint.z - box.minPoint.z,
  };
}
