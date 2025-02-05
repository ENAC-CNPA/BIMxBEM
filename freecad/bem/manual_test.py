# coding: utf8
"""This module allow to use BIMxBEM on various test files for analysis

© All rights reserved.
ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Laboratory CNPA, 2019-2020

See the LICENSE.TXT file for more details.

Author : Cyril Waechter
"""
import os
from pathlib import Path
import FreeCAD
import FreeCADGui
from freecad.bem import boundaries

if __name__ == "__main__":
    FOLDERS = (Path(r"TestFiles\IfcRelSpaceBoundary2ndLevel"), 
               Path(r"TestFiles\Private"))
    TEST_FILES = {
        0: "Triangle_A24_IFC4.ifc",
        1: "Triangle_2x3_R19.ifc",
        2: "2Storey_2x3_A22.ifc",
        3: "2Storey_2x3_R19.ifc",
        4: "OverSplitted_R20_2x3.ifc",
        5: "ExternalEarth_R20_IFC4.ifc",
        6: "3196 Aalseth Lane_R21_bem.ifc",
        7: "3196 Aalseth Lane - AC - IFC4 BIM-BEM - Entier.ifc",
    for folder in FOLDERS:
        ifc_path = folder / TEST_FILES[8]
        if ifc_path.exists():
            break
    DOC = FreeCAD.ActiveDocument
    WITH_GUI = True

    if DOC:  # Remote debugging
        import ptvsd

        # Allow other computers to attach to ptvsd at this IP address and port.
        ptvsd.enable_attach(address=("localhost", 5678), redirect_output=True)
        # Pause the program until a remote debugger is attached
        ptvsd.wait_for_attach()
        # breakpoint()

        boundaries.process_test_file(ifc_path, DOC)
    else:
        if WITH_GUI:
            FreeCADGui.showMainWindow()
            DOC = FreeCAD.newDocument()

            boundaries.process_test_file(ifc_path, DOC)
            FreeCADGui.exec_loop()
        else:
            DOC = FreeCAD.newDocument()
            boundaries.process_test_file(ifc_path, DOC)
