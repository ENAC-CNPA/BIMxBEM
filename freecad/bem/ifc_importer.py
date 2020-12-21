# coding: utf8
"""This module reads IfcRelSpaceBoundary from an IFC file and display them in FreeCAD

© All rights reserved.
ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Laboratory CNPA, 2019-2020

See the LICENSE.TXT file for more details.

Author : Cyril Waechter
"""
from typing import NamedTuple, Generator
import os
import zipfile

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import ifcopenshell.util.unit

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
        self.ifc_file = self.open(ifc_path)
        self.ifc_scale = get_unit_conversion_factor(self.ifc_file, "LENGTHUNIT")
        self.fc_scale = FreeCAD.Units.Metre.Value
        self.element_types = dict()
        self.material_creator = materials.MaterialCreator(self)
        self.xml: str = ""
        self.log: str = ""

    @staticmethod
    def open(ifc_path: str) -> ifcopenshell.file:
        ext = os.path.splitext(ifc_path)[1].lower()
        if ext == ".ifc":
            return ifcopenshell.open(ifc_path)
        if ext == ".ifcxml":
            # TODO: How to do this as ifcopenshell.ifcopenshell_wrapper has no parse_ifcxml ?
            raise NotImplementedError("No support for .ifcXML yet")
        if ext in (".ifczip", ".zip"):
            try:  # python 3.8+
                zip_path = zipfile.Path(ifc_path)
                for member in zip_path.iterdir():
                    zipped_ext = os.path.splitext(member.name)[1].lower()
                    if zipped_ext == ".ifc":
                        return ifcopenshell.file.from_string(member.read_text())
                    if zipped_ext == ".ifcxml":
                        raise NotImplementedError("No support for .ifcXML yet")
            except AttributeError as python36_zip_error:  # python 3.6
                with zipfile.ZipFile(ifc_path) as zip_file:
                    for member in zip_file.namelist():
                        zipped_ext = os.path.splitext(member)[1].lower()
                        if zipped_ext == ".ifc":
                            with zip_file.open(member) as ifc_file:
                                return ifcopenshell.file.from_string(
                                    ifc_file.read().decode()
                                )
                        if zipped_ext == ".ifcxml":
                            raise NotImplementedError(
                                "No support for .ifcXML yet"
                            ) from python36_zip_error
        raise NotImplementedError(
            """Supported files :
    - unzipped : *.ifc | *.ifcXML
    - zipped : *.ifczip | *.zip containing un unzipped type"""
        )

    def generate_rel_space_boundaries(self):
        """Display IfcRelSpaceBoundaries from selected IFC file into FreeCAD documennt"""
        ifc_file = self.ifc_file
        doc = self.doc

        # Generate elements (Door, Window, Wall, Slab etc…) without their geometry
        Progress.set(1, "IfcImport_Elements", "")
        elements_group = get_or_create_group("Elements", doc)
        ifc_elements = ifc_file.by_type("IfcElement")
        for ifc_entity in ifc_elements:
            elements_group.addObject(Element.create_from_ifc(ifc_entity, self))
        element_types_group = get_or_create_group("ElementTypes", doc)
        for element_type in utils.get_by_class(doc, ElementType):
            element_types_group.addObject(element_type)
        materials_group = get_or_create_group("Materials", doc)
        for material in get_materials(doc):
            materials_group.addObject(material)
        # Generate projects structure and boundaries
        Progress.set(5, "IfcImport_StructureAndBoundaries", "")
        for ifc_project in ifc_file.by_type("IfcProject"):
            project = Project.create_from_ifc(ifc_project, self)
            self.generate_containers(ifc_project, project)

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
        bbox = self.element_local_shape_by_brep(ifc_entity).BoundBox
        # Returning bbox thickness for windows or doors is not insteresting
        # as it does not return frame thickness.
        if self.is_wall_like(obj.IfcType):
            return min(bbox.YLength, bbox.XLength)
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
                fc_boundary.RelatingSpace = fc_space
                second_levels.addObject(fc_boundary)
                fc_boundary.Placement = space_placement
            except utils.ShapeCreationError:
                logger.warning(
                    f"Failed to create fc_shape for RelSpaceBoundary <{ifc_boundary.id()}> even with fallback methode _part_by_mesh. IfcOpenShell bug ?"
                )
            except utils.IsTooSmall:
                logger.warning(
                    f"Boundary <{ifc_boundary.id()}> shape is too small and has been ignored"
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

        v_1 = FreeCAD.Vector(
            getattr(position.RefDirection, "DirectionRatios", (1, 0, 0))
        )
        v_3 = FreeCAD.Vector(getattr(position.Axis, "DirectionRatios", (0, 0, 1)))
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

    def get_global_placement(self, obj_placement) -> FreeCAD.Matrix:
        if not obj_placement:
            return FreeCAD.Matrix()
        if not obj_placement.PlacementRelTo:
            parent = FreeCAD.Matrix()
        else:
            parent = self.get_global_placement(obj_placement.PlacementRelTo)
        return parent.multiply(self.get_matrix(obj_placement.RelativePlacement))

    def get_global_y_axis(self, ifc_entity):
        global_placement = self.get_global_placement(ifc_entity)
        return FreeCAD.Vector(global_placement.A[1:12:4])

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
            except (RuntimeError, utils.ShapeCreationError):
                print(f"Failed to generate mesh from {ifc_boundary}")
                try:
                    return self._part_by_mesh(
                        ifc_boundary.ConnectionGeometry.SurfaceOnRelatingElement
                    )
                except RuntimeError:
                    raise utils.ShapeCreationError

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

    def element_local_shape_by_brep(self, ifc_entity) -> Part.Shape:
        """ Create a Element Shape from brep generated by ifcopenshell from ifc geometry"""
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_BREP_DATA, True)
        settings.set(settings.USE_WORLD_COORDS, False)
        ifc_shape = ifcopenshell.geom.create_shape(settings, ifc_entity)
        fc_shape = Part.Shape()
        fc_shape.importBrepFromString(ifc_shape.geometry.brep_data)
        fc_shape.scale(self.fc_scale)
        return fc_shape

    def space_shape_by_brep(self, ifc_entity) -> Part.Shape:
        """ Create a Space Shape from brep generated by ifcopenshell from ifc geometry"""
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_BREP_DATA, True)
        settings.set(settings.USE_WORLD_COORDS, True)
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
        if len(fc_verts) < 3:
            raise utils.ShapeCreationError
        utils.close_vectors(fc_verts)
        return Part.makePolygon(fc_verts)

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


