# coding: utf8
import ifcopenshell

# ifcxml support in ifcopenshell is work in progress
ifc_path = "IfcPython/9000_BIMxBEM_TestModèle_ACAD.ifcxml"


def read_space_boundaries():
    ifc_file = ifcopenshell.open(ifc_path)

    space_boundaries = ifc_file.by_type("IfcRelSpaceBoundary")

    for boundary in (b for b in space_boundaries if b.Name == "2ndLevel"):
        boundary


if __name__ == "__main__":
    read_space_boundaries()
