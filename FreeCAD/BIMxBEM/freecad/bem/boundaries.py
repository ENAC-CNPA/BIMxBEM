# coding: utf8
"""This module reads IfcRelSpaceBoundary from an IFC file and display them in FreeCAD

© All rights reserved.
ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Laboratory CNPA, 2019-2020

See the LICENSE.TXT file for more details.

Author : Cyril Waechter
"""
import os
import io
import itertools
import logging
from collections import namedtuple

import ifcopenshell
import ifcopenshell.geom
from ifcopenshell.util import unit

import FreeCAD
import Part
import FreeCADGui

from freecad.bem.bem_xml import BEMxml

LOG_FORMAT = "{levelname} {asctime} {funcName}-{message}"
LOG_STREAM = io.StringIO()
logging.basicConfig(
    stream=LOG_STREAM, level=logging.WARNING, format=LOG_FORMAT, style="{"
)
logger = logging.getLogger()


def ios_settings(brep):
    """Create ifcopenshell.geom.settings for various cases"""
    settings = ifcopenshell.geom.settings()
    settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
    settings.set(settings.INCLUDE_CURVES, True)
    if brep:
        settings.set(settings.USE_BREP_DATA, True)
    return settings


BREP_SETTINGS = ios_settings(brep=True)
MESH_SETTINGS = ios_settings(brep=False)
TOLERANCE = 0.001

"""With IfcOpenShell 0.6.0a1 recreating face from wires seems to give more consistant results.
Especially when inner boundaries touch outer boundary"""
BREP = False

# IfcOpenShell/IFC default unit is m, FreeCAD internal unit is mm
SCALE = 1000


def generate_space(ifc_space, parent, doc=FreeCAD.ActiveDocument):
    """Generate Space and RelSpaceBoundaries as defined in ifc_file. No post process."""
    fc_space = create_space_from_entity(ifc_space)
    parent.addObject(fc_space)

    boundaries = fc_space.newObject("App::DocumentObjectGroup", "Boundaries")
    fc_space.Boundaries = boundaries
    second_levels = boundaries.newObject("App::DocumentObjectGroup", "SecondLevel")
    fc_space.SecondLevel = second_levels

    # All boundaries have their placement relative to space placement
    space_placement = get_placement(ifc_space)
    for ifc_boundary in (b for b in ifc_space.BoundedBy if b.Name == "2ndLevel"):
        try:
            face = RelSpaceBoundary.create(ifc_entity=ifc_boundary)
            second_levels.addObject(face)
            face.Placement = space_placement
            element = get_related_element(ifc_boundary, doc)
            if element:
                face.RelatedBuildingElement = element
                append(element, "ProvidesBoundaries", face.Id)
            face.RelatingSpace = fc_space.Id
        except ShapeCreationError:
            logger.warning(
                f"Failed to create fc_shape for RelSpaceBoundary <{ifc_boundary.id()}> even with fallback methode _part_by_mesh. IfcOpenShell bug ?"
            )


class ShapeCreationError(RuntimeError):
    pass


def generate_containers(ifc_parent, fc_parent, doc=FreeCAD.ActiveDocument):
    for rel_aggregates in ifc_parent.IsDecomposedBy:
        for element in rel_aggregates.RelatedObjects:
            if element.is_a("IfcSpace"):
                if element.BoundedBy:
                    generate_space(element, fc_parent, doc)
            else:
                fc_container = create_container_from_entity(element)
                fc_parent.addObject(fc_container)
                generate_containers(element, fc_container, doc)


def get_elements(doc=FreeCAD.ActiveDocument):
    """Generator throught FreeCAD document element of specific ifc_type"""
    for element in doc.Objects:
        try:
            if isinstance(element.Proxy, Element):
                yield element
        except AttributeError:
            continue


def get_elements_by_ifctype(ifc_type: str, doc=FreeCAD.ActiveDocument):
    """Generator throught FreeCAD document element of specific ifc_type"""
    for element in doc.Objects:
        try:
            if element.IfcType == ifc_type:
                yield element
        except (AttributeError, ReferenceError):
            continue


def get_unit_conversion_factor(ifc_file, unit_type, default=None):
    # TODO: Test with Imperial units
    units = [
        u
        for u in ifc_file.by_type("IfcUnitAssignment")[0][0]
        if getattr(u, "UnitType", None) == unit_type
    ]
    if len(units) == 0:
        return default

    ifc_unit = units[0]

    unit_factor = 1.0
    if ifc_unit.is_a("IfcConversionBasedUnit"):
        ifc_unit = ifc_unit.ConversionFactor
        unit_factor = ifc_unit.wrappedValue

    assert ifc_unit.is_a("IfcSIUnit")
    prefix_factor = unit.get_prefix_multiplier(ifc_unit.Prefix)

    return unit_factor * prefix_factor


def generate_ifc_rel_space_boundaries(ifc_path, doc=FreeCAD.ActiveDocument):
    """Display IfcRelSpaceBoundaries from selected IFC file into FreeCAD documennt"""
    ifc_file = ifcopenshell.open(ifc_path)

    # Generate elements (Door, Window, Wall, Slab etc…) without their geometry
    Project.length_factor = get_unit_conversion_factor(ifc_file, "LENGTHUNIT")
    elements_group = get_or_create_group("Elements", doc)
    ifc_elements = (e for e in ifc_file.by_type("IfcElement") if e.ProvidesBoundaries)
    for ifc_entity in ifc_elements:
        elements_group.addObject(create_fc_object_from_entity(ifc_entity))

    # Generate projects structure and boundaries
    for ifc_project in ifc_file.by_type("IfcProject"):
        project = create_project_from_entity(ifc_project)
        generate_containers(ifc_project, project, doc)

    # Associate CorrespondingBoundary
    associate_corresponding_boundaries(doc)

    # Associate Host / Hosted elements
    associate_host_element(ifc_file, elements_group)

    # Associate hosted elements an fill gaps
    for fc_space in get_elements_by_ifctype("IfcSpace", doc):
        fc_boundaries = fc_space.SecondLevel.Group
        # Minimal number of boundary is 5: 3 vertical faces, 2 horizontal faces
        # If there is less than 5 boundaries there is an issue or a new case to analyse
        if len(fc_boundaries) == 5:
            continue
        elif len(fc_boundaries) < 5:
            assert ValueError, f"{fc_space.Label} has less than 5 boundaries"

        # Associate hosted elements
        associate_inner_boundaries(fc_boundaries, doc)


def processing_sia_boundaries(doc=FreeCAD.ActiveDocument):
    """Create SIA specific boundaries cf. https://www.sia.ch/fr/services/sia-norm/"""
    for space in get_elements_by_ifctype("IfcSpace", doc):
        ensure_hosted_element_are(space, doc)
        join_over_splitted_boundaries(space, doc)
        find_closest_edges(space)
        set_leso_type(space)
    create_sia_boundaries(doc)
    doc.recompute()


def write_xml(doc=FreeCAD.ActiveDocument):
    bem_xml = BEMxml()
    for project in get_elements_by_ifctype("IfcProject", doc):
        bem_xml.write_project(project)
    for space in get_elements_by_ifctype("IfcSpace", doc):
        bem_xml.write_space(space)
        for boundary in space.SecondLevel.Group:
            bem_xml.write_boundary(boundary)
    for building_element in get_elements(doc):
        bem_xml.write_building_elements(building_element)
    return bem_xml


def output_xml_to_path(bem_xml, xml_path=None):
    if not xml_path:
        xml_path = (
            "./output.xml" if os.name == "nt" else "/home/cyril/git/BIMxBEM/output.xml"
        )
    bem_xml.write_to_file(xml_path)


