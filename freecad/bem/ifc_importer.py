# coding: utf8
"""This module reads IfcRelSpaceBoundary from an IFC file and display them in FreeCAD

© All rights reserved.
ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Laboratory CNPA, 2019-2020

See the LICENSE.TXT file for more details.

Author : Cyril Waechter
"""

from typing import Generator

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.element
import ifcopenshell.util.unit
import ifcopenshell.util.shape

import numpy as np

import FreeCAD
import Part

from freecad.bem import materials
from freecad.bem import utils
from freecad.bem.bem_logging import logger
from freecad.bem.progress import Progress
from freecad.bem.entities import (
    RelSpaceBoundary,
    Element,
    ElementType,
    Container,
    Space,
    Project,
)


TOLERANCE = 0.001


def get_by_class(doc=FreeCAD.ActiveDocument, by_class=object):
    """Generator throught FreeCAD document element of specific python proxy class"""
    for element in doc.Objects:
        try:
            if isinstance(element.Proxy, by_class):
                yield element
        except AttributeError:
            continue


def get_elements_by_ifctype(ifc_type: str, doc=FreeCAD.ActiveDocument) -> Generator[Part.Feature, None, None]:
    """Generator throught FreeCAD document element of specific ifc_type"""
    for element in doc.Objects:
        try:
            if element.IfcType == ifc_type:
                yield element
        except (AttributeError, ReferenceError):
            continue


def get_materials(doc=FreeCAD.ActiveDocument):
    """Generator throught FreeCAD document element of specific python proxy class"""
    for element in doc.Objects:
        try:
            if element.IfcType in (
                "IfcMaterial",
                "IfcMaterialList",
                "IfcMaterialLayerSet",
                "IfcMaterialLayerSetUsage",
                "IfcMaterialConstituentSet",
                "IfcMaterialConstituent",
            ):
                yield element
        except AttributeError:
            continue


def is_second_level(boundary):
    return boundary.is_a("IfcRelSpaceBoundary2ndLevel") or (boundary.Name or "").lower() == "2ndlevel"


