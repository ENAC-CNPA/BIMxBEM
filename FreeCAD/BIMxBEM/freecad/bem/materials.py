# coding: utf8
import FreeCAD

class MaterialCreator:
    def __init__(self):
        self.obj = None
        self.materials = {}
        self.material_layer_sets = {}
        self.material_constituent_sets = {}

    def create(self, obj, ifc_entity):
        self.obj = obj
        self.parse_material(ifc_entity)

    def parse_material(self, ifc_entity):
        for association in ifc_entity.HasAssociations:
            if association.is_a("IfcRelAssociatesMaterial"):
                material_select = association.RelatingMaterial
                if material_select.is_a("IfcMaterialDefinition"):
                    self.assign_material(material_select)
                elif material_select.is_a("IfcMaterialLayerSetUsage"):
                    self.create_layer_set_usage(material_select)

    def create_layer_set_usage(self, usage):
        self.assign_material(usage.ForLayerSet)

    def assign_material(self, material):
        if material.is_a("IfcMaterial"):
            self.obj.Material = self.create_single(material)
        elif material.is_a("IfcMaterialLayerSet"):
            self.obj.Material = self.create_layer_set(material)
        elif material.is_a("IfcMaterialConstituentSet"):
            self.obj.Material = self.create_constituent_set(material)

    def create_single(self, material):
        if material.Name not in self.materials:
            return self.create_new_single(material)
        return self.materials[material.Name]

    def create_new_single(self, material):
        fc_material = Material.create(material)
        self.materials[fc_material.Name] = fc_material
        return fc_material

    def create_layer_set(self, layer_set):
        if layer_set.LayerSetName not in self.material_layer_sets:
            fc_layer_set = LayerSet.create(layer_set)
            layers = []
            layers_thickness = []
            for layer in layer_set.MaterialLayers:
                layers.append(self.create_single(layer.Material))
                layers_thickness.append(layer.LayerThickness)
            fc_layer_set.MaterialLayers = layers
            fc_layer_set.MaterialLayersThickness = layers_thickness
            if not fc_layer_set.TotalThickness:
                fc_layer_set.TotalThickness = sum(layers_thickness) * FreeCAD.Units.Metre.Value
            self.material_layer_sets[fc_layer_set.LayerSetName] = fc_layer_set
            return fc_layer_set
        return self.material_layer_sets[layer_set.LayerSetName]

    def create_constituent_set(self, constituent_set):
        if constituent_set.Name not in self.material_constituent_sets:
            fc_constituent_set = ConstituentSet.create(constituent_set)
            constituents = []
            constituents_fraction = []
            constituents_categories = []
            for constituent in constituent_set.MaterialLayers:
                constituents.append(self.create_single(constituent.Material))
                constituents_fraction.append(constituent.Fraction)
                constituents_categories.append(constituent.Category)
            fc_constituent_set.MaterialConstituents = constituents
            fc_constituent_set.MaterialConstituentFraction = constituents_fraction
            fc_constituent_set.MaterialConstituentCategories = constituents_categories
            self.material_constituent_sets[fc_constituent_set.Name] = fc_constituent_set
            return fc_constituent_set
        return self.material_constituent_sets[constituent_set.LayerSetName]


class ConstituentSet:
    def __init__(self, obj, ifc_entity):
        self.ifc_entity = ifc_entity
        self.setProperties(obj, ifc_entity)
        self.Type = "MaterialConstituentSet"
        obj.Proxy = self

    @classmethod
    def create(cls, ifc_entity=None):
        """Stantard FreeCAD FeaturePython Object creation method
        ifc_entity : Optionnally provide a base entity.
        """
        obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", "MaterialConstituentSet")
        ConstituentSet(obj, ifc_entity)
        return obj

    def setProperties(self, obj, ifc_entity):
        obj.addProperty("App::PropertyFloatList", "MaterialConstituentFraction", "BEM")
        obj.addProperty("App::PropertyStringList", "MaterialConstituentCategories", "BEM")
        ifc_attributes = "IFC Attributes"
        obj.addProperty("App::PropertyInteger", "Id", ifc_attributes)
        obj.addProperty("App::PropertyString", "IfcName", ifc_attributes)
        obj.addProperty("App::PropertyString", "Description", ifc_attributes)

        obj.Id = ifc_entity.id()
        obj.Name = ifc_entity.Name or ""
        obj.Description = ifc_entity.Description or ""
        obj.Label = f"{obj.Id}_{obj.Name}"


