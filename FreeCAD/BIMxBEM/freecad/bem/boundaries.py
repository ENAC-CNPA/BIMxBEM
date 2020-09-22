# coding: utf8
"""This module adapt IfcRelSpaceBoundary and create SIA specific bem boundaries in FreeCAD.

© All rights reserved.
ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Laboratory CNPA, 2019-2020

See the LICENSE.TXT file for more details.

Author : Cyril Waechter
"""
import itertools
import os
from collections import namedtuple
from typing import NamedTuple

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import ifcopenshell.util.unit

import FreeCAD
import FreeCADGui
import Part

from freecad.bem import materials
from freecad.bem.bem_xml import BEMxml
from freecad.bem.bem_logging import logger, LOG_STREAM
from freecad.bem import utils
from freecad.bem.entities import (
    RelSpaceBoundary,
    BEMBoundary,
    Element,
)
from freecad.bem.ifc_importer import IfcImporter, TOLERANCE


def processing_sia_boundaries(doc=FreeCAD.ActiveDocument) -> None:
    """Create SIA specific boundaries cf. https://www.sia.ch/fr/services/sia-norm/"""
    for space in utils.get_elements_by_ifctype("IfcSpace", doc):
        ensure_hosted_element_are(space)
        ensure_hosted_are_coplanar(space)
        compute_space_area(space)
        set_boundary_normal(space)
        join_over_splitted_boundaries(space, doc)
        handle_curtain_walls(space, doc)
        find_closest_edges(space)
        set_leso_type(space)
    create_sia_boundaries(doc)
    doc.recompute()


def set_boundary_normal(space):
    faces = space.Shape.Faces
    for boundary in space.SecondLevel.Group:
        if boundary.IsHosted:
            continue
        center_of_mass = utils.get_outer_wire(boundary).CenterOfMass
        face = min(
            faces, key=lambda x: x.Surface.projectPoint(center_of_mass, "LowerDistance")
        )
        face_normal = face.normalAt(
            *face.Surface.projectPoint(center_of_mass, "LowerDistanceParameters")
        )
        normal = utils.get_normal_at(boundary)
        if normal.dot(face_normal) < 0:
            normal = -normal
        boundary.Normal = normal
        for hosted in boundary.InnerBoundaries:
            hosted.Normal = normal


def compute_space_area(space: Part.Feature):
    """Compute both gross and net area"""
    z_min = space.Shape.BoundBox.ZMin
    z_sre = z_min + 1000  # 1 m above ground. See SIA 380:2015 &3.2.3 p.26-27
    sre_plane = Part.Plane(FreeCAD.Vector(0, 0, z_sre), FreeCAD.Vector(0, 0, 1))
    space.Area = space.Shape.common(sre_plane.toShape()).Area
    # TODO: Not valid yet as it return net area. Find a way to get gross space volume
    space.AreaAE = space.Area


def handle_curtain_walls(space, doc) -> None:
    """Add an hosted window with full area in curtain wall boundaries as they are not handled
    by BEM softwares"""
    for boundary in space.SecondLevel.Group:
        if getattr(boundary.RelatedBuildingElement, "IfcType", "") != "IfcCurtainWall":
            continue
        fake_window = doc.copyObject(boundary)
        fake_window.IsHosted = True
        fake_window.LesoType = "Window"
        fake_window.ParentBoundary = boundary.Id
        fake_window.GlobalId = ifcopenshell.guid.new()
        fake_window.Id = IfcId.new(doc)
        RelSpaceBoundary.set_label(fake_window)
        space.SecondLevel.addObject(fake_window)
        # Host cannot be an empty face so inner wire is scaled down a little
        inner_wire = utils.get_outer_wire(boundary).scale(0.999)
        inner_wire = utils.project_wire_to_plane(inner_wire, utils.get_plane(boundary))
        utils.append_inner_wire(boundary, inner_wire)
        utils.append(boundary, "InnerBoundaries", fake_window)
        if FreeCAD.GuiUp:
            fake_window.ViewObject.ShapeColor = (0.0, 0.7, 1.0)


class IfcId:
    """Generate new id for generated boundaries missing from ifc and keep track of last id used"""

    current_id = 0

    @classmethod
    def new(cls, doc) -> int:
        if not cls.current_id:
            cls.current_id = max((getattr(obj, "Id", 0) for obj in doc.Objects))
        cls.current_id += 1
        return cls.current_id


