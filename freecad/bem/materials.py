# coding: utf8
"""This module reads IfcRelSpaceBoundary from an IFC file and display them in FreeCAD

© All rights reserved.
ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Laboratory CNPA, 2019-2020

See the LICENSE.TXT file for more details.

Author : Cyril Waechter
"""
import re
import typing
import ifcopenshell
import FreeCAD
from freecad.bem import utils

if typing.TYPE_CHECKING:
    from freecad.bem.typing import (  # pylint: disable=no-name-in-module, import-error
        MaterialFeature,
        LayerSetFeature,
        ConstituentSetFeature,
    )


class MaterialCreator:
    def __init__(self, ifc_importer=None):
        self.obj = None
        self.ifc_entity = None
        self.materials = {}
        self.material_layer_sets = {}
        self.material_constituent_sets = {}
        self.material_profile_sets = {}
        self.ifc_scale = 1
        self.fc_scale = 1
        if ifc_importer:
            self.ifc_scale = ifc_importer.ifc_scale
            self.fc_scale = ifc_importer.fc_scale
        self.ifc_importer = ifc_importer

    def create(self, obj, ifc_entity):
        self.obj = obj
        self.ifc_entity = ifc_entity
        self.parse_material(ifc_entity)

    def parse_material(self, ifc_entity):
        self.parse_associations(ifc_entity)
        if self.obj.Material:
            return
        entity_type = ifcopenshell.util.element.get_type(ifc_entity)
        if entity_type:
            self.parse_associations(entity_type)
            if self.obj.Material:
                return
        # When an element is composed of multiple elements
        if ifc_entity.IsDecomposedBy:
            # TODO: See in a real case how to handle every part and not only the first
            ifc_entity = ifc_entity.IsDecomposedBy[0].RelatedObjects[0]
            self.parse_associations(ifc_entity)

        # Set placement except for object type
        if hasattr(ifc_entity, "ObjectPlacement"):
            self.obj.Placement = self.ifc_importer.get_global_placement(
                ifc_entity.ObjectPlacement
            )

    def parse_associations(self, ifc_entity):
        for association in ifc_entity.HasAssociations:
            if association.is_a("IfcRelAssociatesMaterial"):
                material_select = association.RelatingMaterial
                if self.is_material_definition(material_select):
                    self.assign_material(material_select)
                elif material_select.is_a("IfcMaterialLayerSetUsage"):
                    self.create_layer_set_usage(material_select)
                elif material_select.is_a("IfcMaterialList"):
                    self.create_constituent_set_from_material_list(
                        material_select, ifc_entity
                    )
                else:
                    raise NotImplementedError(
                        f"{material_select.is_a()} not handled yet"
                    )

    @staticmethod
    def is_material_definition(material_select):
        """Material Definition is new to IFC4. So doing material_select.is_a("MaterialDefinition")
        in IFC2x3 would return False event if it is in IFC4 schema."""
        valid_class = (
            "IfcMaterial",
            "IfcMaterialLayer",
            "IfcMaterialLayerSet",
            "IfcMaterialProfile",
            "IfcMaterialProfileSet",
            "IfcMaterialConstituent",
            "IfcMaterialConstituentSet",
        )
        return material_select.is_a() in valid_class

    def create_layer_set_usage(self, usage):
        self.assign_material(usage.ForLayerSet)
        self.obj.Material.LayerSetDirection = usage.LayerSetDirection
        self.obj.Material.DirectionSense = usage.DirectionSense

    def assign_material(self, material_select):
        if material_select.is_a("IfcMaterial"):
            self.obj.Material = self.create_single(material_select)
        elif material_select.is_a("IfcMaterialLayerSet"):
            self.obj.Material = self.create_layer_set(material_select)
            utils.append(self.obj.Material, "AssociatedTo", self.obj)
        elif material_select.is_a("IfcMaterialConstituentSet"):
            self.obj.Material = self.create_constituent_set(material_select)
        elif material_select.is_a("IfcMaterialProfileSet"):
            self.obj.Material = self.create_profile_set(material_select)
        else:
            raise NotImplementedError(f"{material_select.is_a()} not handled yet")

    def create_single(self, material):
        if material.Name not in self.materials:
            return self.create_new_single(material)
        return self.materials[material.Name]

    def create_new_single(self, material):
        fc_material = Material.create(material)
        self.materials[material.Name] = fc_material
        return fc_material

    def create_layer_set(self, layer_set):
        if layer_set.LayerSetName not in self.material_layer_sets:
            fc_layer_set = LayerSet.create(layer_set, building_element=self.ifc_entity)
            layers = []
            layers_thickness = []
            for layer in layer_set.MaterialLayers:
                layers.append(self.create_single(layer.Material))
                layers_thickness.append(layer.LayerThickness * self.ifc_scale)
            fc_layer_set.MaterialLayers = layers
            fc_layer_set.Thicknesses = layers_thickness
            if not fc_layer_set.TotalThickness:
                fc_layer_set.TotalThickness = sum(layers_thickness) * self.fc_scale
            self.material_layer_sets[fc_layer_set.IfcName] = fc_layer_set
            return fc_layer_set
        return self.material_layer_sets[layer_set.LayerSetName]

    def create_constituent_set(self, constituent_set):
        if constituent_set.Name in self.material_constituent_sets:
            return self.material_constituent_sets[constituent_set.Name]
        # In MVD IFC4RV IfcMaterialLayerSet do not exist. Layer thicknesses are stored in a
        # quantity set. See: https://standards.buildingsmart.org/MVD/RELEASE/IFC4/ADD2_TC1/RV1_2/HTML/link/ifcmaterialconstituent.htm
        # Also see bsi forum: https://forums.buildingsmart.org/t/why-are-material-layer-sets-excluded-from-ifc4-reference-view-mvd/3638
        layers = {}
        for rel_definition in getattr(self.ifc_entity, "IsDefinedBy", ()):
            definition = rel_definition.RelatingPropertyDefinition
            if not definition.is_a("IfcElementQuantity"):
                continue
            # ArchiCAD stores it in standard Qto eg. Qto_WallBaseQuantities
            if definition.Name.endswith("BaseQuantities"):
                for quantity in definition.Quantities:
                    if not quantity.is_a("IfcPhysicalComplexQuantity"):
                        continue
                    layers[quantity.Name] = (
                        quantity.HasQuantities[0].LengthValue * self.ifc_scale
                    )
        if layers:
            fc_layer_set = LayerSet.create(
                constituent_set, building_element=self.ifc_entity
            )
            thicknesses = []
            materiallayers = []
            for layer in constituent_set.MaterialConstituents:
                thicknesses.append(layers[layer.Name])
                materiallayers.append(self.create_single(layer.Material))
            fc_layer_set.Thicknesses = thicknesses
            fc_layer_set.TotalThickness = sum(thicknesses) * self.fc_scale
            fc_layer_set.MaterialLayers = materiallayers
            self.material_constituent_sets[fc_layer_set.IfcName] = fc_layer_set
            return fc_layer_set

        # Constituent set which cannot be converted to layer sets eg. windows, complex walls
        fc_constituent_set = ConstituentSet.create(constituent_set)
        constituents = []
        constituents_fraction = []
        constituents_categories = []
        for constituent in constituent_set.MaterialConstituents:
            constituents.append(self.create_single(constituent.Material))
            constituents_fraction.append(constituent.Fraction or 0)
            constituents_categories.append(constituent.Category or "")
        fc_constituent_set.MaterialConstituents = constituents
        fc_constituent_set.Fractions = constituents_fraction
        fc_constituent_set.Categories = constituents_categories
        self.material_constituent_sets[fc_constituent_set.IfcName] = fc_constituent_set
        return fc_constituent_set

    def create_constituent_set_from_material_list(self, material_list, ifc_element):
        constituent_set = ConstituentSet.create()
        constituent_set.IfcType = material_list.is_a()
        constituent_set.IfcName = self.get_type_name(ifc_element) or "NoTypeName"
        constituent_set.Id = material_list.id()
        constituent_set.Label = f"{constituent_set.Id}_{constituent_set.IfcName}"
        materials = material_list.Materials
        constituent_set.Fractions = [1 / len(materials)] * len(materials)
        constituent_set.Categories = ["MaterialList"] * len(materials)
        material_constituents = list()
        for material in materials:
            material_constituents.append(self.create_single(material))
        constituent_set.MaterialConstituents = material_constituents
        self.obj.Material = constituent_set

    def create_profile_set(self, profile_set):
        if profile_set.Name not in self.material_profile_sets:
            fc_profile_set = ProfileSet.create(profile_set)
            profiles = []
            profiles_categories = []
            for profile in profile_set.MaterialProfiles:
                profiles.append(self.create_single(profile.Material))
                profiles_categories.append(profile.Category or "")
            fc_profile_set.MaterialProfiles = profiles
            fc_profile_set.Categories = profiles_categories
            self.material_profile_sets[fc_profile_set.IfcName] = fc_profile_set
            return fc_profile_set
        return self.material_profile_sets[profile_set.Name]

    def get_type_name(self, ifc_element):
        if ifc_element.is_a("IfcTypeObject"):
            return ifc_element.Name
        if ifc_element.ObjectType:
            return ifc_element.ObjectType
        for definition in ifc_element.IsDefinedBy:
            if definition.is_a("IfcRelDefinesByType"):
                return definition.RelatingType.Name


