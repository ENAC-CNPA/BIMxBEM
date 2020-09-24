from setuptools import setup
import os
# from freecad.bem.version import __version__
# name: this is the name of the distribution.
# Packages using the same name here cannot be installed together

version_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 
                            "freecad", "bem", "version.py")
with open(version_path) as fp:
    exec(fp.read())

setup(name='freecad.bem',
      version=str(__version__),
      packages=['freecad',
                'freecad.bem'],
      maintainer="CyrilWaechter",
      maintainer_email="cyril.waechter@epfl.ch",
      url="https://c4science.ch/source/BIMxBEM",
      description=", installable with pip",
      install_requires=['ifcopenshell'], # should be satisfied by FreeCAD's system dependencies already
      include_package_data=True)
