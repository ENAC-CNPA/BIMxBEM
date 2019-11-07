import os

import FreeCAD

from freecad.bem import boundaries


class ImportRelSpaceBoundary:
    def IsActive(self):
        return bool(FreeCAD.ActiveDocument)

    def GetResources(self):
        return {
            "Pixmap": "icon.svg",
            "MenuText": "Import",
            "ToolTip": "Import IfcRelSpaceBoundary for selected IFC file",
        }

    def Activated(self):
        if os.name == "nt":
            test_folder = r"C:\git\BIMxBEM\IfcTestFiles"
        else:
            test_folder = "/home/cyril/git/BIMxBEM/IfcTestFiles/"
        test_files = [
            "Triangle_2x3_A22.ifc",
            "Triangle_2x3_R19.ifc",
            "2Storey_2x3_A22.ifc",
            "2Storey_2x3_R19.ifc",
            "0014_Vernier112D_ENE_ModèleÉnergétique_R20.ifc",
            "Investigation_test_R19.ifc",
        ]
        ifc_path = os.path.join(test_folder, test_files[2])
        boundaries.generate_ifc_rel_space_boundaries(
            ifc_path, doc=FreeCAD.ActiveDocument
        )
        return


class GenerateBemBoundaries:
    def IsActive(self):
        return bool(FreeCAD.ActiveDocument)

    def GetResources(self):
        return {
            "Pixmap": "icon.svg",
            "MenuText": "Generate SIA boundaries",
            "ToolTip": "Generate SIA specific BEM boundaries",
        }

    def Activated(self):
        boundaries.create_geo_boundaries()
        return


class WriteToXml:
    def IsActive(self):
        return bool(FreeCAD.ActiveDocument)

    def GetResources(self):
        return {
            "Pixmap": "icon.svg",
            "MenuText": "Import",
            "ToolTip": "Import IfcRelSpaceBoundary for selected IFC file",
        }

    def Activated(self):
        return
