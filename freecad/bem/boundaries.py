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
import typing
from typing import NamedTuple, Iterable, List, Optional, Dict

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
from freecad.bem.progress import Progress
from freecad.bem import utils
from freecad.bem.entities import (
    RelSpaceBoundary,
    BEMBoundary,
    Element,
    ElementType,
)
from freecad.bem.ifc_importer import IfcImporter, TOLERANCE

if typing.TYPE_CHECKING:
    from freecad.bem.typing import (
        SpaceFeature,
        ContainerFeature,
    )  # pylint: disable=no-name-in-module, import-error


def processing_sia_boundaries(doc=FreeCAD.ActiveDocument) -> None:
    """Create SIA specific boundaries cf. https://www.sia.ch/fr/services/sia-norm/"""
    Progress.set(30, "ProcessingSIABoundaries_Prepare", Progress.new_space_count(), 40)
    for space in utils.get_elements_by_ifctype("IfcSpace", doc):
        ensure_hosted_element_are(space, doc)
        ensure_hosted_are_coplanar(space)
        compute_space_area(space)
        set_face_to_boundary_info(space)
        merge_over_splitted_boundaries(space, doc)
        handle_curtain_walls(space, doc)
        find_closest_edges(space)
        set_leso_type(space)
        ensure_external_earth_is_set(space, doc)
        Progress.set()
    Progress.set(70, "ProcessingSIABoundaries_Create", Progress.new_space_count(), 20)
    ensure_materials_layers_order(doc)
    create_sia_boundaries(doc)
    doc.recompute()


def reverse_layers(material):
    material.MaterialLayers = material.MaterialLayers[::-1]
    material.Thicknesses = material.Thicknesses[::-1]


def set_internal_to_external(element, material):
    axis = utils.get_axis_by_name(element.Placement, material.LayerSetDirection)
    if material.DirectionSense == "NEGATIVE":
        axis = -axis
    for boundary in element.ProvidesBoundaries:
        # Check if already set
        if boundary.InternalToExternal:
            continue
        # Flooring always from top to bottom (agreement not in IFC standards)
        if boundary.CorrespondingBoundary and boundary.LesoType == "Ceiling":
            continue
        if boundary.LesoType == "Flooring":
            if axis.z > 0:
                reverse_layers(material)
            boundary.InternalToExternal = 1
            if boundary.CorrespondingBoundary:
                boundary.CorrespondingBoundary.InternalToExternal = -1
        # External always from interior to exterior (agreement not in IFC standards)
        elif boundary.InternalOrExternalBoundary != "INTERNAL":
            if axis.dot(boundary.Normal) < 0:
                reverse_layers(material)
            boundary.InternalToExternal = 1
        # Other internal boundaries
        else:
            if axis.dot(boundary.Normal) < 0:
                boundary.InternalToExternal = -1
            else:
                boundary.InternalToExternal = 1
            if boundary.CorrespondingBoundary:
                boundary.CorrespondingBoundary.InternalToExternal = (
                    -boundary.InternalToExternal
                )


def ensure_materials_layers_order(doc):
    """
    There is no convention for material order in IFC but energy simulation software expect one.
    From interior to exterior for external shell.
    From top to bottom for internal slabs (flooring)
    """
    for material in utils.get_by_class(doc, materials.LayerSet):
        boundaries = []
        for element in material.AssociatedTo:
            try:
                set_internal_to_external(element, material)
            # Happen when element is an element type
            except AttributeError:
                for occurence in element.ApplicableOccurrence:
                    if not element.Material:
                        set_internal_to_external(occurence, material)


def ensure_external_earth_is_set(space: "SpaceFeature", doc=FreeCAD.ActiveDocument):
    sites: List["ContainerFeature"] = list(
        utils.get_elements_by_ifctype("IfcSite", doc)
    )
    ground_bound_box = get_ground_bound_box(sites)
    if space.Shape.BoundBox.ZMin - ground_bound_box.ZMax > 1000:
        return
    ground_shape = Part.Compound([])
    for site in sites:
        ground_shape.add(site.Shape)
    if not ground_shape.BoundBox.isValid():
        ground_shape = Part.Plane().toShape()
    for boundary in space.SecondLevel.Group:
        if boundary.InternalOrExternalBoundary in (
            "INTERNAL",
            "EXTERNAL_EARTH",
            "EXTERNAL_WATER",
            "EXTERNAL_FIRE",
        ):
            continue
        if boundary.InnerBoundaries:
            continue
        if not is_underground(boundary, ground_shape):
            continue
        boundary.InternalOrExternalBoundary = "EXTERNAL_EARTH"