def join_over_splitted_boundaries(space, doc=FreeCAD.ActiveDocument):
    boundaries = space.SecondLevel.Group
    # Considered as the minimal size for an oversplit to occur (1 ceiling, 3 wall, 1 flooring)
    if len(boundaries) < 5:
        return
    elements_dict = dict()
    for rel_boundary in boundaries:
        try:
            key = f"{rel_boundary.RelatedBuildingElement.Id}"
        except AttributeError:
            if rel_boundary.PhysicalOrVirtualBoundary == "VIRTUAL":
                logger.info("IfcElement %s is VIRTUAL. Modeling error ?")
                key = None
            else:
                logger.warning(
                    "IfcElement %s has no RelatedBuildingElement", rel_boundary.Id
                )
        corresponding_boundary = rel_boundary.CorrespondingBoundary
        if corresponding_boundary:
            key += str(corresponding_boundary.Id)
        elements_dict.setdefault(key, []).append(rel_boundary)
    for key, boundary_list in elements_dict.items():
        # None coplanar boundaries should not be connected.
        # eg. round wall splitted with multiple orientations.

        # Case1: No oversplitted boundaries
        if len(boundary_list) == 1:
            continue

        coplanar_boundaries = list([])
        for boundary in boundary_list:
            if not coplanar_boundaries:
                coplanar_boundaries.append([boundary])
                continue
            for coplanar_list in coplanar_boundaries:
                # TODO: Test if this test is not too strict considering precision
                if is_coplanar(boundary, coplanar_list[0]):
                    coplanar_list.append(boundary)
                    break
            else:
                coplanar_boundaries.append([boundary])

        for coplanar_list in coplanar_boundaries:
            # Case 1 : only 1 boundary related to the same element. Cannot group boundaries.
            if len(coplanar_list) == 1:
                continue
            # Case 2 : more than 1 boundary related to the same element might be grouped.
            try:
                join_boundaries(coplanar_list, doc)
            except Part.OCCError:
                logger.warning(
                    f"Cannot join boundaries in space <{space.Id}> with key <{key}>"
                )


def join_boundaries(boundaries: list, doc=FreeCAD.ActiveDocument):
    """Try to join coplanar boundaries"""
    result_boundary = boundaries.pop()
    inner_wires = get_inner_wires(result_boundary)[:]
    vectors1 = get_boundary_outer_vectors(result_boundary)
    junction_found = True
    remove_from_doc = list()

    def find_and_join():
        for boundary2 in boundaries:
            vectors2 = get_boundary_outer_vectors(boundary2)
            for ei1, ei2 in itertools.product(
                range(len(vectors1)), range(len(vectors2))
            ):

                # retrieves points from previous edge to next edge included.
                p0_1, p0_2 = (vectors1[ei1], vectors1[(ei1 + 1) % len(vectors1)])
                p1_1, p1_2 = (vectors2[ei2], vectors2[(ei2 + 1) % len(vectors2)])

                v0_12 = p0_2 - p0_1
                v1_12 = p1_2 - p1_1

                dir0 = (v0_12).normalize()
                dir1 = (v1_12).normalize()

                # if edge1 and edge2 are not collinear no junction is possible.
                if not (
                    (dir0.isEqual(dir1, TOLERANCE) or dir0.isEqual(-dir1, TOLERANCE))
                    and v0_12.cross(p1_1 - p0_1).Length < TOLERANCE
                ):
                    continue

                # Check in which order vectors1 and vectors2 should be connected
                if dir0.isEqual(dir1, TOLERANCE):
                    p0_1_next_point, other_point = p1_1, p1_2
                    reverse_new_points = True
                else:
                    p0_1_next_point, other_point = p1_2, p1_1
                    reverse_new_points = False

                # Check if edge1 and edge2 have a common segment
                if not (
                    dir0.dot(p0_1_next_point - p0_1) < dir0.dot(p0_2 - p0_1)
                    and dir0.negative().dot(other_point - p0_2)
                    < dir0.negative().dot(p0_1 - p0_2)
                ):
                    continue

                # join vectors1 and vectors2 at indexes
                new_points = vectors2[ei2 + 1 :] + vectors2[: ei2 + 1]
                if reverse_new_points:
                    new_points.reverse()

                # Efficient way to insert elements at index : https://stackoverflow.com/questions/14895599/insert-an-element-at-specific-index-in-a-list-and-return-updated-list/48139870#48139870
                vectors1[ei1 + 1 : ei1 + 1] = new_points

                clean_vectors(vectors1)
                inner_wires.extend(get_inner_wires(boundary2))
                if not result_boundary.IsHosted:
                    for inner_boundary in boundary2.InnerBoundaries:
                        append(result_boundary, "InnerBoundaries", inner_boundary)
                        inner_boundary.ParentBoundary = result_boundary.Id
                boundaries.remove(boundary2)
                remove_from_doc.append(boundary2)
                return True
        else:
            logger.warning(
                f"Unable to join boundaries RelSpaceBoundary Id <{result_boundary.Id}> with boundaries <{(b.Id for b in boundaries)}>"
            )
            return False

    while boundaries and junction_found:
        junction_found = find_and_join()

    common_edge_found = True
    while common_edge_found:
        for ei1, ei2 in itertools.combinations(range(len(vectors1)), 2):

            # retrieves points from previous edge to next edge included.
            p0_1, p0_2 = (vectors1[ei1], vectors1[(ei1 + 1) % len(vectors1)])
            p1_1, p1_2 = (vectors1[ei2], vectors1[(ei2 + 1) % len(vectors1)])

            v0_12 = p0_2 - p0_1
            v1_12 = p1_2 - p1_1

            dir0 = (v0_12).normalize()
            dir1 = (v1_12).normalize()

            # if edge1 and edge2 are not collinear no junction is possible.
            same_dir = dir0.isEqual(dir1, TOLERANCE)
            if not (
                (same_dir or dir0.isEqual(-dir1, TOLERANCE))
                and v0_12.cross(p1_1 - p0_1).Length < TOLERANCE
            ):
                continue

            # Check in which order vectors1 and vectors2 should be connected
            if same_dir:
                p0_1_next_point, other_point = p1_1, p1_2
                reverse_new_points = True
            else:
                p0_1_next_point, other_point = p1_2, p1_1
                reverse_new_points = False

            # Check if edge1 and edge2 have a common segment
            if not (
                dir0.dot(p0_1_next_point - p0_1) < dir0.dot(p0_2 - p0_1)
                and dir0.negative().dot(other_point - p0_2)
                < dir0.negative().dot(p0_1 - p0_2)
            ):
                continue

            # join vectors1 and vectors2 at indexes
            vectors_split1 = vectors1[: ei1 + 1] + vectors1[ei2 + 1 :]
            vectors_split2 = vectors1[ei1 + 1 : ei2 + 1]
            clean_vectors(vectors_split1)
            clean_vectors(vectors_split2)
            area1 = Part.Face(
                Part.makePolygon(vectors_split1 + [vectors_split1[0]])
            ).Area
            area2 = Part.Face(
                Part.makePolygon(vectors_split2 + [vectors_split2[0]])
            ).Area
            if area1 > area2:
                vectors1 = vectors_split1
                inner_vectors = vectors_split2
            else:
                vectors1 = vectors_split2
                inner_vectors = vectors_split1

            close_vectors(inner_vectors)
            inner_wires.extend([Part.makePolygon(inner_vectors)])

            common_edge_found = True
            break
        else:
            common_edge_found = False

    # Replace existing shape with joined shapes
    close_vectors(vectors1)
    outer_wire = Part.makePolygon(vectors1)

    generate_boundary_compound(result_boundary, outer_wire, inner_wires)

    # Clean FreeCAD document if join operation was a success
    for fc_object in remove_from_doc:
        doc.removeObject(fc_object.Name)


