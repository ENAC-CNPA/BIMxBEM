# coding: utf8
"""This module reads IfcRelSpaceBoundary from an IFC file and display them in FreeCAD

© All rights reserved.
ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Laboratory CNPA, 2019-2020

See the LICENSE.TXT file for more details.

Author : Cyril Waechter
"""
from typing import NamedTuple, Generator

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import ifcopenshell.util.unit

import FreeCAD
import Part

from freecad.bem import materials
from freecad.bem import utils
from freecad.bem.bem_logging import logger
from freecad.bem.entities import (
    RelSpaceBoundary,
    Element,
    Container,
    Space,
    Project,
)


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


class ShapeCreationError(RuntimeError):
    pass


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
    prefix_factor = ifcopenshell.util.unit.get_prefix_multiplier(ifc_unit.Prefix)

    return unit_factor * prefix_factor


class IfcImporter:
    def __init__(self, ifc_path, doc=None):
        if not doc:
            doc = FreeCAD.newDocument()
        self.doc = doc
        self.ifc_file = ifcopenshell.open(ifc_path)
        self.ifc_scale = get_unit_conversion_factor(self.ifc_file, "LENGTHUNIT")
        self.fc_scale = FreeCAD.Units.Metre.Value
        self.material_creator = materials.MaterialCreator(self)
        self.xml: str = ""
        self.log: str = ""

    def generate_rel_space_boundaries(self):
        """Display IfcRelSpaceBoundaries from selected IFC file into FreeCAD documennt"""
        ifc_file = self.ifc_file
        doc = self.doc

        # Generate elements (Door, Window, Wall, Slab etc…) without their geometry
        elements_group = get_or_create_group("Elements", doc)
        ifc_elements = (
            e for e in ifc_file.by_type("IfcElement") if e.ProvidesBoundaries
        )
        for ifc_entity in ifc_elements:
            elements_group.addObject(Element.create_from_ifc(ifc_entity, self))

        # Generate projects structure and boundaries
        for ifc_project in ifc_file.by_type("IfcProject"):
            project = Project.create_from_ifc(ifc_project, self)
            self.generate_containers(ifc_project, project)

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

    def guess_thickness(self, obj, ifc_entity):
        if obj.Material:
            thickness = getattr(obj.Material, "TotalThickness", 0)
            if thickness:
                return thickness
        if not ifc_entity.Representation:
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
            if (
                representation.RepresentationIdentifier == "Box"
                and representation.RepresentationType == "BoundingBox"
            ):
                if self.is_wall_like(obj.IfcType):
                    return representation.Items[0].YDim * self.fc_scale * self.ifc_scale
                elif self.is_slab_like(obj.IfcType):
                    return representation.Items[0].ZDim * self.fc_scale * self.ifc_scale
                else:
                    return 0
        bbox = self.entity_shape_by_brep(ifc_entity).BoundBox
        # Returning bbox thickness for windows or doors is not insteresting
        # as it does not return frame thickness.
        if self.is_wall_like(obj.IfcType):
            return bbox.YLength
        elif self.is_slab_like(obj.IfcType):
            return bbox.ZLength
        return 0

    @staticmethod
    def is_wall_like(ifc_type):
        return ifc_type in ("IfcWall", "IfcWallStandardCase", "IfcCurtainWall")

    @staticmethod
    def is_slab_like(ifc_type):
        return ifc_type in ("IfcSlab", "IfcSlabStandardCase", "IfcRoof")

    def generate_containers(self, ifc_parent, fc_parent):
        for rel_aggregates in ifc_parent.IsDecomposedBy:
            for element in rel_aggregates.RelatedObjects:
                if element.is_a("IfcSpace"):
                    if element.BoundedBy:
                        self.generate_space(element, fc_parent)
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
        space_placement = self.get_placement(ifc_space)
        for ifc_boundary in (b for b in ifc_space.BoundedBy if b.Name == "2ndLevel"):
            try:
                fc_boundary = RelSpaceBoundary.create_from_ifc(
                    ifc_entity=ifc_boundary, ifc_importer=self
                )
                second_levels.addObject(fc_boundary)
                fc_boundary.Placement = space_placement
            except ShapeCreationError:
                logger.warning(
                    f"Failed to create fc_shape for RelSpaceBoundary <{ifc_boundary.id()}> even with fallback methode _part_by_mesh. IfcOpenShell bug ?"
                )

    def get_placement(self, space):
        """Retrieve object placement"""
        space_geom = ifcopenshell.geom.create_shape(BREP_SETTINGS, space)
        # IfcOpenShell matrix values FreeCAD matrix values are transposed
        ios_matrix = space_geom.transformation.matrix.data
        m_l = list()
        for i in range(3):
            line = list(ios_matrix[i::3])
            line[-1] *= self.fc_scale
            m_l.extend(line)
        return FreeCAD.Matrix(*m_l)

    def get_matrix(self, position):
        """Transform position to FreeCAD.Matrix"""
        total_scale = self.fc_scale * self.ifc_scale
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

    def create_fc_shape(self, ifc_boundary):
        """ Create Part shape from ifc geometry"""
        if BREP:
            try:
                return self._boundary_shape_by_brep(
                    ifc_boundary.ConnectionGeometry.SurfaceOnRelatingElement
                )
            except RuntimeError:
                print(f"Failed to generate brep from {ifc_boundary}")
                fallback = True
        if not BREP or fallback:
            try:
                return self.part_by_wires(
                    ifc_boundary.ConnectionGeometry.SurfaceOnRelatingElement
                )
            except RuntimeError:
                print(f"Failed to generate mesh from {ifc_boundary}")
                try:
                    return self._part_by_mesh(
                        ifc_boundary.ConnectionGeometry.SurfaceOnRelatingElement
                    )
                except RuntimeError:
                    raise ShapeCreationError

    def part_by_wires(self, ifc_entity):
        """ Create a Part Shape from ifc geometry"""
        inner_wires = list()
        outer_wire = self._polygon_by_mesh(ifc_entity.OuterBoundary)
        face = Part.Face(outer_wire)
        try:
            inner_boundaries = ifc_entity.InnerBoundaries or tuple()
            for inner_boundary in inner_boundaries:
                inner_wire = self._polygon_by_mesh(inner_boundary)
                face = face.cut(Part.Face(inner_wire))
                inner_wires.append(inner_wire)
        except RuntimeError:
            pass
        fc_shape = Part.Compound([face, outer_wire, *inner_wires])
        matrix = self.get_matrix(ifc_entity.BasisSurface.Position)
        fc_shape = fc_shape.transformGeometry(matrix)
        return fc_shape

    def _boundary_shape_by_brep(self, ifc_entity):
        """ Create a Part Shape from brep generated by ifcopenshell from ifc geometry"""
        ifc_shape = ifcopenshell.geom.create_shape(BREP_SETTINGS, ifc_entity)
        fc_shape = Part.Shape()
        fc_shape.importBrepFromString(ifc_shape.geometry.brep_data)
        fc_shape.scale(self.fc_scale)
        return fc_shape

    def entity_shape_by_brep(self, ifc_entity) -> Part.Shape:
        """ Create a Part Shape from brep generated by ifcopenshell from ifc geometry"""
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_BREP_DATA, True)
        ifc_shape = ifcopenshell.geom.create_shape(settings, ifc_entity)
        fc_shape = Part.Shape()
        fc_shape.importBrepFromString(ifc_shape.geometry.brep_data)
        fc_shape.scale(self.fc_scale)
        return fc_shape

    def _part_by_mesh(self, ifc_entity):
        """ Create a Part Shape from mesh generated by ifcopenshell from ifc geometry"""
        return Part.Face(self._polygon_by_mesh(ifc_entity))

    def _polygon_by_mesh(self, ifc_entity):
        """Create a Polygon from a compatible ifc entity"""
        ifc_shape = ifcopenshell.geom.create_shape(MESH_SETTINGS, ifc_entity)
        ifc_verts = ifc_shape.verts
        fc_verts = [
            FreeCAD.Vector(ifc_verts[i : i + 3]).scale(*[self.fc_scale] * 3)
            for i in range(0, len(ifc_verts), 3)
        ]
        utils.clean_vectors(fc_verts)
        utils.close_vectors(fc_verts)
        return Part.makePolygon(fc_verts)