def is_underground(boundary, ground_shape) -> bool:
    closest_points = ground_shape.distToShape(boundary.Shape)[1][0]
    direction: FreeCAD.Vector = closest_points[1] - closest_points[0]
    if direction.z > 1000:
        return False
    if boundary.LesoType == "Flooring":
        el_thickness = getattr(
            getattr(getattr(boundary, "RelatedBuildingElement", 0), "Thickness", 0),
            "Value",
            0,
        )
        if direction.z - el_thickness * 1.5 > 0:
            return False
        boundary.UndergroundDepth = abs(direction.z - el_thickness)
        return True
    if boundary.LesoType == "Wall":
        bbox = boundary.Shape.BoundBox
        if (bbox.ZMax + bbox.ZMin) / 2 + direction.z < 0:
            return True
    if boundary.LesoType == "Ceiling":
        if direction.z < TOLERANCE:
            return True
    return False


def get_ground_bound_box(sites: Iterable["ContainerFeature"]) -> FreeCAD.BoundBox:
    boundbox = FreeCAD.BoundBox()
    for site in sites:
        boundbox.add(site.Shape.BoundBox)
    return boundbox if boundbox.isValid() else FreeCAD.BoundBox(0, 0, -30000, 0, 0, 0)


class FaceToBoundary:
    def __init__(self, boundary, face):
        self.boundary = boundary
        self.face = face
        self.point_on_face = None
        self.point_on_boundary = None
        self.compute_shortest()
        self.boundary_normal = utils.get_boundary_normal(
            boundary, self.point_on_boundary
        )
        self.face_normal = utils.get_face_normal(face, self.point_on_face)
        self.distance = self.vec_to_space.Length

    @property
    def vec_to_space(self):
        return self.point_on_face - self.point_on_boundary

    def compute_shortest(self):
        boundary_face = self.boundary.Shape.Faces[0]
        min_dist = self.face.distToShape(boundary_face)
        self.point_on_face = min_dist[1][0][0]
        self.point_on_boundary = min_dist[1][0][1]

    @property
    def is_valid(self):
        # Not valid face if its normal and boundary normal do not point in same direction
        return abs(self.boundary_normal.dot(self.face_normal)) > 1 - TOLERANCE

    @property
    def fixed_normal(self):
        return (
            self.boundary_normal
            if self.face_normal.dot(self.boundary_normal) > 0
            else -self.boundary_normal
        )

    @property
    def translation_to_face(self):
        return self.face_normal * self.face_normal.dot(self.vec_to_space)


def set_face_to_boundary_info(space):
    faces = space.Shape.Faces
    for boundary in space.SecondLevel.Group:
        if boundary.IsHosted:
            continue
        candidates = (FaceToBoundary(boundary, face) for face in faces)
        result = min(candidates, key=lambda x: x.distance if x.is_valid else 10000)
        boundary.TranslationToSpace = result.translation_to_face
        normal = result.fixed_normal
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
        # Prevent Revit issue which produce curtain wall with an hole inside but no inner boundary
        if not boundary.InnerBoundaries:
            if len(boundary.Shape.SubShapes) > 2:
                outer_wire = boundary.Shape.SubShapes[1]
                utils.generate_boundary_compound(boundary, outer_wire, ())
        boundary.LesoType = "Wall"
        fake_window = doc.copyObject(boundary)
        fake_window.IsHosted = True
        fake_window.LesoType = "Window"
        fake_window.ParentBoundary = boundary
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
    for building_element_type in utils.get_by_class(doc, ElementType):
        bem_xml.write_building_element_types(building_element_type)
    for building_element in utils.get_by_class(doc, Element):
        bem_xml.write_building_elements(building_element)
    for material in utils.get_by_class(
        doc,
        (
            materials.Material,
            materials.ConstituentSet,
            materials.LayerSet,
            materials.ProfileSet,
        ),
    ):
        bem_xml.write_material(material)
    return bem_xml