def write_xml(doc=FreeCAD.ActiveDocument) -> BEMxml:
    """Read BEM infos for FreeCAD file and write it to an xml.
    xml is stored in an object to allow different outputs"""
    bem_xml = BEMxml()
    for project in utils.get_elements_by_ifctype("IfcProject", doc):
        bem_xml.write_project(project)
    for space in utils.get_elements_by_ifctype("IfcSpace", doc):
        bem_xml.write_space(space)
        for boundary in space.SecondLevel.Group:
            bem_xml.write_boundary(boundary)
    for building_element in utils.get_by_class(doc, Element):
        bem_xml.write_building_elements(building_element)
    for material in utils.get_by_class(
        doc, (materials.Material, materials.ConstituentSet, materials.LayerSet)
    ):
        bem_xml.write_material(material)
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
    if len(boundaries) <= 5:
        return
    elements_dict = dict()
    for rel_boundary in boundaries:
        try:
            key = f"{rel_boundary.RelatedBuildingElement.Id}"
        except AttributeError:
            if rel_boundary.PhysicalOrVirtualBoundary == "VIRTUAL":
                logger.info("IfcElement %s is VIRTUAL. Modeling error ?")
                key = "VIRTUAL"
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
                if utils.is_coplanar(boundary, coplanar_list[0]):
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
                join_coplanar_boundaries(coplanar_list, doc)
            except Part.OCCError:
                logger.warning(
                    f"Cannot join boundaries in space <{space.Id}> with key <{key}>"
                )


class CommonSegment(NamedTuple):
    index1: int
    index2: int
    opposite_dir: FreeCAD.Vector


