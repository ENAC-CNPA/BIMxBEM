# coding: utf8
"""This module write boundaries informations to an xml format for BEM software use"""

import xml.etree.ElementTree as ET

SCALE = 1000


class BEMxml:
    """Contains methods to write each kind of object to BEMxml"""

    def __init__(self):
        self.root = ET.Element("bimbem")
        self.tree = ET.ElementTree(self.root)
        self.projects = ET.SubElement(self.root, "Projects")
        self.spaces = ET.SubElement(self.root, "Spaces")
        self.boundaries = ET.SubElement(self.root, "Boundaries")
        self.building_elements = ET.SubElement(self.root, "BuildingElements")

    @staticmethod
    def write_root_attrib(xml_element, fc_object):
        ET.SubElement(xml_element, "Id").text = str(fc_object.Id)
        ET.SubElement(xml_element, "GlobalId").text = fc_object.GlobalId
        ET.SubElement(xml_element, "Name").text = fc_object.Name
        ET.SubElement(xml_element, "Description").text = fc_object.Description
        ET.SubElement(xml_element, "IfcType").text = fc_object.IfcType

    def write_project(self, fc_object):
        project = ET.SubElement(self.projects, "Project")
        self.write_root_attrib(project, fc_object)
        ET.SubElement(project, "LongName").text = fc_object.LongName
        north = ET.SubElement(project, "TrueNorth")
        ET.SubElement(north, "point", vector_to_dict(fc_object.TrueNorth))
        wcs = ET.SubElement(project, "WorldCoordinateSystem")
        ET.SubElement(wcs, "point", vector_to_dict(fc_object.WorldCoordinateSystem))
        sites = ET.SubElement(project, "Site")
        ET.SubElement(sites, "Site").text = ""

    def write_space(self, fc_object):
        space = ET.SubElement(self.spaces, "Space")
        self.write_root_attrib(space, fc_object)
        boundaries = ET.SubElement(space, "Boundaries")
        for boundary in fc_object.SecondLevel.Group:
            ET.SubElement(boundaries, "Boundary").text = str(boundary.Id)

    def write_boundary(self, fc_object):
        boundary = ET.SubElement(self.boundaries, "Boundary")
        self.write_root_attrib(boundary, fc_object)

        references = (
            "CorrespondingBoundary",
            "RelatedBuildingElement",
        )
        for name in references:
            self.append_id_element(boundary, fc_object, name)

        ET.SubElement(boundary, "ParentBoundary").text = (
            str(fc_object.ParentBoundary) if fc_object.ParentBoundary else ""
        )

        ET.SubElement(boundary, "RelatingSpace").text = (
            str(fc_object.RelatingSpace) if fc_object.RelatingSpace else ""
        )

        inner_boundaries = ET.SubElement(boundary, "InnerBoundaries")
        for fc_inner_b in fc_object.InnerBoundaries:
            ET.SubElement(inner_boundaries, "InnerBoundary").text = str(fc_inner_b.Id)

        self.write_shape(boundary, fc_object)

        is_hosted = fc_object.IsHosted
        ET.SubElement(boundary, "IsHosted").text = "true" if is_hosted else "false"

        if not is_hosted:
            for geo_type in ("SIA_Interior", "SIA_Exterior"):
                geo = ET.SubElement(boundary, geo_type)
                fc_geo = getattr(fc_object, geo_type)
                self.write_shape(geo, fc_geo)

    def write_building_elements(self, fc_object):
        building_element = ET.SubElement(self.building_elements, "BuildingElement")
        self.write_root_attrib(building_element, fc_object)
        ET.SubElement(building_element, "Thickness").text = str(
            fc_object.Thickness.Value / SCALE
        )
        boundaries = ET.SubElement(building_element, "ProvidesBoundaries")
        for element_id in fc_object.ProvidesBoundaries:
            ET.SubElement(boundaries, "Id").text = str(element_id)

    @staticmethod
    def write_shape(xml_element, fc_object):
        geom = ET.SubElement(xml_element, "geom")
        for wire in fc_object.Shape.Wires:
            polygon = ET.SubElement(geom, "Polygon")
            for vertex in wire.Vertexes:
                ET.SubElement(polygon, "point", vector_to_dict(vertex.Point))
        ET.SubElement(xml_element, "Area").text = fc_area_to_si_xml(fc_object.Area)
        ET.SubElement(xml_element, "AreaWithHosted").text = fc_area_to_si_xml(
            fc_object.AreaWithHosted
        )

    @staticmethod
    def append_id_element(xml_element, fc_object, name):
        value = getattr(fc_object, name)
        ET.SubElement(xml_element, name).text = str(value.Id) if value else ""

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


def fc_area_to_si_xml(fc_area):
    return str(fc_area.Value / SCALE ** 2)


if __name__ == "__main__":
    OUTPUT = BEMxml()
    OUTPUT.write_project(None)

    OUTPUT_FILE = "output.xml"
    OUTPUT.tree.write(OUTPUT_FILE, encoding="UTF-8", xml_declaration=True)