def output_xml_to_path(bem_xml, xml_path=None):
    if not xml_path:
        xml_path = (
            "./output.xml" if os.name == "nt" else "/home/cyril/git/BIMxBEM/output.xml"
        )
    bem_xml.write_to_file(xml_path)


def group_by_shared_element(boundaries) -> Dict[str, List["boundary"]]:
    elements_dict = dict()
    for rel_boundary in boundaries:
        try:
            key = f"{rel_boundary.RelatedBuildingElement.Id}_{rel_boundary.InternalOrExternalBoundary}"
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
    return elements_dict


def group_coplanar_boundaries(boundary_list) -> List[List["boundary"]]:
    coplanar_boundaries = list()
    for boundary in boundary_list:
        if not coplanar_boundaries:
            coplanar_boundaries.append([boundary])
            continue
        for coplanar_list in coplanar_boundaries:
            if utils.is_coplanar(boundary, coplanar_list[0]):
                coplanar_list.append(boundary)
                break
        else:
            coplanar_boundaries.append([boundary])
    return coplanar_boundaries


def merge_over_splitted_boundaries(space, doc=FreeCAD.ActiveDocument):
    """Try to merge oversplitted boundaries to reduce the number of boundaries and make sure that
    windows are not splitted as it is often with some authoring softwares like Revit.
    Why ? Less boundaries is more manageable, closer to what user expect and require
    less computational power"""
    boundaries = space.SecondLevel.Group
    # Considered as the minimal size for an oversplit to occur (1 ceiling, 3 wall, 1 flooring)
    if len(boundaries) <= 5:
        return
    elements_dict = group_by_shared_element(boundaries)

    # Merge hosted elements first
    for key, boundary_list in elements_dict.items():
        if boundary_list[0].IsHosted and len(boundary_list) != 1:
            coplanar_groups = group_coplanar_boundaries(boundary_list)
            for group in coplanar_groups:
                merge_coplanar_boundaries(group, doc)

    for key, boundary_list in elements_dict.items():
        # None coplanar boundaries should not be connected.
        # eg. round wall splitted with multiple orientations.

        # Case1: No oversplitted boundaries
        try:
            if boundary_list[0].IsHosted or len(boundary_list) == 1:
                continue
        except ReferenceError:
            continue

        coplanar_groups = group_coplanar_boundaries(boundary_list)

        for group in coplanar_groups:
            # Case 1 : only 1 boundary related to the same element. Cannot group boundaries.
            if len(group) == 1:
                continue
            # Case 2 : more than 1 boundary related to the same element might be grouped.
            try:
                merge_coplanar_boundaries(group, doc)
            except Part.OCCError:
                logger.warning(
                    f"Cannot join boundaries in space <{space.Id}> with key <{key}>"
                )


def merged_wires(wire1: Part.Wire, wire2: Part.Wire) -> (Part.Wire, List[Part.Wire]):
    """Try to merge 2 wires meant using face merging algorithm.
    1. Transform wires into faces
    2. Merge them
    3. Return face outer wire and eventual inner wires"""
    face1 = Part.Face(wire1)
    face2 = Part.Face(wire2)
    fusion = face1.fuse(face2)
    fusion.sewShape()
    unifier = Part.ShapeUpgrade.UnifySameDomain(fusion)
    unifier.build()
    if len(unifier.shape().SubShapes) == 1:
        new_face = unifier.shape().SubShapes[0]
        try:
            return (new_face.OuterWire, new_face.Wires[1:])
        except AttributeError:  # Rarely returned shape is a Wire. OCCT bug ?
            pass
    return (None, [])


def merge_boundaries(boundary1, boundary2) -> bool:
    """Try to merge 2 boundaries. Retrun True if successfully merged"""
    wire1 = utils.get_outer_wire(boundary1)
    wire2 = utils.get_outer_wire(boundary2)

    new_wire, extra_inner_wires = merged_wires(wire1, wire2)
    if not new_wire:
        return False

    # Update shape
    if boundary1.IsHosted:
        utils.remove_inner_wire(boundary1.ParentBoundary, wire1)
        utils.remove_inner_wire(boundary2.ParentBoundary, wire2)
        utils.append_inner_wire(boundary1.ParentBoundary, new_wire)
    else:
        for inner_boundary in boundary2.InnerBoundaries:
            utils.append(boundary1, "InnerBoundaries", inner_boundary)
            inner_boundary.ParentBoundary = boundary1
    inner_wires = utils.get_inner_wires(boundary1)[:]
    inner_wires.extend(utils.get_inner_wires(boundary2))
    inner_wires.extend(extra_inner_wires)

    try:
        utils.generate_boundary_compound(boundary1, new_wire, inner_wires)
    except RuntimeError as error:
        logger.exception(error)
        return False
    RelSpaceBoundary.recompute_areas(boundary1)

    return True


