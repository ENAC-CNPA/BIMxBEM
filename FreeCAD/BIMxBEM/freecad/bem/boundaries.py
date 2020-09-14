# coding: utf8
"""This module reads IfcRelSpaceBoundary from an IFC file and display them in FreeCAD

© All rights reserved.
ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Laboratory CNPA, 2019-2020

See the LICENSE.TXT file for more details.

Author : Cyril Waechter
"""
import io
import itertools
import logging
import os
from collections import namedtuple
from typing import NamedTuple, Generator, List, Iterable

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import ifcopenshell.util.unit

import FreeCAD
import FreeCADGui
import Part

from freecad.bem import materials
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
        bbox = self._element_shape_by_brep(ifc_entity).BoundBox
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

    def _element_shape_by_brep(self, ifc_entity) -> Part.Shape:
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
        clean_vectors(fc_verts)
        close_vectors(fc_verts)
        return Part.makePolygon(fc_verts)


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


def processing_sia_boundaries(doc=FreeCAD.ActiveDocument) -> None:
    """Create SIA specific boundaries cf. https://www.sia.ch/fr/services/sia-norm/"""
    for space in get_elements_by_ifctype("IfcSpace", doc):
        ensure_hosted_element_are(space)
        ensure_hosted_are_coplanar(space)
        join_over_splitted_boundaries(space, doc)
        handle_curtain_walls(space, doc)
        find_closest_edges(space)
        set_leso_type(space)
    create_sia_boundaries(doc)
    doc.recompute()


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
        inner_wire = get_outer_wire(boundary).scale(0.999)
        inner_wire = project_wire_to_plane(inner_wire, get_plane(boundary))
        append_inner_wire(boundary, inner_wire)
        append(boundary, "InnerBoundaries", fake_window)
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
    for project in get_elements_by_ifctype("IfcProject", doc):
        bem_xml.write_project(project)
    for space in get_elements_by_ifctype("IfcSpace", doc):
        bem_xml.write_space(space)
        for boundary in space.SecondLevel.Group:
            bem_xml.write_boundary(boundary)
    for building_element in get_by_class(doc, Element):
        bem_xml.write_building_elements(building_element)
    for material in get_by_class(
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
                join_coplanar_boundaries(coplanar_list, doc)
            except Part.OCCError:
                logger.warning(
                    f"Cannot join boundaries in space <{space.Id}> with key <{key}>"
                )


def get_vectors_from_shape(shape: Part.Shape):
    return [vx.Point for vx in shape.Vertexes]


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
        p0_1, p0_2 = get_vectors_from_shape(edge1)
        p1_1, p1_2 = get_vectors_from_shape(edge2)

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
        wire1 = get_outer_wire(boundary1)
        vectors1 = get_vectors_from_shape(wire1)
        wire2 = get_outer_wire(boundary2)
        vectors2 = get_vectors_from_shape(wire2)

        common_segment = find_common_segment(wire1, wire2)
        if not common_segment:
            return False
        ei1, ei2, opposite_dir = common_segment

        # join vectors1 and vectors2 at indexes
        new_points = vectors2[ei2 + 1 :] + vectors2[: ei2 + 1]
        if not opposite_dir:
            new_points.reverse()

        # Efficient way to insert elements at index : https://stackoverflow.com/questions/14895599/insert-an-element-at-specific-index-in-a-list-and-return-updated-list/48139870#48139870
        vectors1[ei1 + 1 : ei1 + 1] = new_points

        inner_wires = get_inner_wires(boundary1)[:]
        inner_wires.extend(get_inner_wires(boundary2))
        if not boundary1.IsHosted:
            for inner_boundary in boundary2.InnerBoundaries:
                append(boundary1, "InnerBoundaries", inner_boundary)
                inner_boundary.ParentBoundary = boundary1.Id

        # Update shape
        clean_vectors(vectors1)
        close_vectors(vectors1)
        wire1 = Part.makePolygon(vectors1)
        generate_boundary_compound(boundary1, wire1, inner_wires)
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

    wire1 = get_outer_wire(boundary1)
    vectors1 = get_vectors_from_shape(wire1)
    inner_wires = get_inner_wires(boundary1)[:]
    while True:
        common_segment = find_common_segment(wire1, wire1)
        if not common_segment:
            break

        ei1, ei2 = common_segment[0:2]

        # join vectors1 and vectors2 at indexes
        vectors_split1 = vectors1[: ei1 + 1] + vectors1[ei2 + 1 :]
        vectors_split2 = vectors1[ei1 + 1 : ei2 + 1]
        clean_vectors(vectors_split1)
        clean_vectors(vectors_split2)
        area1 = Part.Face(Part.makePolygon(vectors_split1 + [vectors_split1[0]])).Area
        area2 = Part.Face(Part.makePolygon(vectors_split2 + [vectors_split2[0]])).Area
        if area1 > area2:
            vectors1 = vectors_split1
            inner_vectors = vectors_split2
        else:
            vectors1 = vectors_split2
            inner_vectors = vectors_split1

        close_vectors(inner_vectors)
        inner_wires.extend([Part.makePolygon(inner_vectors)])

        # Update shape
        close_vectors(vectors1)
        wire1 = Part.makePolygon(vectors1)
        generate_boundary_compound(boundary1, wire1, inner_wires)
        RelSpaceBoundary.recompute_areas(boundary1)

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
                boundary.Id
                if isinstance(boundary.Proxy, Root)
                else boundary.SourceBoundary
            )
            logger.warning(
                f"Failure. An inner_wire did not cut face correctly in boundary <{b_id}>. OuterWire area = {Part.Face(outer_wire).Area / 10 ** 6}, InnerWire area = {Part.Face(inner_wire).Area / 10 ** 6}"
            )
            continue
        face = new_face
    boundary.Shape = Part.Compound([face, outer_wire, *inner_wires])


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