def generate_boundary_compound(boundary, outer_wire: Part.Wire, inner_wires: list):
    """Generate boundary compound composed of 1 Face, 1 OuterWire, 0-n InnerWires"""
    face = Part.Face(outer_wire)
    for inner_wire in inner_wires:
        new_face = face.cut(Part.Face(inner_wire))
        if not new_face.Area:
            b_id = (
                boundary.Id if isinstance(boundary, Root) else boundary.SourceBoundary
            )
            logger.warning(
                f"Failure. An inner_wire did not cut face correctly in boundary <{b_id}>. OuterWire area = {Part.Face(outer_wire).Area / 10 ** 6}, InnerWire area = {Part.Face(inner_wire).Area / 10 ** 6}"
            )
            continue
        face = new_face
    boundary.Shape = Part.Compound([face, outer_wire, *inner_wires])


def ensure_hosted_element_are(space, doc=FreeCAD.ActiveDocument):
    for boundary in space.SecondLevel.Group:
        try:
            ifc_type = boundary.RelatedBuildingElement.IfcType
        except AttributeError:
            continue

        if not is_typically_hosted(ifc_type):
            continue

        if boundary.IsHosted and boundary.ParentBoundary:
            continue

        def find_host(boundary):
            fallback_solution = None
            normal = get_normal_at(boundary)
            for boundary2 in space.SecondLevel.Group:
                if not normal.isEqual(get_normal_at(boundary2), TOLERANCE):
                    continue

                fallback_solution = boundary2
                for inner_wire in get_inner_wires(boundary2):
                    if (
                        not abs(Part.Face(inner_wire).Area - boundary.Area.Value)
                        < TOLERANCE
                    ):
                        continue

                    return boundary2
            else:
                if not fallback_solution:
                    raise HostNotFound(
                        f"No host found for RelSpaceBoundary Id<{boundary.Id}>"
                    )
                logger.warning(
                    f"Using fallback solution to resolve host of RelSpaceBoundary Id<{boundary.Id}>"
                )
                return fallback_solution

        try:
            host = find_host(boundary)
        except HostNotFound as err:
            logger.exception(err)
        boundary.IsHosted = True
        boundary.ParentBoundary = host.Id
        append(host, "InnerBoundaries", boundary)


def is_typically_hosted(ifc_type: str):
    """Say if given ifc_type is typically hosted eg. windows, doors"""
    usually_hosted_types = ("IfcWindow", "IfcDoor", "IfcOpeningElement")
    for usual_type in usually_hosted_types:
        if ifc_type.startswith(usual_type):
            return True
    else:
        return False


class HostNotFound(LookupError):
    pass


def clean_vectors(vectors):
    """Clean vectors for polygons creation
    Keep only 1 point if 2 consecutive points are equal.
    Remove point if it makes border go back and forth"""
    count = len(vectors)
    i = 0
    while count:
        count -= 1
        p1 = vectors[i - 1]
        p2 = vectors[i]
        p3 = vectors[(i + 1) % len(vectors)]
        if (
            p2.isEqual(p3, TOLERANCE)
            or p1.isEqual(p2, TOLERANCE)
            or are_3points_collinear(p1, p2, p3)
        ):
            vectors.remove(p2)
            continue
        i += 1


def get_wires(boundary):
    return (s for s in boundary.Shape.SubShapes if isinstance(s, Part.Wire))


def get_outer_wire(boundary):
    return [s for s in boundary.Shape.SubShapes if isinstance(s, Part.Wire)][0]


def get_inner_wires(boundary):
    return [s for s in boundary.Shape.SubShapes if isinstance(s, Part.Wire)][1:]


def close_vectors(vectors):
    vectors.append(vectors[0])


def vectors_dir(p1, p2) -> FreeCAD.Vector:
    return (p2 - p1).normalize()


def are_3points_collinear(p1, p2, p3) -> bool:
    dir1 = vectors_dir(p1, p2)
    dir2 = vectors_dir(p2, p3)
    return dir1.isEqual(dir2, TOLERANCE) or dir1.isEqual(-dir2, TOLERANCE)


def get_boundary_outer_vectors(boundary):
    return [vx.Point for vx in get_outer_wire(boundary).Vertexes]


def is_collinear(edge1, edge2):
    v0_0, v0_1 = (vx.Point for vx in edge1.Vertexes)
    v1_0, v1_1 = (vx.Point for vx in edge2.Vertexes)
    if is_collinear_or_parallel(v0_0, v0_1, v1_0, v1_1):
        return v0_0 == v1_0 or is_collinear_or_parallel(v0_0, v0_1, v0_0, v1_0)


def is_collinear_or_parallel(v0_0, v0_1, v1_0, v1_1):
    return abs(direction(v0_0, v0_1).dot(direction(v1_0, v1_1))) > 0.9999


def direction(v0, v1):
    return (v0 - v1).normalize()


def find_closest_edges(space):
    """Find closest boundary and edge to be able to reconstruct a closed shell"""
    boundaries = [b for b in space.SecondLevel.Group if not b.IsHosted]
    Closest = namedtuple("Closest", ["boundary", "edge", "distance"])
    # Initialise defaults values
    for boundary in boundaries:
        n_edges = len(get_outer_wire(boundary).Edges)
        boundary.Proxy.closest = [
            Closest(boundary=None, edge=-1, distance=100000)
        ] * n_edges

    def compare_closest(boundary1, ei1, edge1, boundary2, ei2, edge2):
        is_closest = False
        closest_boundary, closest_edge, distance = boundary1.Proxy.closest[ei1]
        edge_to_edge = compute_distance(edge1, edge2)

        if distance <= TOLERANCE:
            return

        # Perfect match
        if edge_to_edge <= TOLERANCE:
            is_closest = True

        elif edge_to_edge - distance - TOLERANCE <= 0:
            # Case 1 : boundaries point in same direction so all solution are valid.
            dot_dir = get_normal_at(boundary2).dot(get_normal_at(boundary1))
            if abs(dot_dir) >= 1 - TOLERANCE:
                is_closest = True
            # Case 2 : boundaries intersect
            else:
                # Check if projection on plane intersection cross boundary1. If so edge2 cannot be a valid solution.
                pnt1 = edge1.CenterOfMass
                plane_intersect = get_plane(boundary1).intersect(get_plane(boundary2))[
                    0
                ]
                v_ab = plane_intersect.Direction
                v_ap = pnt1 - plane_intersect.Location
                pnt2 = pnt1 + FreeCAD.Vector().projectToLine(v_ap, v_ab)
                try:
                    projection_edge = Part.makeLine(pnt1, pnt2)
                    common = projection_edge.common(boundary1.Shape.Faces[0])
                    if common.Length <= TOLERANCE:
                        is_closest = True
                # Catch case where pnt1 == pnt2 which is fore sure a valid solution.
                except Part.OCCError:
                    is_closest = True
        if is_closest:
            boundary1.Proxy.closest[ei1] = Closest(boundary2, ei2, edge_to_edge)

    # Loop through all boundaries and edges to find the closest edge
    for boundary1, boundary2 in itertools.combinations(boundaries, 2):
        # If boundary1 and boundary2 are facing an opposite direction no match possible
        if get_normal_at(boundary2).dot(get_normal_at(boundary1)) <= -1 + TOLERANCE:
            continue

        edges1 = get_outer_wire(boundary1).Edges
        edges2 = get_outer_wire(boundary2).Edges
        for (ei1, edge1), (ei2, edge2) in itertools.product(
            enumerate(edges1), enumerate(edges2)
        ):
            if not is_low_angle(edge1, edge2):
                continue

            compare_closest(boundary1, ei1, edge1, boundary2, ei2, edge2)
            compare_closest(boundary2, ei2, edge2, boundary1, ei1, edge1)

    # Store found values in standard FreeCAD properties
    for boundary in boundaries:
        closest_boundaries, boundary.ClosestEdges, closest_distances = (
            list(i) for i in zip(*boundary.Proxy.closest)
        )
        boundary.ClosestBoundaries = [b.Id if b else -1 for b in closest_boundaries]
        boundary.ClosestDistance = [int(d) for d in closest_distances]