def join_coplanar_boundaries(boundaries: list, doc=FreeCAD.ActiveDocument):
    """Try to join coplanar boundaries"""
    boundary1 = boundaries.pop()
    remove_from_doc = list()

    def find_common_segment(wire1, wire2):
        """Find if wires have common segments and between which edges
        return named tuple with edge index from each wire and if they have opposite direction"""
        for (ei1, edge1), (ei2, edge2) in itertools.product(
            enumerate(wire1.Edges), enumerate(wire2.Edges)
        ):
            if wire1 == wire2 and ei1 == ei2:
                continue

            common_segment = edges_have_common_segment(edge1, edge2)
            if common_segment:
                return CommonSegment(ei1, ei2, common_segment.opposite_dir)

    def edges_have_common_segment(edge1, edge2):
        """Check if edges have common segments and tell if these segments have same direction"""
        p0_1, p0_2 = utils.get_vectors_from_shape(edge1)
        p1_1, p1_2 = utils.get_vectors_from_shape(edge2)

        v0_12 = p0_2 - p0_1
        v1_12 = p1_2 - p1_1

        dir0 = (v0_12).normalize()
        dir1 = (v1_12).normalize()

        # if edge1 and edge2 are not collinear no junction is possible.
        if not (
            (dir0.isEqual(dir1, TOLERANCE) or dir0.isEqual(-dir1, TOLERANCE))
            and v0_12.cross(p1_1 - p0_1).Length < TOLERANCE
        ):
            return

        # Check in which order vectors1 and vectors2 should be connected
        if dir0.isEqual(dir1, TOLERANCE):
            p0_1_next_point, other_point = p1_1, p1_2
            opposite_dir = False
        else:
            p0_1_next_point, other_point = p1_2, p1_1
            opposite_dir = True

        # Check if edge1 and edge2 have a common segment
        if not (
            dir0.dot(p0_1_next_point - p0_1) < dir0.dot(p0_2 - p0_1)
            and dir0.negative().dot(other_point - p0_2)
            < dir0.negative().dot(p0_1 - p0_2)
        ):
            return
        return CommonSegment(None, None, opposite_dir)

    def join_boundaries(boundary1, boundary2):
        wire1 = utils.get_outer_wire(boundary1)
        vectors1 = utils.get_vectors_from_shape(wire1)
        wire2 = utils.get_outer_wire(boundary2)
        vectors2 = utils.get_vectors_from_shape(wire2)

        common_segment = find_common_segment(wire1, wire2)
        if not common_segment:
            return False
        ei1, ei2, opposite_dir = common_segment

        # join vectors1 and vectors2 at indexes
        new_points = vectors2[ei2 + 1 :] + vectors2[: ei2 + 1]
        if not opposite_dir:
            new_points.reverse()

        # Efficient way to insert elements at index : https://stackoverflow.com/questions/14895599/insert-an-element-at-specific-index-in-a-list-and-return-updated-list/48139870#48139870 pylint: disable=line-too-long
        vectors1[ei1 + 1 : ei1 + 1] = new_points

        inner_wires = utils.get_inner_wires(boundary1)[:]
        inner_wires.extend(utils.get_inner_wires(boundary2))
        if not boundary1.IsHosted:
            for inner_boundary in boundary2.InnerBoundaries:
                utils.append(boundary1, "InnerBoundaries", inner_boundary)
                inner_boundary.ParentBoundary = boundary1.Id

        # Update shape
        utils.clean_vectors(vectors1)
        utils.close_vectors(vectors1)
        wire1 = Part.makePolygon(vectors1)
        utils.generate_boundary_compound(boundary1, wire1, inner_wires)
        RelSpaceBoundary.recompute_areas(boundary1)

        return True

    while True:
        for boundary2 in boundaries:
            if join_boundaries(boundary1, boundary2):
                boundaries.remove(boundary2)
                remove_from_doc.append(boundary2)
                break
        else:
            logger.warning(
                f"Unable to join boundaries RelSpaceBoundary Id <{boundary1.Id}> with boundaries <{(b.Id for b in boundaries)}>"
            )
            break

    wire1 = utils.get_outer_wire(boundary1)
    vectors1 = utils.get_vectors_from_shape(wire1)
    inner_wires = utils.get_inner_wires(boundary1)[:]
    while True:
        common_segment = find_common_segment(wire1, wire1)
        if not common_segment:
            break

        ei1, ei2 = common_segment[0:2]

        # join vectors1 and vectors2 at indexes
        vectors_split1 = vectors1[: ei1 + 1] + vectors1[ei2 + 1 :]
        vectors_split2 = vectors1[ei1 + 1 : ei2 + 1]
        utils.clean_vectors(vectors_split1)
        utils.clean_vectors(vectors_split2)
        area1 = Part.Face(Part.makePolygon(vectors_split1 + [vectors_split1[0]])).Area
        area2 = Part.Face(Part.makePolygon(vectors_split2 + [vectors_split2[0]])).Area
        if area1 > area2:
            vectors1 = vectors_split1
            inner_vectors = vectors_split2
        else:
            vectors1 = vectors_split2
            inner_vectors = vectors_split1

        utils.close_vectors(inner_vectors)
        inner_wires.extend([Part.makePolygon(inner_vectors)])

        # Update shape
        utils.close_vectors(vectors1)
        wire1 = Part.makePolygon(vectors1)
        utils.generate_boundary_compound(boundary1, wire1, inner_wires)
        RelSpaceBoundary.recompute_areas(boundary1)

    # Clean FreeCAD document if join operation was a success
    for fc_object in remove_from_doc:
        doc.removeObject(fc_object.Name)


def ensure_hosted_element_are(space):
    for boundary in space.SecondLevel.Group:
        try:
            ifc_type = boundary.RelatedBuildingElement.IfcType
        except AttributeError:
            continue

        if not is_typically_hosted(ifc_type):
            continue

        if boundary.IsHosted and boundary.ParentBoundary:
            continue

        def are_too_far(boundary1, boundary2):
            return (
                boundary1.Shape.distToShape(boundary2.Shape)[0]
                - boundary2.RelatedBuildingElement.Thickness.Value
                > TOLERANCE
            )

        def find_host(boundary):
            fallback_solution = None
            for boundary2 in space.SecondLevel.Group:
                if not utils.are_parallel_boundaries(boundary, boundary2):
                    continue

                if are_too_far(boundary, boundary2):
                    continue

                fallback_solution = boundary2
                for inner_wire in utils.get_inner_wires(boundary2):
                    if (
                        not abs(Part.Face(inner_wire).Area - boundary.Area.Value)
                        < TOLERANCE
                    ):
                        continue

                    return boundary2
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
        utils.append(host, "InnerBoundaries", boundary)


