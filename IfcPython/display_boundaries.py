# coding: utf8
import ifcopenshell
import ifcopenshell.geom

ifc_path = "/home/cyril/Projects/BIMxBEM/IfcPython/9000_BIMxBEM_TestModèle_ACAD.ifc"
ifc_file = ifcopenshell.open(ifc_path)
space_boundaries = ifc_file.by_type('IfcRelSpaceBoundary')
s = ifcopenshell.geom.settings()
s.set(s.USE_PYTHON_OPENCASCADE, True)
s.set(s.USE_WORLD_COORDS, True)
s.set(s.EXCLUDE_SOLIDS_AND_SURFACES, False)
s.set(s.INCLUDE_CURVES, True)

occ_display = ifcopenshell.geom.utils.initialize_display()
product_shapes = []
for boundary in (b for b in space_boundaries if b.Name == "2ndLevel"):
    shape = ifcopenshell.geom.create_shape(s, boundary.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary)
    ifcopenshell.geom.utils.display_shape(shape)

input("Press any key")
