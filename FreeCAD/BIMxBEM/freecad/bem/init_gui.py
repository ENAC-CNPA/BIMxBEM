import os
import sys

import FreeCADGui as Gui
import FreeCAD as App

from freecad.bem import ICONPATH


class BIMxBEM(Gui.Workbench):
    """
    class which gets initiated at starup of the gui
    """

    MenuText = "BIMxBEM"
    ToolTip = "a simple template workbench"
    Icon = os.path.join(ICONPATH, "template_resource.svg")
    toolbox = ["Import", "Generate"]

    def GetClassName(self):
        return "Gui::PythonWorkbench"

    def Initialize(self):
        """
        This function is called at the first activation of the workbench.
        here is the place to import all the commands
        """
        sys.path.append("/home/cyril/git/BIMxBEM")
        from freecad.bem import commands

        App.Console.PrintMessage("switching to BIMxBEM workbench")
        self.appendToolbar("Tools", self.toolbox)
        self.appendMenu("Tools", self.toolbox)
        Gui.addCommand("Import", commands.ImportRelSpaceBoundary())
        Gui.addCommand("Generate", commands.GenerateBemBoundaries())

    def reload(self):
        from importlib import reload
        from freecad.bem import commands

        reload(commands)
        App.Console.PrintMessage("Reloading BIMxBEM workbench")
        self.appendToolbar("Tools", self.toolbox)
        self.appendMenu("Tools", self.toolbox)
        Gui.addCommand("Import", commands.ImportRelSpaceBoundary())
        Gui.addCommand("Generate", commands.GenerateBemBoundaries())

    def Activated(self):
        """
        code which should be computed when a user switch to this workbench
        """
        pass

    def Deactivated(self):
        """
        code which should be computed when this workbench is deactivated
        """
        pass


Gui.addWorkbench(BIMxBEM())
