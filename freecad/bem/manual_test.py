
# coding: utf8
"""This module allow to use BIMxBEM on various test files for analysis

© All rights reserved.
ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Laboratory CNPA, 2019-2020

See the LICENSE.TXT file for more details.

Author : Cyril Waechter
"""
import os
import FreeCAD
import FreeCADGui
from freecad.bem import boundaries

if __name__ == "__main__":
    if os.name == "nt":
        TEST_FOLDER = r"C:\git\BIMxBEM\IfcTestFiles"
    else:
        TEST_FOLDER = "/home/cyril/git/BIMxBEM/IfcTestFiles/"
    TEST_FILES = {
        0: "Triangle_A24_IFC4.ifc",
        1: "Triangle_2x3_R19.ifc",
        2: "2Storey_2x3_A22.ifc",
        3: "2Storey_2x3_R19.ifc",
        4: "0014_Vernier112D_ENE_ModèleÉnergétique_R20.ifc",
        5: "3196 Aalseth Lane_R21_bem_space13688.ifc",
        7: "OverSplitted_R20_2x3.ifc",
        8: "3196 Aalseth Lane_R21_bem.ifc",
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
        28: "test 02-02 mur matériau simple.ifc",
        29: "3196 Aalseth Lane_R19_bem.ifc",
        30: "Maison Privée.ifc",
    }
    IFC_PATH = os.path.join(TEST_FOLDER, TEST_FILES[8])
    DOC = FreeCAD.ActiveDocument

    if DOC:  # Remote debugging
        import ptvsd

        # Allow other computers to attach to ptvsd at this IP address and port.
        ptvsd.enable_attach(address=("localhost", 5678), redirect_output=True)
        # Pause the program until a remote debugger is attached
        ptvsd.wait_for_attach()
        # breakpoint()

        boundaries.process_test_file(IFC_PATH, DOC)
    else:
        FreeCADGui.showMainWindow()
        DOC = FreeCAD.newDocument()

        boundaries.process_test_file(IFC_PATH, DOC)
        # xml_str = generate_bem_xml_from_file(IFC_PATH)

        FreeCADGui.exec_loop()