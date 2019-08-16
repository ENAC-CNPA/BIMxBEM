# coding: utf8
"""This module reads IfcRelSpaceBoundary from an IFC file and display them in FreeCAD"""
import ifcopenshell
import ifcopenshell.geom

import FreeCAD
import FreeCADGui
import Part


def ios_settings(brep):
    """Create ifcopenshell.geom.settings for various cases"""
    settings = ifcopenshell.geom.settings()
    settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
    settings.set(settings.INCLUDE_CURVES, True)
    if brep:
        settings.set(settings.USE_BREP_DATA, True)
    return settings


BREP_SETTINGS = ios_settings(brep=True)
MESH_SETTINGS = ios_settings(brep=False)

"""With IfcOpenShell 0.6.0a1 recreating face from wires seems to give more consistant results.
Especially when inner boundaries touch outer boundary"""
BREP = False

# IfcOpenShell/IFC default unit is m, FreeCAD internal unit is mm
SCALE = 1000


def display_boundaries(ifc_path, doc=FreeCAD.ActiveDocument):
    """Display IfcRelSpaceBoundaries from selected IFC file into FreeCAD documennt"""
    # Create default groups
    group = get_group(doc, "IfcRelSpaceBoundary")
    group_2nd = get_group(doc, "SecondLevel")
    group.addObject(group_2nd)

    ifc_file = ifcopenshell.open(ifc_path)

    space_boundaries = ifc_file.by_type("IfcRelSpaceBoundary")

    for space_boundary in (b for b in space_boundaries if b.Name == "2ndLevel"):
        if BREP:
            try:
                fc_shape = part_by_brep(
                    space_boundary.ConnectionGeometry.SurfaceOnRelatingElement
                )
            except RuntimeError:
                print(f"Failed to generate brep from {space_boundary}")
                fallback = True
        if not BREP or fallback:
            try:
                fc_shape = part_by_wires(
                    space_boundary.ConnectionGeometry.SurfaceOnRelatingElement
                )
            except RuntimeError:
                print(f"Failed to generate mesh from {space_boundary}")
                fc_shape = part_by_mesh(
                    space_boundary.ConnectionGeometry.SurfaceOnRelatingElement
                )

        face = doc.addObject("Part::Feature", "Face")
        group_2nd.addObject(face)
        face.Shape = fc_shape
        face.Placement = get_space_placement(space_boundary)
        face.Label = "{} {} / {} {}".format(
            space_boundary.RelatingSpace.Name,
            space_boundary.RelatingSpace.LongName,
            space_boundary.RelatedBuildingElement.id(),
            space_boundary.RelatedBuildingElement.Name,
        )
        face.ViewObject.ShapeColor = get_color(space_boundary.RelatedBuildingElement)

    doc.recompute()


def part_by_brep(ifc_entity):
    """ Create a Part Shape from ifc geometry"""
    ifc_shape = ifcopenshell.geom.create_shape(BREP_SETTINGS, ifc_entity)
    fc_shape = Part.Shape()
    fc_shape.importBrepFromString(ifc_shape.brep_data)
    fc_shape.scale(SCALE)
    return fc_shape


def part_by_mesh(ifc_entity):
    """ Create a Part Shape from ifc geometry"""
    return Part.Face(polygon_by_mesh(ifc_entity))


def polygon_by_mesh(ifc_entity):
    """Create a Polygon from a compatible ifc entity"""
    ifc_shape = ifcopenshell.geom.create_shape(MESH_SETTINGS, ifc_entity)
    ifc_verts = ifc_shape.verts
    fc_verts = [
        FreeCAD.Vector(ifc_verts[i : i + 3]).scale(SCALE, SCALE, SCALE)
        for i in range(0, len(ifc_verts), 3)
    ]
    fc_verts = verts_clean(fc_verts)

    return Part.makePolygon(fc_verts)


