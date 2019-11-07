# coding: utf8
"""This module write IfcRelSpaceBoundary to an ifc file"""

import ifcopenshell

# Default location and directions
ORIGIN = (0.0, 0.0, 0.0)
DIR_X = (1.0, 0.0, 0.0)
DIR_Y = (0.0, 1.0, 0.0)
DIR_Z = (0.0, 0.0, 1.0)


def create_ifc_axis2placement(ifc_file, point=ORIGIN, dir_z=DIR_Z, dir_x=DIR_X):
    point = ifc_file.createIfcCartesianPoint(point)
    dir_z = ifc_file.createIfcDirection(dir_z)
    dir_x = ifc_file.createIfcDirection(dir_x)
    return ifc_file.createIfcAxis2Placement3D(point, dir_z, dir_x)


def create_boundary(ifc_file, points):
    ifc_file.createIfcRelSpaceBoundary(
    GlobalId=ifcopenshell.guid.new(),
    Ownerhistory=None,
    Name=None,
    Description=None,
    RelatingSpace=relating_space,
    RelatedBuildingElement=relating_building,
    ConnectionGeometry,
    PhysicalOrVirtualBoundary,
    InternalOrExternalBoundary,
    )

