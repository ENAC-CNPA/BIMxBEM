# coding: utf8
"""This module contains various utility functions not specific to another module.

© All rights reserved.
ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Laboratory CNPA, 2019-2020

See the LICENSE.TXT file for more details.

Author : Cyril Waechter
"""
import itertools
import typing
from typing import Iterable, Any, Generator, List

import FreeCAD
import Part

from freecad.bem.entities import Root

if typing.TYPE_CHECKING:
    from freecad.bem.typing import (
        RelSpaceBoundaryFeature,
    )  # pylint: disable=no-name-in-module, import-error

TOLERANCE = 0.001


def append(doc_object, fc_property, value: Any):
    """Intended to manipulate FreeCAD list like properties only"""
    current_value = getattr(doc_object, fc_property)
    current_value.append(value)
    setattr(doc_object, fc_property, current_value)


def append_inner_wire(boundary: "RelSpaceBoundaryFeature", wire: Part.Wire) -> None:
    """Intended to manipulate FreeCAD list like properties only"""
    outer_wire = get_outer_wire(boundary)
    inner_wires = get_inner_wires(boundary)
    inner_wires.append(wire)
    generate_boundary_compound(boundary, outer_wire, inner_wires)


def are_parallel_boundaries(
    boundary1: "RelSpaceBoundaryFeature", boundary2: "RelSpaceBoundaryFeature"
) -> bool:
    return (
        1 - abs(get_boundary_normal(boundary1).dot(get_boundary_normal(boundary2)))
        < TOLERANCE
    )


def are_too_far(boundary1, boundary2):
    max_distance = getattr(
        getattr(boundary2.RelatedBuildingElement, "Thickness", 0), "Value", 0
    )
    return boundary1.Shape.distToShape(boundary2.Shape)[0] - max_distance > TOLERANCE


def clean_vectors(vectors: List[FreeCAD.Vector]) -> None:
    """Clean vectors for polygons creation
    Keep only 1 point if 2 consecutive points are equal.
    Remove point if it makes border go back and forth"""
    i = 0
    while i < len(vectors):
        pt1 = vectors[i - 1]
        pt2 = vectors[i]
        pt3 = vectors[(i + 1) % len(vectors)]
        if are_3points_collinear(pt1, pt2, pt3):
            vectors.pop(i)
            i = i - 1 if i > 0 else 0
            continue
        i += 1


def close_vectors(vectors: List[FreeCAD.Vector]) -> None:
    if vectors[0] != vectors[-1]:
        vectors.append(vectors[0])


def direction(vec0: FreeCAD.Vector, vec1: FreeCAD.Vector) -> FreeCAD.Vector:
    return (vec0 - vec1).normalize()


def generate_boundary_compound(
    boundary: "RelSpaceBoundaryFeature",
    outer_wire: Part.Wire,
    inner_wires: List[Part.Wire],
):
    """Generate boundary compound composed of 1 Face, 1 OuterWire, 0-n InnerWires"""
    face = Part.Face(outer_wire)
    for inner_wire in inner_wires:
        new_face = face.cut(Part.Face(inner_wire))
        if not new_face.Area:
            b_id = (
                boundary.Id
                if isinstance(boundary.Proxy, Root)
                else boundary.SourceBoundary.Id
            )
            raise RuntimeError(
                f"""Failure. An inner_wire did not cut face correctly in boundary <{b_id}>.
                OuterWire area = {Part.Face(outer_wire).Area / 10 ** 6},
                InnerWire area = {Part.Face(inner_wire).Area / 10 ** 6}"""
            )
        face = new_face
    boundary.Shape = Part.Compound([face, outer_wire, *inner_wires])


def get_axis_by_name(placement, name):
    axis_dict = {"AXIS1": 0, "AXIS2": 1, "AXIS3": 2}
    return FreeCAD.Vector(placement.Matrix.A[axis_dict[name] : 12 : 4])


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


def get_face_ref_point(face):
    center_of_mass = face.CenterOfMass
    if face.isInside(center_of_mass, TOLERANCE, True):
        return center_of_mass
    pt1 = face.distToShape(Part.Vertex(center_of_mass))[1][0][0]
    line = Part.Line(center_of_mass, pt1)
    plane = Part.Plane(center_of_mass, face.normalAt(0, 0))
    intersections = [line.intersect2d(e.Curve, plane) for e in face.Edges]
    intersections = [i[0] for i in intersections if i]
    if not len(intersections) == 2:
        intersections = sorted(intersections)[0:2]
    mid_param = tuple(sum(params) / len(params) for params in zip(*intersections))
    return plane.value(*mid_param)