class ConstituentSet:
    attributes = ()
    psets_dict = {}
    parts_name = "Constituents"
    part_name = "Constituent"
    part_props = ("MaterialConstituents", "Fractions", "Categories")
    part_attribs = ("Id", "Fraction", "Category")

    def __init__(self, obj, ifc_entity):
        self.ifc_entity = ifc_entity
        self._init_properties(obj, ifc_entity)
        self.Type = "MaterialConstituentSet"  # pylint: disable=invalid-name
        obj.Proxy = self

    @classmethod
    def create(cls, ifc_entity=None) -> "ConstituentSetFeature":
        """Stantard FreeCAD FeaturePython Object creation method
        ifc_entity : Optionnally provide a base entity.
        """
        obj = FreeCAD.ActiveDocument.addObject(
            "Part::FeaturePython", "MaterialConstituentSet"
        )
        ConstituentSet(obj, ifc_entity)
        return obj

    def _init_properties(self, obj: "ConstituentSetFeature", ifc_entity) -> None:
        obj.addProperty("App::PropertyString", "IfcType", "IFC")
        obj.addProperty("App::PropertyFloatList", "Fractions", "BEM")
        obj.addProperty("App::PropertyStringList", "Categories", "BEM")
        ifc_attributes = "IFC Attributes"
        obj.addProperty("App::PropertyInteger", "Id", ifc_attributes)
        obj.addProperty("App::PropertyString", "IfcName", ifc_attributes)
        obj.addProperty("App::PropertyString", "Description", ifc_attributes)
        obj.addProperty("App::PropertyLinkList", "MaterialConstituents", ifc_attributes)

        if not ifc_entity:
            return
        obj.Id = ifc_entity.id()
        obj.IfcName = ifc_entity.Name or ""
        obj.Description = ifc_entity.Description or ""
        obj.Label = f"{obj.Id}_{obj.IfcName}"
        obj.IfcType = ifc_entity.is_a()