class IfcImporter:
    def __init__(self, ifc_path, doc=None):
        if not doc:
            doc = FreeCAD.newDocument()
        self.doc = doc
        self.ifc_file = ifcopenshell.open(ifc_path)
        self.ifc_scale = ifcopenshell.util.unit.calculate_unit_scale(self.ifc_file)
        self.fc_scale = FreeCAD.Units.Metre.Value
        self.total_scale = self.fc_scale * self.ifc_scale
        self.element_types = dict()
        self.material_creator = materials.MaterialCreator(self)
        self.xml: str = ""
        self.log: str = ""
        self.settings = ifcopenshell.geom.settings()
        self.settings_brep_curve = self.load_brep_curve_settings()
        self.settings_brep_local = self.load_brep_settings(use_world_coordinates=False)
        self.settings_brep_world = self.load_brep_settings(use_world_coordinates=True)

    def generate_rel_space_boundaries(self):
        """Display IfcRelSpaceBoundaries from selected IFC file into FreeCAD documennt"""
        ifc_file = self.ifc_file
        doc = self.doc

        Progress.count_elements(ifc_file)
        # Generate elements (Door, Window, Wall, Slab etc…) without their geometry
        Progress.set(1, "IfcImport_Elements", "")
        elements_group = get_or_create_group("Elements", doc)
        element_types_group = get_or_create_group("ElementTypes", doc)
        ifc_types = set()
        for ifc_entity in (e for e in ifc_file.by_type("IfcElement") if e.ProvidesBoundaries):
            elements_group.addObject(Element.create_from_ifc(ifc_entity, self))
            ifc_type = ifcopenshell.util.element.get_type(ifc_entity)
            if ifc_type not in ifc_types and ifc_type is not None:
                ifc_types.add(ifc_type)
                element_types_group.addObject(Element.create_from_ifc(ifc_type, self))
        materials_group = get_or_create_group("Materials", doc)
        for material in get_materials(doc):
            materials_group.addObject(material)
        # Generate projects structure and boundaries
        Progress.set(5, "IfcImport_StructureAndBoundaries", "")
        for ifc_project in ifc_file.by_type("IfcProject"):
            project = Project.create_from_ifc(ifc_project, self)
            self.generate_containers(ifc_project, project)

        # Associate existing ParentBoundary and CorrespondingBoundary
        associate_parent_and_corresponding(ifc_file, doc)

        Progress.set(15, "IfcImporter_EnrichingDatas", "")
        # Associate CorrespondingBoundary
        associate_corresponding_boundaries(doc)

        # Associate Host / Hosted elements
        associate_host_element(ifc_file, elements_group)

        # Associate hosted elements
        i = 0
        for i, fc_space in enumerate(get_elements_by_ifctype("IfcSpace", doc), 1):
            Progress.set(15, "IfcImporter_EnrichingDatas", f"{i}")
            fc_boundaries = fc_space.SecondLevel.Group
            # Minimal number of boundary is 5: 3 vertical faces, 2 horizontal faces
            # If there is less than 5 boundaries there is an issue or a new case to analyse
            if len(fc_boundaries) == 5:
                continue
            elif len(fc_boundaries) < 5:
                assert ValueError, f"{fc_space.Label} has less than 5 boundaries"

            # Associate hosted elements
            associate_inner_boundaries(fc_boundaries, doc)
        Progress.len_spaces = i

    def guess_thickness(self, obj, ifc_entity):
        if obj.Material:
            thickness = getattr(obj.Material, "TotalThickness", 0)
            if thickness:
                return thickness

        if ifc_entity.is_a("IfcWall"):
            qto_lookup_name = "Qto_WallBaseQuantities"
        elif ifc_entity.is_a("IfcSlab"):
            qto_lookup_name = "Qto_SlabBaseQuantities"
        else:
            qto_lookup_name = ""

        if qto_lookup_name:
            for definition in ifc_entity.IsDefinedBy:
                if not definition.is_a("IfcRelDefinesByProperties"):
                    continue
                if definition.RelatingPropertyDefinition.Name == qto_lookup_name:
                    for quantity in definition.RelatingPropertyDefinition.Quantities:
                        if quantity.Name == "Width":
                            return quantity.LengthValue * self.fc_scale * self.ifc_scale

        if not getattr(ifc_entity, "Representation", None):
            return 0
        if ifc_entity.IsDecomposedBy:
            thicknesses = []
            for aggregate in ifc_entity.IsDecomposedBy:
                thickness = 0
                for related in aggregate.RelatedObjects:
                    thickness += self.guess_thickness(obj, related)
                thicknesses.append(thickness)
            return max(thicknesses)
        for representation in ifc_entity.Representation.Representations:
            if representation.RepresentationIdentifier == "Box" and representation.RepresentationType == "BoundingBox":
                if self.is_wall_like(obj.IfcType):
                    return representation.Items[0].YDim * self.fc_scale * self.ifc_scale
                elif self.is_slab_like(obj.IfcType):
                    return representation.Items[0].ZDim * self.fc_scale * self.ifc_scale
                else:
                    return 0
        try:
            fc_shape = self.element_shape_by_brep(ifc_entity)
            bbox = fc_shape.BoundBox
        except RuntimeError:
            return 0
        # Returning bbox thickness for windows or doors is not insteresting
        # as it does not return frame thickness.
        if self.is_wall_like(obj.IfcType):
            return min(bbox.YLength, bbox.XLength)
        elif self.is_slab_like(obj.IfcType):
            return bbox.ZLength
        # Here we consider that thickness is distance between the 2 faces with higher area
        elif ifc_entity.is_a("IfcRoof"):
            faces = sorted(fc_shape.Faces, key=lambda x: x.Area)
            if len(faces) < 2:
                logger.warning(
                    f"""{ifc_entity.is_a()}<{ifc_entity.id()}> has an invalid geometry (empty or less than 2 faces)"""
                )
                return 0
            return faces[-1].distToShape(faces[-2])[0]
        return 0

    @staticmethod
    def is_wall_like(ifc_type):
        return ifc_type in ("IfcWall", "IfcWallStandardCase", "IfcCurtainWall")

    @staticmethod
    def is_slab_like(ifc_type):
        return ifc_type in ("IfcSlab", "IfcSlabStandardCase")

    def generate_containers(self, ifc_parent, fc_parent):
        for rel_aggregates in ifc_parent.IsDecomposedBy:
            for element in rel_aggregates.RelatedObjects:
                if element.is_a("IfcSpace"):
                    if element.BoundedBy:
                        self.generate_space(element, fc_parent)
                        self.generate_containers(element, fc_parent)
                else:
                    if element.is_a("IfcSite"):
                        self.workaround_site_coordinates(element)
                    fc_container = Container.create_from_ifc(element, self)
                    fc_parent.addObject(fc_container)
                    self.generate_containers(element, fc_container)

    def workaround_site_coordinates(self, ifc_site):
        """Multiple softwares (eg. Revit) are storing World Coordinate system in IfcSite location
        instead of using IfcProject IfcGeometricRepresentationContext. This is a bad practice
        should be solved over time"""
        ifc_location = ifc_site.ObjectPlacement.RelativePlacement.Location
        fc_location = FreeCAD.Vector(ifc_location.Coordinates)
        fc_location.scale(*[self.ifc_scale * self.fc_scale] * 3)
        if not fc_location.Length > 1000000:  # 1 km
            return
        for project in get_by_class(self.doc, Project):
            project.WorldCoordinateSystem += fc_location
        ifc_location.Coordinates = (
            0.0,
            0.0,
            0.0,
        )

    def generate_space(self, ifc_space, parent):
        """Generate Space and RelSpaceBoundaries as defined in ifc_file. No post process."""
        fc_space = Space.create_from_ifc(ifc_space, self)
        parent.addObject(fc_space)

        boundaries = fc_space.newObject("App::DocumentObjectGroup", "Boundaries")
        fc_space.Boundaries = boundaries
        second_levels = boundaries.newObject("App::DocumentObjectGroup", "SecondLevel")
        fc_space.SecondLevel = second_levels

        # All boundaries have their placement relative to space placement
        placement = ifcopenshell.util.placement.get_local_placement(ifc_space.ObjectPlacement)
        space_matrix = self.get_fc_placement(placement)
        fc_space.Placement = space_matrix
        for ifc_boundary in (b for b in ifc_space.BoundedBy if is_second_level(b)):
            if not ifc_boundary.ConnectionGeometry:
                logger.warning(f"[Ignored] No ConnectionGeometry: {ifc_boundary}")
                continue
            try:
                fc_boundary = RelSpaceBoundary.create_from_ifc(ifc_entity=ifc_boundary, ifc_importer=self)
                fc_boundary.RelatingSpace = fc_space
                second_levels.addObject(fc_boundary)
                fc_boundary.Placement = space_matrix
            except utils.ShapeCreationError:
                logger.error(f"[Geometry] All fallback failed: {ifc_boundary}")
            except utils.IsTooSmall:
                logger.warning(f"[Ignored] Too small: {ifc_boundary}")

    def get_fc_placement(self, placement):
        """Transform position to FreeCAD.Matrix"""
        placement[:3, -1] *= self.total_scale
        # placement[:3, :3]=placement[:3, :3].transpose()
        matrix = FreeCAD.Matrix(*placement.flatten().tolist())
        return matrix

    def get_global_placement(self, obj_placement) -> FreeCAD.Matrix:
        if not obj_placement:
            return FreeCAD.Matrix()
        if not obj_placement.PlacementRelTo:
            parent = FreeCAD.Matrix()
        else:
            parent = self.get_global_placement(obj_placement.PlacementRelTo)
        return parent.multiply(self.get_fc_placement(obj_placement.RelativePlacement))

    def get_global_y_axis(self, ifc_entity):
        global_placement = self.get_global_placement(ifc_entity)
        return FreeCAD.Vector(global_placement.A[1:12:4])

    def create_fc_shape(self, ifc_boundary):
        """Create Part shape from ifc geometry"""
        surface = ifc_boundary.ConnectionGeometry.SurfaceOnRelatingElement
        placement = ifcopenshell.util.placement.get_axis2placement(surface.BasisSurface.Position)
        matrix = self.get_fc_placement(placement)
        try:
            fc_shape = self.part_by_wires(surface)
            return fc_shape.transformGeometry(matrix)
        except (RuntimeError, utils.ShapeCreationError):
            print(f"[Geometry] Shape by wire failed: {surface}")

    def part_by_relating_element(self, surface):
        shape = ifcopenshell.geom.create_shape(self.settings, surface)
        # if len(shape.faces) != 1:
        # raise utils.ShapeCreationError
        vertices = ifcopenshell.util.shape.get_vertices(shape)
        vertices = np.vstack((vertices, vertices[0]))
        polygon = Part.makePolygon([FreeCAD.Vector(tuple(v)) for v in vertices])
        return Part.makeFace(polygon, "Part::FaceMakerBullseye")

    def part_by_wires(self, surface):
        """Create a Part Shape from ifc geometry"""
        inner_wires = list()
        outer_wire = self._polygon_by_curve(surface.OuterBoundary)
        face = Part.Face(outer_wire)
        try:
            inner_boundaries = surface.InnerBoundaries or tuple()
            for inner_boundary in inner_boundaries:
                inner_wire = self._polygon_by_curve(inner_boundary)
                face = face.cut(Part.Face(inner_wire))
                inner_wires.append(inner_wire)
        except RuntimeError:
            pass
        fc_shape = Part.Compound([face, outer_wire, *inner_wires])
        return fc_shape

    def element_shape_by_brep(self, ifc_entity, world_coordinates=False) -> Part.Shape:
        """Create a Element Shape from brep generated by ifcopenshell from ifc geometry"""
        if world_coordinates:
            settings = self.settings_brep_world
        else:
            settings = self.settings_brep_local
        ifc_shape = ifcopenshell.geom.create_shape(settings, ifc_entity)
        if hasattr(ifc_shape, "geometry"):
            brep_data = ifc_shape.geometry.brep_data
        else:
            brep_data = ifc_shape.brep_data
        fc_shape = Part.Shape()
        fc_shape.importBrepFromString(brep_data)
        fc_shape.scale(self.fc_scale)
        return fc_shape

    def _part_by_mesh(self, ifc_entity):
        """Create a Part Shape from mesh generated by ifcopenshell from ifc geometry"""
        return Part.Face(self._polygon_by_curve(ifc_entity))

    def _polygon_by_curve(self, curve):
        """Create a Polygon from a compatible ifc entity"""
        if curve.is_a("IfcCompositeCurve"):
            parent_curve = curve.Segments[0].ParentCurve
            if parent_curve.is_a("IfcPolyline"):
                points = self.points_by_polyline(parent_curve)
        elif curve.is_a("IfcPolyline"):
            points = self.points_by_polyline(curve)
        elif curve.is_a("IfcIndexedPolyCurve"):
            points = np.array(curve.Points.CoordList)
            np.vstack((points, points[0]))
        points *= self.total_scale
        if points.shape[1] == 2:
            points = np.c_[points, np.zeros(len(points))]
        return Part.makePolygon([FreeCAD.Vector(p) for p in points])

    def points_by_polyline(self, polyline):
        return np.array([p.Coordinates for p in polyline.Points])

    def _polygon_by_curve_using_brep(self, curve):
        """Create a Polygon from a compatible ifc entity"""
        shape = ifcopenshell.geom.create_shape(self.settings_brep_curve, curve)
        if hasattr(shape, "geometry"):
            brep_data = shape.geometry.brep_data
        else:
            brep_data = shape.brep_data
        fc_shape = Part.Shape()
        fc_shape.importBrepFromString(brep_data)
        fc_shape.scale(self.fc_scale)
        Part.show(fc_shape)
        vectors = [FreeCAD.Vector(v.X, v.Y, v.Z) for v in fc_shape.Wires[0].Vertexes]
        vectors.append(vectors[0])
        return Part.makePolygon(vectors)

    def create_element_type(self, fc_element, ifc_entity_type):
        if not ifc_entity_type:
            return
        try:
            fc_element_type = self.element_types[ifc_entity_type.id()]
        except KeyError:
            fc_element_type = ElementType.create_from_ifc(ifc_entity_type, self)
            self.element_types[fc_element_type.Id] = fc_element_type
        fc_element.IsTypedBy = fc_element_type
        utils.append(fc_element_type, "ApplicableOccurrence", fc_element)

    def load_brep_curve_settings(self):
        settings = self.load_brep_settings(use_world_coordinates=False)
        settings.set(
            "dimensionality",
            ifcopenshell.ifcopenshell_wrapper.CURVES_SURFACES_AND_SOLIDS,
        )
        return settings

    def load_brep_settings(self, use_world_coordinates):
        settings = ifcopenshell.geom.settings()
        settings.set("iterator-output", ifcopenshell.ifcopenshell_wrapper.SERIALIZED)
        settings.set("use-world-coords", use_world_coordinates)
        return settings