def ensure_hosted_are_coplanar(space):
    for boundary in space.SecondLevel.Group:
        for inner_boundary in boundary.InnerBoundaries:
            if is_coplanar(inner_boundary, boundary):
                continue
            project_boundary_onto_plane(inner_boundary, get_plane(boundary))
            outer_wire = get_outer_wire(boundary)
            inner_wires = get_inner_wires(boundary)
            inner_wire = get_outer_wire(inner_boundary)
            inner_wires.append(inner_wire)

            try:
                face = boundary.Shape.Faces[0]
                face = face.cut(Part.Face(inner_wire))
            except RuntimeError:
                pass

            boundary.Shape = Part.Compound([face, outer_wire, *inner_wires])


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


def project_wire_to_plane(wire, plane) -> Part.Wire:
    new_vectors = [
        v.Point.projectToPlane(plane.Position, plane.Axis) for v in wire.Vertexes
    ]
    close_vectors(new_vectors)
    return Part.makePolygon(new_vectors)


def is_typically_hosted(ifc_type: str):
    """Say if given ifc_type is typically hosted eg. windows, doors"""
    usually_hosted_types = ("IfcWindow", "IfcDoor", "IfcOpeningElement")
    for usual_type in usually_hosted_types:
        if ifc_type.startswith(usual_type):
            return True
        return False


class HostNotFound(LookupError):
    pass


def get_wires(boundary):
    return (s for s in boundary.Shape.SubShapes if isinstance(s, Part.Wire))


def get_outer_wire(boundary):
    return [s for s in boundary.Shape.SubShapes if isinstance(s, Part.Wire)][0]


def get_inner_wires(boundary):
    return [s for s in boundary.Shape.SubShapes if isinstance(s, Part.Wire)][1:]


def vectors_dir(p1, p2) -> FreeCAD.Vector:
    return (p2 - p1).normalize()


def are_3points_collinear(p1, p2, p3) -> bool:
    for v1, v2 in itertools.combinations((p1, p2, p3), 2):
        if v1.isEqual(v2, TOLERANCE):
            return True
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


def is_collinear_or_parallel(v0_0, v0_1, v1_0, v1_1) -> bool:
    return abs(direction(v0_0, v0_1).dot(direction(v1_0, v1_1))) > 0.9999


def direction(v0: FreeCAD.Vector, v1: FreeCAD.Vector) -> FreeCAD.Vector:
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
        distance = boundary1.Proxy.closest[ei1].distance
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
        if get_normal_at(boundary).z > 0:
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