def merge_corresponding_boundaries(boundary1, boundary2):
    if boundary2.CorrespondingBoundary:
        corresponding_boundary = max(
            boundary1.CorrespondingBoundary,
            boundary2.CorrespondingBoundary,
            key=lambda x: x.Area,
        )
        boundary1.CorrespondingBoundary = corresponding_boundary
        corresponding_boundary.CorrespondingBoundary = boundary1


def merge_coplanar_boundaries(boundaries: list, doc=FreeCAD.ActiveDocument):
    """Try to merge coplanar boundaries"""
    if len(boundaries) == 1:
        return
    boundary1 = max(boundaries, key=lambda x: x.Area)
    # Ensure all boundaries are coplanar
    plane = utils.get_plane(boundary1)
    for boundary in boundaries:
        utils.project_boundary_onto_plane(boundary, plane)
    boundaries.remove(boundary1)
    remove_from_doc = list()

    # Attempt to merge boundaries
    while True and boundaries:
        for boundary2 in boundaries:
            if merge_boundaries(boundary1, boundary2):
                merge_corresponding_boundaries(boundary1, boundary2)
                boundaries.remove(boundary2)
                remove_from_doc.append(boundary2)
                break
        else:
            logger.warning(
                f"""Unable to merge boundaries RelSpaceBoundary Id <{boundary1.Id}>
                with boundaries <{", ".join(str(b.Id) for b in boundaries)}>"""
            )
            break

    # Clean FreeCAD document if join operation was a success
    for fc_object in remove_from_doc:
        doc.removeObject(fc_object.Name)


def create_fake_host(boundary, space, doc):
    fake_host = doc.copyObject(boundary)
    fake_host.IsHosted = False
    fake_host.LesoType = "Wall"
    fake_host.GlobalId = ifcopenshell.guid.new()
    fake_host.Id = IfcId.new(doc)
    RelSpaceBoundary.set_label(fake_host)
    space.SecondLevel.addObject(fake_host)
    inner_wire = utils.get_outer_wire(boundary)
    outer_wire = inner_wire.scaled(1.001, inner_wire.CenterOfMass)
    plane = utils.get_plane(boundary)
    outer_wire = utils.project_wire_to_plane(outer_wire, plane)
    inner_wire = utils.project_wire_to_plane(inner_wire, plane)
    utils.generate_boundary_compound(fake_host, outer_wire, [inner_wire])
    boundary.ParentBoundary = fake_host
    fake_building_element = doc.copyObject(boundary.RelatedBuildingElement)
    fake_building_element.Id = IfcId.new(doc)
    fake_host.RelatedBuildingElement = fake_building_element
    utils.append(fake_host, "InnerBoundaries", boundary)
    if FreeCAD.GuiUp:
        fake_host.ViewObject.ShapeColor = (0.7, 0.3, 0.0)
    return fake_host


def ensure_hosted_element_are(space, doc):
    for boundary in space.SecondLevel.Group:
        try:
            ifc_type = boundary.RelatedBuildingElement.IfcType
        except AttributeError:
            continue

        if not is_typically_hosted(ifc_type):
            continue

        if boundary.IsHosted and boundary.ParentBoundary:
            continue

        def valid_hosts(boundary):
            """Guess valid hosts"""
            for boundary2 in space.SecondLevel.Group:
                if boundary is boundary2 or is_typically_hosted(boundary2.IfcType):
                    continue

                if not boundary2.Area.Value - boundary.Area.Value >= 0:
                    continue

                if not utils.are_parallel_boundaries(boundary, boundary2):
                    continue

                if utils.are_too_far(boundary, boundary2):
                    continue

                yield boundary2

        def find_host(boundary):
            fallback_solution = None
            for boundary2 in valid_hosts(boundary):

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
            host = create_fake_host(boundary, space, doc)
            logger.exception(err)
        boundary.IsHosted = True
        boundary.ParentBoundary = host
        utils.append(host, "InnerBoundaries", boundary)


