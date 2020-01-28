# coding: utf8
"""This module reads IfcRelSpaceBoundary from an IFC file and display them in FreeCAD"""
import os
import itertools

import ifcopenshell
import ifcopenshell.geom

import FreeCAD
import Part
import FreeCADGui

from bem_xml import BEMxml


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
TOLERANCE = 0.001

"""With IfcOpenShell 0.6.0a1 recreating face from wires seems to give more consistant results.
Especially when inner boundaries touch outer boundary"""
BREP = False

# IfcOpenShell/IFC default unit is m, FreeCAD internal unit is mm
SCALE = 1000


def generate_space(ifc_space, parent, doc=FreeCAD.ActiveDocument):
    fc_space = create_space_from_entity(ifc_space)
    parent.addObject(fc_space)

    boundaries = fc_space.newObject("App::DocumentObjectGroup", "Boundaries")
    fc_space.Boundaries = boundaries
    second_levels = boundaries.newObject("App::DocumentObjectGroup", "SecondLevel")
    fc_space.SecondLevel = second_levels

    # All boundaries have their placement relative to space placement
    space_placement = get_placement(ifc_space)
    for ifc_boundary in (b for b in ifc_space.BoundedBy if b.Name == "2ndLevel"):
        face = make_relspaceboundary(ifc_boundary)
        second_levels.addObject(face)
        face.Placement = space_placement
        element = get_related_element(ifc_boundary, doc)
        if element:
            face.RelatedBuildingElement = element
            append(element, "ProvidesBoundaries", face)
        face.RelatingSpace = fc_space


def generate_containers(ifc_parent, fc_parent, doc=FreeCAD.ActiveDocument):
    for rel_aggregates in ifc_parent.IsDecomposedBy:
        for element in rel_aggregates.RelatedObjects:
            if element.is_a("IfcSpace"):
                generate_space(element, fc_parent, doc)
            else:
                fc_container = create_container_from_entity(element)
                fc_parent.addObject(fc_container)
                generate_containers(element, fc_container, doc)


def get_elements(doc=FreeCAD.ActiveDocument):
    """Generator throught FreeCAD document element of specific ifc_type"""
    for element in doc.Objects:
        try:
            if isinstance(element.Proxy, Element):
                yield element
        except AttributeError:
            continue


def get_elements_by_ifctype(ifc_type: str, doc=FreeCAD.ActiveDocument):
    """Generator throught FreeCAD document element of specific ifc_type"""
    for element in doc.Objects:
        try:
            if element.IfcType == ifc_type:
                yield element
        except AttributeError:
            continue


def generate_ifc_rel_space_boundaries(ifc_path, doc=FreeCAD.ActiveDocument):
    """Display IfcRelSpaceBoundaries from selected IFC file into FreeCAD documennt"""
    ifc_file = ifcopenshell.open(ifc_path)

    # Generate elements (Door, Window, Wall, Slab etc…) without their geometry
    elements_group = get_or_create_group("Elements", doc)
    ifc_elements = (e for e in ifc_file.by_type("IfcElement") if e.ProvidesBoundaries)
    for ifc_entity in ifc_elements:
        elements_group.addObject(create_fc_object_from_entity(ifc_entity))

    # Generate projects structure and boundaries
    for ifc_project in ifc_file.by_type("IfcProject"):
        project = create_project_from_entity(ifc_project)
        generate_containers(ifc_project, project, doc)

    # Associate CorrespondingBoundary
    associate_corresponding_boundaries(doc)

    # Join over splitted boundaries
    for space in get_elements_by_ifctype("IfcSpace", doc):
        join_over_splitted_boundaries(space)

    # Associate Host / Hosted elements
    associate_host_element(ifc_file, elements_group)

    # Associate hosted elements an fill gaps
    for fc_space in get_elements_by_ifctype("IfcSpace", doc):
        fc_boundaries = fc_space.SecondLevel.Group
        # Minimal number of boundary is 5: 3 vertical faces, 2 horizontal faces
        # If there is less than 5 boundaries there is an issue or a new case to analyse
        if len(fc_boundaries) == 5:
            continue
        elif len(fc_boundaries) < 5:
            assert ValueError, f"{fc_space.Label} has less than 5 boundaries"

        # Find coplanar boundaries to identify hosted boundaries and fill gaps (2b)
        associate_coplanar_boundaries(fc_boundaries)

        # Associate hosted elements
        associate_inner_boundaries(fc_boundaries)


def create_geo_boundaries(doc=FreeCAD.ActiveDocument):
    """Create SIA specific boundaries cf. https://www.sia.ch/fr/services/sia-norm/"""
    for space in get_elements_by_ifctype("IfcSpace", doc):
        close_space_boundaries(space)
        find_closest_edges(space)
    # create_geo_ext_boundaries(doc)
    # sia_interiors = boundaries.newObject("App::DocumentObjectGroup", "SIA_Interiors")
    # sia_exteriors = boundaries.newObject("App::DocumentObjectGroup", "SIA_Exteriors")
    # create_geo_int_boundaries(doc)

    doc.recompute()


def write_xml(doc=FreeCAD.ActiveDocument):
    bem_xml = BEMxml()
    for project in get_elements_by_ifctype("IfcProject", doc):
        bem_xml.write_project(project)
    for space in get_elements_by_ifctype("IfcSpace", doc):
        bem_xml.write_space(space)
        for boundary in space.Group:
            bem_xml.write_boundary(boundary)
    for building_element in get_elements():
        bem_xml.write_building_elements(building_element)
    return bem_xml


