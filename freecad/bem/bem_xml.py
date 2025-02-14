# coding: utf8
"""This module write boundaries informations to an xml format for BEM software use

© All rights reserved.
ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Laboratory CNPA, 2019-2020

See the LICENSE.TXT file for more details.

Author : Cyril Waechter
"""

import xml.etree.ElementTree as ET
import typing
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util

import FreeCAD

if typing.TYPE_CHECKING:
    from freecad.bem.entities import *

SCALE = 1000


class BEMxml:
    """Contains methods to write each kind of object to BEMxml"""

    def __init__(self, model=None):
        self.root = ET.Element("bimbem")
        self.tree = ET.ElementTree(self.root)
        self.projects = ET.SubElement(self.root, "Projects")
        self.zones = ET.SubElement(self.root, "Zones")
        self.spaces = ET.SubElement(self.root, "Spaces")
        self.boundaries = ET.SubElement(self.root, "Boundaries")
        self.building_element_types = ET.SubElement(self.root, "BuildingElementTypes")
        self.building_elements = ET.SubElement(self.root, "BuildingElements")
        self.materials = ET.SubElement(self.root, "Materials")
        self.shades = ET.SubElement(self.root, "Shades")
        self.sites = None
        self.buildings = None
        self.storeys = None
        self.model = model

    @staticmethod
    def write_id(xml_element, model_element):
        try:
            ET.SubElement(xml_element, "Id").text = str(model_element.Id)
        except AttributeError:
            ET.SubElement(xml_element, "Id").text = str(model_element.id())

    @staticmethod
    def write_name(xml_element, model_element):
        try:
            ET.SubElement(xml_element, "Name").text = model_element.IfcName
        except AttributeError:
            ET.SubElement(xml_element, "Name").text = model_element.Name

    @staticmethod
    def write_description(xml_element, model_element):
        ET.SubElement(xml_element, "Description").text = model_element.Description

    def write_root_attrib(self, xml_element, model_element):
        self.write_id(xml_element, model_element)
        ET.SubElement(xml_element, "GlobalId").text = model_element.GlobalId
        self.write_name(xml_element, model_element)
        self.write_description(xml_element, model_element)
        try:
            ET.SubElement(xml_element, "IfcType").text = model_element.IfcType
        except AttributeError:
            ET.SubElement(xml_element, "IfcType").text = model_element.is_a()

    @staticmethod
    def write_attributes(parent, fc_object, attributes):
        for attrib in attributes:
            value = getattr(fc_object, attrib)
            if isinstance(value, FreeCAD.Units.Quantity):
                if value.Unit.Type == "Length":
                    value = value.Value / SCALE
                else:
                    value = value.Value
            ET.SubElement(parent, attrib).text = str(value or "")

    def write_project(self, fc_object: "ProjectFeature") -> None:
        project = ET.SubElement(self.projects, "Project")
        self.write_root_attrib(project, fc_object)
        ET.SubElement(project, "LongName").text = fc_object.LongName
        north = ET.SubElement(project, "TrueNorth")
        ET.SubElement(north, "point", unitary_vector_to_dict(fc_object.TrueNorth))
        wcs = ET.SubElement(project, "WorldCoordinateSystem")
        ET.SubElement(wcs, "point", vector_to_dict(fc_object.WorldCoordinateSystem))
        self.sites = ET.SubElement(project, "Sites")
        for site in fc_object.Group:
            self.write_site(site)

    def write_zone(self, ifc_zone) -> None:
        zone = ET.SubElement(self.zones, "Zone")
        self.write_root_attrib(zone, ifc_zone)
        ET.SubElement(zone, "LongName").text = getattr(ifc_zone, "LongName", "")
        spaces = ET.SubElement(zone, "Spaces")
        for space in (s for s in ifc_zone.IsGroupedBy[0].RelatedObjects if s.BoundedBy):
            ET.SubElement(spaces, "Space").text = str(space.id())

    def write_site(self, fc_object: "ContainerFeature") -> None:
        site = ET.SubElement(self.sites, "Site")
        self.write_root_attrib(site, fc_object)
        self.buildings = ET.SubElement(site, "Buildings")
        for building in fc_object.Group:
            self.write_building(building)

    def write_building(self, fc_object: "ContainerFeature") -> None:
        site = ET.SubElement(self.buildings, "Building")
        self.write_root_attrib(site, fc_object)
        self.storeys = ET.SubElement(site, "Storeys")
        for storey in fc_object.Group:
            self.write_storey(storey)

    def write_storey(self, fc_object: "ContainerFeature") -> None:
        storey = ET.SubElement(self.storeys, "Storey")
        self.write_root_attrib(storey, fc_object)
        spaces = ET.SubElement(storey, "Spaces")
        for space in fc_object.Group:
            ET.SubElement(spaces, "Space").text = str(space.Id)

    def write_space(self, fc_object: "SpaceFeature") -> None:
        space = ET.SubElement(self.spaces, "Space")
        self.write_root_attrib(space, fc_object)
        self.write_attributes(space, fc_object, ("LongName",))
        boundaries = ET.SubElement(space, "Boundaries")
        for boundary in fc_object.SecondLevel.Group:
            ET.SubElement(boundaries, "Boundary").text = str(boundary.Id)

    def write_boundary(self, fc_object: "RelSpaceBoundaryFeature") -> None:
        boundary = ET.SubElement(self.boundaries, "Boundary")
        self.write_root_attrib(boundary, fc_object)
        ET.SubElement(boundary, "Normal", unitary_vector_to_dict(fc_object.Normal))

        id_references = (
            "CorrespondingBoundary",
            "RelatedBuildingElement",
        )
        for name in id_references:
            self.append_id_element(boundary, fc_object, name)

        text_references = (
            "InternalOrExternalBoundary",
            "PhysicalOrVirtualBoundary",
            "LesoType",
        )

        for name in text_references:
            self.append_text_element(boundary, fc_object, name)

        ET.SubElement(boundary, "ParentBoundary").text = (
            str(fc_object.ParentBoundary.Id) if fc_object.ParentBoundary else ""
        )

        ET.SubElement(boundary, "RelatingSpace").text = (
            str(fc_object.RelatingSpace.Id) if fc_object.RelatingSpace else ""
        )

        inner_boundaries = ET.SubElement(boundary, "InnerBoundaries")
        for fc_inner_b in fc_object.InnerBoundaries:
            ET.SubElement(inner_boundaries, "InnerBoundary").text = str(fc_inner_b.Id)

        self.write_fc_polygon(boundary, fc_object)
        self.write_attributes(boundary, fc_object, ("UndergroundDepth",))

        is_hosted = fc_object.IsHosted
        ET.SubElement(boundary, "IsHosted").text = "true" if is_hosted else "false"

        value = fc_object.InternalToExternal
        param = ET.SubElement(boundary, "InternalToExternal")
        if value == 1:
            param.text = "true"
        elif value == -1:
            param.text = "false"
        else:
            param.text = "null"

        if not is_hosted and fc_object.PhysicalOrVirtualBoundary != "VIRTUAL":
            for geo_type in ("SIA_Interior", "SIA_Exterior"):
                geo = ET.SubElement(boundary, geo_type)
                fc_geo = getattr(fc_object, geo_type)
                self.write_fc_polygon(geo, fc_geo)

    def write_building_element_types(self, fc_object):
        building_element_types = ET.SubElement(self.building_element_types, "BuildingElementType")
        self.write_root_attrib(building_element_types, fc_object)
        ET.SubElement(building_element_types, "Thickness").text = str(fc_object.Thickness.Value / SCALE)
        ET.SubElement(building_element_types, "ThermalTransmittance").text = str(fc_object.ThermalTransmittance or "")
        occurences = ET.SubElement(building_element_types, "ApplicableOccurrence")
        for element in fc_object.ApplicableOccurrence:
            ET.SubElement(occurences, "Id").text = str(element.Id)
        if fc_object.Material:
            ET.SubElement(building_element_types, "Material").text = str(fc_object.Material.Id or "")

    def write_building_elements(self, fc_object):
        building_element = ET.SubElement(self.building_elements, "BuildingElement")
        self.write_root_attrib(building_element, fc_object)
        ET.SubElement(building_element, "IsTypedBy").text = str(getattr(fc_object.IsTypedBy, "Id", ""))
        ET.SubElement(building_element, "Thickness").text = str(fc_object.Thickness.Value / SCALE)
        ET.SubElement(building_element, "ThermalTransmittance").text = str(fc_object.ThermalTransmittance or "")
        boundaries = ET.SubElement(building_element, "ProvidesBoundaries")
        for element in fc_object.ProvidesBoundaries:
            ET.SubElement(boundaries, "Id").text = str(element.Id)
        if fc_object.Material:
            ET.SubElement(building_element, "Material").text = str(fc_object.Material.Id or "")

    def write_class_attrib(self, xml_element, fc_object):
        self.write_attributes(xml_element, fc_object, fc_object.Proxy.attributes)

    @staticmethod
    def write_psets(xml_element, fc_object):
        for props in fc_object.Proxy.psets_dict.values():
            for prop in props:
                ET.SubElement(xml_element, prop).text = str(getattr(fc_object, prop))

    def write_material(self, fc_object):
        proxy = fc_object.Proxy
        material = ET.SubElement(self.materials, type(proxy).__name__)
        self.write_id(material, fc_object)
        self.write_name(material, fc_object)
        self.write_description(material, fc_object)
        self.write_class_attrib(material, fc_object)
        self.write_psets(material, fc_object)
        if not proxy.part_name:
            return
        parts = ET.SubElement(material, proxy.parts_name)
        for values in zip(*[getattr(fc_object, prop) for prop in proxy.part_props]):
            part = ET.SubElement(parts, proxy.part_name)
            for i, value, attrib in zip(range(len(values)), values, proxy.part_attribs):
                if i == 0:
                    ET.SubElement(part, attrib).text = str(value.Id)
                else:
                    ET.SubElement(part, attrib).text = str(value)

    def write_shade(self, model_element):
        shade = ET.SubElement(self.shades, "Shade")
        self.write_root_attrib(shade, model_element)
        self.write_polygon(shade, model_element)

    def write_polygon(self, xml_element, boundary):
        surface = boundary.ConnectionGeometry.SurfaceOnRelatingElement
        settings = ifcopenshell.geom.settings()
        shape = ifcopenshell.geom.create_shape(settings, surface)
        geom = ET.SubElement(xml_element, "geom")
        polygon = ET.SubElement(geom, "Polygon")
        for v in ifcopenshell.util.shape.get_vertices(shape):
            ET.SubElement(polygon, "point", array_to_vector_dict(v))

    @staticmethod
    def write_fc_polygon(xml_element, fc_object):
        geom = ET.SubElement(xml_element, "geom")
        try:
            wires = fc_object.Proxy.get_wires(fc_object)
        except AttributeError:
            wires = ()
        for wire in wires:
            polygon = ET.SubElement(geom, "Polygon")
            for vertex in wire.Vertexes:
                ET.SubElement(polygon, "point", vector_to_dict(vertex.Point))
        ET.SubElement(xml_element, "Area").text = fc_area_to_si_xml(fc_object.Area)
        ET.SubElement(xml_element, "AreaWithHosted").text = fc_area_to_si_xml(fc_object.AreaWithHosted)

    @staticmethod
    def append_id_element(xml_element, fc_object, name):
        value = getattr(fc_object, name)
        ET.SubElement(xml_element, name).text = str(value.Id) if value else ""

    @staticmethod
    def append_text_element(xml_element, fc_object, name):
        ET.SubElement(xml_element, name).text = getattr(fc_object, name)

    def write_to_file(self, full_path):
        self.tree.write(full_path, encoding="UTF-8", xml_declaration=True)

    def tostring(self):
        # Return a bytes
        # return ET.tostring(self.root, encoding="utf8", method="xml")
        # Return a string
        return ET.tostring(self.root, encoding="unicode")


def vector_to_dict(vector):
    """Convert a FreeCAD.Vector into a dict to write it as attribute in xml"""
    return {key: str(getattr(vector, key) / SCALE) for key in ("x", "y", "z")}


def array_to_vector_dict(array):
    """Convert a FreeCAD.Vector into a dict to write it as attribute in xml"""
    return {key: str(value) for key, value in zip(("x", "y", "z"), array.tolist())}


def unitary_vector_to_dict(vector):
    return {key: str(getattr(vector, key)) for key in ("x", "y", "z")}


def fc_area_to_si_xml(fc_area):
    return str(fc_area.getValueAs("m^2"))


if __name__ == "__main__":
    OUTPUT = BEMxml()
    OUTPUT.write_project(None)

    OUTPUT_FILE = "output.xml"
    OUTPUT.tree.write(OUTPUT_FILE, encoding="UTF-8", xml_declaration=True)