def ensure_hosted_are_coplanar(space):
    for boundary in space.SecondLevel.Group:
        inner_wires = utils.get_inner_wires(boundary)
        missing_inner_wires = False
        if len(inner_wires) < len(boundary.InnerBoundaries):
            missing_inner_wires = True
        outer_wire = utils.get_outer_wire(boundary)
        for inner_boundary in boundary.InnerBoundaries:
            if utils.is_coplanar(inner_boundary, boundary) and not missing_inner_wires:
                continue
            utils.project_boundary_onto_plane(inner_boundary, utils.get_plane(boundary))
            inner_wire = utils.get_outer_wire(inner_boundary)
            inner_wires.append(inner_wire)
        try:
            utils.generate_boundary_compound(boundary, outer_wire, inner_wires)
        except RuntimeError:
            continue


def is_typically_hosted(ifc_type: str):
    """Say if given ifc_type is typically hosted eg. windows, doors"""
    usually_hosted_types = ("IfcWindow", "IfcDoor", "IfcOpeningElement")
    for usual_type in usually_hosted_types:
        if ifc_type.startswith(usual_type):
            return True
    return False


class HostNotFound(LookupError):
    pass


Closest = namedtuple("Closest", ["boundary", "edge", "distance"])


def init_closest_default_values(boundaries):
    for boundary in boundaries:
        n_edges = len(utils.get_outer_wire(boundary).Edges)
        boundary.Proxy.closest = [
            Closest(boundary=None, edge=-1, distance=100000)
        ] * n_edges


def compare_closest_edges(boundary1, ei1, edge1, boundary2, ei2, edge2):
    distance = boundary1.Proxy.closest[ei1].distance
    edge_to_edge = edge_distance_to_edge(edge1, edge2)

    if distance <= TOLERANCE:
        return

    elif edge_to_edge <= TOLERANCE or edge_to_edge - distance - TOLERANCE <= 0:
        boundary1.Proxy.closest[ei1] = Closest(boundary2, ei2, edge_to_edge)


def find_closest_by_distance(boundary1, boundary2):
    edges1 = utils.get_outer_wire(boundary1).Edges
    edges2 = utils.get_outer_wire(boundary2).Edges
    for (ei1, edge1), (ei2, edge2) in itertools.product(
        enumerate(edges1), enumerate(edges2)
    ):
        if not is_low_angle(edge1, edge2):
            continue

        compare_closest_edges(boundary1, ei1, edge1, boundary2, ei2, edge2)
        compare_closest_edges(  # pylint: disable=arguments-out-of-order
            boundary2, ei2, edge2, boundary1, ei1, edge1
        )


def find_closest_by_intersection(boundary1, boundary2):
    intersect_line = utils.get_plane(boundary1).intersectSS(utils.get_plane(boundary2))[
        0
    ]
    boundaries_distance = boundary1.Shape.distToShape(boundary2.Shape)[0]
    edges1 = utils.get_outer_wire(boundary1).Edges
    edges2 = utils.get_outer_wire(boundary2).Edges
    for (ei1, edge1), (ei2, edge2) in itertools.product(
        enumerate(edges1), enumerate(edges2)
    ):
        distance1 = edge_distance_to_line(edge1, intersect_line) + boundaries_distance
        distance2 = edge_distance_to_line(edge2, intersect_line) + boundaries_distance

        min_distance = boundary1.Proxy.closest[ei1].distance
        if distance1 < min_distance:
            boundary1.Proxy.closest[ei1] = Closest(boundary2, -1, distance1)

        min_distance = boundary2.Proxy.closest[ei2].distance
        if distance2 < min_distance:
            boundary2.Proxy.closest[ei2] = Closest(boundary1, -1, distance2)