def output_xml_to_path(bem_xml, xml_path=None):
    if not xml_path:
        xml_path = (
            "./output.xml" if os.name == "nt" else "/home/cyril/git/BIMxBEM/output.xml"
        )
    bem_xml.write_to_file(xml_path)


def close_space_boundaries(space):
    sia = space.Boundaries.newObject("App::DocumentObjectGroup", "SIA")

    join_over_splitted_boundaries(space)
    boundaries = space.SecondLevel.Group
    for rel_boundary1 in boundaries:
        for edge1 in rel_boundary1.Shape.OuterWire.Edges:
            mid_point = edge1.CenterOfMass
            for rel_boundary2 in boundaries:
                if rel_boundary1 == rel_boundary2:
                    continue
                for edge2 in enumerate(rel_boundary2.Shape.OuterWire.Edges):
                    pass


def join_over_splitted_boundaries(space):
    boundaries = space.SecondLevel.Group
    if len(boundaries) < 5:
        return
    elements_dict = dict()
    for rel_boundary in boundaries:
        key = f"{rel_boundary.RelatedBuildingElement.Id}"
        corresponding_boundary = rel_boundary.CorrespondingBoundary
        if corresponding_boundary:
            key += str(corresponding_boundary.Id)
        elements_dict.setdefault(key, []).append(rel_boundary)
    for boundary_list in elements_dict.values():
        # None coplanar boundaries should not be connected.
        # eg. round wall splitted with multiple orientations.
        coplanar_boundaries = list()
        for boundary in boundary_list:
            for coplanar_list in coplanar_boundaries:
                # TODO: Test if this test is not too strict considering precision
                if is_coplanar(boundary, coplanar_list[0]):
                    coplanar_list.append(boundary)
                else:
                    coplanar_boundaries.append([boundary])

        for coplanar_list in coplanar_boundaries:
            # Case 1 : only 1 boundary related to the same element. Cannot group boundaries.
            if len(coplanar_list) == 1:
                continue
            # Case 2 : more than 1 boundary related to the same element might be grouped.
            join_boundaries(coplanar_list)


def join_boundaries(boundaries: list, doc=FreeCAD.ActiveDocument):
    """Try to join coplanar boundaries"""
    result_boundary = boundaries.pop()
    inner_wires = get_inner_wires(result_boundary)[:]
    vectors1 = get_boundary_outer_vectors(result_boundary)
    while boundaries:
        for boundary2 in boundaries:
            vectors2 = get_boundary_outer_vectors(boundary2)
            for ei1, ei2 in itertools.product(
                range(len(vectors1)), range(len(vectors2))
            ):

                # retrieves points from previous edge to next edge included.
                p0_1, p0_2 = (vectors1[ei1], vectors1[(ei1 + 1) % len(vectors1)])
                p1_1, p1_2 = (vectors2[ei2], vectors2[(ei2 + 1) % len(vectors2)])

                v0_12 = p0_2 - p0_1
                v1_12 = p1_2 - p1_1

                dir0 = (v0_12).normalize()
                dir1 = (v1_12).normalize()

                # if edge1 and edge2 are not collinear no junction is possible.
                if not (
                    (dir0.isEqual(dir1, TOLERANCE) or dir0.isEqual(-dir1, TOLERANCE))
                    and v0_12.cross(p1_1 - p0_1) < TOLERANCE
                ):
                    continue

                # Check in which order vectors1 and vectors2 should be connected
                if dir0.isEqual(dir1, TOLERANCE):
                    p0_1_next_point = p1_2
                    reverse_new_points = True
                else:
                    p0_1_next_point = p1_1
                    reverse_new_points = False

                # Check if edge1 and edge2 have a common segment
                if not dir0.dot(p0_1_next_point - p0_1) < dir0.dot(p0_2 - p0_1):
                    continue

                # join vectors1 and vectors2 at indexes
                new_points = vectors2[ei2 + 1 :] + vectors2[: ei2 + 1]
                if reverse_new_points:
                    new_points.reverse()

                # Efficient way to insert elements at index : https://stackoverflow.com/questions/14895599/insert-an-element-at-specific-index-in-a-list-and-return-updated-list/48139870#48139870
                vectors1[ei1 + 1 : ei1 + 1] = new_points

                clean_vectors(vectors1)
                inner_wires.extend(get_inner_wires(boundary2))
                boundaries.remove(boundary2)
                doc.removeObject(boundary2.Name)

    # Replace existing shape with joined shapes
    close_vectors(vectors1)
    wires = [Part.makePolygon(vectors1)] + inner_wires
    result_boundary.Shape = Part.makeFace(wires, "Part::FaceMakerBullseye")


def clean_vectors(vectors):
    """Clean vectors for polygons creation
    Keep only 1 point if 2 consecutive points are equal.
    Remove point if it makes border go back and forth"""
    count = len(vectors)
    i = 0
    while count:
        count -= 1
        p1 = vectors[i - 1]
        p2 = vectors[i]
        p3 = vectors[(i + 1) % len(vectors)]
        if p2 == p3 or are_3points_collinear(p1, p2, p3):
            vectors.remove(p2)
            continue
        i += 1


def get_inner_wires(boundary):
    return boundary.Shape.Wires[1:]


def close_vectors(vectors):
    vectors.append(vectors[0])


def vectors_dir(p1, p2) -> FreeCAD.Vector:
    return (p2 - p1).normalize()