def set_leso_type(space):
    for boundary in space.SecondLevel.Group:
        boundary.LesoType = define_leso_type(boundary)


def define_leso_type(boundary):
    try:
        ifc_type = boundary.RelatedBuildingElement.IfcType
    except AttributeError:
        if boundary.PhysicalOrVirtualBoundary != "VIRTUAL":
            logger.warning(f"Unable to define LesoType for boundary <{boundary.Id}>")
        return "Unknown"
    if ifc_type.startswith("IfcWindow"):
        return "Window"
    elif ifc_type.startswith("IfcDoor"):
        return "Door"
    elif ifc_type.startswith("IfcWall"):
        return "Façade"
    elif ifc_type.startswith("IfcSlab") or ifc_type == "IfcRoof":
        # Pointing up => Ceiling. Pointing down => Flooring
        if boundary.Shape.Faces[0].normalAt(0, 0).z > 0:
            return "Ceiling"
        return "Flooring"
    elif ifc_type.startswith("IfcOpeningElement"):
        return "Opening"
    else:
        logger.warning(f"Unable to define LesoType for Boundary Id <{boundary.Id}>")
        return "Unknown"


def compute_distance(edge1, edge2):
    mid_point = edge1.CenterOfMass
    line_segment = (v.Point for v in edge2.Vertexes)
    return mid_point.distanceToLineSegment(*line_segment).Length


def is_low_angle(edge1, edge2):
    dir1 = (edge1.Vertexes[1].Point - edge1.Vertexes[0].Point).normalize()
    dir2 = (edge2.Vertexes[1].Point - edge2.Vertexes[0].Point).normalize()
    return abs(dir1.dot(dir2)) > 0.5  # Low angle considered as < 30°. cos(pi/3)=0.5.


def associate_host_element(ifc_file, elements_group):
    # Associate Host / Hosted elements
    ifc_elements = (e for e in ifc_file.by_type("IfcElement") if e.ProvidesBoundaries)
    for ifc_entity in ifc_elements:
        if ifc_entity.FillsVoids:
            host = get_element_by_guid(get_host_guid(ifc_entity), elements_group)
            hosted = get_element_by_guid(ifc_entity.GlobalId, elements_group)
            append(host, "HostedElements", hosted)
            hosted.HostElement = host.Id


def associate_inner_boundaries(fc_boundaries, doc):
    """Associate hosted elements like a window or a door in a wall"""
    for fc_boundary in fc_boundaries:
        if not fc_boundary.IsHosted:
            continue
        candidates = set(fc_boundaries).intersection(
            get_boundaries_by_element_id(
                fc_boundary.RelatedBuildingElement.HostElement, doc
            )
        )

        # If there is more than 1 candidate it doesn't really matter
        # as they share the same host element and space
        try:
            host_element = candidates.pop()
        except KeyError:
            logger.warning(
                f"RelSpaceBoundary Id<{fc_boundary.Id}> is hosted but host not found. Investigations required."
            )
            continue
        fc_boundary.ParentBoundary = host_element.Id
        append(host_element, "InnerBoundaries", fc_boundary)


def associate_coplanar_boundaries(fc_boundaries):
    """ Find coplanar boundaries to identify hosted boundaries and fill gaps (2b)
    FIXME: Apparently in ArchiCAD, doors are not coplanar.
    Idea: Make it coplanar with other boundaries sharing the same space+wall before"""
    for fc_boundary_1, fc_boundary_2 in itertools.combinations(fc_boundaries, 2):
        if is_coplanar(fc_boundary_1, fc_boundary_2):
            append(fc_boundary_1, "ShareRelatedElementWith", fc_boundary_2)
            append(fc_boundary_2, "ShareRelatedElementWith", fc_boundary_1)


def associate_corresponding_boundaries(doc=FreeCAD.ActiveDocument):
    # Associate CorrespondingBoundary
    for fc_boundary in get_elements_by_ifctype("IfcRelSpaceBoundary", doc):
        associate_corresponding_boundary(fc_boundary, doc)


def is_coplanar(shape_1, shape_2):
    """Intended for RelSpaceBoundary use only
    For some reason native Part.Shape.isCoplanar(Part.Shape) do not always work"""
    return get_plane(shape_1).toShape().isCoplanar(get_plane(shape_2).toShape())


def get_plane(fc_boundary):
    """Intended for RelSpaceBoundary use only"""
    return Part.Plane(fc_boundary.Shape.Vertexes[0].Point, get_normal_at(fc_boundary))


def get_normal_at(fc_boundary, at=(0, 0)):
    return fc_boundary.Shape.Faces[0].normalAt(*at)


def append(doc_object, fc_property, value):
    """Intended to manipulate FreeCAD list like properties only"""
    current_value = getattr(doc_object, fc_property)
    current_value.append(value)
    setattr(doc_object, fc_property, current_value)


def clean_corresponding_candidates(fc_boundary, doc):
    other_boundaries = get_boundaries_by_element(
        fc_boundary.RelatedBuildingElement, doc
    )
    other_boundaries.remove(fc_boundary)
    return [
        b
        for b in other_boundaries
        if not b.CorrespondingBoundary or b.RelatingSpace != fc_boundary.RelatingSpace
    ]


def get_boundaries_by_element(element, doc):
    return [
        boundary
        for boundary in get_elements_by_ifctype("IfcRelSpaceBoundary", doc)
        if boundary.RelatedBuildingElement == element
    ]


def get_boundaries_by_element_id(element_id, doc):
    def _compare_related_id(boundary, id):
        try:
            return boundary.RelatedBuildingElement.Id == element_id
        except AttributeError:
            if boundary.PhysicalOrVirtualBoundary != "VIRTUAL":
                logger.warning(
                    f"RelSpaceBoundary Id<{boundary.Id}> is not VIRTUAL and has\
                        no RelatedBuildingElement. Investigations required"
                )
            return False

    return [
        boundary
        for boundary in get_elements_by_ifctype("IfcRelSpaceBoundary", doc)
        if _compare_related_id(boundary, element_id)
    ]


def associate_corresponding_boundary(fc_boundary, doc):
    """Associate corresponding boundaries according to IFC definition.

    Reference to the other space boundary of the pair of two space boundaries on either side of a space separating thermal boundary element.
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcrelspaceboundary2ndlevel.htm
    """
    if (
        fc_boundary.InternalOrExternalBoundary != "INTERNAL"
        or fc_boundary.CorrespondingBoundary
    ):
        return

    other_boundaries = clean_corresponding_candidates(fc_boundary, doc)
    if len(other_boundaries) == 1:
        corresponding_boundary = other_boundaries[0]
    else:
        center_of_mass = get_outer_wire(fc_boundary).CenterOfMass
        min_lenght = 10000  # No element has 10 m
        for boundary in other_boundaries:
            distance = center_of_mass.distanceToPoint(
                get_outer_wire(boundary).CenterOfMass
            )
            if distance < min_lenght:
                min_lenght = distance
                corresponding_boundary = boundary
    try:
        fc_boundary.CorrespondingBoundary = corresponding_boundary
        corresponding_boundary.CorrespondingBoundary = fc_boundary
    except NameError:
        # TODO: What to do with uncorrectly classified boundaries which have no corresponding boundary
        logger.warning(f"Boundary {fc_boundary.GlobalId} from space {fc_boundary}")
        return


