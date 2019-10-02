import unittest
import FreeCAD
import Part
from IfcPython.read_boundaries import RelSpaceBoundary, make_relspaceboundary


class RelSpaceBoundaryTest(unittest.case.TestCase):
    def setUp(self):
        doc_name = "RelSpaceBoundaryTest"
        FreeCAD.newDocument(doc_name)
        FreeCAD.setActiveDocument(doc_name)
        self.doc_name = doc_name

    def test_make(self):
        FreeCAD.Console.PrintLog("Checking RelSpaceBoundary creation")
        polygon_verts = [
            FreeCAD.Vector(t)
            for t in [(0, 0, 0), (1000, 0, 0), (1000, 3000, 0), (0, 3000, 0), (0, 0, 0)]
        ]
        polygon = Part.makePolygon(polygon_verts)
        face = Part.Face(polygon)
        b1 = make_relspaceboundary("TestRelSpaceBoundary1")
        b2 = make_relspaceboundary("TestRelSpaceBoundary2")
        b1.Shape = b2.Shape = face
        # nfmt: off
        b1.Placement = FreeCAD.Matrix(
            1, 0, 0, 0,
            0, 0, -1, 0,
            0, 1, 0, 0,
            0, 0, 0, 1
        )
        b2.Placement = FreeCAD.Matrix(
            0, 0, 1, 0,
            1, 0, 0, 0,
            0, 1, 0, 0,
            0, 0, 0, 1
        )
        # fmt: on
        



    def tearDown(self):
        FreeCAD.closeDocument(self.doc_name)


if __name__ == "__main__":
    unittest.main()