def are_3points_collinear(p1, p2, p3) -> bool:
    dir1 = vectors_dir(p1, p2)
    dir2 = vectors_dir(p2, p3)
    return dir1.isEqual(dir2, TOLERANCE) or dir1.isEqual(-dir2, TOLERANCE)


def get_boundary_outer_vectors(boundary):
    return [vx.Point for vx in boundary.Shape.OuterWire.Vertexes]


def is_collinear(edge1, edge2):
    v0_0, v0_1 = (vx.Point for vx in edge1.Vertexes)
    v1_0, v1_1 = (vx.Point for vx in edge2.Vertexes)
    if is_collinear_or_parallel(v0_0, v0_1, v1_0, v1_1):
        return v0_0 == v1_0 or is_collinear_or_parallel(v0_0, v0_1, v0_0, v1_0)


def is_collinear_or_parallel(v0_0, v0_1, v1_0, v1_1):
    return abs(direction(v0_0, v0_1).dot(direction(v1_0, v1_1))) > 0.9999


def direction(v0, v1):
    return (v0 - v1).normalize()


def find_closest_edges(space):
    boundaries = [b for b in space.SecondLevel.Group if not b.IsHosted]
    closest_dict = dict()
    for i, boundary in enumerate(boundaries):
        n = len(boundary.Shape.OuterWire.Edges)
        closest_dict[i] = {
            "boundaries": [-1] * n,
            "edges": [-1] * n,
            "distances": [10000] * n,
        }
    for (bi1, boundary1), (bi2, boundary2) in itertools.combinations(
        enumerate(boundaries), 2
    ):
        distances1 = closest_dict[bi1]["distances"]
        distances2 = closest_dict[bi2]["distances"]
        edges1 = boundary1.Shape.OuterWire.Edges
        edges2 = boundary2.Shape.OuterWire.Edges
        for (ei1, edge1), (ei2, edge2) in itertools.product(
            enumerate(edges1), enumerate(edges2)
        ):
            if not is_low_angle(edge1, edge2):
                continue
            distance = distances1[ei1]
            edge_to_edge = compute_distance(edge1, edge2)
            if edge_to_edge < distance:
                closest_dict[bi1]["boundaries"][ei1] = bi2
                closest_dict[bi1]["edges"][ei1] = ei2
                distances1[ei1] = round(edge_to_edge)

            distance = distances2[ei2]
            edge_to_edge = compute_distance(edge2, edge1)
            if edge_to_edge < distance:
                closest_dict[bi2]["boundaries"][ei2] = bi1
                closest_dict[bi2]["edges"][ei2] = ei1
                distances2[ei2] = round(edge_to_edge)

    for i, boundary in enumerate(boundaries):
        boundary.ClosestBoundaries = closest_dict[i]["boundaries"]
        boundary.ClosestEdges = closest_dict[i]["edges"]
        boundary.ClosestDistance = closest_dict[i]["distances"]


def compute_distance(edge1, edge2):
    mid_point = edge1.CenterOfMass
    line_segment = (v.Point for v in edge2.Vertexes)
    return mid_point.distanceToLineSegment(*line_segment).Length


def is_low_angle(edge1, edge2):
    dir1 = (edge1.Vertexes[1].Point - edge1.Vertexes[0].Point).normalize()
    dir2 = (edge2.Vertexes[1].Point - edge2.Vertexes[0].Point).normalize()
    return abs(dir1.dot(dir2)) > 0.5  # Low angle considered as < 30°. cos(pi/3)=0.5.


def associate_host_element(ifc_file, elements_group):
    # Associate Host / Hosted elements
    ifc_elements = (e for e in ifc_file.by_type("IfcElement") if e.ProvidesBoundaries)
    for ifc_entity in ifc_elements:
        if ifc_entity.FillsVoids:
            host = get_element_by_guid(get_host_guid(ifc_entity), elements_group)
            hosted = get_element_by_guid(ifc_entity.GlobalId, elements_group)
            append(host, "HostedElements", hosted)
            hosted.HostElement = host


def fill2b(fc_boundaries):
    """Modify boundary to include area of type 2b between boundaries"""
    for fc_boundary in fc_boundaries:
        non_hosted_shared_element = [
            b for b in fc_boundary.ShareRelatedElementWith if not b.IsHosted
        ]
        # FIXME : Simplification which doesn't handle case where 2b touch a corner
        # FIXME : Currently assuming 2b boundaries are bounded by 4 vertices
        if not non_hosted_shared_element:
            continue
        elif len(non_hosted_shared_element) == 1:
            # Find side by side corresponding edges
            fc_boundary1 = fc_boundary
            fc_boundary2 = non_hosted_shared_element[0]
            edges1 = fc_boundary1.Shape.OuterWire.Edges
            edges2 = fc_boundary2.Shape.OuterWire.Edges
            min_distance = 100000
            closest_indexes = None
            for (i, edge1), (j, edge2) in itertools.product(
                enumerate(edges1), enumerate(edges2)
            ):
                if edge1.Length <= edge2.Length:
                    mid_point = edge1.CenterOfMass
                    line_segment = (v.Point for v in edge2.Vertexes)
                else:
                    mid_point = edge2.CenterOfMass
                    line_segment = (v.Point for v in edge1.Vertexes)
                distance = mid_point.distanceToLineSegment(*line_segment).Length
                if distance < min_distance:
                    min_distance = distance
                    closest_indexes = (i, j)
            i, j = closest_indexes

            # Compute centerline
            vec1 = edges1[i].Vertexes[0].Point
            vec2 = edges2[j].Vertexes[0].Point

            line_segment = (v.Point for v in edges2[j].Vertexes)
            vec2 = vec2 + vec2.distanceToLineSegment(*line_segment) / 2
            mid_line = Part.Line(vec1, vec2)

            # Compute intersection on center line between edges
            vxs1_len = len(fc_boundary1.Shape.Vertexes)
            vxs2_len = len(fc_boundary2.Shape.Vertexes)
            b1_v1 = mid_line.intersectCC(edges1[i - 1].Curve)
            b1_v2 = mid_line.intersectCC(edges1[(i + 1) % vxs1_len].Curve)
            b2_v1 = mid_line.intersectCC(edges2[j - 1].Curve)
            b2_v2 = mid_line.intersectCC(edges2[(j + 1) % vxs2_len].Curve)
            vectors = [v.Point for v in fc_boundary1.Shape.OuterWire.Vertexes]
            vectors[i] = b1_v1
            vectors[(i + 1) % len(vectors)] = b1_v2
            vectors.append(vectors[0])
            wires = [Part.makePolygon(vectors)]
            wires.extend(fc_boundary1.Shape.Wires[1:])
            new_shape = Part.Face(wires)
            fc_boundary1.Shape = new_shape


