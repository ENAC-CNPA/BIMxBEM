# coding: utf8
# import ptvsd

# # Allow other computers to attach to ptvsd at this IP address and port.
# ptvsd.enable_attach(address=('localhost', 5678), redirect_output=True)

# # Pause the program until a remote debugger is attached
# ptvsd.wait_for_attach()
# # breakpoint()

import FreeCAD
import ifcopenshell
import ifcopenshell.geom
import importIFC
from FreeCAD import Part

ifc_path = "/home/cyril/Projects/BIMxBEM/IfcPython/9000_BIMxBEM_TestModèle_ACAD.ifc"
ifc_file = ifcopenshell.open(ifc_path)
s = ifcopenshell.geom.settings()
s.set(s.USE_PYTHON_OPENCASCADE, True)
s.set(s.USE_WORLD_COORDS, True)
s.set(s.INCLUDE_CURVES, True)
s.set(s.USE_BREP_DATA, True)
space_boundaries = ifc_file.by_type('IfcRelSpaceBoundary')

doc = FreeCAD.ActiveDocument

vectorize = lambda x:FreeCAD.Vector(x[0], x[1])

for space_boundary in (b for b in space_boundaries if b.Name == "2ndLevel"):
    outer_boundary = space_boundary.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary
    # basis_surface = space_boundary.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface

    # Create face
    s=Part.makeBox(10,10,10)
    if outer_boundary.is_a("IfcCompositeCurve"):
        ifc_points = outer_boundary.Segments[0].ParentCurve.Points
    elif outer_boundary.is_a("IfcPolyline"):
        ifc_points = outer_boundary.Points
    else:
        print(f"Create Face: {outer_boundary.is_a()} not handled")
        continue
    fc_points = [vectorize(p.Coordinates) for p in ifc_points]
    polygon = Part.makePolygon(fc_points)
    face = Part.Face(polygon)

    # occ_shape = ifcopenshell.geom.create_shape(s, outer_boundary)
    # face = Part.__fromPythonOCC__(occ_shape)

    # Translate face to its actual position
    # position = outer_boundary.BasisSurface.Position
    # matrix = FreeCAD.Matrix()
    # matrix.move(FreeCAD.Vector(position.Location.Coordinates))
    # matrix.rotate()
    # position.Location

    # Display result
    Part.show(face)

doc.recompute()