def associate_host_element(ifc_file, elements_group):
    # Associate Host / Hosted elements
    ifc_elements = (e for e in ifc_file.by_type("IfcElement") if e.ProvidesBoundaries)
    for ifc_entity in ifc_elements:
        if ifc_entity.FillsVoids:
            try:
                host = utils.get_element_by_guid(utils.get_host_guid(ifc_entity), elements_group)
            except LookupError as err:
                logger.exception(err)
                continue
            hosted = utils.get_element_by_guid(ifc_entity.GlobalId, elements_group)
            utils.append(host, "HostedElements", hosted)
            utils.append(hosted, "HostElements", host)


def get_host(boundary, hosts):
    if not hosts:
        # Common issue with both ArchiCAD and Revit
        logger.debug(f"Boundary <{boundary.Label}> is hosted but host not found.")
        return None
    if len(hosts) == 1:
        host = hosts.pop()
        if utils.are_parallel_boundaries(boundary, host):
            return host
    else:
        for host in hosts:
            if not utils.are_parallel_boundaries(boundary, host):
                continue
            if utils.are_too_far(boundary, host):
                continue
            return host
    raise InvalidBoundary(
        f""" boundary {boundary.Label} is hosted and his related building element fills
    an element void. Boundary is invalid.
    This occur with Revit models. Invalid boundary is created when a window is
    touching another wall which is not his host """
    )


