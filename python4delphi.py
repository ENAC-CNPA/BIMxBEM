import sys
sys.path.append("Mod/BIMxBEM")
from freecad.bem.boundaries import generate_bem_xml_from_file

GUI_UP = False

if GUI_UP:
    from PySide2 import QtCore, QtGui
    import FreeCADGui
    FreeCADGui.showMainWindow()

xml_str = generate_bem_xml_from_file(r"C:\git\BIMxBEM\IfcTestFiles\2Storey_2x3_A22.ifc", GUI_UP)
print(xml_str)

if GUI_UP:
    FreeCADGui.activeView().viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    FreeCADGui.exec_loop()