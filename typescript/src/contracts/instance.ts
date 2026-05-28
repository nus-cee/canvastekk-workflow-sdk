import type { Point3D, BoundingBox3D } from "./point3d.js";

/**
 * Instance in a point cloud with classification and spatial info.
 */
export interface Instance {
  instanceId: number;
  classId: number;
  className: string;
  confidence: number;
  pointIndices: number[];
  centroid?: Point3D | null;
  boundingBox?: BoundingBox3D | null;
  metadata: Record<string, unknown>;
}

/**
 * Gets the number of points in an instance.
 * @param inst - Instance
 * @returns Point count
 */
export function instanceNumPoints(inst: Instance): number {
  return inst.pointIndices.length;
}

/**
 * Data for a set of instances.
 */
export interface InstanceSetData {
  contract_version: string;
  source_node?: string | null;
  source_file?: string | null;
  instances: Instance[];
  classNames: string[];
  pointCount: number;
  semanticLabels?: number[] | null;
  instanceLabels?: number[] | null;
}

/**
 * Gets all instances of a specific class.
 * @param set - Instance set
 * @param className - Class name to filter by
 * @returns Array of matching instances
 */
export function getInstancesByClass(set: InstanceSetData, className: string): Instance[] {
  return set.instances.filter((i) => i.className === className);
}

/**
 * Gets all instances of a specific class ID.
 * @param set - Instance set
 * @param classId - Class ID to filter by
 * @returns Array of matching instances
 */
export function getInstancesByClassId(set: InstanceSetData, classId: number): Instance[] {
  return set.instances.filter((i) => i.classId === classId);
}