def associate_corresponding_boundaries(doc=FreeCAD.ActiveDocument):
    # Associate CorrespondingBoundary
    for fc_boundary in get_elements_by_ifctype("IfcRelSpaceBoundary", doc):
        associate_corresponding_boundary(fc_boundary, doc)


def is_coplanar(shape_1, shape_2):
    """Intended for RelSpaceBoundary use only
    For some reason native Part.Shape.isCoplanar(Part.Shape) do not always work"""
    return get_plane(shape_1).toShape().isCoplanar(get_plane(shape_2).toShape())


def get_plane(fc_boundary) -> Part.Plane:
    """Intended for RelSpaceBoundary use only"""
    return Part.Plane(fc_boundary.Shape.Vertexes[0].Point, get_normal_at(fc_boundary))


def get_normal_at(fc_boundary, at_uv=(0, 0)) -> FreeCAD.Vector:
    return fc_boundary.Shape.Faces[0].normalAt(*at_uv)


def append(doc_object, fc_property, value):
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
    return (
        boundary
        for boundary in doc.Objects
        if getattr(getattr(boundary, "RelatedBuilding", None), "Id", None) == element_id
    )


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
        center_of_mass = get_outer_wire(fc_boundary).CenterOfMass
        min_lenght = 10000  # No element has 10 m thickness
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
        # TODO: Handle uncorrectly classified boundaries which have no corresponding boundary
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
    for fc_element in getattr(elements_group, "Group", elements_group):
        if getattr(fc_element, "GlobalId", None) == guid:
            return fc_element
        logger.warning(f"Unable to get element by {guid}")


def create_sia_boundaries(doc=FreeCAD.ActiveDocument):
    """Create boundaries necessary for SIA calculations"""
    project = next(get_elements_by_ifctype("IfcProject", doc))
    is_from_revit = project.ApplicationIdentifier == "Revit"
    is_from_archicad = project.ApplicationFullName == "ARCHICAD-64"
    for space in get_elements_by_ifctype("IfcSpace", doc):
        create_sia_ext_boundaries(space, is_from_revit)
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
            or not base_boundary.RelatedBuildingElement
        ):
            continue
        b1_plane = get_plane(boundary1)
        b1_normal = get_normal_at(boundary1)
        for b2_id, (ei1, ei2) in zip(
            base_boundary.ClosestBoundaries, enumerate(base_boundary.ClosestEdges)
        ):
            boundary2 = getattr(
                get_in_list_by_id(base_boundaries, b2_id), sia_type, None
            )
            if not boundary2:
                logger.warning(f"Cannot find corresponding boundary with id <{b2_id}>")
                lines.append(line_from_edge(get_outer_wire(base_boundary).Edges[ei1]))
                continue
            # Case 1 : boundaries are not parallel
            if not b1_normal.isEqual(get_normal_at(boundary2), TOLERANCE):
                plane_intersect = b1_plane.intersect(get_plane(boundary2))
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
            outer_wire = polygon_from_lines(lines, b1_plane)
        except NoIntersectionError:
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
    raise LookupError(f"No element with Id <{element_id}> found")


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
        normal = get_normal_at(boundary)
        if is_from_archicad:
            normal = normal.negative()

        bem_boundary = BEMBoundary.create(boundary, "SIA_Interior")
        sia_group_obj.addObject(bem_boundary)
        if not boundary.RelatedBuildingElement:
            continue

        ifc_type = boundary.RelatedBuildingElement.IfcType
        if is_from_revit and ifc_type.startswith("IfcWall"):
            thickness = boundary.RelatedBuildingElement.Thickness.Value
            lenght = thickness / 2
            bem_boundary.Placement.move(normal.negative() * lenght)


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