def associate_inner_boundaries(fc_boundaries):
    """Associate hosted elements like a window or a door in a wall"""
    for fc_boundary in fc_boundaries:
        if not fc_boundary.IsHosted:
            continue
        candidates = set(fc_boundaries).intersection(
            fc_boundary.RelatedBuildingElement.HostElement.ProvidesBoundaries
        )

        # If there is more than 1 candidate it doesn't really matter
        # as they share the same host element and space
        host_element = candidates.pop()
        fc_boundary.ParentBoundary = host_element
        append(host_element, "InnerBoundaries", fc_boundary)


def associate_coplanar_boundaries(fc_boundaries):
    """ Find coplanar boundaries to identify hosted boundaries and fill gaps (2b)
    FIXME: Apparently in ArchiCAD, doors are not coplanar.
    Idea: Make it coplanar with other boundaries sharing the same space+wall before"""
    for fc_boundary_1, fc_boundary_2 in itertools.combinations(fc_boundaries, 2):
        if is_coplanar(fc_boundary_1, fc_boundary_2):
            append(fc_boundary_1, "ShareRelatedElementWith", fc_boundary_2)
            append(fc_boundary_2, "ShareRelatedElementWith", fc_boundary_1)


def associate_corresponding_boundaries(doc=FreeCAD.ActiveDocument):
    # Associate CorrespondingBoundary
    for fc_boundary in get_elements_by_ifctype("IfcRelSpaceBoundary", doc):
        associate_corresponding_boundary(fc_boundary)


def is_coplanar(shape_1, shape_2):
    """Intended for RelSpaceBoundary use only
    For some reason native Part.Shape.isCoplanar(Part.Shape) do not always work"""
    return get_plane(shape_1).toShape().isCoplanar(get_plane(shape_2).toShape())


def get_plane(fc_boundary):
    """Intended for RelSpaceBoundary use only"""
    return Part.Plane(
        fc_boundary.Shape.Vertexes[0].Point, fc_boundary.Shape.normalAt(0, 0)
    )


def append(doc_object, fc_property, value):
    """Intended to manipulate FreeCAD list like properties only"""
    current_value = getattr(doc_object, fc_property)
    current_value.append(value)
    setattr(doc_object, fc_property, current_value)


def clean_corresponding_candidates(fc_boundary):
    if fc_boundary.PhysicalOrVirtualBoundary == "VIRTUAL":
        return []
    other_boundaries = fc_boundary.RelatedBuildingElement.ProvidesBoundaries
    other_boundaries.remove(fc_boundary)
    return [
        b
        for b in other_boundaries
        if not b.CorrespondingBoundary or b.RelatingSpace != fc_boundary.RelatingSpace
    ]


def associate_corresponding_boundary(fc_boundary):
    """Associate corresponding boundaries according to IFC definition.

    Reference to the other space boundary of the pair of two space boundaries on either side of a space separating thermal boundary element.
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcrelspaceboundary2ndlevel.htm
    """
    if (
        fc_boundary.InternalOrExternalBoundary != "INTERNAL"
        or fc_boundary.CorrespondingBoundary
    ):
        return

    other_boundaries = clean_corresponding_candidates(fc_boundary)
    if len(other_boundaries) == 1:
        corresponding_boundary = other_boundaries[0]
    else:
        center_of_mass = fc_boundary.Shape.CenterOfMass
        min_lenght = 10000  # No element has 10 m
        for boundary in other_boundaries:
            distance = center_of_mass.distanceToPoint(boundary.Shape.CenterOfMass)
            if distance < min_lenght:
                min_lenght = distance
                corresponding_boundary = boundary
    try:
        fc_boundary.CorrespondingBoundary = corresponding_boundary
        corresponding_boundary.CorrespondingBoundary = fc_boundary
    except NameError:
        # TODO: What to do with uncorrectly classified boundaries which have no corresponding boundary
        FreeCAD.Console.PrintLog(
            f"Boundary {fc_boundary.GlobalId} from space {fc_boundary}"
        )
        return