class CommonSegment(NamedTuple):
    index1: int
    index2: int
    opposite_dir: FreeCAD.Vector


def associate_host_element(ifc_file, elements_group):
    # Associate Host / Hosted elements
    ifc_elements = (e for e in ifc_file.by_type("IfcElement") if e.ProvidesBoundaries)
    for ifc_entity in ifc_elements:
        if ifc_entity.FillsVoids:
            host = utils.get_element_by_guid(
                utils.get_host_guid(ifc_entity), elements_group
            )
            hosted = utils.get_element_by_guid(ifc_entity.GlobalId, elements_group)
            utils.append(host, "HostedElements", hosted)
            hosted.HostElement = host.Id


def associate_inner_boundaries(fc_boundaries, doc):
    """Associate hosted elements like a window or a door in a wall"""
    for fc_boundary in fc_boundaries:
        if not fc_boundary.IsHosted:
            continue
        candidates = set(fc_boundaries).intersection(
            utils.get_boundaries_by_element_id(
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
        utils.append(host_element, "InnerBoundaries", fc_boundary)


def associate_corresponding_boundaries(doc=FreeCAD.ActiveDocument):
    # Associate CorrespondingBoundary
    for fc_boundary in get_elements_by_ifctype("IfcRelSpaceBoundary", doc):
        associate_corresponding_boundary(fc_boundary, doc)


def clean_corresponding_candidates(fc_boundary, doc):
    other_boundaries = utils.get_boundaries_by_element(
        fc_boundary.RelatedBuildingElement, doc
    )
    other_boundaries.remove(fc_boundary)
    return [
        b
        for b in other_boundaries
        if not b.CorrespondingBoundary or b.RelatingSpace != fc_boundary.RelatingSpace
    ]


def associate_corresponding_boundary(fc_boundary, doc):
    """Associate corresponding boundaries according to IFC definition.

    Reference to the other space boundary of the pair of two space boundaries on either side of a
    space separating thermal boundary element.
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
        center_of_mass = utils.get_outer_wire(fc_boundary).CenterOfMass
        min_lenght = 10000  # No element has 10 m thickness
        for boundary in other_boundaries:
            distance = center_of_mass.distanceToPoint(
                utils.get_outer_wire(boundary).CenterOfMass
            )
            if distance < min_lenght:
                min_lenght = distance
                corresponding_boundary = boundary
    try:
        fc_boundary.CorrespondingBoundary = corresponding_boundary
        corresponding_boundary.CorrespondingBoundary = fc_boundary
    except NameError:
        # Considering test above. Assume that it has been missclassified but log the issue.
        fc_boundary.InternalOrExternalBoundary = "EXTERNAL"
        logger.warning(f"Boundary {fc_boundary.GlobalId} from space {fc_boundary}")
        return


def get_or_create_group(name, doc=FreeCAD.ActiveDocument):
    """Get group by name or create one if not found"""
    group = doc.findObjects("App::DocumentObjectGroup", name)
    if group:
        return group[0]
    return doc.addObject("App::DocumentObjectGroup", name)


if __name__ == "__main__":
    pass