class LayerSet:
    attributes = ("TotalThickness",)
    psets_dict = {}
    parts_name = "Layers"
    part_name = "Layer"
    part_props = ("MaterialLayers", "Thicknesses")
    part_attribs = ("Id", "Thickness")

    def __init__(self, obj: "LayerSetFeature", ifc_entity, building_element) -> None:
        self.ifc_entity = ifc_entity
        self.building_element = building_element
        self._init_properties(obj, ifc_entity)
        self.materials = {}
        self.Type = "MaterialLayerSet"  # pylint: disable=invalid-name
        obj.Proxy = self

    @classmethod
    def create(cls, ifc_entity=None, building_element=None) -> "ConstituentSetFeature":
        """Stantard FreeCAD FeaturePython Object creation method
        ifc_entity : Optionnally provide a base entity.
        """
        obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", "Material")
        LayerSet(obj, ifc_entity, building_element)
        return obj

    def _init_properties(self, obj: "LayerSetFeature", ifc_entity) -> None:
        obj.addProperty("App::PropertyString", "IfcType", "IFC")
        obj.addProperty("App::PropertyFloatList", "Thicknesses", "BEM")
        ifc_attributes = "IFC Attributes"
        obj.addProperty("App::PropertyInteger", "Id", ifc_attributes)
        obj.addProperty("App::PropertyLinkList", "MaterialLayers", ifc_attributes)
        obj.addProperty("App::PropertyString", "IfcName", ifc_attributes)
        obj.addProperty("App::PropertyString", "Description", ifc_attributes)
        obj.addProperty("App::PropertyLength", "TotalThickness", ifc_attributes)
        obj.addProperty(
            "App::PropertyEnumeration", "LayerSetDirection", ifc_attributes
        ).LayerSetDirection = ["AXIS1", "AXIS2", "AXIS3"]
        obj.addProperty(
            "App::PropertyEnumeration", "DirectionSense", ifc_attributes
        ).DirectionSense = ["POSITIVE", "NEGATIVE"]
        obj.addProperty("App::PropertyLinkListHidden", "AssociatedTo", ifc_attributes)

        if not ifc_entity:
            return
        obj.Id = ifc_entity.id()
        if ifc_entity.is_a("IfcMaterialLayerSet"):
            obj.IfcName = ifc_entity.LayerSetName or ""
        elif ifc_entity.is_a("IfcMaterialConstituentSet"):  # for MVD IFC4RV
            obj.IfcName = ifc_entity.Name
        # Description is new to IFC4 so IFC2x3
        obj.Description = getattr(ifc_entity, "Description", None) or ""
        obj.Label = f"{obj.Id}_{obj.IfcName}"
        obj.IfcType = ifc_entity.is_a()
        building_element = self.building_element
        if building_element.is_a("IfcWall") or building_element.is_a("IfcWallType"):
            obj.LayerSetDirection = "AXIS2"
        else:
            for ifc_class in ["IfcSlab", "IfcSlabType", "IfcRoof", "IfcRoofType"]:
                if building_element.is_a(ifc_class):
                    obj.LayerSetDirection = "AXIS3"
                    break
        obj.DirectionSense = "POSITIVE"


