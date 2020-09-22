# coding: utf8
"""This module contains various utility functions not specific to another module.

© All rights reserved.
ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Laboratory CNPA, 2019-2020

See the LICENSE.TXT file for more details.

Author : Cyril Waechter
"""
import itertools
from typing import Iterable, Any, Generator, List

import FreeCAD
import Part

from freecad.bem.entities import Root


TOLERANCE = 0.001


def append(doc_object, fc_property, value: Any):
    """Intended to manipulate FreeCAD list like properties only"""
    current_value = getattr(doc_object, fc_property)
    current_value.append(value)
    setattr(doc_object, fc_property, current_value)


def append_inner_wire(boundary, wire):
    """Intended to manipulate FreeCAD list like properties only"""
    outer_wire = get_outer_wire(boundary)
    inner_wires = get_inner_wires(boundary)
    inner_wires.append(wire)
    generate_boundary_compound(boundary, outer_wire, inner_wires)


def are_parallel_boundaries(boundary1, boundary2):
    return 1 - abs(get_normal_at(boundary1).dot(get_normal_at(boundary2))) < TOLERANCE


def clean_vectors(vectors: List[FreeCAD.Vector]) -> None:
    """Clean vectors for polygons creation
    Keep only 1 point if 2 consecutive points are equal.
    Remove point if it makes border go back and forth"""
    i = 0
    while i < len(vectors):
        p1 = vectors[i - 1]
        p2 = vectors[i]
        p3 = vectors[(i + 1) % len(vectors)]
        if are_3points_collinear(p1, p2, p3):
            vectors.pop(i)
            i -= 1
            continue
        i += 1


def close_vectors(vectors):
    if vectors[0] != vectors[-1]:
        vectors.append(vectors[0])


def direction(v0: FreeCAD.Vector, v1: FreeCAD.Vector) -> FreeCAD.Vector:
    return (v0 - v1).normalize()


def generate_boundary_compound(boundary, outer_wire: Part.Wire, inner_wires: list):
    """Generate boundary compound composed of 1 Face, 1 OuterWire, 0-n InnerWires"""
    face = Part.Face(outer_wire)
    for inner_wire in inner_wires:
        new_face = face.cut(Part.Face(inner_wire))
        if not new_face.Area:
            b_id = (
                boundary.Id
                if isinstance(boundary.Proxy, Root)
                else boundary.SourceBoundary
            )
            raise RuntimeError(
                f"Failure. An inner_wire did not cut face correctly in boundary <{b_id}>. OuterWire area = {Part.Face(outer_wire).Area / 10 ** 6}, InnerWire area = {Part.Face(inner_wire).Area / 10 ** 6}"
            )
        face = new_face
    boundary.Shape = Part.Compound([face, outer_wire, *inner_wires])


def get_by_id(ifc_id: int, elements: Iterable[Part.Feature]) -> Part.Feature:
    for element in elements:
        try:
            if element.Id == ifc_id:
                return element
        except AttributeError:
            continue


def get_by_class(doc=FreeCAD.ActiveDocument, by_class=object):
    """Generator throught FreeCAD document element of specific python proxy class"""
    for element in doc.Objects:
        try:
            if isinstance(element.Proxy, by_class):
                yield element
        except AttributeError:
            continue


def get_elements_by_ifctype(
    ifc_type: str, doc=FreeCAD.ActiveDocument
) -> Generator[Part.Feature, None, None]:
    """Generator throught FreeCAD document element of specific ifc_type"""
    for element in doc.Objects:
        try:
            if element.IfcType == ifc_type:
                yield element
        except (AttributeError, ReferenceError):
            continue


def get_boundaries_by_element(element: Part.Feature, doc) -> List[Part.Feature]:
    return [
        boundary
        for boundary in get_elements_by_ifctype("IfcRelSpaceBoundary", doc)
        if boundary.RelatedBuildingElement == element
    ]


def get_boundaries_by_element_id(element_id, doc):
    return (
        boundary
        for boundary in doc.Objects
        if getattr(getattr(boundary, "RelatedBuilding", None), "Id", None) == element_id
    )


def get_element_by_guid(guid, elements_group):
    for fc_element in getattr(elements_group, "Group", elements_group):
        if getattr(fc_element, "GlobalId", None) == guid:
            return fc_element
    raise LookupError(f"Unable to get element by {guid}")