def associate_host_element(ifc_file, elements_group):
    # Associate Host / Hosted elements
    ifc_elements = (e for e in ifc_file.by_type("IfcElement") if e.ProvidesBoundaries)
    for ifc_entity in ifc_elements:
        if ifc_entity.FillsVoids:
            try:
                host = utils.get_element_by_guid(
                    utils.get_host_guid(ifc_entity), elements_group
                )
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
        if not fc_boundary.IsHosted:
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

        fc_boundary.ParentBoundary = host
        utils.append(host, "InnerBoundaries", fc_boundary)

    # Remove invalid boundary and corresponding inner wire
    updated_boundaries = fc_boundaries[:]
    for boundary in to_delete:
        remove_invalid_inner_wire(boundary, updated_boundaries)
        updated_boundaries.remove(boundary)
        doc.removeObject(boundary.Name)


def associate_corresponding_boundaries(doc=FreeCAD.ActiveDocument):
    # Associate CorrespondingBoundary
    for fc_boundary in get_elements_by_ifctype("IfcRelSpaceBoundary", doc):
        associate_corresponding_boundary(fc_boundary, doc)


def cleaned_corresponding_candidates(boundary1):
    candidates = []
    for boundary2 in getattr(
        boundary1.RelatedBuildingElement, "ProvidesBoundaries", ()
    ):
        if boundary2.CorrespondingBoundary:
            continue
        if boundary2.InternalOrExternalBoundary != "INTERNAL":
            continue
        if boundary1.RelatingSpace is boundary2.RelatingSpace:
            continue
        if not abs(boundary1.Area.Value - boundary2.Area.Value) < TOLERANCE:
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
        distance = center_of_mass.distanceToPoint(
            utils.get_outer_wire(candidate).CenterOfMass
        )
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
    if (
        boundary.InternalOrExternalBoundary != "INTERNAL"
        or boundary.CorrespondingBoundary
    ):
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
