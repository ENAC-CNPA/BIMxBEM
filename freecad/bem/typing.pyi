# coding: utf8
"""This module contains stubs for FreeCAD Feature Python.

© All rights reserved.
ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Laboratory CNPA, 2019-2020

See the LICENSE.TXT file for more details.

Author : Cyril Waechter
"""
from typing import List

import FreeCAD
import Part
from freecad.bem.entities import (
    Root,
    Container,
    RelSpaceBoundary,
    BEMBoundary,
    Space,
    Element,
    Project,
    Zone,
)
from freecad.bem.materials import Material, LayerSet, ConstituentSet

class RootFeature(Part.Feature):
    Proxy: Root = ...
    Group: List[Part.Feature] = ...
    IfcType: str = ...
    Id: int = ...
    GlobalId: str = ...
    IfcName: str = ...
    Description: str = ...
    Shape: Part.Shape = ...

class RelSpaceBoundaryFeature(RootFeature):
    Proxy: RelSpaceBoundary = ...
    RelatingSpace: int = ...
    RelatedBuildingElement: ElementFeature = ...
    PhysicalOrVirtualBoundary: str = ...
    InternalOrExternalBoundary: str = ...
    CorrespondingBoundary: RelSpaceBoundaryFeature = ...
    ParentBoundary: int = ...
    InnerBoundaries: List[RelSpaceBoundaryFeature] = ...
    UndergroundDepth: PropertyLength = ...
    Normal: FreeCAD.Vector = ...
    ClosestBoundaries: List[int] = ...
    ClosestEdges: List[int] = ...
    ClosestDistance: List[int] = ...
    IsHosted: bool = ...
    PropertyArea: PropertyArea = ...
    AreaWithHosted: PropertyArea = ...
    SIA_Interior: BEMBoundaryFeature = ...
    SIA_Exterior: BEMBoundaryFeature = ...
    LesoType: str = ...

class ElementFeature(RootFeature):
    Proxy: Element = ...
    Material: MaterialFeature = ...
    FillsVoids: List[ElementFeature] = ...
    HasOpenings: List[ElementFeature] = ...
    ProvidesBoundaries: List[int] = ...
    ThermalTransmittance: float = ...
    HostedElements: List[ElementFeature] = ...
    HostElement: int = ...
    Thickness: PropertyLength = ...

class BEMBoundaryFeature(Part.Feature):
    Proxy: BEMBoundary = ...
    SourceBoundary: int = ...
    Area: PropertyArea = ...
    AreaWithHosted: PropertyArea = ...

class ContainerFeature(RootFeature):
    Proxy: Container = ...

class ProjectFeature(RootFeature):
    Proxy: Project = ...
    LongName: str = ...
    TrueNorth: FreeCAD.Vector = ...
    WorldCoordinateSystem: FreeCAD.Vector = ...
    ApplicationIdentifier: str = ...
    ApplicationVersion: str = ...
    ApplicationFullName: str = ...

class SecondLevelGroup:
    Group: List[RelSpaceBoundaryFeature] = ...

class SIAGroups:
    Group: List[BEMBoundaryFeature] = ...

class SpaceFeature(RootFeature):
    Proxy: Space = ...
    LongName: str = ...
    Boundaries: List[SecondLevelGroup] = ...
    SecondLevel: SecondLevelGroup = ...
    SIA_Interiors: SIAGroups = ...
    SIA_Exteriors: SIAGroups = ...
    Area: PropertyArea = ...
    AreaAE: PropertyArea = ...

class ZoneFeature(RootFeature):
    Proxy: Zone = ...
    LongName: str = ...
    RelatedObjects: List[SpaceFeature] = ...

class MaterialFeature(Part.Feature):
    Proxy: Material = ...
    Id: int = ...
    IfcName: str = ...
    Description: str = ...
    Category: str = ...
    MassDensity: str = ...
    Porosity: str = ...
    VisibleTransmittance: float = ...
    SolarTransmittance: float = ...
    ThermalIrTransmittance: float = ...
    ThermalIrEmissivityBack: float = ...
    ThermalIrEmissivityFront: float = ...
    SpecificHeatCapacity: float = ...
    ThermalConductivity: float = ...

class LayerSetFeature(Part.Feature):
    Proxy: LayerSet
    Thicknesses: List[float] = ...
    Id: int = ...
    MaterialLayers: List[MaterialFeature] = ...
    IfcName: str = ...
    Description: str = ...
    TotalThickness: str = ...

class ConstituentSetFeature(Part.Feature):
    Proxy: ConstituentSet
    Id: int = ...
    IfcName: str = ...
    Description: str = ...
    Fractions: List[float] = ...
    Categories: List[str] = ...
    MaterialConstituents: List[MaterialFeature] = ...