def remove_invalid_inner_wire(boundary, boundaries):
    """Find and remove inner wire produce by invalid hosted boundary"""
    area = boundary.Area.Value
    for host in boundaries:
        if not utils.are_parallel_boundaries(boundary, host):
            continue
        if utils.are_too_far(boundary, host):
            continue
        inner_wires = utils.get_inner_wires(host)
        for wire in inner_wires:
            if abs(Part.Face(wire).Area - area) < TOLERANCE:
                utils.remove_inner_wire(host, wire)
                utils.update_boundary_shape(host)
                return


def associate_inner_boundaries(fc_boundaries, doc):
    """Associate parent boundary and inner boundaries"""
    to_delete = []
    for fc_boundary in fc_boundaries:
        if not fc_boundary.IsHosted or fc_boundary.ParentBoundary:
            continue
        host_boundaries = []
        for host_element in fc_boundary.RelatedBuildingElement.HostElements:
            host_boundaries.extend(host_element.ProvidesBoundaries)

        candidates = set(fc_boundaries).intersection(host_boundaries)

        try:
            host = get_host(fc_boundary, candidates)
        except InvalidBoundary as err:
            logger.exception(err)
            to_delete.append(fc_boundary)
            continue

        fc_boundary.ParentBoundary = host
        if host:
            utils.append(host, "InnerBoundaries", fc_boundary)

    # Remove invalid boundary and corresponding inner wire
    updated_boundaries = fc_boundaries[:]
    for boundary in to_delete:
        remove_invalid_inner_wire(boundary, updated_boundaries)
        updated_boundaries.remove(boundary)
        doc.removeObject(boundary.Name)