def get_related_element(ifc_entity, doc=FreeCAD.ActiveDocument):
    if not ifc_entity.RelatedBuildingElement:
        return
    guid = ifc_entity.RelatedBuildingElement.GlobalId
    for element in doc.Objects:
        try:
            if element.GlobalId == guid:
                return element
        except AttributeError:
            continue


def get_host_guid(ifc_entity):
    return (
        ifc_entity.FillsVoids[0]
        .RelatingOpeningElement.VoidsElements[0]
        .RelatingBuildingElement.GlobalId
    )


def get_element_by_guid(guid, elements_group):
    for fc_element in elements_group.Group:
        if fc_element.GlobalId == guid:
            return fc_element
    else:
        logger.warning(f"Unable to get element by {guid}")


def get_thickness(ifc_entity):
    thickness = 0
    if ifc_entity.IsDecomposedBy:
        ifc_entity = ifc_entity.IsDecomposedBy[0].RelatedObjects[0]

    for association in ifc_entity.HasAssociations:
        if not association.is_a("IfcRelAssociatesMaterial"):
            continue
        try:
            material_layers = association.RelatingMaterial.ForLayerSet.MaterialLayers
        except AttributeError:
            try:
                material_layers = association.RelatingMaterial.MaterialLayers
            except AttributeError:
                # TODO: Fallback method to handle materials with no layers. eg. association.RelatingMaterial.Materials
                continue

        for material_layer in material_layers:
            thickness += material_layer.LayerThickness * SCALE * Project.length_factor
    return thickness


def create_sia_boundaries(doc=FreeCAD.ActiveDocument):
    """Create boundaries necessary for SIA calculations"""
    project = next(get_elements_by_ifctype("IfcProject", doc))
    is_from_revit = project.ApplicationIdentifier == "Revit"
    is_from_archicad = project.ApplicationFullName == "ARCHICAD-64"
    for space in get_elements_by_ifctype("IfcSpace", doc):
        create_sia_ext_boundaries(space, is_from_revit, is_from_archicad)
        create_sia_int_boundaries(space, is_from_revit, is_from_archicad)
        rejoin_boundaries(space, "SIA_Exterior")
        rejoin_boundaries(space, "SIA_Interior")


def rejoin_boundaries(space, sia_type):
    """
    Rejoin boundaries after their translation to get a correct close shell surfaces.
    1 Fill gaps between boundaries (2b)
    2 Fill gaps gerenate by translation to make a boundary on the inside or outside boundary of building elements
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4/ADD2_TC1/HTML/schema/ifcproductextension/lexical/ifcrelspaceboundary2ndlevel.htm
    """
    base_boundaries = space.SecondLevel.Group
    for base_boundary in base_boundaries:
        lines = []
        boundary1 = getattr(base_boundary, sia_type)
        if (
            base_boundary.IsHosted
            or base_boundary.PhysicalOrVirtualBoundary == "VIRTUAL"
        ):
            continue
        for b2_id, (ei1, ei2) in zip(
            base_boundary.ClosestBoundaries, enumerate(base_boundary.ClosestEdges)
        ):
            boundary2 = getattr(get_in_list_by_id(base_boundaries, b2_id), sia_type, None)
            if not boundary2:
                logger.warning(f"Cannot find corresponding boundary with id <{b2_id}>")
                lines.append(line_from_edge(get_outer_wire(base_boundary).Edges[ei1]))
                continue
            base_plane = get_plane(boundary1)
            # Case 1 : boundaries are not parallel
            plane_intersect = base_plane.intersect(get_plane(boundary2))
            if plane_intersect:
                lines.append(plane_intersect[0])
                continue
            # Case 2 : boundaries are parallel
            line1 = line_from_edge(get_outer_wire(boundary1).Edges[ei1])
            try:
                line2 = line_from_edge(get_outer_wire(boundary2).Edges[ei2])
            except IndexError:
                logger.warning(
                    f"Cannot find closest edge index <{ei2}> in boundary id <{b2_id}> to rejoin boundary <{base_boundary.Id}>"
                )
                lines.append(line_from_edge(get_outer_wire(base_boundary).Edges[ei1]))
                continue

            # Case 2a : edges are not parallel
            line_intersect = line1.intersect2d(line2, base_plane)
            if line_intersect:
                point1 = line_intersect[0]
                # TODO: Investigate to see if line.intersect2d(line2, base_plane) might cause some real issues
                if not isinstance(point1, FreeCAD.Vector):
                    point1 = FreeCAD.Vector(*point1)
                if line1.Direction.dot(line2.Direction) > 0:
                    point2 = point1 + line1.Direction + line2.Direction
                else:
                    point2 = point1 + line1.Direction - line2.Direction
            # Case 2b : edges are parallel
            else:
                point1 = (line1.Location + line2.Location) * 0.5
                point2 = point1 + line1.Direction

            try:
                lines.append(Part.Line(point1, point2))
            except Part.OCCError as err:
                logger.exception(
                    f"Failure in boundary id <{base_boundary.Id}> {point1} and {point2} are equal"
                )

        # Generate new shape
        try:
            outer_wire = polygon_from_lines(lines)
        except NoIntersectionError:
            # TODO: Investigate to see why this happens
            logger.exception(f"Unable to rejoin boundary Id <{base_boundary.Id}>")
            continue
        except Part.OCCError as e:
            logger.exception(
                f"Invalid geometry while rejoining boundary Id <{base_boundary.Id}>"
            )
            continue
        try:
            face = Part.Face(outer_wire)
        except Part.OCCError:
            logger.exception(f"Unable to rejoin boundary Id <{base_boundary.Id}>")
            continue

        inner_wires = get_inner_wires(boundary1)
        generate_boundary_compound(boundary1, outer_wire, inner_wires)

        boundary1.Area = area = boundary1.Shape.Area
        for inner_boundary in base_boundary.InnerBoundaries:
            area = area + inner_boundary.Shape.Area
        boundary1.AreaWithHosted = area


def get_in_list_by_id(elements, element_id):
    if element_id == -1:
        return None
    for element in elements:
        if element.Id == element_id:
            return element
    else:
        raise LookupError(f"No element with Id <{element_id}> found")


def create_sia_ext_boundaries(space, is_from_revit, is_from_archicad):
    """Create SIA boundaries from RelSpaceBoundaries and translate it if necessary"""
    sia_group_obj = space.Boundaries.newObject(
        "App::DocumentObjectGroup", "SIA_Exteriors"
    )
    space.SIA_Exteriors = sia_group_obj
    for boundary1 in space.SecondLevel.Group:
        if boundary1.IsHosted or boundary1.PhysicalOrVirtualBoundary == "VIRTUAL":
            continue
        bem_boundary = BEMBoundary.create(boundary1, "SIA_Exterior")
        sia_group_obj.addObject(bem_boundary)
        thickness = boundary1.RelatedBuildingElement.Thickness.Value
        ifc_type = boundary1.RelatedBuildingElement.IfcType
        normal = boundary1.Shape.Faces[0].normalAt(0, 0)
        # if is_from_archicad:
        # normal = -normal
        # EXTERNAL: there is multiple possible values for external so testing internal is better.
        if boundary1.InternalOrExternalBoundary != "INTERNAL":
            lenght = thickness
            if is_from_revit and ifc_type.startswith("IfcWall"):
                lenght /= 2
            bem_boundary.Placement.move(normal * lenght)
        # INTERNAL. TODO: Check during tests if NOTDEFINED case need to be handled ?
        else:
            type1 = {"IfcSlab"}
            if ifc_type in type1:
                lenght = thickness / 2
            else:
                if is_from_revit:
                    continue
                lenght = thickness / 2
            bem_boundary.Placement.move(normal * lenght)