def get_element_by_guid(guid, elements_group):
    for fc_element in getattr(elements_group, "Group", elements_group):
        if getattr(fc_element, "GlobalId", None) == guid:
            return fc_element
    raise LookupError(
        f"""Unable to get element by {guid}.
This error is known to occurs when you model 2 parallel walls instead of a multilayer wall."""
    )


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


def get_face_normal(face, at_point=None) -> FreeCAD.Vector:
    at_point = at_point or face.Vertexes[0].Point
    params = face.Surface.projectPoint(at_point, "LowerDistanceParameters")
    return face.normalAt(*params)


def get_boundary_normal(fc_boundary, at_point=None) -> FreeCAD.Vector:
    return get_face_normal(fc_boundary.Shape.Faces[0], at_point)


def get_plane(fc_boundary) -> Part.Plane:
    """Intended for RelSpaceBoundary use only"""
    vertexes = get_outer_wire(fc_boundary).Vertexes
    vec1, vec2 = [v.Point for v in vertexes[0:2]]
    for vtx in vertexes[2:]:
        try:
            return Part.Plane(vec1, vec2, vtx.Point)
        except Part.OCCError:
            continue


def get_area_from_points(points: List[FreeCAD.Vector]) -> float:
    """Return area considering points are consecutive points of a polygon
    Return 0 for invalid polygons"""
    clean_vectors(points)
    close_vectors(points)
    try:
        return Part.Face(Part.makePolygon(points)).Area
    except Part.OCCError:
        return 0


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


def are_edges_parallel(edge1: Part.Edge, edge2: Part.Edge) -> bool:
    dir1 = line_from_edge(edge1).Direction
    dir2 = line_from_edge(edge2).Direction
    return abs(dir1.dot(dir2)) > 1 - TOLERANCE


def is_coplanar(boundary1, boundary2):
    """Intended for RelSpaceBoundary use only
    For some reason native Part.Shape.isCoplanar(Part.Shape) do not always work"""
    plane1 = get_plane(boundary1)
    plane2 = get_plane(boundary2)
    same_dir = plane1.Axis.dot(plane2.Axis) > 1 - TOLERANCE
    p2_on_plane = (  # Strangely distanceToPlane can be negative
        abs(plane2.Position.distanceToPlane(plane1.Position, plane1.Axis)) < TOLERANCE
    )
    return same_dir and p2_on_plane


def line_from_edge(edge: Part.Edge) -> Part.Line:
    points = [v.Point for v in edge.Vertexes]
    return Part.Line(*points)


def polygon_from_lines(lines, base_plane):
    new_points = []
    for li1, line1 in enumerate(lines):
        li2 = li1 - 1
        line2 = lines[li2]
        # Need to ensure direction are not same to avoid crash in OCCT 7.4
        if abs(line1.Direction.dot(line2.Direction)) >= 1 - TOLERANCE:
            continue
        new_points.append(base_plane.value(*line1.intersect2d(line2, base_plane)[0]))
    clean_vectors(new_points)
    if len(new_points) < 3:
        raise ShapeCreationError
    close_vectors(new_points)
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

    generate_boundary_compound(boundary, outer_wire, inner_wires)


def remove_inner_wire(boundary, wire) -> None:
    if wire in boundary.Shape.Wires:
        boundary.Shape = boundary.Shape.removeShape([wire])
        return

    area = Part.Face(wire).Area
    for inner_wire in get_inner_wires(boundary):
        if abs(Part.Face(inner_wire).Area - area) < TOLERANCE:
            boundary.Shape = boundary.Shape.removeShape([inner_wire])
            return


def update_boundary_shape(boundary) -> None:
    outer_wire = get_outer_wire(boundary)
    inner_wires = get_inner_wires(boundary)
    generate_boundary_compound(boundary, outer_wire, inner_wires)


def are_3points_collinear(
    pt1: FreeCAD.Vector, pt2: FreeCAD.Vector, pt3: FreeCAD.Vector
) -> bool:
    for vec1, vec2 in itertools.combinations((pt1, pt2, pt3), 2):
        if vec1.isEqual(vec2, TOLERANCE):
            return True
    dir1 = vectors_dir(pt1, pt2)
    dir2 = vectors_dir(pt2, pt3)
    return dir1.isEqual(dir2, TOLERANCE) or dir1.isEqual(-dir2, TOLERANCE)


def vectors_dir(pt1: FreeCAD.Vector, pt2: FreeCAD.Vector) -> FreeCAD.Vector:
    return (pt2 - pt1).normalize()


class IsTooSmall(BaseException):
    pass


class ShapeCreationError(RuntimeError):
    pass
