# FreeCAD BIMxBEM Workbench
This workbench has following features :
* Read existing [IfcRelSpaceBoundary2ndlevel][1] produced by any authoring tool.
* Complete missing information (not filled by authoring tool or missing in older schema eg. 2x3).
* Adapt boundaries according local (Switzerland) standard for energy analysis.
* Translate gathered information in simpler xml format to be used by energy analysis software.
* Supported [schema versions][2] : 2x3, 4, 4.3
* Supported [file formats][3] :

| Name           | Extension | MIMEType           |
| :-------------:| :-------: | :----------------: |
| IFC-SPF (STEP) | .ifc      | application/x-step |
| ifcXML         | .ifcXML   | application/xml    |
| ifcZIP         | .ifcZIP   | application/zip    |

# Dependencies
* [ifcopenshell](https://github.com/IfcOpenShell/IfcOpenShell) : read ifc, generate geometries
* [FreeCAD](https://github.com/FreeCAD/FreeCAD) : manipulate geometries and store data (based on OpenCascade, see FreeCAD dependencies)

# Code tools used
* [black - The uncompromising Python code formatter][4]
* [pylint - It's not just a linter that annoys you! ][5]
* [mypy - Optional static typing for Python 3 and 2 (PEP 484)][6]

[1]: https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcrelspaceboundary2ndlevel.htm "IfcRelSpaceBoundary2ndlevel"
[2]: https://technical.buildingsmart.org/standards/ifc/ifc-schema-specifications/ "Ifc schema versions"
[3]: https://technical.buildingsmart.org/standards/ifc/ifc-formats/ "Ifc file formats"
[4]: https://github.com/psf/black
[5]: https://github.com/PyCQA/pylint
[6]: https://github.com/python/mypy