def associate_parent_and_corresponding(ifc_file, doc):
    try:
        for boundary in ifc_file.by_type("IfcRelSpaceBoundary2ndLevel"):
            if boundary.ParentBoundary:
                fc_boundary = utils.get_object(boundary, doc)
                fc_parent = utils.get_object(boundary.ParentBoundary, doc)
                fc_boundary.ParentBoundary = fc_parent
                utils.append(fc_parent, "InnerBoundaries", fc_boundary)
            if boundary.CorrespondingBoundary:
                fc_boundary = utils.get_object(boundary, doc)
                if fc_boundary.CorrespondingBoundary:
                    continue
                fc_corresponding_boundary = utils.get_object(boundary.CorrespondingBoundary, doc)
                fc_boundary.CorrespondingBoundary = fc_corresponding_boundary
                fc_corresponding_boundary.CorrespondingBoundary = fc_boundary
    except RuntimeError:
        # When entity do not exist in the schema
        pass


def associate_corresponding_boundaries(doc=FreeCAD.ActiveDocument):
    # Associate CorrespondingBoundary
    for fc_boundary in get_elements_by_ifctype("IfcRelSpaceBoundary", doc):
        associate_corresponding_boundary(fc_boundary, doc)


def cleaned_corresponding_candidates(boundary1):
    candidates = []
    for boundary2 in getattr(boundary1.RelatedBuildingElement, "ProvidesBoundaries", ()):
        if boundary2 is boundary1:
            continue
        if boundary2.CorrespondingBoundary:
            continue
        if boundary2.InternalOrExternalBoundary != "INTERNAL":
            continue
        if boundary1.RelatingSpace is boundary2.RelatingSpace:
            continue
        if not abs(1 - boundary1.Area.Value / boundary2.Area.Value) < TOLERANCE:
            continue
        candidates.append(boundary2)
    return candidates