def get_host_guid(ifc_entity):
    return (
        ifc_entity.FillsVoids[0]
        .RelatingOpeningElement.VoidsElements[0]
        .RelatingBuildingElement.GlobalId
    )


def get_in_list_by_id(elements, element_id):
    if element_id == -1:
        return None
    for element in elements:
        if element.Id == element_id:
            return element
    raise LookupError(f"No element with Id <{element_id}> found")


def get_normal_at(fc_boundary, at_uv=(0, 0)) -> FreeCAD.Vector:
    return fc_boundary.Shape.Faces[0].normalAt(*at_uv)


def get_plane(fc_boundary) -> Part.Plane:
    """Intended for RelSpaceBoundary use only"""
    return Part.Plane(fc_boundary.Shape.Vertexes[0].Point, get_normal_at(fc_boundary))


def get_vectors_from_shape(shape: Part.Shape):
    return [vx.Point for vx in shape.Vertexes]


def get_boundary_outer_vectors(boundary):
    return [vx.Point for vx in get_outer_wire(boundary).Vertexes]


def get_outer_wire(boundary):
    return [s for s in boundary.Shape.SubShapes if isinstance(s, Part.Wire)][0]


def get_inner_wires(boundary):
    return [s for s in boundary.Shape.SubShapes if isinstance(s, Part.Wire)][1:]


def get_wires(boundary: Part.Feature) -> Generator[Part.Wire, None, None]:
    return (s for s in boundary.Shape.SubShapes if isinstance(s, Part.Wire))


def is_collinear(edge1, edge2):
    v0_0, v0_1 = (vx.Point for vx in edge1.Vertexes)
    v1_0, v1_1 = (vx.Point for vx in edge2.Vertexes)
    if is_collinear_or_parallel(v0_0, v0_1, v1_0, v1_1):
        return v0_0 == v1_0 or is_collinear_or_parallel(v0_0, v0_1, v0_0, v1_0)


def is_collinear_or_parallel(v0_0, v0_1, v1_0, v1_1) -> bool:
    return abs(direction(v0_0, v0_1).dot(direction(v1_0, v1_1))) > 0.9999


def is_coplanar(shape_1, shape_2):
    """Intended for RelSpaceBoundary use only
    For some reason native Part.Shape.isCoplanar(Part.Shape) do not always work"""
    return get_plane(shape_1).toShape().isCoplanar(get_plane(shape_2).toShape())


def line_from_edge(edge: Part.Edge) -> Part.Line:
    points = [v.Point for v in edge.Vertexes]
    return Part.Line(*points)


def polygon_from_lines(lines, base_plane):
    new_points = []
    for line1, line2 in zip(lines, lines[1:] + lines[:1]):
        try:
            # Need to ensure direction are not same to avoid crash
            if abs(line1.Direction.dot(line2.Direction)) >= 1 - TOLERANCE:
                continue
            new_points.append(
                base_plane.value(*line1.intersect2d(line2, base_plane)[0])
            )
        except IndexError:
            raise NoIntersectionError
    new_points[0:0] = new_points[-1:]
    return Part.makePolygon(new_points)


def project_wire_to_plane(wire, plane) -> Part.Wire:
    new_vectors = [
        v.Point.projectToPlane(plane.Position, plane.Axis) for v in wire.Vertexes
    ]
    close_vectors(new_vectors)
    return Part.makePolygon(new_vectors)


def project_boundary_onto_plane(boundary, plane: Part.Plane):
    outer_wire = get_outer_wire(boundary)
    inner_wires = get_inner_wires(boundary)
    outer_wire = project_wire_to_plane(outer_wire, plane)
    inner_wires = [project_wire_to_plane(wire, plane) for wire in inner_wires]

    face = Part.Face(outer_wire)
    try:
        for inner_wire in inner_wires:
            face = face.cut(Part.Face(inner_wire))
    except RuntimeError:
        pass

    boundary.Shape = Part.Compound([face, outer_wire, *inner_wires])


def are_3points_collinear(p1, p2, p3) -> bool:
    for v1, v2 in itertools.combinations((p1, p2, p3), 2):
        if v1.isEqual(v2, TOLERANCE):
            return True
    dir1 = vectors_dir(p1, p2)
    dir2 = vectors_dir(p2, p3)
    return dir1.isEqual(dir2, TOLERANCE) or dir1.isEqual(-dir2, TOLERANCE)


def vectors_dir(p1, p2) -> FreeCAD.Vector:
    return (p2 - p1).normalize()


class NoIntersectionError(IndexError):
    pass