def ensure_hosted_are_coplanar(space):
    for boundary in space.SecondLevel.Group:
        for inner_boundary in boundary.InnerBoundaries:
            if utils.is_coplanar(inner_boundary, boundary):
                continue
            utils.project_boundary_onto_plane(inner_boundary, utils.get_plane(boundary))
            outer_wire = utils.get_outer_wire(boundary)
            inner_wires = utils.get_inner_wires(boundary)
            inner_wire = utils.get_outer_wire(inner_boundary)
            inner_wires.append(inner_wire)

            try:
                face = boundary.Shape.Faces[0]
                face = face.cut(Part.Face(inner_wire))
            except RuntimeError:
                pass

            boundary.Shape = Part.Compound([face, outer_wire, *inner_wires])


def is_typically_hosted(ifc_type: str):
    """Say if given ifc_type is typically hosted eg. windows, doors"""
    usually_hosted_types = ("IfcWindow", "IfcDoor", "IfcOpeningElement")
    for usual_type in usually_hosted_types:
        if ifc_type.startswith(usual_type):
            return True
    return False


class HostNotFound(LookupError):
    pass


def find_closest_edges(space):
    """Find closest boundary and edge to be able to reconstruct a closed shell"""
    boundaries = [b for b in space.SecondLevel.Group if not b.IsHosted]
    Closest = namedtuple("Closest", ["boundary", "edge", "distance"])
    # Initialise defaults values
    for boundary in boundaries:
        n_edges = len(utils.get_outer_wire(boundary).Edges)
        boundary.Proxy.closest = [
            Closest(boundary=None, edge=-1, distance=100000)
        ] * n_edges

    def compare_closest(boundary1, ei1, edge1, boundary2, ei2, edge2):
        is_closest = False
        distance = boundary1.Proxy.closest[ei1].distance
        edge_to_edge = compute_distance(edge1, edge2)

        if distance <= TOLERANCE:
            return

        # Perfect match
        if edge_to_edge <= TOLERANCE:
            is_closest = True

        elif edge_to_edge - distance - TOLERANCE <= 0:
            # Case 1 : boundaries point in same direction so all solution are valid.
            dot_dir = boundary2.Normal.dot(boundary1.Normal)
            if abs(dot_dir) >= 1 - TOLERANCE:
                is_closest = True
            # Case 2 : boundaries intersect
            else:
                # Check if projection on plane intersection cross boundary1.
                # If so edge2 cannot be a valid solution.
                pnt1 = edge1.CenterOfMass
                plane_intersect = utils.get_plane(boundary1).intersect(
                    utils.get_plane(boundary2)
                )[0]
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
        if boundary2.Normal.dot(boundary1.Normal) <= -1 + TOLERANCE:
            continue

        edges1 = utils.get_outer_wire(boundary1).Edges
        edges2 = utils.get_outer_wire(boundary2).Edges
        for (ei1, edge1), (ei2, edge2) in itertools.product(
            enumerate(edges1), enumerate(edges2)
        ):
            if not is_low_angle(edge1, edge2):
                continue

            compare_closest(boundary1, ei1, edge1, boundary2, ei2, edge2)
            compare_closest(  # pylint: disable=arguments-out-of-order
                boundary2, ei2, edge2, boundary1, ei1, edge1
            )

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
        return "Wall"
    elif ifc_type.startswith("IfcSlab") or ifc_type == "IfcRoof":
        # Pointing up => Ceiling. Pointing down => Flooring
        if boundary.Normal.z > 0:
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


def create_sia_boundaries(doc=FreeCAD.ActiveDocument):
    """Create boundaries necessary for SIA calculations"""
    project = next(utils.get_elements_by_ifctype("IfcProject", doc))
    is_from_revit = project.ApplicationIdentifier == "Revit"
    is_from_archicad = project.ApplicationFullName == "ARCHICAD-64"
    for space in utils.get_elements_by_ifctype("IfcSpace", doc):
        create_sia_ext_boundaries(space, is_from_revit)
        create_sia_int_boundaries(space, is_from_revit, is_from_archicad)
        rejoin_boundaries(space, "SIA_Exterior")
        rejoin_boundaries(space, "SIA_Interior")


