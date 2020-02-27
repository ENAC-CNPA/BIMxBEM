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
        ifc_path = os.path.join(test_folder, test_files[0])
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
        boundaries.processing_sia_boundaries()
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


class DisplaySIAInt:
    def IsActive(self):
        return bool(FreeCAD.ActiveDocument)

    def GetResources(self):
        return {
            "Pixmap": "icon.svg",
            "MenuText": "Display SIA Interior boundaries",
            "ToolTip": "Display SIA Interior boundaries",
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        display_only(doc, "SIA_Interiors")
        return


class DisplaySIAExt:
    def IsActive(self):
        return bool(FreeCAD.ActiveDocument)

    def GetResources(self):
        return {
            "Pixmap": "icon.svg",
            "MenuText": "Display SIA Exterior boundaries",
            "ToolTip": "Display SIA Exterior boundaries",
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        display_only(doc, "SIA_Exteriors")
        return


def display_only(doc, sia_type):
    for element in doc.findObjects():
        element.Visibility = False
    for group_obj in doc.findObjects("App::DocumentObjectGroup"):
        if group_obj.Label.startswith(sia_type):
            for element in group_obj.Group:
                element.Visibility = True


class DisplayAll:
    def IsActive(self):
        return bool(FreeCAD.ActiveDocument)

    def GetResources(self):
        return {
            "Pixmap": "icon.svg",
            "MenuText": "Display all boundaries",
            "ToolTip": "Display all boundaries",
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        for group_obj in doc.findObjects("App::DocumentObjectGroup"):
            if group_obj.Label.startswith("Boundaries"):
                for sub_group_obj in group_obj.Group:
                    for element in sub_group_obj.Group:
                        element.Visibility = True
        display_only(doc, "SIA_Exteriors")
        return