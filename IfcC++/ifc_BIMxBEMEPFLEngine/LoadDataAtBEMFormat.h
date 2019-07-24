#pragma once

#include "ifc_Tree.h"
#include "ifc_TreePostTreatment.h"

//typedef std::map<STRUCT_IFCENTITY*, std::string> Map_Basified_Tree;
//
class LoadDataAtBEMFormat
{
public:
	LoadDataAtBEMFormat(double dbl_Minisurf);
	~LoadDataAtBEMFormat();

	int LoadLesosaiFormat(ifc_Tree* CurrentIfcTree);
	int GetLesosaiEntitiesNumber();
	int GetLesosaiEntitiesAttributesSize();
	int GetLesosaiEntitiesDefinition(string *&str_EntDef);
	int GetLesosaiLogFile(string *&str_LogFile);

	int ConvertIfcProject(STRUCT_IFCENTITY *st_IfcEnt);
	int ConvertIfcSite(STRUCT_IFCENTITY *st_IfcEnt);
	int ConvertIfcBuilding(STRUCT_IFCENTITY *st_IfcEnt);
	int ConvertIfcBuildingStorey(STRUCT_IFCENTITY *st_IfcEnt);
	int ConvertIfcSpace(STRUCT_IFCENTITY *st_IfcEnt);
	int ConvertIfcProductDefinitionShape(STRUCT_IFCENTITY *st_IfcEnt);
	int ConvertTIFCSurface(STRUCT_IFCENTITY *st_IfcEnt);
	int ConvertTIFCGeo2D(STRUCT_IFCENTITY *st_IfcEnt);
	int ConvertIfcFace(STRUCT_IFCENTITY *st_IfcEnt);
	int ConvertIfcSubFace(STRUCT_IFCENTITY *st_IfcEnt);
	int ConvertIfcConnectionSurfaceGeometry(STRUCT_IFCENTITY *st_IfcEnt);

	int ConvertBasifiedTree(Map_Basified_Tree *&map_BasifTree);

	int SpecificConversionOfContains(STRUCT_IFCENTITY *&st_IfcEnt, string &str_EntsDefinitions, string &str_ContainsName, string &str_InsideContainsName);
	int SpecificConversionOfContainsBuilding(STRUCT_IFCENTITY *&st_IfcEnt, string &str_EntsDefinitions, string &str_ContainsName, string &str_InsideContainsName);
	int SpecificConversionOfContainsForSpace(STRUCT_IFCENTITY *&st_IfcEnt, string &str_EntsDefinitions, string &str_ContainsName, string &str_InsideContainsName);
	int SpecificConversionOfContainsForFaceAndSubFace(STRUCT_IFCENTITY *&st_IfcEnt, string &str_EntsDefinitions, string &str_ContainsName, string &str_InsideContainsName);
	//int SpecificConversionOfContainsForSubFace(STRUCT_IFCENTITY *&st_IfcEnt, string &str_EntsDefinitions, string &str_ContainsName);
	int SpecificConversionOfContainsForTIFCGeo2D(STRUCT_IFCENTITY *&st_IfcEnt, string &str_EntsDefinitions, string &str_ContainsName, string &str_InsideContainsName);
	int SpecificConversionOfContainsForConnectionSurfaceGeometry(STRUCT_IFCENTITY *&st_IfcEnt, string &str_EntsDefinitions, string &str_ContainsName, string &str_InsideContainsName, string str_FaceToFaceName = "FaceToFace", string str_Centroid = "Centroid", string str_SideBySideName = "SideBySide");
	int SpecificConversionOfContainsForTIFCSurface(STRUCT_IFCENTITY *&st_IfcEnt, string &str_EntsDefinitions, string &str_ContainsName, string &str_InsideContainsName);
	int SpecificConversionOfNorthProject(STRUCT_IFCENTITY *&st_IfcEnt, string &str_EntsDefinitions/*, string &str_ContainsName, string &str_InsideContainsName*/);
	int GenericConversion(STRUCT_IFCENTITY *&st_IfcEnt, string &str_EntsDefinitions, string &str_ContainsName, string &str_InsideContainsName);
	int ConvertIfcEnt(STRUCT_IFCENTITY *&st_IfcEnt, string &str_Balise, string &str_EntsDefinitions, string &str_ContainsName, string &str_InsideContainsName);
	//int BasifyTreeFrom(STRUCT_IFCENTITY *&st_IfcTree, Map_Basified_Tree &map_BasifTree);
	void OpenSets();
	void CloseSets();

private:
	int LineForLevel(int &int_Level, string &str_EntsDefinitions, string &str_KW, string &str_ValKW);