def verts_clean(vertices):
    new_verts = list()
    for i in range(len(vertices) - 1):
        if vertices[i] != vertices[i + 1]:
            new_verts.append(vertices[i])
    new_verts.append(vertices[-1])
    return new_verts


def part_by_wires(ifc_entity):
    """ Create a Part Shape from ifc geometry"""
    boundaries = list()
    boundaries.append(polygon_by_mesh(ifc_entity.OuterBoundary))
    try:
        inner_boundaries = ifc_entity.InnerBoundaries
        for inner_boundary in tuple(inner_boundaries) if inner_boundaries else tuple():
            boundaries.append(polygon_by_mesh(inner_boundary))
    except RuntimeError:
        pass
    fc_shape = Part.makeFace(boundaries, "Part::FaceMakerBullseye")
    matrix = get_matrix(ifc_entity.BasisSurface.Position)
    fc_shape = fc_shape.transformGeometry(matrix)
    return fc_shape


def get_matrix(position):
    """Transform position to FreeCAD.Matrix"""
    location = FreeCAD.Vector(position.Location.Coordinates).scale(SCALE, SCALE, SCALE)

    v_1 = FreeCAD.Vector(position.RefDirection.DirectionRatios)
    v_3 = FreeCAD.Vector(position.Axis.DirectionRatios)
    v_2 = v_3.cross(v_1)

    # fmt: off
    matrix = FreeCAD.Matrix(
        v_1.x, v_2.x, v_3.x, location.x,
        v_1.y, v_2.y, v_3.y, location.y,
        v_1.z, v_2.z, v_3.z, location.z,
        0, 0, 0, 1,
    )
    # fmt: on

    return matrix


def get_space_placement(boundary):
    """Retrieve the plane boundary placement"""
    space = ifcopenshell.geom.create_shape(BREP_SETTINGS, boundary.RelatingSpace)
    # IfcOpenShell matrix values FreeCAD matrix values are transposed
    ios_matrix = space.transformation.matrix.data
    m_l = list()
    for i in range(3):
        line = list(ios_matrix[i::3])
        line[-1] *= SCALE
        m_l.extend(line)
    return FreeCAD.Matrix(*m_l)


def get_color(ifc_product):
    """Return a color depending on IfcClass given"""
    product_colors = {
        "IfcWall": (0.7, 0.3, 0.0),
        "IfcWindow": (0.0, 0.7, 1.0),
        "IfcSlab": (0.7, 0.7, 0.5),
        "IfcRoof": (0.0, 0.3, 0.0),
        "IfcDoor": (1.0, 1.0, 1.0),
    }
    for product, color in product_colors.items():
        if ifc_product.is_a(product):
            return color
    else:
        print(f"No color found for {ifc_product.is_a()}")
        return (0.0, 0.0, 0.0)


def get_group(doc, name):
    """Get group by name or create one if not found"""
    group = doc.findObjects("App::DocumentObjectGroup", name)
    if group:
        return group[0]
    else:
        return doc.addObject("App::DocumentObjectGroup", name)


if __name__ == "__main__":
    IFC_PATH = "/home/cyril/git/BIMxBEM/IfcTestFiles/Triangle_R19.ifc"
    DOC = FreeCAD.ActiveDocument
    if DOC:  # Remote debugging
        import ptvsd

        # Allow other computers to attach to ptvsd at this IP address and port.
        ptvsd.enable_attach(address=("localhost", 5678), redirect_output=True)
        # Pause the program until a remote debugger is attached
        ptvsd.wait_for_attach()
        # breakpoint()

        display_boundaries(ifc_path=IFC_PATH, doc=DOC)
        FreeCADGui.activeView().viewIsometric()
        FreeCADGui.SendMsgToActiveView("ViewFit")
    else:
        FreeCADGui.showMainWindow()
        DOC = FreeCAD.newDocument()

        display_boundaries(ifc_path=IFC_PATH, doc=DOC)

        FreeCADGui.activeView().viewIsometric()
        FreeCADGui.SendMsgToActiveView("ViewFit")

        FreeCADGui.exec_loop()
