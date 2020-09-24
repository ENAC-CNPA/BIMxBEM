# FreeCAD BIMxBEM Workbench
This workbench has following features :
* Read existing [IfcRelSpaceBoundary2ndlevel][1] produced by any authoring tool.
* Complete missing information (not filled by authoring tool or missing in older schema eg. 2x3).
* Adapt boundaries according local (Switzerland) standard for energy analysis.
* Translate gathered information in simpler xml format to be used by energy analysis software.
* Supported [schema versions][2] : 2x3, 4, 4.1
* Supported [file formats][3] :

| Name           | Extension | MIMEType           |
| :-------------:| :-------: | :----------------: |
| IFC-SPF (STEP) | .ifc      | application/x-step |
| ifcXML         | .ifcXML   | application/xml    |

[1]: https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcrelspaceboundary2ndlevel.htm "IfcRelSpaceBoundary2ndlevel"
[2]: https://technical.buildingsmart.org/standards/ifc/ifc-schema-specifications/ "Ifc schema versions"
[3]: https://technical.buildingsmart.org/standards/ifc/ifc-formats/ "Ifc file formats"