class LayerSet:
    def __init__(self, obj, ifc_entity):
        self.ifc_entity = ifc_entity
        self.setProperties(obj, ifc_entity)
        self.materials = {}
        self.Type = "MaterialLayerSet"
        obj.Proxy = self

    @classmethod
    def create(cls, ifc_entity=None, fallback_name=None):
        """Stantard FreeCAD FeaturePython Object creation method
        ifc_entity : Optionnally provide a base entity.
        """
        obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", "Material")
        LayerSet(obj, ifc_entity)
        return obj

    def setProperties(self, obj, ifc_entity):
        obj.addProperty("App::PropertyFloatList", "MaterialLayersThickness", "BEM")
        ifc_attributes = "IFC Attributes"
        obj.addProperty("App::PropertyInteger", "Id", ifc_attributes)
        obj.addProperty("App::PropertyLinkList", "MaterialLayers", ifc_attributes)
        obj.addProperty("App::PropertyString", "LayerSetName", ifc_attributes)
        obj.addProperty("App::PropertyString", "Description", ifc_attributes)
        obj.addProperty("App::PropertyLength", "TotalThickness", ifc_attributes)

        obj.Id = ifc_entity.id()
        obj.LayerSetName = ifc_entity.LayerSetName or ""
        # Description is new to IFC4 so IFC2x3 raise attribute error
        try:
            obj.Description = ifc_entity.Description or ""
        except AttributeError:
            pass
        obj.Label = f"{obj.Id}_{obj.LayerSetName}"


class Material:
    pset_dict = {
        "Pset_MaterialCommon": ("MassDensity", "Porosity"),
        "Pset_MaterialOptical": (
            "VisibleTransmittance",
            "SolarTransmittance",
            "ThermalIrTransmittance",
            "ThermalIrEmissivityBack",
            "ThermalIrEmissivityBack",
            "ThermalIrEmissivityFront",
        ),
        "Pset_MaterialThermal": ("SpecificHeatCapacity", "ThermalConductivity",),
    }

    def __init__(self, obj, ifc_entity=None):
        self.ifc_entity = ifc_entity
        self.setProperties(obj)
        self.Type = "Material"
        obj.Proxy = self

    @classmethod
    def create(cls, ifc_entity=None):
        """Stantard FreeCAD FeaturePython Object creation method
        ifc_entity : Optionnally provide a base entity.
        """
        obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", "Material")
        feature_python_object = cls(obj, ifc_entity)
        return obj

    def setProperties(self, obj):
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
        try:
            obj.Description = ifc_entity.Description or ""
        except AttributeError:
            pass
        if not hasattr(ifc_entity, "IsDefinedBy") or not ifc_entity.IsDefinedBy:
            return
        for definition in ifc_entity.IsDefinedBy:
            if not definition.is_a("IfcRelDefinesByProperties"):
                continue
            if definition.RelatingPropertyDefinition.is_a("IfcPropertySet"):
                if definition.RelatingPropertyDefinition.Name in self.pset_dict.keys():
                    for prop in definition.RelatingPropertyDefinition.HasProperties:
                        if (
                            prop.Name
                            in self.pset_dict[
                                definition.RelatingPropertyDefinition.Name
                            ]
                        ):
                            setattr(obj, prop.Name, prop.NominalValue)

    def add_product_definitions(self, element, obj):
        if not hasattr(element, "IsDefinedBy") or not element.IsDefinedBy:
            return
        for definition in element.IsDefinedBy:
            if not definition.is_a("IfcRelDefinesByProperties"):
                continue
            if definition.RelatingPropertyDefinition.is_a("IfcPropertySet"):
                self.add_pset(definition.RelatingPropertyDefinition, obj)
            elif definition.RelatingPropertyDefinition.is_a("IfcElementQuantity"):
                self.add_qto(definition.RelatingPropertyDefinition, obj)

    def add_pset(self, pset, obj):
        new_pset = obj.BIMObjectProperties.psets.add()
        new_pset.name = pset.Name
        if new_pset.name in schema.ifc.psets:
            for prop_name in schema.ifc.psets[new_pset.name][
                "HasPropertyTemplates"
            ].keys():
                prop = new_pset.properties.add()
                prop.name = prop_name
        # Invalid IFC, but some vendors like Solidworks do this so we accomodate it
        if not pset.HasProperties:
            return
        for prop in pset.HasProperties:
            if prop.is_a("IfcPropertySingleValue") and prop.NominalValue:
                index = new_pset.properties.find(prop.Name)
                if index >= 0:
                    new_pset.properties[index].string_value = str(
                        prop.NominalValue.wrappedValue
                    )
                else:
                    new_prop = new_pset.properties.add()
                    new_prop.name = prop.Name
                    new_prop.string_value = str(prop.NominalValue.wrappedValue)


def get_type(ifc_entity):
    if ifc_entity.ObjectType:
        return ifc_entity.ObjectType
    for definition in ifc_entity.IsDefinedBy:
        if definition.is_a("IfcRelDefineByType"):
            return definition.RelatingType.Name
