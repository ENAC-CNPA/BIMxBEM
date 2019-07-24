# coding: utf8
import ifcopenshell
import ifcopenshell.geom
import OCC.BRep
import OCC.BRepTools
import OCC.TopoDS
import ptvsd

import FreeCAD
import Part


def display_boundaries(ifc_path):
    ifc_file = ifcopenshell.open(ifc_path)
    settings = ifcopenshell.geom.settings()
    settings.set(settings.INCLUDE_CURVES, True)
    brep = False
    if brep:
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
        settings.set(settings.USE_BREP_DATA, True)
        settings.set(settings.USE_WORLD_COORDS, True)
    else:
        settings.set(settings.USE_PYTHON_OPENCASCADE, False)
    space_boundaries = ifc_file.by_type("IfcRelSpaceBoundary")

    doc = FreeCAD.ActiveDocument

    for space_boundary in (b for b in space_boundaries if b.Name == "2ndLevel"):
        outer_boundary = (
            space_boundary.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary
        )
        ifc_shape = ifcopenshell.geom.create_shape(settings, outer_boundary)


        face = doc.addObject("Part::Feature", "Face")
        if brep:
            face.Shape = Part.Face(geom_by_brep(ifc_shape))
        else:
            face.Shape = Part.Face(geom_by_mesh(ifc_shape))
        face.Placement = get_placement(space_boundary)
        face.ViewObject.ShapeColor = get_color(space_boundary.RelatedBuildingElement)

    doc.recompute()


def geom_by_brep(ifc_shape):
    tmp_file = "/tmp/shape.brep"
    OCC.BRepTools.breptools_Write(ifc_shape, tmp_file)
    return Part.read(tmp_file).Wires


def geom_by_mesh(ifc_shape):
    """Retrieve boundaries surface wire"""
    ifc_verts = ifc_shape.verts
    occ_verts = [FreeCAD.Vector(ifc_verts[i:i+3]) for i in range(0, len(ifc_verts), 3)]
    return Part.makePolygon(occ_verts)


def get_placement(boundary):
    """Retrieve the plane boundary placement"""
    position = (
        boundary.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.Position
    )
    base = FreeCAD.Vector(position.Location.Coordinates)
    rotation = FreeCAD.Rotation(
        FreeCAD.Vector(1, 0, 0), FreeCAD.Vector(position.RefDirection.DirectionRatios)
    )
    return FreeCAD.Placement(base, rotation)


def get_color(ifc_product):
    product_colors = {
        "IfcWall": (0.7, 0.3, 0.0),
        "IfcWindow": (0.0, 0.7, 1.0),
        "IfcSlab": (0.7, 0.7, 0.5),
        "IfcRoof": (0.0, 0.3, 0.0),
    }
    for product, color in product_colors.items():
        if ifc_product.is_a(product):
            return color


if __name__ == "__main__":
    # Allow other computers to attach to ptvsd at this IP address and port.
    ptvsd.enable_attach(address=("localhost", 5678), redirect_output=True)
    # Pause the program until a remote debugger is attached
    ptvsd.wait_for_attach()
    # breakpoint()
    display_boundaries(
        ifc_path="/home/cyril/git/BIMxBEM/IfcPython/9000_BIMxBEM_TestModèle_ACAD.ifc"
    )