def get_related_element(ifc_entity, doc=FreeCAD.ActiveDocument):
    if not ifc_entity.RelatedBuildingElement:
        return
    guid = ifc_entity.RelatedBuildingElement.GlobalId
    for element in doc.Objects:
        try:
            if element.GlobalId == guid:
                return element
        except AttributeError:
            continue


def get_host_guid(ifc_entity):
    return (
        ifc_entity.FillsVoids[0]
        .RelatingOpeningElement.VoidsElements[0]
        .RelatingBuildingElement.GlobalId
    )


def get_element_by_guid(guid, elements_group):
    for fc_element in elements_group.Group:
        if fc_element.GlobalId == guid:
            return fc_element
    else:
        FreeCAD.Console.PrintLog(f"Unable to get element by {guid}")


def get_thickness(ifc_entity):
    thickness = 0
    if ifc_entity.IsDecomposedBy:
        ifc_entity = ifc_entity.IsDecomposedBy[0].RelatedObjects[0]

    for association in ifc_entity.HasAssociations:
        if not association.is_a("IfcRelAssociatesMaterial"):
            continue
        try:
            material_layers = association.RelatingMaterial.ForLayerSet.MaterialLayers
        except AttributeError:
            try:
                material_layers = association.RelatingMaterial.MaterialLayers
            except AttributeError:
                # TODO: Fallback method to handle materials with no layers. eg. association.RelatingMaterial.Materials
                continue

        for material_layer in material_layers:
            thickness += material_layer.LayerThickness * SCALE
    return thickness


def create_geo_ext_boundaries(doc=FreeCAD.ActiveDocument):
    """Create boundaries necessary for SIA calculations"""
    project = next(get_elements_by_ifctype("IfcProject"), doc)
    is_from_revit = project.ApplicationIdentifier == "Revit"
    is_from_archicad = project.ApplicationFullName == "ARCHICAD-64"
    for boundary in get_elements_by_ifctype("IfcRelSpaceBoundary", doc):
        if boundary.IsHosted or boundary.PhysicalOrVirtualBoundary == "VIRTUAL":
            continue
        bem_boundary = make_bem_boundary(boundary, "geoExt")
        boundary.addObject(bem_boundary)
        thickness = boundary.RelatedBuildingElement.Thickness.Value
        ifc_type = boundary.RelatedBuildingElement.IfcType
        normal = boundary.Shape.normalAt(0, 0)
        if is_from_archicad:
            normal = -normal
        if boundary.InternalOrExternalBoundary != "INTERNAL":
            lenght = thickness
            if is_from_revit and ifc_type.startswith("IfcWall"):
                lenght /= 2
            bem_boundary.Placement.move(normal * lenght)
        else:
            type1 = {"IfcSlab"}
            if ifc_type in type1:
                if normal.z > 0:
                    lenght = thickness
                else:
                    continue
            else:
                if is_from_revit:
                    continue
                lenght = thickness / 2
            bem_boundary.Placement.move(normal * lenght)


def create_geo_int_boundaries(doc, group_2nd):
    """Create boundaries necessary for SIA calculations"""
    bem_group = doc.addObject("App::DocumentObjectGroup", "geoInt")
    is_from_revit = group_2nd.getParentGroup().ApplicationIdentifier == "Revit"
    is_from_archicad = group_2nd.getParentGroup().ApplicationFullName == "ARCHICAD-64"
    for fc_space in group_2nd.Group:
        for boundary in fc_space.Group:
            if boundary.IsHosted or boundary.PhysicalOrVirtualBoundary == "VIRTUAL":
                continue
            normal = boundary.Shape.normalAt(0, 0)
            if is_from_archicad:
                normal = -normal

            bem_boundary = make_bem_boundary(boundary, "geoInt")
            bem_group.addObject(bem_boundary)

            ifc_type = boundary.RelatedBuildingElement.IfcType
            if is_from_revit and ifc_type.startswith("IfcWall"):
                thickness = boundary.RelatedBuildingElement.Thickness.Value
                lenght = -thickness / 2
                bem_boundary.Placement.move(normal * lenght)


def create_fc_shape(space_boundary):
    """ Create Part shape from ifc geometry"""
    if BREP:
        try:
            return _part_by_brep(
                space_boundary.ConnectionGeometry.SurfaceOnRelatingElement
            )
        except RuntimeError:
            print(f"Failed to generate brep from {space_boundary}")
            fallback = True
    if not BREP or fallback:
        try:
            return part_by_wires(
                space_boundary.ConnectionGeometry.SurfaceOnRelatingElement
            )
        except RuntimeError:
            print(f"Failed to generate mesh from {space_boundary}")
            return _part_by_mesh(
                space_boundary.ConnectionGeometry.SurfaceOnRelatingElement
            )


def _part_by_brep(ifc_entity):
    """ Create a Part Shape from brep generated by ifcopenshell from ifc geometry"""
    ifc_shape = ifcopenshell.geom.create_shape(BREP_SETTINGS, ifc_entity)
    fc_shape = Part.Shape()
    fc_shape.importBrepFromString(ifc_shape.brep_data)
    fc_shape.scale(SCALE)
    return fc_shape


def _part_by_mesh(ifc_entity):
    """ Create a Part Shape from mesh generated by ifcopenshell from ifc geometry"""
    return Part.Face(_polygon_by_mesh(ifc_entity))