def get_best_corresponding_candidate(boundary, candidates):
    if len(candidates) == 1:
        return candidates[0]
    corresponding_boundary = None
    center_of_mass = utils.get_outer_wire(boundary).CenterOfMass
    min_lenght = 10000  # No element has 10 m thickness
    for candidate in candidates:
        distance = center_of_mass.distanceToPoint(utils.get_outer_wire(candidate).CenterOfMass)
        if distance < min_lenght:
            min_lenght = distance
            corresponding_boundary = candidate
    return corresponding_boundary


def seems_too_smal(boundary) -> bool:
    """considered as too small if width or heigth < 100 mm"""
    try:
        uv_nodes = boundary.Shape.Faces[0].getUVNodes()
        return min(abs(n_2 - n_1) for n_1, n_2 in zip(uv_nodes[0], uv_nodes[2])) < 100
    except RuntimeError:  # TODO: further investigation to see why it happens
        if boundary.Shape.Faces[0].Area < 10000:  # 0.01 m²
            return True
        else:
            return False


def associate_corresponding_boundary(boundary, doc):
    """Associate corresponding boundaries according to IFC definition.

    Reference to the other space boundary of the pair of two space boundaries on either side of a
    space separating thermal boundary element.
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcrelspaceboundary2ndlevel.htm
    """
    if boundary.InternalOrExternalBoundary != "INTERNAL" or boundary.CorrespondingBoundary:
        return

    candidates = cleaned_corresponding_candidates(boundary)
    corresponding_boundary = get_best_corresponding_candidate(boundary, candidates)
    if corresponding_boundary:
        boundary.CorrespondingBoundary = corresponding_boundary
        corresponding_boundary.CorrespondingBoundary = boundary
    elif boundary.PhysicalOrVirtualBoundary == "VIRTUAL" and seems_too_smal(boundary):
        logger.warning(
            f"""
    Boundary {boundary.Label} from space {boundary.RelatingSpace.Id} has been removed.
    It is VIRTUAL, INTERNAL, thin and has no corresponding boundary. It looks like a parasite."""
        )
        doc.removeObject(boundary.Name)
    else:
        # Considering test above. Assume that it has been missclassified but log the issue.
        boundary.InternalOrExternalBoundary = "EXTERNAL"
        logger.warning(
            f"""
    No corresponding boundary found for {boundary.Label} from space {boundary.RelatingSpace.Id}.
    Assigning to EXTERNAL assuming it was missclassified as INTERNAL"""
        )


def get_or_create_group(name, doc=FreeCAD.ActiveDocument):
    """Get group by name or create one if not found"""
    group = doc.findObjects("App::DocumentObjectGroup", name)
    if group:
        return group[0]
    return doc.addObject("App::DocumentObjectGroup", name)


class InvalidBoundary(LookupError):
    pass


if __name__ == "__main__":
    pass