class Material:
    attributes = ("Category",)
    psets_dict = {
        "Pset_MaterialCommon": ("MassDensity", "Porosity"),
        "Pset_MaterialOptical": (
            "VisibleTransmittance",
            "SolarTransmittance",
            "ThermalIrTransmittance",
            "ThermalIrEmissivityBack",
            "ThermalIrEmissivityFront",
        ),
        "Pset_MaterialThermal": (
            "SpecificHeatCapacity",
            "ThermalConductivity",
        ),
        "materialsdb.org_layer": ("MaterialsDBLayerId",),
    }
    parts_name = ""
    part_name = ""
    part_props = ()
    part_attribs = ()

    def __init__(self, obj, ifc_entity=None):
        self.ifc_entity = ifc_entity
        self._init_properties(obj)
        self.Type = "Material"  # pylint: disable=invalid-name
        obj.Proxy = self

    @classmethod
    def create(cls, ifc_entity=None) -> "MaterialFeature":
        """Stantard FreeCAD FeaturePython Object creation method
        ifc_entity : Optionnally provide a base entity.
        """
        obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", "Material")
        cls(obj, ifc_entity)
        return obj

    def _init_properties(self, obj) -> None:
        obj.addProperty("App::PropertyString", "IfcType", "IFC")
        ifc_attributes = "IFC Attributes"
        obj.addProperty("App::PropertyInteger", "Id", ifc_attributes)
        obj.addProperty("App::PropertyString", "IfcName", ifc_attributes)
        obj.addProperty("App::PropertyString", "Description", ifc_attributes)
        obj.addProperty("App::PropertyString", "Category", ifc_attributes)

        pset_name = "Pset_MaterialCommon"
        obj.addProperty("App::PropertyFloat", "MassDensity", pset_name)
        obj.addProperty("App::PropertyFloat", "Porosity", pset_name)

        pset_name = "Pset_MaterialOptical"
        obj.addProperty("App::PropertyFloat", "VisibleTransmittance", pset_name)
        obj.addProperty("App::PropertyFloat", "SolarTransmittance", pset_name)
        obj.addProperty("App::PropertyFloat", "ThermalIrTransmittance", pset_name)
        obj.addProperty("App::PropertyFloat", "ThermalIrEmissivityBack", pset_name)
        obj.addProperty("App::PropertyFloat", "ThermalIrEmissivityFront", pset_name)

        pset_name = "Pset_MaterialThermal"
        obj.addProperty("App::PropertyFloat", "SpecificHeatCapacity", pset_name)
        obj.addProperty("App::PropertyFloat", "ThermalConductivity", pset_name)

        pset_name = "materialsdb.org_layer"
        obj.addProperty("App::PropertyString", "MaterialsDBLayerId", pset_name)

        ifc_entity = self.ifc_entity

        if not ifc_entity:
            return
        obj.Id = ifc_entity.id()
        obj.IfcName = ifc_entity.Name
        obj.Label = f"{obj.Id}_{obj.IfcName}"
        # Description is new to IFC4 so IFC2x3 raise attribute error
        obj.Description = getattr(ifc_entity, "Description", "") or ""
        obj.IfcType = ifc_entity.is_a()
        for pset in getattr(ifc_entity, "HasProperties", ()):
            if pset.Name in self.psets_dict.keys():
                for prop in pset.Properties:
                    if prop.Name in self.psets_dict[pset.Name]:
                        setattr(obj, prop.Name, prop.NominalValue.wrappedValue)
        # Read materialdb.org layer id from entity name when authoring software is not able to export it
        m = re.search("id\((\S+)\)", ifc_entity.Name)
        if m:
            setattr(obj, "MaterialsDBLayerId", m.group(1))