def _polygon_by_mesh(ifc_entity):
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
    """For some reason, vertices are not always clean and sometime a same vertex is repeated"""
    new_verts = list()
    for i in range(len(vertices) - 1):
        if vertices[i] != vertices[i + 1]:
            new_verts.append(vertices[i])
    new_verts.append(vertices[-1])
    return new_verts


def part_by_wires(ifc_entity):
    """ Create a Part Shape from ifc geometry"""
    boundaries = list()
    boundaries.append(_polygon_by_mesh(ifc_entity.OuterBoundary))
    try:
        inner_boundaries = ifc_entity.InnerBoundaries
        for inner_boundary in tuple(inner_boundaries) if inner_boundaries else tuple():
            boundaries.append(_polygon_by_mesh(inner_boundary))
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


def get_placement(space):
    """Retrieve object placement"""
    space_geom = ifcopenshell.geom.create_shape(BREP_SETTINGS, space)
    # IfcOpenShell matrix values FreeCAD matrix values are transposed
    ios_matrix = space_geom.transformation.matrix.data
    m_l = list()
    for i in range(3):
        line = list(ios_matrix[i::3])
        line[-1] *= SCALE
        m_l.extend(line)
    return FreeCAD.Matrix(*m_l)


def get_color(ifc_boundary):
    """Return a color depending on IfcClass given"""
    product_colors = {
        "IfcWall": (0.7, 0.3, 0.0),
        "IfcWindow": (0.0, 0.7, 1.0),
        "IfcSlab": (0.7, 0.7, 0.5),
        "IfcRoof": (0.0, 0.3, 0.0),
        "IfcDoor": (1.0, 1.0, 1.0),
    }
    if ifc_boundary.PhysicalOrVirtualBoundary == "VIRTUAL":
        return (1.0, 0.0, 1.0)

    ifc_product = ifc_boundary.RelatedBuildingElement
    for product, color in product_colors.items():
        # Not only test if IFC class is in dictionnary but it is a subclass
        if ifc_product.is_a(product):
            return color
    else:
        print(f"No color found for {ifc_product.is_a()}")
        return (0.0, 0.0, 0.0)


def get_or_create_group(name, doc=FreeCAD.ActiveDocument):
    """Get group by name or create one if not found"""
    group = doc.findObjects("App::DocumentObjectGroup", name)
    if group:
        return group[0]
    return doc.addObject("App::DocumentObjectGroup", name)


def make_relspaceboundary(ifc_entity):
    """Stantard FreeCAD FeaturePython Object creation method"""
    obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", "RelSpaceBoundary")
    # ViewProviderRelSpaceBoundary(obj.ViewObject)
    RelSpaceBoundary(obj, ifc_entity)
    try:
        obj.ViewObject.Proxy = 0
    except AttributeError:
        FreeCAD.Console.PrintLog("No ViewObject ok if running with no Gui")
    return obj


class Root:
    """Wrapping various IFC entity :
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcroot.htm
    """

    def __init__(self, obj, ifc_entity):
        self.Type = self.__class__.__name__
        obj.Proxy = self
        obj.addExtension("App::GroupExtensionPython", self)

        ifc_attributes = "IFC Attributes"
        obj.addProperty("App::PropertyString", "IfcType", "IFC")
        obj.addProperty("App::PropertyInteger", "Id", ifc_attributes)
        obj.addProperty("App::PropertyString", "GlobalId", ifc_attributes)
        obj.addProperty("App::PropertyString", "Description", ifc_attributes)

        obj.Id = ifc_entity.id()
        obj.GlobalId = ifc_entity.GlobalId
        obj.IfcType = ifc_entity.is_a()
        self.set_label(obj, ifc_entity)
        try:
            obj.Description = ifc_entity.Description
        except TypeError:
            pass

    def onChanged(self, obj, prop):
        """Do something when a property has changed"""
        return

    def execute(self, obj):
        """Do something when doing a recomputation, this method is mandatory"""
        return

    @staticmethod
    def set_label(obj, ifc_entity):
        """Allow specific method for specific elements"""
        obj.Label = "{} {}".format(ifc_entity.id(), ifc_entity.Name)

    @classmethod
    def create(cls, obj_name, ifc_entity=None):
        """Stantard FreeCAD FeaturePython Object creation method
        ifc_entity : Optionnally provide a base entity.
        """
        obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", obj_name)
        feature_python_object = cls(obj)
        return obj


class ViewProviderRoot:
    def __init__(self, vobj):
        vobj.Proxy = self
        vobj.addExtension("Gui::ViewProviderGroupExtensionPython", self)