def create_sia_int_boundaries(space, is_from_revit, is_from_archicad):
    """Create boundaries necessary for SIA calculations"""
    sia_group_obj = space.Boundaries.newObject(
        "App::DocumentObjectGroup", "SIA_Interiors"
    )
    space.SIA_Interiors = sia_group_obj
    for boundary in space.SecondLevel.Group:
        if boundary.IsHosted or boundary.PhysicalOrVirtualBoundary == "VIRTUAL":
            continue
        normal = boundary.Shape.Faces[0].normalAt(0, 0)
        if is_from_archicad:
            normal = -normal

        bem_boundary = BEMBoundary.create(boundary, "SIA_Interior")
        sia_group_obj.addObject(bem_boundary)

        ifc_type = boundary.RelatedBuildingElement.IfcType
        if is_from_revit and ifc_type.startswith("IfcWall"):
            thickness = boundary.RelatedBuildingElement.Thickness.Value
            lenght = -thickness / 2
            bem_boundary.Placement.move(normal * lenght)


def line_from_edge(edge: Part.Edge) -> Part.Line:
    points = [v.Point for v in edge.Vertexes]
    return Part.Line(*points)


def polygon_from_lines(lines):
    new_points = []
    for line1, line2 in zip(lines, lines[1:] + lines[:1]):
        try:
            # Need to ensure direction are not same to avoid crash
            if abs(line1.Direction.dot(line2.Direction)) >= 1 - TOLERANCE:
                continue
            new_points.append(line1.intersectCC(line2, 1)[0].toShape().Point)
        except IndexError:
            raise NoIntersectionError
    new_points[0:0] = new_points[-1:]
    return Part.makePolygon(new_points)


class NoIntersectionError(IndexError):
    pass


def create_fc_shape(space_boundary):
    """ Create Part shape from ifc geometry"""
    if BREP:
        try:
            return _part_by_brep(
                space_boundary.ConnectionGeometry.SurfaceOnRelatingElement
            )
        except RuntimeError:
            print(f"Failed to generate brep from {space_boundary}")
            fallback = True
    if not BREP or fallback:
        try:
            return part_by_wires(
                space_boundary.ConnectionGeometry.SurfaceOnRelatingElement
            )
        except RuntimeError:
            print(f"Failed to generate mesh from {space_boundary}")
            try:
                return _part_by_mesh(
                    space_boundary.ConnectionGeometry.SurfaceOnRelatingElement
                )
            except RuntimeError:
                raise ShapeCreationError


def _part_by_brep(ifc_entity):
    """ Create a Part Shape from brep generated by ifcopenshell from ifc geometry"""
    ifc_shape = ifcopenshell.geom.create_shape(BREP_SETTINGS, ifc_entity)
    fc_shape = Part.Shape()
    fc_shape.importBrepFromString(ifc_shape.brep_data)
    fc_shape.scale(SCALE)
    return fc_shape


def _part_by_mesh(ifc_entity):
    """ Create a Part Shape from mesh generated by ifcopenshell from ifc geometry"""
    return Part.Face(_polygon_by_mesh(ifc_entity))


def _polygon_by_mesh(ifc_entity):
    """Create a Polygon from a compatible ifc entity"""
    ifc_shape = ifcopenshell.geom.create_shape(MESH_SETTINGS, ifc_entity)
    ifc_verts = ifc_shape.verts
    fc_verts = [
        FreeCAD.Vector(ifc_verts[i : i + 3]).scale(SCALE, SCALE, SCALE)
        for i in range(0, len(ifc_verts), 3)
    ]
    fc_verts = verts_clean(fc_verts)

    return Part.makePolygon(fc_verts)


def verts_clean(vertices):
    """For some reason, vertices are not always clean and sometime a same vertex is repeated"""
    new_verts = list()
    for i in range(len(vertices) - 1):
        if vertices[i] != vertices[i + 1]:
            new_verts.append(vertices[i])
    new_verts.append(vertices[-1])
    return new_verts


def part_by_wires(ifc_entity):
    """ Create a Part Shape from ifc geometry"""
    inner_wires = list()
    outer_wire = _polygon_by_mesh(ifc_entity.OuterBoundary)
    face = Part.Face(outer_wire)
    try:
        inner_boundaries = ifc_entity.InnerBoundaries
        for inner_boundary in tuple(inner_boundaries) if inner_boundaries else tuple():
            inner_wire = _polygon_by_mesh(inner_boundary)
            face = face.cut(Part.Face(inner_wire))
            inner_wires.append(inner_wire)
    except RuntimeError:
        pass
    fc_shape = Part.Compound([face, outer_wire, *inner_wires])
    matrix = get_matrix(ifc_entity.BasisSurface.Position)
    fc_shape = fc_shape.transformGeometry(matrix)
    return fc_shape


def get_matrix(position):
    """Transform position to FreeCAD.Matrix"""
    total_scale = SCALE * Project.length_factor
    location = FreeCAD.Vector(position.Location.Coordinates)
    location.scale(*list(3 * [total_scale]))

    v_1 = FreeCAD.Vector(position.RefDirection.DirectionRatios)
    v_3 = FreeCAD.Vector(position.Axis.DirectionRatios)
    v_2 = v_3.cross(v_1)

    # fmt: off
    matrix = FreeCAD.Matrix(
        v_1.x, v_2.x, v_3.x, location.x,
        v_1.y, v_2.y, v_3.y, location.y,
        v_1.z, v_2.z, v_3.z, location.z,
        0, 0, 0, 1,
    )
    # fmt: on

    return matrix


def get_placement(space):
    """Retrieve object placement"""
    space_geom = ifcopenshell.geom.create_shape(BREP_SETTINGS, space)
    # IfcOpenShell matrix values FreeCAD matrix values are transposed
    ios_matrix = space_geom.transformation.matrix.data
    m_l = list()
    for i in range(3):
        line = list(ios_matrix[i::3])
        line[-1] *= SCALE
        m_l.extend(line)
    return FreeCAD.Matrix(*m_l)


def get_color(ifc_boundary):
    """Return a color depending on IfcClass given"""
    product_colors = {
        "IfcWall": (0.7, 0.3, 0.0),
        "IfcWindow": (0.0, 0.7, 1.0),
        "IfcSlab": (0.7, 0.7, 0.5),
        "IfcRoof": (0.0, 0.3, 0.0),
        "IfcDoor": (1.0, 1.0, 1.0),
    }
    if ifc_boundary.PhysicalOrVirtualBoundary == "VIRTUAL":
        return (1.0, 0.0, 1.0)

    ifc_product = ifc_boundary.RelatedBuildingElement
    for product, color in product_colors.items():
        # Not only test if IFC class is in dictionnary but it is a subclass
        if ifc_product.is_a(product):
            return color
    else:
        print(f"No color found for {ifc_product.is_a()}")
        return (0.0, 0.0, 0.0)


def get_or_create_group(name, doc=FreeCAD.ActiveDocument):
    """Get group by name or create one if not found"""
    group = doc.findObjects("App::DocumentObjectGroup", name)
    if group:
        return group[0]
    return doc.addObject("App::DocumentObjectGroup", name)