class NoIntersectionError(IndexError):
    pass


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
    if not ifc_product:
        return (1.0, 0.0, 0.0)
    for product, color in product_colors.items():
        # Not only test if IFC class is in dictionnary but it is a subclass
        if ifc_product.is_a(product):
            return color
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

    def __init__(self, obj: Part.Feature):
        self.Type = self.__class__.__name__  # pylint: disable=invalid-name
        obj.Proxy = self  # pylint: disable=invalid-name
        obj.addExtension("App::GroupExtensionPython", self)

    @classmethod
    def _init_properties(cls, obj: Part.Feature):
        ifc_attributes = "IFC Attributes"
        obj.addProperty("App::PropertyString", "IfcType", "IFC")
        obj.addProperty("App::PropertyInteger", "Id", ifc_attributes)
        obj.addProperty("App::PropertyString", "GlobalId", ifc_attributes)
        obj.addProperty("App::PropertyString", "IfcName", ifc_attributes)
        obj.addProperty("App::PropertyString", "Description", ifc_attributes)

    @classmethod
    def create(cls) -> Part.Feature:
        """Stantard FreeCAD FeaturePython Object creation method"""
        obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", cls.__name__)
        cls(obj)
        cls._init_properties(obj)

        if FreeCAD.GuiUp:
            obj.ViewObject.Proxy = ViewProviderRoot(obj.ViewObject)
        return obj

    @classmethod
    def create_from_ifc(cls, ifc_entity, ifc_importer: IfcImporter) -> Part.Feature:
        """As cls.create but providing an ifc source"""
        obj = cls.create()
        obj.Proxy.ifc_importer = ifc_importer
        cls.read_from_ifc(obj, ifc_entity)
        cls.set_label(obj)
        return obj

    @classmethod
    def read_from_ifc(cls, obj, ifc_entity):
        obj.Id = ifc_entity.id()
        obj.GlobalId = ifc_entity.GlobalId
        obj.IfcType = ifc_entity.is_a()
        obj.IfcName = ifc_entity.Name or ""
        obj.Description = ifc_entity.Description or ""

    @staticmethod
    def set_label(obj: Part.Feature):
        """Allow specific method for specific elements"""
        obj.Label = f"{obj.Id}_{obj.IfcName or obj.IfcType}"

    @staticmethod
    def read_pset_from_ifc(obj, ifc_entity, properties: Iterable[str]) -> None:
        psets = ifcopenshell.util.element.get_psets(ifc_entity)
        for pset in psets.values():
            for prop_name, prop in pset.items():
                if prop_name in properties:
                    setattr(obj, prop_name, getattr(prop, "wrappedValue", prop))


class ViewProviderRoot:
    def __init__(self, vobj):
        vobj.Proxy = self
        vobj.addExtension("Gui::ViewProviderGroupExtensionPython", self)


class RelSpaceBoundary(Root):
    """Wrapping IFC entity :
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcrelspaceboundary2ndlevel.htm"""

    def __init__(self, obj: Part.Feature):
        super().__init__(obj)
        obj.Proxy = self

    @classmethod
    def _init_properties(cls, obj: Part.Feature):
        super()._init_properties(obj)
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
            "Wall",
            "Flooring",
            "Window",
            "Door",
            "Opening",
            "Unknown",
        ]

    @classmethod
    def read_from_ifc(cls, obj: Part.Feature, ifc_entity):
        super().read_from_ifc(obj, ifc_entity)
        ifc_importer = obj.Proxy.ifc_importer
        element = get_related_element(ifc_entity, ifc_importer.doc)
        if element:
            obj.RelatedBuildingElement = element
            append(element, "ProvidesBoundaries", obj.Id)
        obj.RelatingSpace = ifc_entity.RelatingSpace.id()
        obj.InternalOrExternalBoundary = ifc_entity.InternalOrExternalBoundary
        obj.PhysicalOrVirtualBoundary = ifc_entity.PhysicalOrVirtualBoundary
        obj.Shape = ifc_importer.create_fc_shape(ifc_entity)
        obj.Area = obj.AreaWithHosted = obj.Shape.Area
        try:
            obj.IsHosted = bool(ifc_entity.RelatedBuildingElement.FillsVoids)
        except AttributeError:
            obj.IsHosted = False
        obj.LesoType = "Unknown"

        if FreeCAD.GuiUp:
            obj.ViewObject.Proxy = 0
            obj.ViewObject.ShapeColor = get_color(ifc_entity)

    def onChanged(self, obj, prop):  # pylint: disable=invalid-name
        if prop == "InnerBoundaries":
            self.recompute_area_with_hosted(obj)

    @classmethod
    def recompute_areas(cls, obj: Part.Feature):
        obj.Area = obj.Shape.Faces[0].Area
        cls.recompute_area_with_hosted(obj)

    @staticmethod
    def recompute_area_with_hosted(obj: Part.Feature):
        """Recompute area including inner boundaries"""
        area = obj.Area
        for boundary in obj.InnerBoundaries:
            area = area + boundary.Area
        obj.AreaWithHosted = area

    @classmethod
    def set_label(cls, obj):
        try:
            obj.Label = f"{obj.Id}_{obj.RelatedBuildingElement.IfcName}"
        except AttributeError:
            obj.Label = f"{obj.Id} VIRTUAL"
            if obj.PhysicalOrVirtualBoundary != "VIRTUAL":
                logger.warning(
                    f"{obj.Id} is not VIRTUAL and has no RelatedBuildingElement"
                )

    @staticmethod
    def get_wires(obj):
        return get_wires(obj)


