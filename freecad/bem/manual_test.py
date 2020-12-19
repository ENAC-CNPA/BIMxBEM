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
        4: "OverSplitted_R20_2x3.ifc",
        5: "ExternalEarth_R20_IFC4.ifc",
        6: "3196 Aalseth Lane_R21_bem.ifc",
        7: "3196 Aalseth Lane - AC - IFC4 BIM-BEM - Entier.ifc",
        8: "0014_Vernier112D_ENE_ModèleÉnergétique_R21_1LocalParEtage.ifc",
        9: "0014_Vernier112D_ENE_ModèleÉnergétique_R21_1LocalParEtage_space[460].ifc",
        10: "Ersatzneubau Alphütte_1-1210_31_23.ifc",
    }
    IFC_PATH = os.path.join(TEST_FOLDER, TEST_FILES[3])
    DOC = FreeCAD.ActiveDocument
    WITH_GUI = True

    if DOC:  # Remote debugging
        import ptvsd

        # Allow other computers to attach to ptvsd at this IP address and port.
        ptvsd.enable_attach(address=("localhost", 5678), redirect_output=True)
        # Pause the program until a remote debugger is attached
        ptvsd.wait_for_attach()
        # breakpoint()

        boundaries.process_test_file(IFC_PATH, DOC)
    else:
        if WITH_GUI:
            FreeCADGui.showMainWindow()
            DOC = FreeCAD.newDocument()

            boundaries.process_test_file(IFC_PATH, DOC)
            FreeCADGui.exec_loop()
        else:
            xml_str = boundaries.generate_bem_xml_from_file(IFC_PATH)