def find_closest_edges(space: "SpaceFeature") -> None:
    """Find closest boundary and edge to be able to reconstruct a closed shell"""
    boundaries = [b for b in space.SecondLevel.Group if not b.IsHosted]
    init_closest_default_values(boundaries)

    # Loop through all boundaries and edges to find the closest edge
    for boundary1, boundary2 in itertools.combinations(boundaries, 2):
        # If boundary1 and boundary2 have opposite direction no match possible
        normals_dot = boundary2.Normal.dot(boundary1.Normal)
        if normals_dot <= -1 + TOLERANCE:
            continue

        # If boundaries are not almost parallel, they must intersect
        if not normals_dot >= 1 - TOLERANCE:
            find_closest_by_intersection(boundary1, boundary2)

        # If they are parallel all edges need to be compared
        else:
            find_closest_by_distance(boundary1, boundary2)

    # Store found values in standard FreeCAD properties
    for boundary in boundaries:
        closest_boundaries, boundary.ClosestEdges, closest_distances = (
            list(i) for i in zip(*boundary.Proxy.closest)
        )
        boundary.ClosestBoundaries = [b.Id if b else -1 for b in closest_boundaries]
        boundary.ClosestDistance = [int(d) for d in closest_distances]


def set_leso_type(space):
    for boundary in space.SecondLevel.Group:
        # LesoType is defined in previous steps for curtain walls
        if boundary.LesoType != "Unknown":
            continue
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


def edge_distance_to_edge(edge1: Part.Edge, edge2: Part.Edge) -> float:
    mid_point = edge1.CenterOfMass
    line_segment = (v.Point for v in edge2.Vertexes)
    return mid_point.distanceToLineSegment(*line_segment).Length


def edge_distance_to_line(edge, line):
    mid_point = edge.CenterOfMass
    return mid_point.distanceToLine(line.Location, line.Direction)


def is_low_angle(edge1, edge2):
    try:
        dir1 = (edge1.Vertexes[1].Point - edge1.Vertexes[0].Point).normalize()
        dir2 = (edge2.Vertexes[1].Point - edge2.Vertexes[0].Point).normalize()
        return (
            abs(dir1.dot(dir2)) > 0.866
        )  # Low angle considered as < 30°. cos(pi/6)=0.866.
    except IndexError:
        return False


def create_sia_boundaries(doc=FreeCAD.ActiveDocument):
    """Create boundaries necessary for SIA calculations"""
    for space in utils.get_elements_by_ifctype("IfcSpace", doc):
        create_sia_ext_boundaries(space)
        create_sia_int_boundaries(space)
        rejoin_boundaries(space, "SIA_Exterior")
        rejoin_boundaries(space, "SIA_Interior")
        Progress.set()


def get_intersecting_line(boundary1, boundary2) -> Optional[Part.Line]:
    plane_intersect = utils.get_plane(boundary1).intersectSS(utils.get_plane(boundary2))
    return plane_intersect[0] if plane_intersect else None


def get_medial_axis(boundary1, boundary2, ei1, ei2) -> Optional[Part.Line]:
    line1 = utils.line_from_edge(utils.get_outer_wire(boundary1).Edges[ei1])
    try:
        line2 = utils.line_from_edge(utils.get_outer_wire(boundary2).Edges[ei2])
    except IndexError:
        logger.warning(
            f"""Cannot find closest edge index <{ei2}> in boundary <{boundary2.Label}>
            to rejoin boundary <{boundary1.Label}>"""
        )
        return None

    # Case 2a : edges are not parallel
    if abs(line1.Direction.dot(line2.Direction)) < 1 - TOLERANCE:
        b1_plane = utils.get_plane(boundary1)
        line_intersect = line1.intersect2d(line2, b1_plane)
        if line_intersect:
            point1 = b1_plane.value(*line_intersect[0])
            if line1.Direction.dot(line2.Direction) > 0:
                point2 = point1 + line1.Direction + line2.Direction
            else:
                point2 = point1 + line1.Direction - line2.Direction
    # Case 2b : edges are parallel
    else:
        point1 = (line1.Location + line2.Location) * 0.5
        point2 = point1 + line1.Direction

    try:
        return Part.Line(point1, point2)
    except Part.OCCError:
        logger.exception(
            f"Failure in boundary id <{boundary1.SourceBoundary.Id}> {point1} and {point2} are equal"
        )
        return None