	// Compilation de toutes les entités d'un même type
	string _str_ProjectsDefinitions;
	string _str_SitesDefinitions;
	string _str_BuildingsDefinitions;
	string _str_BuildingStoreysDefinitions;
	string _str_SpacesDefinitions;
	string _str_FacesDefinitions;
	string _str_SubFacesDefinitions;
	string _str_ProductDefinitionShapesDefinitions;
	string _str_ConnectionSurfaceGeometriesDefinitions;
	string _str_TIFCSurfacesDefinitions;
	string _str_TIFCGeo2DDefinitions;

	// Initialisation des différents mots-clés lexicaux
	string _str_LESOSAI_SetsRoot = "bimbem"; //Root_Of_TIFCSets
	string _str_LESOSAI_ProjetsSet = "Set_Of_TIFCProjects";		string _str_LESOSAI_Projets = "TIFCProjects";	string _str_LESOSAI_Projet = "TIFCProject";
	string _str_LESOSAI_SitesSet = "Set_Of_TIFCSites";			string _str_LESOSAI_Sites = "TIFCSites";		string _str_LESOSAI_Site = "TIFCSite";
	string _str_LESOSAI_BuildingsSet = "Set_Of_TIFCBuildings";	string _str_LESOSAI_Buildings = "TIFCBuildings";string _str_LESOSAI_Building = "TIFCBuilding";
	string _str_LESOSAI_StoreysSet = "Set_Of_TIFCStoreys";		string _str_LESOSAI_Storeys = "TIFCStoreys";	string _str_LESOSAI_Storey = "TIFCStorey";
	string _str_LESOSAI_ZonesSet = "Set_Of_TIFCZones";			string _str_LESOSAI_Zones = "TIFCZones";		string _str_LESOSAI_Zone = "TIFCZone";
	string _str_LESOSAI_SpacesSet = "Set_Of_TIFCSpaces";		string _str_LESOSAI_Spaces = "TIFCSpaces";		string _str_LESOSAI_Space = "TIFCSpace";
	string _str_LESOSAI_SurfacesSet = "Set_Of_TIFCSurfaces";	string _str_LESOSAI_Surfaces = "TIFCSurfaces";	string _str_LESOSAI_Surface = "TIFCSurface";
	string _str_LESOSAI_PolygonsSet = "Set_Of_TIFCPolygons";	string _str_LESOSAI_Polygons = "TIFCPolygons";	string _str_LESOSAI_Polygon = "TIFCPolygon";
	string _str_LESOSAI_PointsSet = "Set_Of_TIFCPoints";		string _str_LESOSAI_Points = "TIFCPoints";		string _str_LESOSAI_Point = "TIFCPoint";
	string _str_LESOSAI_Geo2DSet = "Set_Of_TIFCGeo2Ds";			string _str_LESOSAI_Geo2Ds = "TIFCGeo2Ds";		string _str_LESOSAI_Geo2D = "TIFCGeo2D";

	// Initialisation des différents mots-clés grammaticaux
	string DEB_KW0_L = "<";
	string DEB_KW1_L = "\t<";
	string DEB_KW2_L = "\t\t<";
	string DEB_KW3_L = "\t\t\t<";
	string DEB_KW4_L = "\t\t\t\t<";

	string KW_R = ">";
	string KW_Rn = ">\n";
	string KW1_Rn = "/>\n";

	string FIN_KW0_L = "</";
	string FIN_KW1_L = "\t</";
	string FIN_KW2_L = "\t\t</";
	string FIN_KW3_L = "\t\t\t</";
	string FIN_KW4_L = "\t\t\t\t</";

	//Param Géométrique: Surface minimale à partir de laquelle Lesosai considère la surface nulle
	double _dbl_MinimalSurface;

	// Compilation de toutes les entités (variable utilisée pour passer l'info au code appelant)
	string *_str_EntitiesDefinitions;
	string *_str_LogFile;
};

