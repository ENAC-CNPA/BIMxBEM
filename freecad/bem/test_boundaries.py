# coding: utf8
"""This module test generation of IfcRelSpaceBoundary from an IFC file and display them in FreeCAD

© All rights reserved.
ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Laboratory CNPA, 2019-2020

See the LICENSE.TXT file for more details.

Author : Cyril Waechter
"""
import os

import pytest
from pytest import approx

import FreeCAD
import FreeCADGui

from freecad.bem import utils
from freecad.bem.boundaries import (
    generate_bem_xml_from_file,
    process_test_file,
)


TEST_FILES = [
    "Triangle_A24_IFC4.ifc",
    "Triangle_2x3_R19.ifc",
    "2Storey_2x3_A22.ifc",
    "2Storey_2x3_R19.ifc",
    "OverSplitted_R20_2x3.ifc",
    # "0014_Vernier112D_ENE_ModèleÉnergétique_R20.ifc",
    # "Investigation_test_R19.ifc",
    "ExternalEarth_R20_2x3.ifc",
    "ExternalEarth_R20_IFC4.ifc",
    # "Ersatzneubau Alphütte_1-1210_31_23.ifc",
    # "GRAPHISOFT_ARCHICAD_Sample_Project_Hillside_House_v1.ifczip",
    # "GRAPHISOFT_ARCHICAD_Sample_Project_S_Office_v1.ifczip",
    # "Cas1_EXPORT_REVIT_IFC2x3 (EDITED)_Space_Boundaries.ifc",
    # "Cas1_EXPORT_REVIT_IFC4DTV (EDITED)_Space_Boundaries.ifc",
    # "Cas1_EXPORT_REVIT_IFC4RV (EDITED)_Space_Boundaries.ifc",
    # "Cas1_EXPORT_REVIT_IFC4RV (EDITED)_Space_Boundaries_RECREATED.ifc",
    # "Cas2_EXPORT_REVIT_IFC4RV (EDITED)_Space_Boudaries.ifc",
    # "Cas2_EXPORT_REVIT_IFC4DTV (EDITED)_Space_Boundaries_RECREATED.ifc",
    # "Cas2_EXPORT_REVIT_IFC4DTV (EDITED)_Space_Boundaries.ifc",
    # "Cas2_EXPORT_REVIT_IFC2x3 (EDITED)_Space_Boundaries.ifc",
    # "Temoin.ifc",
]


@pytest.mark.parametrize("ifc_path", TEST_FILES)
def test_model_import_do_not_crash(ifc_path):
    ifc_path = os.path.join(os.getcwd(), "IfcTestFiles", ifc_path)
    assert bool(generate_bem_xml_from_file(ifc_path).xml)


COLORS = (
    ("IfcWall", (0.7, 0.3, 0.0, 0.0), "1gbc2T7D95owjIQ62vLUpi"),
    ("IfcWindow", (0.0, 0.7, 1.0, 0.0), "3WWI_X3UT8sBwwvwPJt8VH"),
    ("IfcSlab", (0.7, 0.7, 0.5, 0.0), "3ifhrLAVv9cBu73LKAQG8s"),
    ("IfcRoof", (0.0, 0.3, 0.0, 0.0), "3e25P8nWn4EhyPjVq9fYLx"),
    ("IfcDoor", (1.0, 1.0, 1.0, 0.0), "09R2N2LjP0FR0xkSyoPdDs"),
)


class TestTriangleDoc:
    @classmethod
    def setup_class(cls):
        ifc_path = os.path.join(os.getcwd(), "IfcTestFiles", "Triangle_2x3_R19.ifc")
        FreeCADGui.showMainWindow()
        doc = FreeCAD.newDocument()
        cls.ifc_importer = process_test_file(ifc_path, doc)

    @pytest.mark.parametrize(("ifc_type", "color", "global_id"), COLORS)
    def test_color(self, ifc_type, color, global_id):
        element = utils.get_element_by_guid(global_id, self.ifc_importer.doc.Objects)
        assert element.ViewObject.ShapeColor == approx(color)