def rejoin_boundaries(space, sia_type):
    """
    Rejoin boundaries after their translation to get a correct close shell surfaces.
    1 Fill gaps between boundaries (2b)
    2 Fill gaps gerenate by translation to make a boundary on the inside or outside boundary of
    building elements
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4/ADD2_TC1/HTML/schema/ifcproductextension/lexical/ifcrelspaceboundary2ndlevel.htm # pylint: disable=line-too-long
    """
    base_boundaries = space.SecondLevel.Group
    for base_boundary in base_boundaries:
        lines = []
        boundary1 = getattr(base_boundary, sia_type)
        if (
            base_boundary.IsHosted
            or base_boundary.PhysicalOrVirtualBoundary == "VIRTUAL"
            or not base_boundary.RelatedBuildingElement
        ):
            continue
        b1_plane = utils.get_plane(boundary1)
        for b2_id, (ei1, ei2) in zip(
            base_boundary.ClosestBoundaries, enumerate(base_boundary.ClosestEdges)
        ):
            base_boundary2 = utils.get_in_list_by_id(base_boundaries, b2_id)
            boundary2 = getattr(base_boundary2, sia_type, None)
            if not boundary2:
                logger.warning(f"Cannot find corresponding boundary with id <{b2_id}>")
                lines.append(
                    utils.line_from_edge(utils.get_outer_wire(base_boundary).Edges[ei1])
                )
                continue
            # Case 1 : boundaries are not parallel
            if not base_boundary.Normal.isEqual(base_boundary2.Normal, TOLERANCE):
                plane_intersect = b1_plane.intersect(utils.get_plane(boundary2))
                if plane_intersect:
                    lines.append(plane_intersect[0])
                    continue
            # Case 2 : boundaries are parallel
            line1 = utils.line_from_edge(utils.get_outer_wire(boundary1).Edges[ei1])
            try:
                line2 = utils.line_from_edge(utils.get_outer_wire(boundary2).Edges[ei2])
            except IndexError:
                logger.warning(
                    f"Cannot find closest edge index <{ei2}> in boundary id <{b2_id}> to rejoin boundary <{base_boundary.Id}>"
                )
                lines.append(
                    utils.line_from_edge(utils.get_outer_wire(base_boundary).Edges[ei1])
                )
                continue

            # Case 2a : edges are not parallel
            if abs(line1.Direction.dot(line2.Direction)) < 1 - TOLERANCE:
                line_intersect = line1.intersect2d(line2, b1_plane)
                if line_intersect:
                    point1 = b1_plane.value(*line_intersect[0])
                    if line1.Direction.dot(line2.Direction) > 0:
                        point2 = point1 + line1.Direction + line2.Direction
                    else:
                        point2 = point1 + line1.Direction - line2.Direction
                        continue
            # Case 2b : edges are parallel
            else:
                point1 = (line1.Location + line2.Location) * 0.5
                point2 = point1 + line1.Direction

            try:
                lines.append(Part.Line(point1, point2))
            except Part.OCCError:
                logger.exception(
                    f"Failure in boundary id <{base_boundary.Id}> {point1} and {point2} are equal"
                )

        # Generate new shape
        try:
            outer_wire = utils.polygon_from_lines(lines, b1_plane)
        except utils.NoIntersectionError:
            # TODO: Investigate to see why this happens
            logger.exception(f"Unable to rejoin boundary Id <{base_boundary.Id}>")
            continue
        except Part.OCCError:
            logger.exception(
                f"Invalid geometry while rejoining boundary Id <{base_boundary.Id}>"
            )
            continue
        try:
            Part.Face(outer_wire)
        except Part.OCCError:
            logger.exception(f"Unable to rejoin boundary Id <{base_boundary.Id}>")
            continue

        inner_wires = utils.get_inner_wires(boundary1)
        utils.generate_boundary_compound(boundary1, outer_wire, inner_wires)

        boundary1.Area = area = boundary1.Shape.Area
        for inner_boundary in base_boundary.InnerBoundaries:
            area = area + inner_boundary.Shape.Area
        boundary1.AreaWithHosted = area


