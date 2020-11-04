# coding: utf8
"""This module reads IfcRelSpaceBoundary from an IFC file and display them in FreeCAD

© All rights reserved.
ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Laboratory CNPA, 2019-2020

See the LICENSE.TXT file for more details.

Author : Cyril Waechter
"""
import typing
import FreeCAD

if typing.TYPE_CHECKING:
    from freecad.bem.typing import (  # pylint: disable=no-name-in-module, import-error
        MaterialFeature,
        LayerSetFeature,
        ConstituentSetFeature,
    )


class MaterialCreator:
    def __init__(self, ifc_importer=None):
        self.obj = None
        self.materials = {}
        self.material_layer_sets = {}
        self.material_constituent_sets = {}
        self.ifc_scale = 1
        self.fc_scale = 1
        if ifc_importer:
            self.ifc_scale = ifc_importer.ifc_scale
            self.fc_scale = ifc_importer.fc_scale
        self.ifc_importer = ifc_importer

    def create(self, obj, ifc_entity):
        self.obj = obj
        self.parse_material(ifc_entity)

    def parse_material(self, ifc_entity):
        self.parse_associations(ifc_entity)
        if self.obj.Material:
            return
        # When an element is composed of multiple elements
        if ifc_entity.IsDecomposedBy:
            # TODO: See in a real case how to handle every part and not only the first
            ifc_entity = ifc_entity.IsDecomposedBy[0].RelatedObjects[0]
            self.parse_associations(ifc_entity)

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

    def assign_material(self, material_select):
        if material_select.is_a("IfcMaterial"):
            self.obj.Material = self.create_single(material_select)
        elif material_select.is_a("IfcMaterialLayerSet"):
            self.obj.Material = self.create_layer_set(material_select)
        elif material_select.is_a("IfcMaterialConstituentSet"):
            self.obj.Material = self.create_constituent_set(material_select)
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
            fc_layer_set = LayerSet.create(layer_set)
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
        if constituent_set.Name not in self.material_constituent_sets:
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
            self.material_constituent_sets[
                fc_constituent_set.IfcName
            ] = fc_constituent_set
            return fc_constituent_set
        return self.material_constituent_sets[constituent_set.Name]

    def create_constituent_set_from_material_list(self, material_list, ifc_element):
        constituent_set = ConstituentSet.create()
        constituent_set.IfcName = self.get_type_name(ifc_element)
        constituent_set.Id = material_list.id()
        constituent_set.Label = f"{constituent_set.Id}_{constituent_set.IfcName}"
        materials = material_list.Materials
        constituent_set.Fractions = [1 / len(materials)] * len(materials)
        constituent_set.Categories = ["MaterialList"] * len(materials)
        material_constituents = list()
        for material in materials:
            material_constituents.append(self.create_single(material))
        constituent_set.MaterialConstituents = material_constituents

    def get_type_name(self, ifc_element):
        if ifc_element.ObjectType:
            return ifc_element.ObjectType
        for definition in ifc_element.IsDefinedBy:
            if definition.is_a("IfcRelDefinesByType"):
                return definition.RelatingType.Name


class ConstituentSet:
    attributes = ()
    psets_dict = {}
    parts_name = "Layers"
    part_name = "Layer"
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

    def __init__(self, obj: "LayerSetFeature", ifc_entity) -> None:
        self.ifc_entity = ifc_entity
        self._init_properties(obj, ifc_entity)
        self.materials = {}
        self.Type = "MaterialLayerSet"  # pylint: disable=invalid-name
        obj.Proxy = self

    @classmethod
    def create(cls, ifc_entity=None) -> "ConstituentSetFeature":
        """Stantard FreeCAD FeaturePython Object creation method
        ifc_entity : Optionnally provide a base entity.
        """
        obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", "Material")
        LayerSet(obj, ifc_entity)
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

        if not ifc_entity:
            return
        obj.Id = ifc_entity.id()
        obj.IfcName = ifc_entity.LayerSetName or ""
        # Description is new to IFC4 so IFC2x3 raise attribute error
        try:
            obj.Description = ifc_entity.Description or ""
        except AttributeError:
            pass
        obj.Label = f"{obj.Id}_{obj.IfcName}"
        obj.IfcType = ifc_entity.is_a()


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


def get_type(ifc_entity):
    if ifc_entity.ObjectType:
        return ifc_entity.ObjectType
    for definition in ifc_entity.IsDefinedBy:
        if definition.is_a("IfcRelDefineByType"):
            return definition.RelatingType.Name