class ProfileSet:
    attributes = ()
    psets_dict = {}
    parts_name = "Profiles"
    part_name = "Profile"
    part_props = ("MaterialProfiles",)
    part_attribs = (
        "Id",
        "Category",
    )

    def __init__(self, obj, ifc_entity):
        self.ifc_entity = ifc_entity
        self._init_properties(obj, ifc_entity)
        self.Type = "ProfileSet"  # pylint: disable=invalid-name
        obj.Proxy = self

    @classmethod
    def create(cls, ifc_entity=None) -> "ProfileSetFeature":
        """Stantard FreeCAD FeaturePython Object creation method
        ifc_entity : Optionnally provide a base entity.
        """
        obj = FreeCAD.ActiveDocument.addObject(
            "Part::FeaturePython", "MaterialProfileSet"
        )
        ProfileSet(obj, ifc_entity)
        return obj

    def _init_properties(self, obj: "ProfileSetFeature", ifc_entity) -> None:
        obj.addProperty("App::PropertyString", "IfcType", "IFC")
        obj.addProperty("App::PropertyStringList", "Categories", "BEM")
        ifc_attributes = "IFC Attributes"
        obj.addProperty("App::PropertyInteger", "Id", ifc_attributes)
        obj.addProperty("App::PropertyString", "IfcName", ifc_attributes)
        obj.addProperty("App::PropertyString", "Description", ifc_attributes)
        obj.addProperty("App::PropertyLinkList", "MaterialProfiles", ifc_attributes)

        if not ifc_entity:
            return
        obj.Id = ifc_entity.id()
        obj.IfcName = ifc_entity.Name or ""
        obj.Description = ifc_entity.Description or ""
        obj.Label = f"{obj.Id}_{obj.IfcName}"
        obj.IfcType = ifc_entity.is_a()


def get_type(ifc_entity):
    if ifc_entity.ObjectType:
        return ifc_entity.ObjectType
    for definition in ifc_entity.IsDefinedBy:
        if definition.is_a("IfcRelDefineByType"):
            return definition.RelatingType.Name
