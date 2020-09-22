# coding: utf8
"""This module contains FreeCAD wrapper class for IfcEntities

© All rights reserved.
ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Laboratory CNPA, 2019-2020

See the LICENSE.TXT file for more details.

Author : Cyril Waechter
"""
import typing
from typing import Iterable

import ifcopenshell

import FreeCAD
import Part

from freecad.bem.bem_logging import logger
from freecad.bem import utils

if typing.TYPE_CHECKING:  # https://www.python.org/dev/peps/pep-0484/#id36
    from freecad.bem.ifc_importer import IfcImporter


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
    if not ifc_product:
        return (1.0, 0.0, 0.0)
    for product, color in product_colors.items():
        # Not only test if IFC class is in dictionnary but it is a subclass
        if ifc_product.is_a(product):
            return color
    print(f"No color found for {ifc_product.is_a()}")
    return (0.0, 0.0, 0.0)


def get_related_element(ifc_entity, doc=FreeCAD.ActiveDocument) -> Part.Feature:
    if not ifc_entity.RelatedBuildingElement:
        return
    guid = ifc_entity.RelatedBuildingElement.GlobalId
    for element in doc.Objects:
        try:
            if element.GlobalId == guid:
                return element
        except AttributeError:
            continue


class Root:
    """Wrapping various IFC entity :
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcroot.htm
    """

    def __init__(self, obj: Part.Feature):
        self.Type = self.__class__.__name__  # pylint: disable=invalid-name
        obj.Proxy = self  # pylint: disable=invalid-name
        obj.addExtension("App::GroupExtensionPython", self)

    @classmethod
    def _init_properties(cls, obj: Part.Feature):
        ifc_attributes = "IFC Attributes"
        obj.addProperty("App::PropertyString", "IfcType", "IFC")
        obj.addProperty("App::PropertyInteger", "Id", ifc_attributes)
        obj.addProperty("App::PropertyString", "GlobalId", ifc_attributes)
        obj.addProperty("App::PropertyString", "IfcName", ifc_attributes)
        obj.addProperty("App::PropertyString", "Description", ifc_attributes)

    @classmethod
    def create(cls) -> Part.Feature:
        """Stantard FreeCAD FeaturePython Object creation method"""
        obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", cls.__name__)
        cls(obj)
        cls._init_properties(obj)

        if FreeCAD.GuiUp:
            obj.ViewObject.Proxy = ViewProviderRoot(obj.ViewObject)
        return obj

    @classmethod
    def create_from_ifc(cls, ifc_entity, ifc_importer: "IfcImporter") -> Part.Feature:
        """As cls.create but providing an ifc source"""
        obj = cls.create()
        obj.Proxy.ifc_importer = ifc_importer
        cls.read_from_ifc(obj, ifc_entity)
        cls.set_label(obj)
        return obj

    @classmethod
    def read_from_ifc(cls, obj, ifc_entity):
        obj.Id = ifc_entity.id()
        obj.GlobalId = ifc_entity.GlobalId
        obj.IfcType = ifc_entity.is_a()
        obj.IfcName = ifc_entity.Name or ""
        obj.Description = ifc_entity.Description or ""

    @staticmethod
    def set_label(obj: Part.Feature):
        """Allow specific method for specific elements"""
        obj.Label = f"{obj.Id}_{obj.IfcName or obj.IfcType}"

    @staticmethod
    def read_pset_from_ifc(obj, ifc_entity, properties: Iterable[str]) -> None:
        psets = ifcopenshell.util.element.get_psets(ifc_entity)
        for pset in psets.values():
            for prop_name, prop in pset.items():
                if prop_name in properties:
                    setattr(obj, prop_name, getattr(prop, "wrappedValue", prop))


class ViewProviderRoot:
    def __init__(self, vobj):
        vobj.Proxy = self
        vobj.addExtension("Gui::ViewProviderGroupExtensionPython", self)


