# coding: utf8
"""This patch extract a space and related component including boundaries into a new file"""
from typing import List, Any
import pathlib

import ifcopenshell


class IfcPatch:
    def __init__(self, src, file, logger, space_ids: List[int], **kwargs):
        self.src = src
        self.file = file
        self.logger = logger
        self.space_ids = space_ids
        self.kwargs = kwargs
        self.new_file = None
        self.elements: List[Any] = []

    def write_element(self, element):
        if not element or element in self.elements:
            return
        self.elements.append(element)
        new_file = self.new_file
        new_file.add(element)
        for inverse in self.file.get_inverse(element):
            if inverse.is_a("IfcRelAssociatesMaterial"):
                new_file.add(inverse)
            if inverse.is_a("IfcRelAggregates"):
                new_file.add(inverse)
                for obj in inverse.RelatedObjects:
                    self.write_element(obj)
            if not element.is_a("IfcTypeObject") and inverse.is_a(
                "IfcRelDefinesByType"
            ):
                new_file.add(inverse)
                self.write_element(inverse.RelatingType)

    def add_container(self, container, old_file, new_file):
        new_file.add(container)
        for inverse in old_file.get_inverse(container):
            new_file.add(inverse)
        try:
            self.add_container(
                container.Decomposes[0].RelatingObject, old_file, new_file
            )
        except IndexError:
            return

    def patch(self):
        ifc_file = self.file
        new_file = ifcopenshell.file(schema=ifc_file.schema)
        self.new_file = new_file
        for space_id in self.space_ids:
            self.write_space(space_id)
        new_file.write(self.output_path())

    def write_space(self, space_id):
        new_file = self.new_file
        ifc_file = self.file
        space = ifc_file.by_id(space_id)
        storey = space.Decomposes[0].RelatingObject
        self.add_container(storey, ifc_file, new_file)
        new_file.add(space)
        for entity in ifc_file.get_inverse(space):
            new_file.add(entity)
        for boundary in space.BoundedBy:
            new_file.add(boundary)
            self.write_element(boundary.RelatedBuildingElement)
        for rel in self.file.by_type("IfcRelVoidsElement"):
            try:
                if new_file.by_guid(rel.RelatingBuildingElement.GlobalId):
                    new_file.add(rel.RelatedOpeningElement)
                    new_file.add(rel)
            except RuntimeError:
                pass
        for rel in self.file.by_type("IfcRelFillsElement"):
            try:
                if new_file.by_guid(rel.RelatedBuildingElement.GlobalId):
                    new_file.add(rel.RelatingOpeningElement)
                    new_file.add(rel)
            except RuntimeError:
                pass

    def output_path(self) -> str:
        path = self.kwargs.get("output", None)
        if not path:
            path = pathlib.Path(self.src)
            path = str(
                path.parent.joinpath(f"{path.stem}_space{self.space_ids}{path.suffix}")
            )
        return path


def main():
    path = "IfcTestFiles/0014_Vernier112D_ENE_ModèleÉnergétique_R21_1LocalParEtage.ifc"
    ifc_file = ifcopenshell.open(path)
    IfcPatch(path, ifc_file, logger=None, space_ids=[10928,10219]).patch()


if __name__ == "__main__":
    main()