class Root:
    """Wrapping various IFC entity :
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcroot.htm
    """

    def __init__(self, obj, ifc_entity):
        self.Type = self.__class__.__name__
        obj.Proxy = self
        obj.addExtension("App::GroupExtensionPython", self)

        ifc_attributes = "IFC Attributes"
        obj.addProperty("App::PropertyString", "IfcType", "IFC")
        obj.addProperty("App::PropertyInteger", "Id", ifc_attributes)
        obj.addProperty("App::PropertyString", "GlobalId", ifc_attributes)
        obj.addProperty("App::PropertyString", "IfcName", ifc_attributes)
        obj.addProperty("App::PropertyString", "Description", ifc_attributes)

        obj.Id = ifc_entity.id()
        obj.GlobalId = ifc_entity.GlobalId
        obj.IfcType = ifc_entity.is_a()
        obj.IfcName = ifc_entity.Name or ""
        self.set_label(obj, ifc_entity)
        obj.Description = ifc_entity.Description or ""

    def onChanged(self, obj, prop):
        """Do something when a property has changed"""
        return

    def execute(self, obj):
        """Do something when doing a recomputation, this method is mandatory"""
        return

    @staticmethod
    def set_label(obj, ifc_entity):
        """Allow specific method for specific elements"""
        obj.Label = "{} {}".format(ifc_entity.id(), obj.Name)

    @classmethod
    def create(cls, obj_name, ifc_entity=None):
        """Stantard FreeCAD FeaturePython Object creation method
        ifc_entity : Optionnally provide a base entity.
        """
        obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", obj_name)
        feature_python_object = cls(obj)
        return obj


class ViewProviderRoot:
    def __init__(self, vobj):
        vobj.Proxy = self
        vobj.addExtension("Gui::ViewProviderGroupExtensionPython", self)


class RelSpaceBoundary(Root):
    """Wrapping IFC entity : 
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcrelspaceboundary2ndlevel.htm"""

    def __init__(self, obj, ifc_entity):
        super().__init__(obj, ifc_entity)
        obj.Proxy = self
        bem_category = "BEM"
        ifc_attributes = "IFC Attributes"
        obj.addProperty("App::PropertyInteger", "RelatingSpace", ifc_attributes)
        obj.addProperty("App::PropertyLink", "RelatedBuildingElement", ifc_attributes)
        obj.addProperty(
            "App::PropertyEnumeration", "PhysicalOrVirtualBoundary", ifc_attributes
        ).PhysicalOrVirtualBoundary = ["PHYSICAL", "VIRTUAL", "NOTDEFINED"]
        obj.addProperty(
            "App::PropertyEnumeration", "InternalOrExternalBoundary", ifc_attributes
        ).InternalOrExternalBoundary = [
            "INTERNAL",
            "EXTERNAL",
            "EXTERNAL_EARTH",
            "EXTERNAL_WATER",
            "EXTERNAL_FIRE",
            "NOTDEFINED",
        ]
        obj.addProperty("App::PropertyLink", "CorrespondingBoundary", ifc_attributes)
        obj.addProperty("App::PropertyInteger", "ParentBoundary", ifc_attributes)
        obj.addProperty("App::PropertyLinkList", "InnerBoundaries", ifc_attributes)
        obj.addProperty("App::PropertyLink", "ProcessedShape", bem_category)
        obj.addProperty("App::PropertyIntegerList", "ClosestBoundaries", bem_category)
        obj.addProperty("App::PropertyIntegerList", "ClosestEdges", bem_category)
        obj.addProperty("App::PropertyIntegerList", "ClosestDistance", bem_category)
        obj.addProperty("App::PropertyBoolList", "ClosestHasSameNormal", bem_category)
        obj.addProperty(
            "App::PropertyLinkList", "ShareRelatedElementWith", bem_category
        )
        obj.addProperty("App::PropertyBool", "IsHosted", bem_category)
        obj.addProperty("App::PropertyArea", "Area", bem_category)
        obj.addProperty("App::PropertyArea", "AreaWithHosted", bem_category)
        obj.addProperty("App::PropertyLink", "SIA_Interior", bem_category)
        obj.addProperty("App::PropertyLink", "SIA_Exterior", bem_category)
        obj.addProperty(
            "App::PropertyEnumeration", "LesoType", bem_category
        ).LesoType = [
            "Ceiling",
            "Façade",
            "Flooring",
            "Window",
            "Door",
            "Opening",
            "Unknown",
        ]

        if not ifc_entity:
            return

        if FreeCAD.GuiUp:
            obj.ViewObject.ShapeColor = get_color(ifc_entity)
        obj.GlobalId = ifc_entity.GlobalId
        obj.InternalOrExternalBoundary = ifc_entity.InternalOrExternalBoundary
        obj.PhysicalOrVirtualBoundary = ifc_entity.PhysicalOrVirtualBoundary
        obj.Shape = create_fc_shape(ifc_entity)
        obj.Area = obj.AreaWithHosted = obj.Shape.Area
        self.set_label(obj, ifc_entity)
        if not obj.PhysicalOrVirtualBoundary == "VIRTUAL":
            obj.IsHosted = bool(ifc_entity.RelatedBuildingElement.FillsVoids)
        obj.LesoType = "Unknown"

    @staticmethod
    def create(obj_name: str = "RelSpaceBoundary", ifc_entity=None):
        """Stantard FreeCAD FeaturePython Object creation method"""
        obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", obj_name)
        RelSpaceBoundary(obj, ifc_entity)
        try:
            # ViewProviderRelSpaceBoundary(obj.ViewObject)
            obj.ViewObject.Proxy = 0
        except AttributeError:
            FreeCAD.Console.PrintLog("No ViewObject ok if running with no Gui")
        return obj

    def onChanged(self, obj, prop):
        super().onChanged(obj, prop)
        if prop == "InnerBoundaries":
            obj.AreaWithHosted = self.recompute_area_with_hosted(obj)

    @staticmethod
    def recompute_area_with_hosted(obj):
        """Recompute area including inner boundaries"""
        area = obj.Area
        for boundary in obj.InnerBoundaries:
            area = area + boundary.Area
        return area

    @staticmethod
    def set_label(obj, ifc_entity):
        try:
            obj.Label = "{} {}".format(
                ifc_entity.id(), ifc_entity.RelatedBuildingElement.Name,
            )
        except AttributeError:
            obj.Label = f"{ifc_entity.id()} VIRTUAL"
            if ifc_entity.PhysicalOrVirtualBoundary != "VIRTUAL":
                logger.warning(
                    f"{ifc_entity.id()} is not VIRTUAL and has no RelatedBuildingElement"
                )

    @staticmethod
    def get_wires(obj):
        return get_wires(obj)


def create_fc_object_from_entity(ifc_entity):
    """Stantard FreeCAD FeaturePython Object creation method"""
    obj_name = "Element"
    obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", obj_name)
    Element(obj, ifc_entity)
    try:
        obj.ViewObject.Proxy = 0
    except AttributeError:
        FreeCAD.Console.PrintLog("No ViewObject ok if running with no Gui")
    return obj


class Element(Root):
    """Wrapping various IFC entity :
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/schema/ifcproductextension/lexical/ifcelement.htm
    """

    def __init__(self, obj, ifc_entity):
        super().__init__(obj, ifc_entity)
        self.Type = "IfcRelSpaceBoundary"
        obj.Proxy = self
        ifc_attributes = "IFC Attributes"
        bem_category = "BEM"
        obj.addProperty("App::PropertyLinkList", "HasAssociations", ifc_attributes)
        obj.addProperty("App::PropertyLinkList", "FillsVoids", ifc_attributes)
        obj.addProperty("App::PropertyLinkList", "HasOpenings", ifc_attributes)
        obj.addProperty(
            "App::PropertyIntegerList", "ProvidesBoundaries", ifc_attributes
        )
        obj.addProperty("App::PropertyLinkList", "HostedElements", bem_category)
        obj.addProperty("App::PropertyInteger", "HostElement", bem_category)
        obj.addProperty("App::PropertyLength", "Thickness", ifc_attributes)

        ifc_walled_entities = {"IfcWall", "IfcSlab", "IfcRoof"}
        for entity_class in ifc_walled_entities:
            if ifc_entity.is_a(entity_class):
                obj.Thickness = get_thickness(ifc_entity)