class Element(Root):
    """Wrapping various IFC entity :
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/schema/ifcproductextension/lexical/ifcelement.htm
    """

    def __init__(self, obj):
        super().__init__(obj)
        self.Type = "IfcRelSpaceBoundary"
        obj.Proxy = self

    @classmethod
    def create_from_ifc(cls, ifc_entity, ifc_importer):
        """Stantard FreeCAD FeaturePython Object creation method"""
        obj = super().create_from_ifc(ifc_entity, ifc_importer)
        ifc_importer.material_creator.create(obj, ifc_entity)
        obj.Thickness = ifc_importer.guess_thickness(obj, ifc_entity)

        if FreeCAD.GuiUp:
            obj.ViewObject.Proxy = 0
        return obj

    @classmethod
    def _init_properties(cls, obj):
        super()._init_properties(obj)
        ifc_attributes = "IFC Attributes"
        bem_category = "BEM"
        obj.addProperty("App::PropertyLink", "Material", ifc_attributes)
        obj.addProperty("App::PropertyLinkList", "FillsVoids", ifc_attributes)
        obj.addProperty("App::PropertyLinkList", "HasOpenings", ifc_attributes)
        obj.addProperty(
            "App::PropertyIntegerList", "ProvidesBoundaries", ifc_attributes
        )
        obj.addProperty("App::PropertyFloat", "ThermalTransmittance", ifc_attributes)
        obj.addProperty("App::PropertyLinkList", "HostedElements", bem_category)
        obj.addProperty("App::PropertyInteger", "HostElement", bem_category)
        obj.addProperty("App::PropertyLength", "Thickness", bem_category)

    @classmethod
    def read_from_ifc(cls, obj, ifc_entity):
        super().read_from_ifc(obj, ifc_entity)
        obj.Label = f"{obj.Id}_{obj.IfcType}"

        super().read_pset_from_ifc(
            obj,
            ifc_entity,
            [
                "ThermalTransmittance",
            ],
        )


class BEMBoundary:
    def __init__(self, obj, boundary):
        self.Type = "BEMBoundary"  # pylint: disable=invalid-name
        obj.Proxy = self
        category_name = "BEM"
        obj.addProperty("App::PropertyInteger", "SourceBoundary", category_name)
        obj.SourceBoundary = boundary.Id
        obj.addProperty("App::PropertyArea", "Area", category_name)
        obj.addProperty("App::PropertyArea", "AreaWithHosted", category_name)
        obj.Shape = boundary.Shape.copy()
        self.set_label(obj, boundary)
        obj.Area = boundary.Area
        obj.AreaWithHosted = boundary.AreaWithHosted

    @staticmethod
    def create(boundary, geo_type):
        """Stantard FreeCAD FeaturePython Object creation method"""
        obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", "BEMBoundary")
        BEMBoundary(obj, boundary)
        setattr(boundary, geo_type, obj)
        if FreeCAD.GuiUp:
            # ViewProviderRelSpaceBoundary(obj.ViewObject)
            obj.ViewObject.Proxy = 0
            obj.ViewObject.ShapeColor = boundary.ViewObject.ShapeColor
        return obj

    @staticmethod
    def set_label(obj, source_boundary):
        obj.Label = source_boundary.Label

    @staticmethod
    def get_wires(obj):
        return get_wires(obj)


