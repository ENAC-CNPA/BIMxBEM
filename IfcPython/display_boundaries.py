# coding: utf8
"""This module display IfcRelSpaceBoundary with standard ifcopenshell viewer"""
import ifcopenshell
import ifcopenshell.geom
import OCC.BRep
import OCC.BRepBuilderAPI
import OCC.gp
import OCC.TopoDS


def display_boundaries(ifc_path):
    """Display all IfcRelSpace Boundary from file"""
    ifc_file = ifcopenshell.open(ifc_path)

    space_boundaries = ifc_file.by_type("IfcRelSpaceBoundary")
    settings = ifcopenshell.geom.settings()
    # s.set(s.USE_PYTHON_OPENCASCADE, True)
    # s.set(s.USE_WORLD_COORDS, True)
    settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
    settings.set(settings.INCLUDE_CURVES, True)

    occ_display = ifcopenshell.geom.utils.initialize_display()
    for boundary in (b for b in space_boundaries if b.Name == "2ndLevel"):
        # Retrieve boundary wire
        geom = ifcopenshell.geom.create_shape(
            settings, boundary.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary
        )  # type: OCC.TopoDS.Compound

        wire = get_wire(geom)

        plane = get_plane(boundary)

        # Create boundary face
        face = OCC.BRepBuilderAPI.BRepBuilderAPI_MakeFace(plane, wire).Face()

        # Display boundary face
        ifcopenshell.geom.utils.display_shape(face)

    occ_display.FitAll()

    input("Press any key")


def get_wire(geom):
    """Retrieve boundaries surface wire"""
    ifc_verts = geom.verts
    occ_verts = [
        OCC.gp.gp_Pnt(ifc_verts[i], ifc_verts[i + 1], ifc_verts[i + 2])
        for i in range(0, len(ifc_verts), 3)
    ]
    edges = [
        OCC.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(
            occ_verts[i], occ_verts[i + 1]
        ).Edge()
        for i in range(0, len(occ_verts), 2)
    ]
    wire_maker = OCC.BRepBuilderAPI.BRepBuilderAPI_MakeWire()
    for edge in edges:
        wire_maker.Add(edge)
    return wire_maker.Wire()


def get_plane(boundary):
    """Retrieve the plane boundary is built on"""
    position = (
        boundary.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.Position
    )
    coordinates = position.Location.Coordinates
    direction = position.RefDirection.DirectionRatios
    location = OCC.gp.gp_Pnt(coordinates[0], coordinates[1], coordinates[2])
    direction = OCC.gp.gp_Dir(direction[0], direction[1], direction[2])
    return OCC.gp.gp_Pln(location, direction)


if __name__ == "__main__":
    display_boundaries(ifc_path="IfcPython/9000_BIMxBEM_TestModèle_ACAD.ifc")