class BEMBoundary:
    def __init__(self, obj, boundary):
        self.Type = "BEMBoundary"
        obj.Proxy = self
        category_name = "BEM"
        obj.addProperty("App::PropertyInteger", "SourceBoundary", category_name)
        obj.SourceBoundary = boundary.Id
        obj.addProperty("App::PropertyArea", "Area", category_name)
        obj.addProperty("App::PropertyArea", "AreaWithHosted", category_name)
        obj.Shape = boundary.Shape.copy()
        self.set_label(obj, boundary)

    @staticmethod
    def create(boundary, geo_type):
        """Stantard FreeCAD FeaturePython Object creation method"""
        obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", "BEMBoundary")
        BEMBoundary(obj, boundary)
        setattr(boundary, geo_type, obj)
        try:
            # ViewProviderRelSpaceBoundary(obj.ViewObject)
            obj.ViewObject.Proxy = 0
            obj.ViewObject.ShapeColor = boundary.ViewObject.ShapeColor
        except AttributeError:
            FreeCAD.Console.PrintLog("No ViewObject ok if running with no Gui")
        return obj

    @staticmethod
    def set_label(obj, source_boundary):
        obj.Label = source_boundary.Label

    @staticmethod
    def get_wires(obj):
        return get_wires(obj)


def create_container_from_entity(ifc_entity):
    """Stantard FreeCAD FeaturePython Object creation method"""
    obj_name = ifc_entity.is_a()
    obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", obj_name)
    Container(obj, ifc_entity)
    if FreeCAD.GuiUp:
        obj.ViewObject.Proxy = ViewProviderRoot(obj.ViewObject)
        obj.ViewObject.DisplayMode = "Wireframe"
    return obj


class Container(Root):
    """Representation of an IfcProject:
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcproject.htm"""

    def __init__(self, obj, ifc_entity):
        super().__init__(obj, ifc_entity)
        self.ifc_entity = ifc_entity
        self.setProperties(obj)

    def setProperties(self, obj):
        return


def create_project_from_entity(ifc_entity):
    """Stantard FreeCAD FeaturePython Object creation method"""
    obj_name = "Project"
    obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", obj_name)
    Project(obj, ifc_entity)
    if FreeCAD.GuiUp:
        obj.ViewObject.Proxy = ViewProviderRoot(obj.ViewObject)
        obj.ViewObject.DisplayMode = "Wireframe"
    return obj


class Project(Root):
    """Representation of an IfcProject:
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcproject.htm"""

    length_factor = 1

    def __init__(self, obj, ifc_entity):
        super().__init__(obj, ifc_entity)
        self.ifc_entity = ifc_entity
        self.setProperties(obj)

    def setProperties(self, obj):
        ifc_entity = self.ifc_entity
        ifc_attributes = "IFC Attributes"
        obj.addProperty("App::PropertyString", "LongName", ifc_attributes)
        obj.addProperty("App::PropertyVector", "TrueNorth", ifc_attributes)
        obj.addProperty("App::PropertyVector", "WorldCoordinateSystem", ifc_attributes)
        obj.LongName = ifc_entity.LongName or ""
        obj.TrueNorth = FreeCAD.Vector(
            *ifc_entity.RepresentationContexts[0].TrueNorth.DirectionRatios
        )
        obj.WorldCoordinateSystem = FreeCAD.Vector(
            ifc_entity.RepresentationContexts[
                0
            ].WorldCoordinateSystem.Location.Coordinates
        )

        owning_application = "OwningApplication"
        obj.addProperty(
            "App::PropertyString", "ApplicationIdentifier", owning_application
        )
        obj.addProperty("App::PropertyString", "ApplicationVersion", owning_application)
        obj.addProperty(
            "App::PropertyString", "ApplicationFullName", owning_application
        )
        owning_application = ifc_entity.OwnerHistory.OwningApplication
        obj.ApplicationIdentifier = owning_application.ApplicationIdentifier
        obj.ApplicationVersion = owning_application.Version
        obj.ApplicationFullName = owning_application.ApplicationFullName


def create_space_from_entity(ifc_entity):
    """Stantard FreeCAD FeaturePython Object creation method"""
    obj_name = "Space"
    obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", obj_name)
    Space(obj, ifc_entity)
    if FreeCAD.GuiUp:
        obj.ViewObject.Proxy = ViewProviderRoot(obj.ViewObject)
        obj.ViewObject.DisplayMode = "Wireframe"
    return obj


class Space(Root):
    """Representation of an IfcProject:
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcproject.htm"""

    def __init__(self, obj, ifc_entity):
        super().__init__(obj, ifc_entity)
        self.ifc_entity = ifc_entity
        self.setProperties(obj)

    def setProperties(self, obj):
        ifc_entity = self.ifc_entity
        category_name = "Boundaries"
        obj.addProperty("App::PropertyLink", "Boundaries", category_name)
        obj.addProperty("App::PropertyLink", "SecondLevel", category_name)
        obj.addProperty("App::PropertyLink", "SIA", category_name)
        obj.addProperty("App::PropertyLink", "SIA_Interiors", category_name)
        obj.addProperty("App::PropertyLink", "SIA_Exteriors", category_name)

        space_full_name = f"{ifc_entity.Name} {ifc_entity.LongName}"
        obj.Label = space_full_name
        try:
            obj.Description = ifc_entity.Description
        except TypeError:
            pass

        return obj


def generate_bem_xml_from_file(ifc_path: str, gui_up: bool = False) -> namedtuple:
    doc = FreeCAD.newDocument()

    generate_ifc_rel_space_boundaries(ifc_path, doc)
    processing_sia_boundaries(doc)
    Result = namedtuple("Result", ["xml", "log"])
    xml_str = write_xml(doc).tostring()
    log_str = LOG_STREAM.getvalue()
    result = Result(xml_str, log_str)
    return result


if __name__ == "__main__":
    if os.name == "nt":
        TEST_FOLDER = r"C:\git\BIMxBEM\IfcTestFiles"
    else:
        TEST_FOLDER = "/home/cyril/git/BIMxBEM/IfcTestFiles/"
    TEST_FILES = {
        0: "Triangle_2x3_A23.ifc",
        1: "Triangle_2x3_R19.ifc",
        2: "2Storey_2x3_A22.ifc",
        3: "2Storey_2x3_R19.ifc",
        4: "0014_Vernier112D_ENE_ModèleÉnergétique_R20.ifc",
        6: "Investigation_test_R19.ifc",
        7: "OverSplitted_R20_2x3.ifc",
        8: "ExternalEarth_R20_2x3.ifc",
        9: "ExternalEarth_R20_IFC4.ifc",
        10: "Testmodell_BEM_AC22.ifc"
    }
    IFC_PATH = os.path.join(TEST_FOLDER, TEST_FILES[7])
    DOC = FreeCAD.ActiveDocument
    if DOC:  # Remote debugging
        import ptvsd

        # Allow other computers to attach to ptvsd at this IP address and port.
        ptvsd.enable_attach(address=("localhost", 5678), redirect_output=True)
        # Pause the program until a remote debugger is attached
        ptvsd.wait_for_attach()
        # breakpoint()

        display_boundaries(ifc_path=IFC_PATH, doc=DOC)
        FreeCADGui.activeView().viewIsometric()
        FreeCADGui.SendMsgToActiveView("ViewFit")
    else:
        FreeCADGui.showMainWindow()
        DOC = FreeCAD.newDocument()

        generate_ifc_rel_space_boundaries(IFC_PATH, DOC)
        processing_sia_boundaries(DOC)
        bem_xml = write_xml(DOC)
        output_xml_to_path(bem_xml)

        # xml_str = generate_bem_xml_from_file(IFC_PATH)

        with open("./boundaries.log", "w") as f:
            f.write(LOG_STREAM.getvalue())

        FreeCADGui.activeView().viewIsometric()
        FreeCADGui.SendMsgToActiveView("ViewFit")

        FreeCADGui.exec_loop()