class RelSpaceBoundary(Root):
    """Wrapping IFC entity :
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcrelspaceboundary2ndlevel.htm"""

    def __init__(self, obj: Part.Feature):
        super().__init__(obj)
        obj.Proxy = self

    @classmethod
    def _init_properties(cls, obj: Part.Feature):
        super()._init_properties(obj)
        bem_category = "BEM"
        ifc_attributes = "IFC Attributes"
        obj.addProperty("App::PropertyInteger", "RelatingSpace", ifc_attributes)
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
        obj.addProperty("App::PropertyInteger", "ParentBoundary", ifc_attributes)
        obj.addProperty("App::PropertyLinkList", "InnerBoundaries", ifc_attributes)
        obj.addProperty("App::PropertyVector", "Normal", bem_category)
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
        obj.addProperty("App::PropertyLink", "SIA_Interior", bem_category)
        obj.addProperty("App::PropertyLink", "SIA_Exterior", bem_category)
        obj.addProperty(
            "App::PropertyEnumeration", "LesoType", bem_category
        ).LesoType = [
            "Ceiling",
            "Wall",
            "Flooring",
            "Window",
            "Door",
            "Opening",
            "Unknown",
        ]

    @classmethod
    def read_from_ifc(cls, obj: Part.Feature, ifc_entity):
        super().read_from_ifc(obj, ifc_entity)
        ifc_importer = obj.Proxy.ifc_importer
        element = get_related_element(ifc_entity, ifc_importer.doc)
        if element:
            obj.RelatedBuildingElement = element
            utils.append(element, "ProvidesBoundaries", obj.Id)
        obj.RelatingSpace = ifc_entity.RelatingSpace.id()
        obj.InternalOrExternalBoundary = ifc_entity.InternalOrExternalBoundary
        obj.PhysicalOrVirtualBoundary = ifc_entity.PhysicalOrVirtualBoundary
        obj.Shape = ifc_importer.create_fc_shape(ifc_entity)
        obj.Area = obj.AreaWithHosted = obj.Shape.Area
        try:
            obj.IsHosted = bool(ifc_entity.RelatedBuildingElement.FillsVoids)
        except AttributeError:
            obj.IsHosted = False
        obj.LesoType = "Unknown"

        if FreeCAD.GuiUp:
            obj.ViewObject.Proxy = 0
            obj.ViewObject.ShapeColor = get_color(ifc_entity)

    def onChanged(self, obj, prop):  # pylint: disable=invalid-name
        if prop == "InnerBoundaries":
            self.recompute_area_with_hosted(obj)

    @classmethod
    def recompute_areas(cls, obj: Part.Feature):
        obj.Area = obj.Shape.Faces[0].Area
        cls.recompute_area_with_hosted(obj)

    @staticmethod
    def recompute_area_with_hosted(obj: Part.Feature):
        """Recompute area including inner boundaries"""
        area = obj.Area
        for boundary in obj.InnerBoundaries:
            area = area + boundary.Area
        obj.AreaWithHosted = area

    @classmethod
    def set_label(cls, obj):
        try:
            obj.Label = f"{obj.Id}_{obj.RelatedBuildingElement.IfcName}"
        except AttributeError:
            obj.Label = f"{obj.Id} VIRTUAL"
            if obj.PhysicalOrVirtualBoundary != "VIRTUAL":
                logger.warning(
                    f"{obj.Id} is not VIRTUAL and has no RelatedBuildingElement"
                )

    @staticmethod
    def get_wires(obj):
        return utils.get_wires(obj)


class Element(Root):
    """Wrapping various IFC entity :
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/schema/ifcproductextension/lexical/ifcelement.htm
    """

    def __init__(self, obj):
        super().__init__(obj)
        self.Type = "IfcRelSpaceBoundary"
        obj.Proxy = self

    @classmethod
    def create_from_ifc(cls, ifc_entity: "Part.Feature", ifc_importer: "IfcImporter"):
        """Stantard FreeCAD FeaturePython Object creation method"""
        obj = super().create_from_ifc(ifc_entity, ifc_importer)
        ifc_importer.material_creator.create(obj, ifc_entity)
        obj.Thickness = ifc_importer.guess_thickness(obj, ifc_entity)

        if FreeCAD.GuiUp:
            obj.ViewObject.Proxy = 0
        return obj

    @classmethod
    def _init_properties(cls, obj):
        super()._init_properties(obj)
        ifc_attributes = "IFC Attributes"
        bem_category = "BEM"
        obj.addProperty("App::PropertyLink", "Material", ifc_attributes)
        obj.addProperty("App::PropertyLinkList", "FillsVoids", ifc_attributes)
        obj.addProperty("App::PropertyLinkList", "HasOpenings", ifc_attributes)
        obj.addProperty(
            "App::PropertyIntegerList", "ProvidesBoundaries", ifc_attributes
        )
        obj.addProperty("App::PropertyFloat", "ThermalTransmittance", ifc_attributes)
        obj.addProperty("App::PropertyLinkList", "HostedElements", bem_category)
        obj.addProperty("App::PropertyInteger", "HostElement", bem_category)
        obj.addProperty("App::PropertyLength", "Thickness", bem_category)

    @classmethod
    def read_from_ifc(cls, obj, ifc_entity):
        super().read_from_ifc(obj, ifc_entity)
        obj.Label = f"{obj.Id}_{obj.IfcType}"

        super().read_pset_from_ifc(
            obj,
            ifc_entity,
            [
                "ThermalTransmittance",
            ],
        )