class RelSpaceBoundary(Root):
    """Wrapping IFC entity : 
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcrelspaceboundary2ndlevel.htm"""

    def __init__(self, obj, ifc_entity):
        super().__init__(obj, ifc_entity)
        obj.Proxy = self
        bem_category = "BEM"
        ifc_attributes = "IFC Attributes"
        obj.addProperty("App::PropertyLink", "RelatingSpace", ifc_attributes)
        obj.addProperty("App::PropertyLink", "RelatedBuildingElement", ifc_attributes)
        obj.addProperty(
            "App::PropertyEnumeration", "PhysicalOrVirtualBoundary", ifc_attributes
        ).PhysicalOrVirtualBoundary = ["PHYSICAL", "VIRTUAL", "NOTDEFINED"]
        obj.addProperty(
            "App::PropertyEnumeration", "InternalOrExternalBoundary", ifc_attributes
        ).InternalOrExternalBoundary = [
            "INTERNAL",
            "EXTERNAL",
            "EXTERNAL_EARTH",
            "EXTERNAL_WATER",
            "EXTERNAL_FIRE",
            "NOTDEFINED",
        ]
        obj.addProperty("App::PropertyLink", "CorrespondingBoundary", ifc_attributes)
        obj.addProperty("App::PropertyLink", "ParentBoundary", ifc_attributes)
        obj.addProperty("App::PropertyLinkList", "InnerBoundaries", ifc_attributes)
        obj.addProperty("App::PropertyLink", "ProcessedShape", bem_category)
        obj.addProperty("App::PropertyIntegerList", "ClosestBoundaries", bem_category)
        obj.addProperty("App::PropertyIntegerList", "ClosestEdges", bem_category)
        obj.addProperty("App::PropertyIntegerList", "ClosestDistance", bem_category)
        obj.addProperty("App::PropertyBoolList", "ClosestHasSameNormal", bem_category)
        obj.addProperty(
            "App::PropertyLinkList", "ShareRelatedElementWith", bem_category
        )
        obj.addProperty("App::PropertyBool", "IsHosted", bem_category)
        obj.addProperty("App::PropertyArea", "Area", bem_category)
        obj.addProperty("App::PropertyArea", "AreaWithHosted", bem_category)
        obj.addProperty("App::PropertyLink", "geoInt", bem_category)
        obj.addProperty("App::PropertyLink", "geoExt", bem_category)

        obj.ViewObject.ShapeColor = get_color(ifc_entity)
        obj.GlobalId = ifc_entity.GlobalId
        obj.InternalOrExternalBoundary = ifc_entity.InternalOrExternalBoundary
        obj.PhysicalOrVirtualBoundary = ifc_entity.PhysicalOrVirtualBoundary
        obj.Shape = create_fc_shape(ifc_entity)
        obj.Area = obj.AreaWithHosted = obj.Shape.Area
        self.set_label(obj, ifc_entity)
        if not obj.PhysicalOrVirtualBoundary == "VIRTUAL":
            obj.IsHosted = bool(ifc_entity.RelatedBuildingElement.FillsVoids)
        self.coplanar_with = []

    def onChanged(self, obj, prop):
        super().onChanged(obj, prop)
        if prop == "InnerBoundaries":
            obj.AreaWithHosted = self.recompute_area_with_hosted(obj)

    @staticmethod
    def recompute_area_with_hosted(obj):
        """Recompute area including inner boundaries"""
        area = obj.Area
        for boundary in obj.InnerBoundaries:
            area = area + boundary.Area
        return area

    @staticmethod
    def set_label(obj, ifc_entity):
        try:
            obj.Label = "{} {}".format(
                ifc_entity.RelatedBuildingElement.id(),
                ifc_entity.RelatedBuildingElement.Name,
            )
        except AttributeError:
            FreeCAD.Console.PrintLog(
                f"{ifc_entity.GlobalId} has no RelatedBuildingElement"
            )
            return


def create_fc_object_from_entity(ifc_entity):
    """Stantard FreeCAD FeaturePython Object creation method"""
    obj_name = "Element"
    obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", obj_name)
    Element(obj, ifc_entity)
    try:
        obj.ViewObject.Proxy = 0
    except AttributeError:
        FreeCAD.Console.PrintLog("No ViewObject ok if running with no Gui")
    return obj


class Element(Root):
    """Wrapping various IFC entity :
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/schema/ifcproductextension/lexical/ifcelement.htm
    """

    def __init__(self, obj, ifc_entity):
        super().__init__(obj, ifc_entity)
        self.Type = "IfcRelSpaceBoundary"
        obj.Proxy = self
        ifc_attributes = "IFC Attributes"
        bem_category = "BEM"
        obj.addProperty("App::PropertyLinkList", "HasAssociations", ifc_attributes)
        obj.addProperty("App::PropertyLinkList", "FillsVoids", ifc_attributes)
        obj.addProperty("App::PropertyLinkList", "HasOpenings", ifc_attributes)
        obj.addProperty("App::PropertyLinkList", "ProvidesBoundaries", ifc_attributes)
        obj.addProperty("App::PropertyLinkList", "HostedElements", bem_category)
        obj.addProperty("App::PropertyLink", "HostElement", bem_category)
        obj.addProperty("App::PropertyLength", "Thickness", ifc_attributes)

        ifc_walled_entities = {"IfcWall", "IfcSlab", "IfcRoof"}
        for entity_class in ifc_walled_entities:
            if ifc_entity.is_a(entity_class):
                obj.Thickness = get_thickness(ifc_entity)


def make_bem_boundary(boundary, geo_type):
    """Stantard FreeCAD FeaturePython Object creation method"""
    obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", "BEMBoundary")
    # ViewProviderRelSpaceBoundary(obj.ViewObject)
    BEMBoundary(obj, boundary)
    setattr(boundary, geo_type, obj)
    try:
        obj.ViewObject.Proxy = 0
        obj.ViewObject.ShapeColor = boundary.ViewObject.ShapeColor
    except AttributeError:
        FreeCAD.Console.PrintLog("No ViewObject ok if running with no Gui")
    return obj