def create_sia_ext_boundaries(space, is_from_revit):
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
        if not boundary1.RelatedBuildingElement:
            continue
        thickness = boundary1.RelatedBuildingElement.Thickness.Value
        ifc_type = boundary1.RelatedBuildingElement.IfcType
        normal = boundary1.Shape.Faces[0].normalAt(0, 0)
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
        normal = boundary.Normal

        bem_boundary = BEMBoundary.create(boundary, "SIA_Interior")
        sia_group_obj.addObject(bem_boundary)
        if not boundary.RelatedBuildingElement:
            continue

        ifc_type = boundary.RelatedBuildingElement.IfcType
        if is_from_revit and ifc_type.startswith("IfcWall"):
            thickness = boundary.RelatedBuildingElement.Thickness.Value
            lenght = thickness / 2
            bem_boundary.Placement.move(normal.negative() * lenght)


class XmlResult(NamedTuple):
    xml: str
    log: str


def generate_bem_xml_from_file(ifc_path: str) -> XmlResult:
    ifc_importer = IfcImporter(ifc_path)
    ifc_importer.generate_rel_space_boundaries()
    doc = ifc_importer.doc
    processing_sia_boundaries(doc)
    xml_str = write_xml(doc).tostring()
    log_str = LOG_STREAM.getvalue()
    return XmlResult(xml_str, log_str)


def process_test_file(ifc_path, doc):
    ifc_importer = IfcImporter(ifc_path, doc)
    ifc_importer.generate_rel_space_boundaries()
    processing_sia_boundaries(doc)
    bem_xml = write_xml(doc)
    output_xml_to_path(bem_xml)
    ifc_importer.xml = bem_xml
    ifc_importer.log = LOG_STREAM.getvalue()
    if FreeCAD.GuiUp:
        FreeCADGui.activeView().viewIsometric()
        FreeCADGui.SendMsgToActiveView("ViewFit")
    with open("./boundaries.log", "w") as log_file:
        log_file.write(ifc_importer.log)
    return ifc_importer


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
        10: "Ersatzneubau Alphütte_1-1210_31_23.ifc",
        11: "GRAPHISOFT_ARCHICAD_Sample_Project_Hillside_House_v1.ifczip",
        12: "GRAPHISOFT_ARCHICAD_Sample_Project_S_Office_v1.ifczip",
        13: "Cas1_EXPORT_REVIT_IFC2x3 (EDITED)_Space_Boundaries.ifc",
        14: "Cas1_EXPORT_REVIT_IFC4DTV (EDITED)_Space_Boundaries.ifc",
        15: "Cas1_EXPORT_REVIT_IFC4RV (EDITED)_Space_Boundaries.ifc",
        16: "Cas1_EXPORT_REVIT_IFC4RV (EDITED)_Space_Boundaries_RECREATED.ifc",
        17: "Cas2_EXPORT_REVIT_IFC4RV (EDITED)_Space_Boudaries.ifc",
        18: "Cas2_EXPORT_REVIT_IFC4DTV (EDITED)_Space_Boundaries_RECREATED.ifc",
        19: "Cas2_EXPORT_REVIT_IFC4DTV (EDITED)_Space_Boundaries.ifc",
        20: "Cas2_EXPORT_REVIT_IFC2x3 (EDITED)_Space_Boundaries.ifc",
        21: "Temoin.ifc",
        22: "1708 maquette test 01.ifc",
        23: "test 02-03 mur int baseslab dalle de sol.ifc",
        24: "test 02-06 murs composites.ifc",
        25: "test 02-07 dalle étage et locaux mansardés.ifc",
        26: "test 02-08 raccords nettoyés étage.ifc",
        27: "test 02-09 sous-sol.ifc",
    }
    IFC_PATH = os.path.join(TEST_FOLDER, TEST_FILES[1])
    DOC = FreeCAD.ActiveDocument

    if DOC:  # Remote debugging
        import ptvsd

        # Allow other computers to attach to ptvsd at this IP address and port.
        ptvsd.enable_attach(address=("localhost", 5678), redirect_output=True)
        # Pause the program until a remote debugger is attached
        ptvsd.wait_for_attach()
        # breakpoint()

        process_test_file(IFC_PATH, DOC)
    else:
        FreeCADGui.showMainWindow()
        DOC = FreeCAD.newDocument()

        process_test_file(IFC_PATH, DOC)
        # xml_str = generate_bem_xml_from_file(IFC_PATH)

        FreeCADGui.exec_loop()