def is_valid_join(line, fallback_line):
    """Angle < 15 ° is considered as valid join. cos(pi/6 ≈ 0.96)"""
    return abs(line.Direction.dot(fallback_line.Direction)) > 0.96


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
        boundary1 = getattr(base_boundary, sia_type)
        if not boundary1:
            continue
        lines = []
        fallback_lines = [
            utils.line_from_edge(edge) for edge in utils.get_outer_wire(boundary1).Edges
        ]

        # bound_box used to make sure line solution is in a reallistic scope (distance <= 5 m)
        bound_box = boundary1.Shape.BoundBox
        bound_box.enlarge(5000)

        if (
            base_boundary.IsHosted
            or base_boundary.PhysicalOrVirtualBoundary == "VIRTUAL"
            or not base_boundary.RelatedBuildingElement
        ):
            continue

        b1_plane = utils.get_plane(boundary1)
        for b2_id, (ei1, ei2), fallback_line in zip(
            base_boundary.ClosestBoundaries,
            enumerate(base_boundary.ClosestEdges),
            fallback_lines,
        ):
            base_boundary2 = utils.get_in_list_by_id(base_boundaries, b2_id)
            boundary2 = getattr(base_boundary2, sia_type, None)
            if not boundary2:
                logger.warning(f"Cannot find corresponding boundary with id <{b2_id}>")
                lines.append(fallback_line)
                continue
            # Case 1 : boundaries are not parallel
            line = get_intersecting_line(boundary1, boundary2)
            if line:
                if not is_valid_join(line, fallback_line):
                    line = fallback_line
                if not bound_box.intersect(line.Location, line.Direction):
                    line = fallback_line
                lines.append(line)
                continue
            # Case 2 : boundaries are parallel
            line = get_medial_axis(boundary1, boundary2, ei1, ei2)
            if line and is_valid_join(line, fallback_line):
                lines.append(line)
                continue

            lines.append(fallback_line)

        # Generate new shape
        try:
            outer_wire = utils.polygon_from_lines(lines, b1_plane)
        except (Part.OCCError, utils.ShapeCreationError):
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
        try:
            utils.generate_boundary_compound(boundary1, outer_wire, inner_wires)
        except RuntimeError as err:
            logger.exception(err)
            continue

        boundary1.Area = area = boundary1.Shape.Area
        for inner_boundary in base_boundary.InnerBoundaries:
            area = area + inner_boundary.Shape.Area
        boundary1.AreaWithHosted = area


def create_sia_ext_boundaries(space):
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
        leso_type = boundary1.LesoType
        normal = boundary1.Normal
        # EXTERNAL: there is multiple possible values for external so testing internal is better.
        if boundary1.InternalOrExternalBoundary != "INTERNAL":
            distance = thickness
        # INTERNAL
        else:
            if leso_type == "Flooring":
                distance = 0
            elif leso_type == "Ceiling":
                distance = thickness
            else:  # Walls
                distance = thickness / 2
        bem_boundary.Placement.move(normal * distance + boundary1.TranslationToSpace)


def create_sia_int_boundaries(space):
    """Create boundaries necessary for SIA calculations"""
    sia_group_obj = space.Boundaries.newObject(
        "App::DocumentObjectGroup", "SIA_Interiors"
    )
    space.SIA_Interiors = sia_group_obj
    for boundary in space.SecondLevel.Group:
        if boundary.IsHosted or boundary.PhysicalOrVirtualBoundary == "VIRTUAL":
            continue

        bem_boundary = BEMBoundary.create(boundary, "SIA_Interior")
        sia_group_obj.addObject(bem_boundary)

        # Bad location in some software like Revit (last check : revit-ifc 21.1.0.0)
        if not boundary.TranslationToSpace.isEqual(FreeCAD.Vector(), TOLERANCE):
            bem_boundary.Placement.move(boundary.TranslationToSpace)


class XmlResult(NamedTuple):
    xml: str
    log: str


def generate_bem_xml_from_file(ifc_path: str) -> XmlResult:
    try:
        import pyCaller

        Progress.progress_func = pyCaller.SetProgress
    except ImportError:
        pass
    Progress.set(0, "IfcImport_OpenIfcFile", "")
    ifc_importer = IfcImporter(ifc_path)
    ifc_importer.generate_rel_space_boundaries()
    doc = ifc_importer.doc
    processing_sia_boundaries(doc)
    Progress.set(90, "Communicate_Write", "")
    xml_str = write_xml(doc).tostring()
    log_str = LOG_STREAM.getvalue()
    Progress.set(100, "Communicate_Send", "")
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
    with open("./boundaries.log", "w", encoding="utf-8") as log_file:
        log_file.write(ifc_importer.log)
    return ifc_importer


class InvalidMergeError(RuntimeError):
    pass