class BEMBoundary:
    def __init__(self, obj, boundary):
        self.Type = "BEMBoundary"  # pylint: disable=invalid-name
        obj.Proxy = self
        category_name = "BEM"
        obj.addProperty("App::PropertyInteger", "SourceBoundary", category_name)
        obj.SourceBoundary = boundary.Id
        obj.addProperty("App::PropertyArea", "Area", category_name)
        obj.addProperty("App::PropertyArea", "AreaWithHosted", category_name)
        obj.Shape = boundary.Shape.copy()
        self.set_label(obj, boundary)
        obj.Area = boundary.Area
        obj.AreaWithHosted = boundary.AreaWithHosted

    @staticmethod
    def create(boundary, geo_type):
        """Stantard FreeCAD FeaturePython Object creation method"""
        obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", "BEMBoundary")
        BEMBoundary(obj, boundary)
        setattr(boundary, geo_type, obj)
        if FreeCAD.GuiUp:
            # ViewProviderRelSpaceBoundary(obj.ViewObject)
            obj.ViewObject.Proxy = 0
            obj.ViewObject.ShapeColor = boundary.ViewObject.ShapeColor
        return obj

    @staticmethod
    def set_label(obj, source_boundary):
        obj.Label = source_boundary.Label

    @staticmethod
    def get_wires(obj):
        return utils.get_wires(obj)


class Container(Root):
    """Representation of an IfcProject:
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcproject.htm"""

    def __init__(self, obj):
        super().__init__(obj)
        obj.Proxy = self

    @classmethod
    def create_from_ifc(cls, ifc_entity, ifc_importer: "IfcImporter"):
        obj = super().create_from_ifc(ifc_entity, ifc_importer)
        cls.set_label(obj)
        if FreeCAD.GuiUp:
            obj.ViewObject.DisplayMode = "Wireframe"
        return obj


class Project(Root):
    """Representation of an IfcProject:
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcproject.htm"""

    @classmethod
    def create(cls):
        obj = super().create()
        if FreeCAD.GuiUp:
            obj.ViewObject.DisplayMode = "Wireframe"
        return obj

    @classmethod
    def _init_properties(cls, obj):
        super()._init_properties(obj)
        ifc_attributes = "IFC Attributes"
        obj.addProperty("App::PropertyString", "LongName", ifc_attributes)
        obj.addProperty("App::PropertyVector", "TrueNorth", ifc_attributes)
        obj.addProperty("App::PropertyVector", "WorldCoordinateSystem", ifc_attributes)

        owning_application = "OwningApplication"
        obj.addProperty(
            "App::PropertyString", "ApplicationIdentifier", owning_application
        )
        obj.addProperty("App::PropertyString", "ApplicationVersion", owning_application)
        obj.addProperty(
            "App::PropertyString", "ApplicationFullName", owning_application
        )

    @classmethod
    def read_from_ifc(cls, obj, ifc_entity):
        super().read_from_ifc(obj, ifc_entity)
        obj.LongName = ifc_entity.LongName or ""
        obj.TrueNorth = FreeCAD.Vector(
            *ifc_entity.RepresentationContexts[0].TrueNorth.DirectionRatios
        )
        obj.WorldCoordinateSystem = FreeCAD.Vector(
            ifc_entity.RepresentationContexts[
                0
            ].WorldCoordinateSystem.Location.Coordinates
        )

        owning_application = ifc_entity.OwnerHistory.OwningApplication
        obj.ApplicationIdentifier = owning_application.ApplicationIdentifier
        obj.ApplicationVersion = owning_application.Version
        obj.ApplicationFullName = owning_application.ApplicationFullName

    @classmethod
    def set_label(cls, obj):
        obj.Label = f"{obj.IfcName}_{obj.LongName}"


class Space(Root):
    """Representation of an IfcProject:
    https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcproject.htm"""

    @classmethod
    def create(cls):
        obj = super().create()
        if FreeCAD.GuiUp:
            obj.ViewObject.ShapeColor = (0.33, 1.0, 1.0)
            obj.ViewObject.Transparency = 90
        return obj

    @classmethod
    def _init_properties(cls, obj):
        super()._init_properties(obj)
        ifc_attributes = "IFC Attributes"
        obj.addProperty("App::PropertyString", "LongName", ifc_attributes)
        category_name = "Boundaries"
        obj.addProperty("App::PropertyLink", "Boundaries", category_name)
        obj.addProperty("App::PropertyLink", "SecondLevel", category_name)
        obj.addProperty("App::PropertyLink", "SIA", category_name)
        obj.addProperty("App::PropertyLink", "SIA_Interiors", category_name)
        obj.addProperty("App::PropertyLink", "SIA_Exteriors", category_name)
        bem_category = "BEM"
        obj.addProperty("App::PropertyArea", "Area", bem_category)
        obj.addProperty("App::PropertyArea", "AreaAE", bem_category)

    @classmethod
    def read_from_ifc(cls, obj, ifc_entity):
        super().read_from_ifc(obj, ifc_entity)
        ifc_importer = obj.Proxy.ifc_importer
        obj.Shape = ifc_importer.entity_shape_by_brep(ifc_entity)
        obj.LongName = ifc_entity.LongName or ""
        space_full_name = f"{ifc_entity.Name} {ifc_entity.LongName}"
        obj.Label = space_full_name
        obj.Description = ifc_entity.Description or ""

    @classmethod
    def set_label(cls, obj):
        obj.Label = f"{obj.IfcName}_{obj.LongName}"
