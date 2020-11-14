# coding: utf8
"""This patch extract a space and related component including boundaries into a new file"""
import pathlib

import ifcopenshell


class IfcPatch:
    def __init__(self, src, file, logger, space_id: int, **kwargs):
        self.src = src
        self.file = file
        self.logger = logger
        self.space_id = space_id
        self.kwargs = kwargs
        self.new_file = None

    def write_element(self, element):
        if not element:
            return
        new_file = self.new_file
        new_file.add(element)
        for inverse in self.file.get_inverse(element):
            if inverse.is_a("IfcRelAssociatesMaterial"):
                new_file.add(inverse)
            if inverse.is_a("IfcRelAggregates"):
                new_file.add(inverse)
                for obj in inverse.RelatedObjects:
                    if not obj == element:
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
        space = ifc_file.by_id(self.space_id)
        storey = space.Decomposes[0].RelatingObject
        self.add_container(storey, ifc_file, new_file)
        new_file.add(space)
        for entity in ifc_file.get_inverse(space):
            new_file.add(entity)
        for boundary in space.BoundedBy:
            new_file.add(boundary)
            self.write_element(boundary.RelatedBuildingElement)
        new_file.write(self.output_path())

    def output_path(self) -> str:
        path = self.kwargs.get("output", None)
        if not path:
            path = pathlib.Path(self.src)
            path = str(
                path.parent.joinpath(f"{path.stem}_space{self.space_id}{path.suffix}")
            )
        return path


def main():
    path = "IfcTestFiles/3196 Aalseth Lane_R21_bem.ifc"
    ifc_file = ifcopenshell.open(path)
    IfcPatch(path, ifc_file, logger=None, space_id=5608).patch()


if __name__ == "__main__":
    main()