class BEMBoundary:
    def __init__(self, obj, boundary):
        self.Type = "BEMBoundary"
        category_name = "BEM"
        obj.addProperty("App::PropertyLink", "SourceBoundary", category_name)
        obj.SourceBoundary = boundary
        obj.addProperty("App::PropertyArea", "Area", category_name)
        obj.addProperty("App::PropertyArea", "AreaWithHosted", category_name)
        obj.Shape = boundary.Shape.copy()
        obj.Area = obj.Shape.Area
        obj.AreaWithHosted = self.recompute_area_with_hosted(obj)
        self.set_label(obj)

    @staticmethod
    def recompute_area_with_hosted(obj):
        """Recompute area including inner boundaries"""
        area = obj.Area
        for boundary in obj.SourceBoundary.InnerBoundaries:
            area = area + boundary.Area
        return area

    @staticmethod
    def set_label(obj):
        obj.Label = obj.SourceBoundary.Label


def create_container_from_entity(ifc_entity):
    """Stantard FreeCAD FeaturePython Object creation method"""
    obj_name = "Project"
    obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", obj_name)
    Container(obj, ifc_entity)
    if FreeCAD.GuiUp:
        obj.ViewObject.Proxy = ViewProviderRoot(obj.ViewObject)
    return obj


class Container(Root):
    """Representation of an IfcProject:
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcproject.htm"""

    def __init__(self, obj, ifc_entity):
        super().__init__(obj, ifc_entity)
        self.ifc_entity = ifc_entity
        self.setProperties(obj)

    def setProperties(self, obj):
        return


def create_project_from_entity(ifc_entity):
    """Stantard FreeCAD FeaturePython Object creation method"""
    obj_name = "Project"
    obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", obj_name)
    Project(obj, ifc_entity)
    if FreeCAD.GuiUp:
        obj.ViewObject.Proxy = ViewProviderRoot(obj.ViewObject)
    return obj


class Project(Root):
    """Representation of an IfcProject:
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcproject.htm"""

    def __init__(self, obj, ifc_entity):
        super().__init__(obj, ifc_entity)
        self.ifc_entity = ifc_entity
        self.setProperties(obj)

    def setProperties(self, obj):
        ifc_entity = self.ifc_entity
        ifc_attributes = "IFC Attributes"
        obj.addProperty("App::PropertyString", "LongName", ifc_attributes)
        obj.addProperty("App::PropertyVector", "TrueNorth", ifc_attributes)
        obj.addProperty("App::PropertyVector", "WorldCoordinateSystem", ifc_attributes)
        obj.LongName = ifc_entity.LongName
        obj.TrueNorth = FreeCAD.Vector(
            *ifc_entity.RepresentationContexts[0].TrueNorth.DirectionRatios
        )
        obj.WorldCoordinateSystem = FreeCAD.Vector(
            ifc_entity.RepresentationContexts[
                0
            ].WorldCoordinateSystem.Location.Coordinates
        )

        owning_application = "OwningApplication"
        obj.addProperty(
            "App::PropertyString", "ApplicationIdentifier", owning_application
        )
        obj.addProperty("App::PropertyString", "ApplicationVersion", owning_application)
        obj.addProperty(
            "App::PropertyString", "ApplicationFullName", owning_application
        )
        owning_application = ifc_entity.OwnerHistory.OwningApplication
        obj.ApplicationIdentifier = owning_application.ApplicationIdentifier
        obj.ApplicationVersion = owning_application.Version
        obj.ApplicationFullName = owning_application.ApplicationFullName


def create_space_from_entity(ifc_entity):
    """Stantard FreeCAD FeaturePython Object creation method"""
    obj_name = "Space"
    obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", obj_name)
    Space(obj, ifc_entity)
    if FreeCAD.GuiUp:
        obj.ViewObject.Proxy = ViewProviderRoot(obj.ViewObject)
    return obj


class Space(Root):
    """Representation of an IfcProject:
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcproject.htm"""

    def __init__(self, obj, ifc_entity):
        super().__init__(obj, ifc_entity)
        self.ifc_entity = ifc_entity
        self.setProperties(obj)

    def setProperties(self, obj):
        ifc_entity = self.ifc_entity
        category_name = "Boundaries"
        obj.addProperty("App::PropertyLink", "Boundaries", category_name)
        obj.addProperty("App::PropertyLink", "SecondLevel", category_name)
        obj.addProperty("App::PropertyLink", "SIA", category_name)
        obj.addProperty("App::PropertyLink", "SIA_Interiors", category_name)
        obj.addProperty("App::PropertyLink", "SIA_Exteriors", category_name)

        space_full_name = f"{ifc_entity.Name} {ifc_entity.LongName}"
        obj.Label = space_full_name
        try:
            obj.Description = ifc_entity.Description
        except TypeError:
            pass

        return obj


if __name__ == "__main__":
    if os.name == "nt":
        TEST_FOLDER = r"C:\git\BIMxBEM\IfcTestFiles"
    else:
        TEST_FOLDER = "/home/cyril/git/BIMxBEM/IfcTestFiles/"
    TEST_FILES = [
        "Triangle_2x3_A22.ifc",
        "Triangle_2x3_R19.ifc",
        "2Storey_2x3_A22.ifc",
        "2Storey_2x3_R19.ifc",
        "0014_Vernier112D_ENE_ModèleÉnergétique_R20.ifc",
        "Investigation_test_R19.ifc",
    ]
    IFC_PATH = os.path.join(TEST_FOLDER, TEST_FILES[2])
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

        generate_ifc_rel_space_boundaries(IFC_PATH, DOC)
        create_geo_boundaries(DOC)

        FreeCADGui.activeView().viewIsometric()
        FreeCADGui.SendMsgToActiveView("ViewFit")

        FreeCADGui.exec_loop()
