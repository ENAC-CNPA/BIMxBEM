# coding: utf8
import ifcopenshell
import ifcopenshell.geom
import OCC.BRepBuilderAPI
import OCC.BRep
import OCC.gp
import OCC.TopoDS

ifc_path = "IfcPython/9000_BIMxBEM_TestModèle_ACAD.ifc"
ifc_file = ifcopenshell.open(ifc_path)

space_boundaries = ifc_file.by_type('IfcRelSpaceBoundary')
s = ifcopenshell.geom.settings()
# s.set(s.USE_PYTHON_OPENCASCADE, True)
# s.set(s.USE_WORLD_COORDS, True)
s.set(s.EXCLUDE_SOLIDS_AND_SURFACES, False)
s.set(s.INCLUDE_CURVES, True)

occ_display = ifcopenshell.geom.utils.initialize_display()
product_shapes = []
for boundary in (b for b in space_boundaries if b.Name == "2ndLevel"):
    # Retrieve boundary wire    
    geom = ifcopenshell.geom.create_shape(s, boundary.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary) # type: OCC.TopoDS.Compound
    v = geom.verts
    verts = [OCC.gp.gp_Pnt(v[i], v[i+1], v[i+2]) for i in range(0, len(v), 3)]
    edges = [OCC.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(verts[i], verts[i+1]).Edge() for i in range(0, len(verts), 2)]
    w = OCC.BRepBuilderAPI.BRepBuilderAPI_MakeWire()
    for edge in edges:
        w.Add(edge)
    wire = w.Wire()    

    # Retrieve boundary plane
    position = boundary.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.Position
    c = position.Location.Coordinates
    d = position.RefDirection.DirectionRatios
    location = OCC.gp.gp_Pnt(c[0], c[1], c[2])
    direction = OCC.gp.gp_Dir(d[0], d[1], d[2])
    plane = OCC.gp.gp_Pln(location, direction)

    # Create boundary face
    face = OCC.BRepBuilderAPI.BRepBuilderAPI_MakeFace(plane, wire).Face()
    
    # Display boundary face
    ifcopenshell.geom.utils.display_shape(face)

input("Press any key")