class Container(Root):
    """Representation of an IfcProject:
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcproject.htm"""

    def __init__(self, obj):
        super().__init__(obj)
        obj.Proxy = self

    @classmethod
    def create_from_ifc(cls, ifc_entity, ifc_importer: IfcImporter):
        obj = super().create_from_ifc(ifc_entity, ifc_importer)
        cls.set_label(obj)
        if FreeCAD.GuiUp:
            obj.ViewObject.DisplayMode = "Wireframe"
        return obj


class Project(Root):
    """Representation of an IfcProject:
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcproject.htm"""

    def __init__(self, obj):
        super().__init__(obj)

    @classmethod
    def create(cls):
        obj = super().create()
        if FreeCAD.GuiUp:
            obj.ViewObject.DisplayMode = "Wireframe"
        return obj

    @classmethod
    def _init_properties(cls, obj):
        super()._init_properties(obj)
        ifc_attributes = "IFC Attributes"
        obj.addProperty("App::PropertyString", "LongName", ifc_attributes)
        obj.addProperty("App::PropertyVector", "TrueNorth", ifc_attributes)
        obj.addProperty("App::PropertyVector", "WorldCoordinateSystem", ifc_attributes)

        owning_application = "OwningApplication"
        obj.addProperty(
            "App::PropertyString", "ApplicationIdentifier", owning_application
        )
        obj.addProperty("App::PropertyString", "ApplicationVersion", owning_application)
        obj.addProperty(
            "App::PropertyString", "ApplicationFullName", owning_application
        )

    @classmethod
    def read_from_ifc(cls, obj, ifc_entity):
        super().read_from_ifc(obj, ifc_entity)
        obj.LongName = ifc_entity.LongName or ""
        obj.TrueNorth = FreeCAD.Vector(
            *ifc_entity.RepresentationContexts[0].TrueNorth.DirectionRatios
        )
        obj.WorldCoordinateSystem = FreeCAD.Vector(
            ifc_entity.RepresentationContexts[
                0
            ].WorldCoordinateSystem.Location.Coordinates
        )

        owning_application = ifc_entity.OwnerHistory.OwningApplication
        obj.ApplicationIdentifier = owning_application.ApplicationIdentifier
        obj.ApplicationVersion = owning_application.Version
        obj.ApplicationFullName = owning_application.ApplicationFullName

    @classmethod
    def set_label(cls, obj):
        obj.Label = f"{obj.IfcName}_{obj.LongName}"


class Space(Root):
    """Representation of an IfcProject:
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcproject.htm"""

    def __init__(self, obj):
        super().__init__(obj)

    @classmethod
    def create(cls):
        obj = super().create()
        if FreeCAD.GuiUp:
            obj.ViewObject.DisplayMode = "Wireframe"
        return obj

    @classmethod
    def _init_properties(cls, obj):
        super()._init_properties(obj)
        ifc_attributes = "IFC Attributes"
        obj.addProperty("App::PropertyString", "LongName", ifc_attributes)
        category_name = "Boundaries"
        obj.addProperty("App::PropertyLink", "Boundaries", category_name)
        obj.addProperty("App::PropertyLink", "SecondLevel", category_name)
        obj.addProperty("App::PropertyLink", "SIA", category_name)
        obj.addProperty("App::PropertyLink", "SIA_Interiors", category_name)
        obj.addProperty("App::PropertyLink", "SIA_Exteriors", category_name)

    @classmethod
    def read_from_ifc(cls, obj, ifc_entity):
        super().read_from_ifc(obj, ifc_entity)
        # obj.Shape = self.ifc_importer.create_fc_shape(ifc_entity)
        obj.LongName = ifc_entity.LongName or ""
        space_full_name = f"{ifc_entity.Name} {ifc_entity.LongName}"
        obj.Label = space_full_name
        obj.Description = ifc_entity.Description or ""

    @classmethod
    def set_label(cls, obj):
        obj.Label = f"{obj.IfcName}_{obj.LongName}"


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
