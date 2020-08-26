# coding: utf8
"""This module test generation of IfcRelSpaceBoundary from an IFC file and display them in FreeCAD

© All rights reserved.
ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Laboratory CNPA, 2019-2020

See the LICENSE.TXT file for more details.

Author : Cyril Waechter
"""
import pytest
import os
from freecad.bem.boundaries import generate_bem_xml_from_file


TEST_FILES = [
        "Triangle_2x3_A23.ifc",
        "Triangle_2x3_R19.ifc",
        "2Storey_2x3_A22.ifc",
        "2Storey_2x3_R19.ifc",
        "OverSplitted_R20_2x3.ifc",
        # "0014_Vernier112D_ENE_ModèleÉnergétique_R20.ifc",
        # "Investigation_test_R19.ifc",
        # "ExternalEarth_R20_2x3.ifc",
        # "ExternalEarth_R20_IFC4.ifc",
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
