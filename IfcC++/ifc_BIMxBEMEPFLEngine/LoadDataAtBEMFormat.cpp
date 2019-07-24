#include "LoadDataAtBEMFormat.h"

#include <string>

LoadDataAtBEMFormat::LoadDataAtBEMFormat(double dbl_Minisurf)
{
	_dbl_MinimalSurface = dbl_Minisurf;
}


LoadDataAtBEMFormat::~LoadDataAtBEMFormat()
{
}

//Convertit les structures attendues par Lesosai en chaine de caractères
int LoadDataAtBEMFormat::GetLesosaiEntitiesDefinition(string *&str_EntDef)
{
	int res = 0;
	str_EntDef = _str_EntitiesDefinitions;
	return res;
}

int LoadDataAtBEMFormat::GetLesosaiLogFile(string *&str_LogFile)
{
	int res = 0;
	str_LogFile = _str_LogFile;
	return res;
}

int LoadDataAtBEMFormat::GetLesosaiEntitiesNumber()
{
	int res = 0;
	return res;
}

int LoadDataAtBEMFormat::GetLesosaiEntitiesAttributesSize()
{
	int res = 0;
	return res;
}


//Transforme la structure générique ifc_Tree en des structures attendues par Lesosai
int LoadDataAtBEMFormat::LoadLesosaiFormat(ifc_Tree* CurrentIfcTree)
{
	int res = 0;

	// Allocation de la chaine de caractere (log pour consigner certaines infos: retrait des surfaces quasi-nulles par exple)
	_str_LogFile = new string();

	//Pour Post-traiter le tree => mettre l'arbre en rateau (sans duplication des entités)
	ifc_TreePostTreatment *cl_PostTreatmt = new ifc_TreePostTreatment(CurrentIfcTree);

	//Mise à plat de l'arbre (en rateau)
	Map_Basified_Tree *map_BasifTree=nullptr;
	if(cl_PostTreatmt)
		cl_PostTreatmt->BasifyTree(map_BasifTree);

	//Certains contours sont définis avec en dernier point le 1er points (loop)
	//Pour la suite des traitements, cela nous gêne (calcul du centre de gravité=CentroidsComputation, détection des points les plus proche=RelimitSideBySideSurfaces)
	//Retrait dans les contours (st_PointsDesContours) du derniers point lorsqu'il est égal au 1er (+ consigne bool bo_IsItLoop=true)
	if (cl_PostTreatmt)
		cl_PostTreatmt->RemoveLastPointOfLoopContours(_str_LogFile);

	//Calcul des surfaces IfcConnectionSurfaceGeometry 
	//  => à faire avant changement de coord car algo fonctionne en 2D => si la 3ème coord est la même pour toute!
	if (cl_PostTreatmt)
		cl_PostTreatmt->ComputeIfcConnectionSurfaceGeometrySurface();

	if (cl_PostTreatmt)
		cl_PostTreatmt->RemoveQuasiNullIfcConnectionSurfaceGeometrySurface(_dbl_MinimalSurface, _str_LogFile);
	//Relance pour nettoyer map_BasifTree
	if (cl_PostTreatmt)
		cl_PostTreatmt->BasifyTree(map_BasifTree);

	//Changement repere => repere projet
	if (cl_PostTreatmt)
		cl_PostTreatmt->TransformEntitiesToWorlCoordFrame();

	//Calcul des centres de gravité de chaque IfcConnectionSurfaceGeometry
	if (cl_PostTreatmt)
		cl_PostTreatmt->CentroidsComputation();

	//Repérage des IfcConnectionSurfaceGeometry en vis-à-vis et côte-à-côte
	if (cl_PostTreatmt)
		cl_PostTreatmt->FindFaceToFaceAndSideBySideSurfaces();

	//Raccord des IfcConnectionSurfaceGeometry en côte-à-côte
	if (cl_PostTreatmt)
		cl_PostTreatmt->RelimitSideBySideSurfaces(_str_LogFile);

	//Raccord des IfcConnectionSurfaceGeometry en côte-à-côte
	if (cl_PostTreatmt)
		cl_PostTreatmt->CreateTIFCSurfaces();

	//Ajout des TIFCSurfaces à ifc_TreePostTreatment::_map_BasifTree
	if (cl_PostTreatmt)
		cl_PostTreatmt->CompleteBasifiedTreeFromByTIFCSurfaces();

	// Allocation de la chaine de caractere (fourniture des données du Tree via cette chaine de caractere)
	_str_EntitiesDefinitions = new string();

	//Conversion des entités dans la chaine de caractere _str_EntitiesDefinitions (membre de la classe)
	ConvertBasifiedTree(map_BasifTree);

	return res;
}

//int LoadDataAtBEMFormat::BasifyTreeFrom(STRUCT_IFCENTITY *&st_IfcTree, Map_Basified_Tree &map_BasifTree)
//{
//	int res = 0;
//	//Memo adresse pointeur (si existe pas ajouté) et son type "Ifc" 
//	// => la map permet de ne pas référencer de multiple fois une même entité 
//	//    dans l'arbre, des entités sont référencés plusieurs fois car elles appartiennent à plusieurs objets
//	map_BasifTree[st_IfcTree] = st_IfcTree->ch_Type;
//
//	list <STRUCT_IFCENTITY*> ::iterator it_Elem;
//	for (it_Elem = (st_IfcTree->st_Contains).begin(); it_Elem != (st_IfcTree->st_Contains).end(); it_Elem++)
//	{
//		BasifyTreeFrom((*it_Elem), map_BasifTree);
//	}// for (it_Elem = (st_IfcTree->st_Contains).begin(); it_Elem != (st_IfcTree->st_Contains).end(); it_Elem++)
//
//	return res;
//}
//
int LoadDataAtBEMFormat::ConvertBasifiedTree(Map_Basified_Tree *&map_BasifTree)
{
	int res = 0;

	OpenSets();

	std::map<STRUCT_IFCENTITY*, std::string>::iterator it_Elem;
	for (it_Elem = map_BasifTree->begin(); it_Elem != map_BasifTree->end(); it_Elem++)
	{
		if (it_Elem->second == "IfcConnectionSurfaceGeometry")
		{
			ConvertIfcConnectionSurfaceGeometry(it_Elem->first);
			//Pour Lesosai
			ConvertTIFCGeo2D(it_Elem->first);
		}// if (it_Elem->second == "IfcConnectionSurfaceGeometry")
		else if (it_Elem->second == "TIFCSurface")
			ConvertTIFCSurface(it_Elem->first);
		else if (it_Elem->second == "IfcFace")
			ConvertIfcFace(it_Elem->first);
		else if (it_Elem->second == "IfcCurveBoundedPlane")
			ConvertIfcSubFace(it_Elem->first);
		//else if (it_Elem->second == "IfcProductDefinitionShape")
		//	ConvertIfcProductDefinitionShape(it_Elem->first);
		else if (it_Elem->second == "IfcSpace")
			ConvertIfcSpace(it_Elem->first);
		else if (it_Elem->second == "IfcBuildingStorey")
			ConvertIfcBuildingStorey(it_Elem->first);
		else if (it_Elem->second == "IfcBuilding")
			ConvertIfcBuilding(it_Elem->first);
		else if (it_Elem->second == "IfcSite")
			ConvertIfcSite(it_Elem->first);
		else if (it_Elem->second == "IfcProject")
			ConvertIfcProject(it_Elem->first);
	}// for (it_Elem = map_BasifTree.begin(); it_Elem != map_BasifTree.end(); it_Elem++)

	CloseSets();

	//Merge des 2 Set_Of_TIFCPolygons: _str_FacesDefinitions + _str_SubFacesDefinitions
	string str_Deb = "";
	string str_Fin = "";
	int int_Level = 10;
	string str_ValKW = "";
	string str_KW = _str_LESOSAI_PolygonsSet;
	LineForLevel(int_Level, str_Deb, str_KW, str_ValKW);
	int_Level = 11;
	LineForLevel(int_Level, str_Fin, str_KW, str_ValKW);
	//string str_Deb = DEB_KW0_L + _str_LESOSAI_PolygonsSet + KW_R;
	//string str_Fin = FIN_KW0_L + _str_LESOSAI_PolygonsSet + KW_R;

	//Retrait fin du paragraphe </Set_Of_TIFCPolygons>
	_str_FacesDefinitions = _str_FacesDefinitions.substr(0, _str_FacesDefinitions.length() - str_Fin.length());
	//Retrait début du paragraphe <Set_Of_TIFCPolygons>
	_str_SubFacesDefinitions = _str_SubFacesDefinitions.substr(str_Deb.length(), _str_SubFacesDefinitions.length() - str_Deb.length());

	int_Level = 0;
	str_ValKW = "";
	str_KW = _str_LESOSAI_SetsRoot;
	LineForLevel(int_Level, *_str_EntitiesDefinitions, str_KW, str_ValKW);

	*_str_EntitiesDefinitions += /*DEB_KW0_L + _str_LESOSAI_SetsRoot + KW_Rn
		+*/_str_ProjectsDefinitions
		+ _str_SitesDefinitions
		+ _str_BuildingsDefinitions
		+ _str_BuildingStoreysDefinitions
		+ _str_SpacesDefinitions
		//+ _str_ProductDefinitionShapesDefinitions
		+ _str_TIFCSurfacesDefinitions
		+ _str_TIFCGeo2DDefinitions
		+ _str_FacesDefinitions
		+ _str_SubFacesDefinitions
		//+_str_ConnectionSurfaceGeometriesDefinitions
		/*+ FIN_KW0_L + _str_LESOSAI_SetsRoot + KW_R*/
		;

	int_Level = 1;
	str_ValKW = "";
	str_KW = _str_LESOSAI_SetsRoot;
	LineForLevel(int_Level, *_str_EntitiesDefinitions, str_KW, str_ValKW);

	return res;
}

void LoadDataAtBEMFormat::OpenSets()
{
	int int_Level = 10;
	string str_ValKW = "";
	string str_KW = _str_LESOSAI_ProjetsSet;
	LineForLevel(int_Level, _str_ProjectsDefinitions, str_KW, str_ValKW);
	str_KW = _str_LESOSAI_SitesSet;
	LineForLevel(int_Level, _str_SitesDefinitions, str_KW, str_ValKW);
	str_KW = _str_LESOSAI_BuildingsSet;
	LineForLevel(int_Level, _str_BuildingsDefinitions, str_KW, str_ValKW);
	str_KW = _str_LESOSAI_StoreysSet;
	LineForLevel(int_Level, _str_BuildingStoreysDefinitions, str_KW, str_ValKW);
	str_KW = _str_LESOSAI_SpacesSet;
	LineForLevel(int_Level, _str_SpacesDefinitions, str_KW, str_ValKW);
	str_KW = _str_LESOSAI_SurfacesSet;
	LineForLevel(int_Level, _str_TIFCSurfacesDefinitions, str_KW, str_ValKW);
	str_KW = _str_LESOSAI_PolygonsSet;
	LineForLevel(int_Level, _str_FacesDefinitions, str_KW, str_ValKW);
	str_KW = _str_LESOSAI_Geo2DSet;
	LineForLevel(int_Level, _str_TIFCGeo2DDefinitions, str_KW, str_ValKW);
	str_KW = _str_LESOSAI_PolygonsSet;
	LineForLevel(int_Level, _str_SubFacesDefinitions, str_KW, str_ValKW);
	str_KW = "ProductDefinitionShapes";
	LineForLevel(int_Level, _str_ProductDefinitionShapesDefinitions, str_KW, str_ValKW);
	str_KW = "ConnectionSurfaceGeometries";
	LineForLevel(int_Level, _str_ConnectionSurfaceGeometriesDefinitions, str_KW, str_ValKW);

	//_str_ProjectsDefinitions += DEB_KW0_L + _str_LESOSAI_ProjetsSet + KW_R;
	//_str_SitesDefinitions += DEB_KW0_L + _str_LESOSAI_SitesSet + KW_R;
	//_str_BuildingsDefinitions += DEB_KW0_L + _str_LESOSAI_BuildingsSet + KW_R;
	//_str_BuildingStoreysDefinitions += DEB_KW0_L + _str_LESOSAI_StoreysSet + KW_R;
	//_str_SpacesDefinitions += DEB_KW0_L + _str_LESOSAI_SpacesSet + KW_R;
	//_str_TIFCSurfacesDefinitions += DEB_KW0_L + _str_LESOSAI_SurfacesSet + KW_R;
	//_str_FacesDefinitions += DEB_KW0_L + _str_LESOSAI_PolygonsSet + KW_R;
	//_str_TIFCGeo2DDefinitions += DEB_KW0_L + _str_LESOSAI_Geo2DSet + KW_R;
	//_str_SubFacesDefinitions += DEB_KW0_L + _str_LESOSAI_PolygonsSet + KW_R;//"SubFaces"
	//_str_ProductDefinitionShapesDefinitions += DEB_KW0_L + "ProductDefinitionShapes" + KW_R;
	//_str_ConnectionSurfaceGeometriesDefinitions += DEB_KW0_L + "ConnectionSurfaceGeometries" + KW_R;
}

void LoadDataAtBEMFormat::CloseSets()
{
	int int_Level = 11;
	string str_ValKW = "";
	string str_KW = _str_LESOSAI_ProjetsSet;
	LineForLevel(int_Level, _str_ProjectsDefinitions, str_KW, str_ValKW);
	str_KW = _str_LESOSAI_SitesSet;
	LineForLevel(int_Level, _str_SitesDefinitions, str_KW, str_ValKW);
	str_KW = _str_LESOSAI_BuildingsSet;
	LineForLevel(int_Level, _str_BuildingsDefinitions, str_KW, str_ValKW);
	str_KW = _str_LESOSAI_StoreysSet;
	LineForLevel(int_Level, _str_BuildingStoreysDefinitions, str_KW, str_ValKW);
	str_KW = _str_LESOSAI_SpacesSet;
	LineForLevel(int_Level, _str_SpacesDefinitions, str_KW, str_ValKW);
	str_KW = _str_LESOSAI_SurfacesSet;
	LineForLevel(int_Level, _str_TIFCSurfacesDefinitions, str_KW, str_ValKW);
	str_KW = _str_LESOSAI_PolygonsSet;
	LineForLevel(int_Level, _str_FacesDefinitions, str_KW, str_ValKW);
	str_KW = _str_LESOSAI_Geo2DSet;
	LineForLevel(int_Level, _str_TIFCGeo2DDefinitions, str_KW, str_ValKW);
	str_KW = _str_LESOSAI_PolygonsSet;
	LineForLevel(int_Level, _str_SubFacesDefinitions, str_KW, str_ValKW);
	str_KW = "ProductDefinitionShapes";
	LineForLevel(int_Level, _str_ProductDefinitionShapesDefinitions, str_KW, str_ValKW);
	str_KW = "ConnectionSurfaceGeometries";
	LineForLevel(int_Level, _str_ConnectionSurfaceGeometriesDefinitions, str_KW, str_ValKW);

	//_str_ProjectsDefinitions += FIN_KW0_L + _str_LESOSAI_ProjetsSet + KW_R;
	//_str_SitesDefinitions += FIN_KW0_L + _str_LESOSAI_SitesSet + KW_R;
	//_str_BuildingsDefinitions += FIN_KW0_L + _str_LESOSAI_BuildingsSet + KW_R;
	//_str_BuildingStoreysDefinitions += FIN_KW0_L + _str_LESOSAI_StoreysSet + KW_R;
	//_str_SpacesDefinitions += FIN_KW0_L + _str_LESOSAI_SpacesSet + KW_R;
	//_str_TIFCSurfacesDefinitions += FIN_KW0_L + _str_LESOSAI_SurfacesSet + KW_R;
	//_str_FacesDefinitions += FIN_KW0_L + _str_LESOSAI_PolygonsSet + KW_R;
	//_str_TIFCGeo2DDefinitions += FIN_KW0_L + _str_LESOSAI_Geo2DSet + KW_R;
	//_str_SubFacesDefinitions += FIN_KW0_L + _str_LESOSAI_PolygonsSet + KW_R;//"SubFaces"
	//_str_ProductDefinitionShapesDefinitions += FIN_KW0_L + "ProductDefinitionShapes" + KW_R;
	//_str_ConnectionSurfaceGeometriesDefinitions += FIN_KW0_L + "ConnectionSurfaceGeometries" + KW_R;
}

int LoadDataAtBEMFormat::LineForLevel(int &int_Level, string &str_EntsDefinitions, string &str_KW, string &str_ValKW)
{
	switch (int_Level)
	{
	case 0: str_EntsDefinitions = str_EntsDefinitions + DEB_KW0_L + str_KW + KW_Rn; break;
	case 1: str_EntsDefinitions = str_EntsDefinitions + FIN_KW0_L + str_KW + KW_Rn; break;
	case 10: str_EntsDefinitions = str_EntsDefinitions + DEB_KW1_L + str_KW + KW_Rn; break;
	case 11: str_EntsDefinitions = str_EntsDefinitions + FIN_KW1_L + str_KW + KW_Rn; break;
	case 20: str_EntsDefinitions = str_EntsDefinitions + DEB_KW2_L + str_KW + KW_Rn; break;
	case 21: str_EntsDefinitions = str_EntsDefinitions + FIN_KW2_L + str_KW + KW_Rn; break;
	case 30: str_EntsDefinitions = str_EntsDefinitions + DEB_KW3_L + str_KW + KW_R + str_ValKW + FIN_KW0_L + str_KW + KW_Rn; break;
	case 32: str_EntsDefinitions = str_EntsDefinitions + DEB_KW3_L + str_KW + KW_Rn; break;
	case 33: str_EntsDefinitions = str_EntsDefinitions + FIN_KW3_L + str_KW + KW_Rn; break;
	case 40: str_EntsDefinitions = str_EntsDefinitions + DEB_KW4_L + str_KW + KW_R + str_ValKW + FIN_KW0_L + str_KW + KW_Rn; break;
	case 42: str_EntsDefinitions = str_EntsDefinitions + DEB_KW4_L + str_ValKW + KW1_Rn; break;
	default: return 1;
	}// switch (int_Level)

	return 0;
}

int LoadDataAtBEMFormat::ConvertIfcEnt(STRUCT_IFCENTITY *&st_IfcEnt, string &str_Balise, string &str_EntsDefinitions, string &str_ContainsName, string &str_InsideContainsName)
{
	int res = 0;

	// Entête Début
	int int_Level = 20;
	string str_KW = str_Balise;
	string str_ValKW = "";
	LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
	//str_EntsDefinitions = str_EntsDefinitions + DEB_KW1_L + str_Balise + KW_R;

	// Id, Name, Contains
	GenericConversion(st_IfcEnt, str_EntsDefinitions, str_ContainsName, str_InsideContainsName);

	// Entête Fin
	int_Level = 21;
	LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
	//str_EntsDefinitions = str_EntsDefinitions + FIN_KW1_L + str_Balise + KW_R;

	return res;
}

int LoadDataAtBEMFormat::GenericConversion(STRUCT_IFCENTITY *&st_IfcEnt, string &str_EntsDefinitions, string &str_ContainsName, string &str_InsideContainsName)
{
	int res = 0;

	// Id
	int int_Level = 30;
	string str_KW = "Id";
	string str_ValKW = st_IfcEnt->ch_Id;
	LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
	//str_EntsDefinitions = str_EntsDefinitions + DEB_KW2_L + str_KW + KW_R + st_IfcEnt->ch_Id + FIN_KW0_L + str_KW + KW_R;

	// GlobalId
	str_KW= "GlobalId";
	str_ValKW = st_IfcEnt->ch_GlobalId;
	LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
	//str_EntsDefinitions = str_EntsDefinitions + DEB_KW2_L + str_KW + KW_R + st_IfcEnt->ch_GlobalId + FIN_KW0_L + str_KW + KW_R;

	// Name
	str_KW= "Name";
	str_ValKW = st_IfcEnt->ch_Name;
	LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
	//str_EntsDefinitions = str_EntsDefinitions + DEB_KW2_L + str_KW + KW_R + st_IfcEnt->ch_Name + FIN_KW0_L + str_KW + KW_R;

	// Contains
	if (string(st_IfcEnt->ch_Type) == string("IfcFace"))
	{
		res = SpecificConversionOfContainsForFaceAndSubFace(st_IfcEnt, str_EntsDefinitions, str_ContainsName, str_InsideContainsName);
	}// if (string(st_IfcEnt->ch_Type) == string("IfcFace"))
	else if (string(st_IfcEnt->ch_Type) == string("IfcCurveBoundedPlane"))
	{
		res = SpecificConversionOfContainsForFaceAndSubFace(st_IfcEnt, str_EntsDefinitions, str_ContainsName, str_InsideContainsName);
	}// else if (string(st_IfcEnt->ch_Type) == string("IfcCurveBoundedPlane"))
	else if (string(st_IfcEnt->ch_Type) == string("IfcSpace"))
	{
			res = SpecificConversionOfContainsForSpace(st_IfcEnt, str_EntsDefinitions, str_ContainsName, str_InsideContainsName);
	}// else if (string(st_IfcEnt->ch_Type) == string("IfcSpace"))
	else if (string(st_IfcEnt->ch_Type) == string("IfcConnectionSurfaceGeometry"))
	{
		if(str_InsideContainsName == _str_LESOSAI_Polygon)
			res = SpecificConversionOfContainsForTIFCGeo2D(st_IfcEnt, str_EntsDefinitions, str_ContainsName, str_InsideContainsName);
		else
			res = SpecificConversionOfContainsForConnectionSurfaceGeometry(st_IfcEnt, str_EntsDefinitions, str_ContainsName, str_InsideContainsName);
	}// else if (string(st_IfcEnt->ch_Type) == string("IfcConnectionSurfaceGeometry"))
	else if (string(st_IfcEnt->ch_Type) == string("TIFCSurface"))
	{
		res = SpecificConversionOfContainsForTIFCSurface(st_IfcEnt, str_EntsDefinitions, str_ContainsName, str_InsideContainsName);
	}// else if (string(st_IfcEnt->ch_Type) == string("TIFCSurface"))
	else if (string(st_IfcEnt->ch_Type) == string("IfcBuilding"))
	{
		res = SpecificConversionOfContainsBuilding(st_IfcEnt, str_EntsDefinitions, str_ContainsName, str_InsideContainsName);
	}// else if (string(st_IfcEnt->ch_Type) == string("TIFCSurface"))
	else
	{
		if (string(st_IfcEnt->ch_Type) == string("IfcProject"))
			res = SpecificConversionOfNorthProject(st_IfcEnt, str_EntsDefinitions/*, str_ContainsName, str_InsideContainsName*/);

		res = SpecificConversionOfContains(st_IfcEnt, str_EntsDefinitions, str_ContainsName, str_InsideContainsName);
	}// else if (string(st_IfcEnt->ch_Type) == string("IfcFace"))

	return res;
}

int LoadDataAtBEMFormat::SpecificConversionOfContainsForTIFCGeo2D(STRUCT_IFCENTITY *&st_IfcEnt, string &str_EntsDefinitions, string &str_ContainsName, string &str_InsideContainsName)
{
	int res = 0;

	// Contains
	res = SpecificConversionOfContains(st_IfcEnt, str_EntsDefinitions, str_ContainsName, str_InsideContainsName);

	//Map_String_String::iterator it_MapVal;
	if (st_IfcEnt->map_DefValues)
	{
		for (Map_String_String::iterator it_MapVal = (st_IfcEnt->map_DefValues)->begin(); it_MapVal != (st_IfcEnt->map_DefValues)->end(); it_MapVal++)
		{
			int int_Level = 30;
			string str_KW = (*it_MapVal).first;
			string str_ValKW = (*it_MapVal).second;
			LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
			//str_EntsDefinitions = str_EntsDefinitions + DEB_KW2_L + (*it_MapVal).first + "=" + (*it_MapVal).second + KW_R;
		}// for (it_MapVal = (st_IfcEnt->map_DefValues)->begin(); it_MapVal != (st_IfcEnt->map_DefValues)->end(); it_MapVal++)
	}// if (st_IfcEnt->map_DefValues)

	return res;
}

int LoadDataAtBEMFormat::SpecificConversionOfContainsForConnectionSurfaceGeometry(STRUCT_IFCENTITY *&st_IfcEnt, string &str_EntsDefinitions, string &str_ContainsName, string &str_InsideContainsName, string str_FaceToFaceName, string str_Centroid, string str_SideBySideName)
{
	int res = 0;

	// Contains
	res = SpecificConversionOfContains(st_IfcEnt, str_EntsDefinitions, str_ContainsName, str_InsideContainsName);

	//Map_String_String::iterator it_MapVal;
	if (st_IfcEnt->map_DefValues)
	{
		for (Map_String_String::iterator it_MapVal = (st_IfcEnt->map_DefValues)->begin(); it_MapVal != (st_IfcEnt->map_DefValues)->end(); it_MapVal++)
		{
			int int_Level = 30;
			string str_KW = (*it_MapVal).first;
			string str_ValKW = (*it_MapVal).second;
			LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
			//str_EntsDefinitions = str_EntsDefinitions + DEB_KW2_L + (*it_MapVal).first + "=" + (*it_MapVal).second + KW_R;
		}// for (it_MapVal = (st_IfcEnt->map_DefValues)->begin(); it_MapVal != (st_IfcEnt->map_DefValues)->end(); it_MapVal++)
	}// if (st_IfcEnt->map_DefValues)

	// FaceToface
	int int_Level = 32;
	string str_KW = str_FaceToFaceName;
	string str_ValKW = "";
	LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
	//string str_Balise = str_FaceToFaceName;
	//str_EntsDefinitions = str_EntsDefinitions + DEB_KW2_L + str_Balise + KW_R;
	//list <STRUCT_IFCENTITY*> ::iterator it_Elem;
	for (list <STRUCT_IFCENTITY*> ::iterator it_Elem = (st_IfcEnt->st_FaceToFace).begin(); it_Elem != (st_IfcEnt->st_FaceToFace).end(); it_Elem++)
	{
		int_Level = 40;
		str_KW = "";
		str_ValKW = (*it_Elem)->ch_Id;
		LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
		//str_EntsDefinitions = str_EntsDefinitions + DEB_KW3_L + (*it_Elem)->ch_Id + KW_R;
	}// for (it_Elem = (st_IfcEnt->st_Contains).begin(); it_Elem != (st_IfcEnt->st_Contains).end(); it_Elem++)
	int_Level = 33;
	str_KW = str_FaceToFaceName;
	str_ValKW = "";
	LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
	//str_EntsDefinitions = str_EntsDefinitions + FIN_KW2_L + str_Balise + KW_R;

	// SideBySide
	int_Level = 32;
	str_KW = str_SideBySideName;
	str_ValKW = "";
	LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
	//str_Balise = str_SideBySideName;
	//str_EntsDefinitions = str_EntsDefinitions + DEB_KW2_L + str_Balise + KW_R;
	//list <STRUCT_IFCENTITY*> ::iterator it_Elem;
	//for (it_Elem = (st_IfcEnt->st_SideBySide).begin(); it_Elem != (st_IfcEnt->st_SideBySide).end(); it_Elem++)
	//map <STRUCT_IFCENTITY*,bool> ::iterator it_ElemBool;
	//for (map <STRUCT_IFCENTITY*, pair<double, bool>> ::iterator it_ElemBool = (st_IfcEnt->mp_SideBySide).begin(); it_ElemBool != (st_IfcEnt->mp_SideBySide).end(); it_ElemBool++)
	for (set <pair<STRUCT_IFCENTITY*, pair<double, bool>>> ::iterator it_ElemBool = (st_IfcEnt->mp_SideBySide).begin(); it_ElemBool != (st_IfcEnt->mp_SideBySide).end(); it_ElemBool++)
	{
		string bo_val = "><PAS RACCORDEE";
		if ((*it_ElemBool).second.second) bo_val = "><RACCORDEE";

		int_Level = 40;
		str_KW = "";
		str_ValKW = (*it_ElemBool).first->ch_Id + bo_val;
		LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
		//str_EntsDefinitions = str_EntsDefinitions + DEB_KW3_L + (*it_ElemBool).first->ch_Id + bo_val + KW_R;
	}// for (it_ElemBool = (st_IfcEnt->mp_SideBySide).begin(); it_ElemBool != (st_IfcEnt->mp_SideBySide).end(); it_ElemBool++)
	int_Level = 33;
	str_KW = str_SideBySideName;
	str_ValKW = "";
	LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
	//str_EntsDefinitions = str_EntsDefinitions + FIN_KW2_L + str_Balise + KW_R;

	// Centroid
	int_Level = 32;
	str_KW = str_Centroid;
	str_ValKW = "";
	LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
	//str_Balise = str_Centroid;
	//str_EntsDefinitions = str_EntsDefinitions + DEB_KW2_L + str_Balise + KW_R;
	//list <double*> ::iterator it_DbVal;
	for (list <double*> ::iterator it_DbVal = (st_IfcEnt->db_Centroid).begin(); it_DbVal != (st_IfcEnt->db_Centroid).end(); it_DbVal++)
	{
		int_Level = 40;
		str_KW = "";
		str_ValKW = to_string(*(*it_DbVal));
		LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
		//str_EntsDefinitions = str_EntsDefinitions + DEB_KW3_L + to_string(*(*it_DbVal)) + KW_R;
	}// for (it_Elem = (st_IfcEnt->st_Contains).begin(); it_Elem != (st_IfcEnt->st_Contains).end(); it_Elem++)
	int_Level = 33;
	str_KW = str_Centroid;
	str_ValKW = "";
	LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
	//str_EntsDefinitions = str_EntsDefinitions + FIN_KW2_L + str_Balise + KW_R;

	// TIFCSurface
	int_Level = 32;
	str_KW = _str_LESOSAI_Surface;
	str_ValKW = "";
	LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
	//str_Balise = _str_LESOSAI_Surface;
	//str_EntsDefinitions = str_EntsDefinitions + DEB_KW2_L + str_Balise + KW_R;
	if (st_IfcEnt->st_TIFCSurface)
	{
		int_Level = 40;
		str_KW = "";
		str_ValKW = st_IfcEnt->st_TIFCSurface->ch_Id;
		LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
		//str_EntsDefinitions = str_EntsDefinitions + DEB_KW3_L + st_IfcEnt->st_TIFCSurface->ch_Id + KW_R;
	}// if (st_IfcEnt->st_TIFCSurface)
	int_Level = 33;
	str_KW = _str_LESOSAI_Surface;
	str_ValKW = "";
	LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
	//str_EntsDefinitions = str_EntsDefinitions + FIN_KW2_L + str_Balise + KW_R;

	return res;
}

int LoadDataAtBEMFormat::SpecificConversionOfContainsForTIFCSurface(STRUCT_IFCENTITY *&st_IfcEnt, string &str_EntsDefinitions, string &str_ContainsName, string &str_InsideContainsName)
{
	int res = 0;

	// Contains
	//string str_Balise = str_ContainsName;
	//str_EntsDefinitions = str_EntsDefinitions + DEB_KW2_L + str_Balise + KW_R;
	int i_Ind=1;
	list <STRUCT_IFCENTITY*> ::iterator it_Elem;
	for (it_Elem = (st_IfcEnt->st_Contains).begin(); it_Elem != (st_IfcEnt->st_Contains).end(); it_Elem++)
	{
		// geoInt1 et geoInt2 (geoInt2 est vide si c'est une TIFCsurface en vis-à-vis avec extérieur)
		int int_Level = 30;
		string str_KW = "geoInt" + std::to_string(i_Ind);
		string str_ValKW = (*it_Elem)->ch_Id;
		LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
		//str_EntsDefinitions = str_EntsDefinitions + DEB_KW2_L + "geoInt" + std::to_string(i_Ind) + "=" + (*it_Elem)->ch_Id + KW_R;
		list <STRUCT_IFCENTITY*> ::iterator it_Elem2;
		for (it_Elem2 = ((*it_Elem)->st_BelongsTo).begin(); it_Elem2 != ((*it_Elem)->st_BelongsTo).end(); it_Elem2++)
		{
			if (string((*it_Elem2)->ch_Type) == "IfcSpace")
			{
				int_Level = 30;
				str_KW = "room" + std::to_string(i_Ind);
				str_ValKW = (*it_Elem2)->ch_Id;
				LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
				//str_EntsDefinitions = str_EntsDefinitions + DEB_KW2_L + "room" + std::to_string(i_Ind) + "=" + (*it_Elem2)->ch_Id + KW_R;
			}// if (string((*it_Elem2)->ch_Type) == "IfcSpace")

			// Type de TIFCSurface : ifcWall, ifcCeiling, ifcFloor
			else if (i_Ind == 1)
			{
				int_Level = 30;
				str_KW = "surfType";
				if ((*it_Elem2)->ch_PredifinedType != nullptr /*&& (*it_Elem2)->ch_PredifinedType != "notdefined"*/)
					str_ValKW = (*it_Elem2)->ch_PredifinedType;
				else
					str_ValKW = (*it_Elem2)->ch_Type;
				LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
				//str_EntsDefinitions = str_EntsDefinitions + DEB_KW2_L + "surfType" + "=" + (*it_Elem2)->ch_Type + KW_R;
			}// else if (i_Ind == 1)
		}// for (it_Elem = (st_IfcEnt->st_Contains).begin(); it_Elem != (st_IfcEnt->st_Contains).end(); it_Elem++)
		i_Ind ++ ;
	}// for (it_Elem = (st_IfcEnt->st_Contains).begin(); it_Elem != (st_IfcEnt->st_Contains).end(); it_Elem++)
	//str_EntsDefinitions = str_EntsDefinitions + FIN_KW2_L + str_Balise + KW_R;

	return res;
}

int LoadDataAtBEMFormat::SpecificConversionOfContainsBuilding(STRUCT_IFCENTITY *&st_IfcEnt, string &str_EntsDefinitions, string &str_ContainsName, string &str_InsideContainsName)
{
	int res = 0;

	res = SpecificConversionOfContains(st_IfcEnt, str_EntsDefinitions, str_ContainsName, str_InsideContainsName);

	// boucle à partir du building sur ses storey, puis les espaces puis les ifconnecturface puis les TIFCSurface
	//	pour recuperer tous les TIFCSurface du building(de maniere unique) = > map ou liste(+unique()) puis lire les id des TIFCSurface
	list <STRUCT_IFCENTITY*> li_TIFCSurfaceByBuilding;
	list <STRUCT_IFCENTITY*> ::iterator it_ElemStorey;
	for (it_ElemStorey = (st_IfcEnt->st_Contains).begin(); it_ElemStorey != (st_IfcEnt->st_Contains).end(); it_ElemStorey++)
	{
		list <STRUCT_IFCENTITY*> ::iterator it_ElemSpace;
		for (it_ElemSpace = ((*it_ElemStorey)->st_Contains).begin(); it_ElemSpace != ((*it_ElemStorey)->st_Contains).end(); it_ElemSpace++)
		{
			list <STRUCT_IFCENTITY*> ::iterator it_ElemCSAndBE;
			for (it_ElemCSAndBE = ((*it_ElemSpace)->st_Contains).begin(); it_ElemCSAndBE != ((*it_ElemSpace)->st_Contains).end(); it_ElemCSAndBE++)
			{
				if((*it_ElemCSAndBE)->st_TIFCSurface)
					li_TIFCSurfaceByBuilding.push_back((*it_ElemCSAndBE)->st_TIFCSurface);
			}// for (it_ElemCSAndBE = ((*it_ElemSpace)->st_Contains).begin(); it_ElemCSAndBE != ((*it_ElemSpace)->st_Contains).end(); it_ElemCSAndBE++)
		}// for (it_ElemSpace = ((*it_ElemStorey)->st_Contains).begin(); it_ElemSpace != ((*it_ElemStorey)->st_Contains).end(); it_ElemSpace++)
	}// for (it_ElemStorey = (st_IfcEnt->st_Contains).begin(); it_ElemStorey != (st_IfcEnt->st_Contains).end(); it_ElemStorey++)
	li_TIFCSurfaceByBuilding.sort();
	li_TIFCSurfaceByBuilding.unique();

	// surfaces
	int int_Level = 32;
	string str_KW = "surfaces" /*+ _str_LESOSAI_Surfaces*/;
	string str_ValKW = "";
	LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
	//string str_Balise = "surfaces : " + _str_LESOSAI_Surfaces;
	//str_EntsDefinitions = str_EntsDefinitions + DEB_KW2_L + str_Balise + KW_R;

	list <STRUCT_IFCENTITY*> ::iterator it_Elem;
	for (it_Elem = li_TIFCSurfaceByBuilding.begin(); it_Elem != li_TIFCSurfaceByBuilding.end(); it_Elem++)
	{
		int_Level = 40;
		str_KW = _str_LESOSAI_Surface;
		str_ValKW = (*it_Elem)->ch_Id;
		LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
		//str_EntsDefinitions = str_EntsDefinitions + DEB_KW3_L + _str_LESOSAI_Surface + "=" + (*it_Elem)->ch_Id + KW_R;
	}// for (it_Elem = (st_IfcEnt->st_Contains).begin(); it_Elem != (st_IfcEnt->st_Contains).end(); it_Elem++)

	int_Level = 33;
	str_KW = "surfaces" /*+ _str_LESOSAI_Surfaces*/;
	str_ValKW = "";
	LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
	//str_EntsDefinitions = str_EntsDefinitions + FIN_KW2_L + str_Balise + KW_R;

	return res;
}


int LoadDataAtBEMFormat::SpecificConversionOfContains(STRUCT_IFCENTITY *&st_IfcEnt, string &str_EntsDefinitions, string &str_ContainsName, string &str_InsideContainsName)
{
	int res = 0;

	// Contains
	int int_Level = 32;
	string str_KW = str_ContainsName;
	string str_ValKW = "";
	LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
	//string str_Balise = str_ContainsName;
	//str_EntsDefinitions = str_EntsDefinitions + DEB_KW2_L + str_Balise + KW_R;
	list <STRUCT_IFCENTITY*> ::iterator it_Elem;
	for (it_Elem = (st_IfcEnt->st_Contains).begin(); it_Elem != (st_IfcEnt->st_Contains).end(); it_Elem++)
	{
		if (str_InsideContainsName == "")
		{
			int_Level = 40;
			str_KW = "";
			str_ValKW = (*it_Elem)->ch_Id;
			LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
			//str_EntsDefinitions = str_EntsDefinitions + DEB_KW3_L + (*it_Elem)->ch_Id + KW_R;
		}// if (str_InsideContainsName == "")
		else
		{
			int_Level = 40;
			str_KW = str_InsideContainsName;
			str_ValKW = (*it_Elem)->ch_Id;
			LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
			//str_EntsDefinitions = str_EntsDefinitions + DEB_KW3_L + str_InsideContainsName + "=" + (*it_Elem)->ch_Id + KW_R;
		}// else if (str_InsideContainsName == "")
	}// for (it_Elem = (st_IfcEnt->st_Contains).begin(); it_Elem != (st_IfcEnt->st_Contains).end(); it_Elem++)
	int_Level = 33;
	str_KW = str_ContainsName;
	str_ValKW = "";
	LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
	//str_EntsDefinitions = str_EntsDefinitions + FIN_KW2_L + str_Balise + KW_R;

	return res;
}

int LoadDataAtBEMFormat::SpecificConversionOfContainsForSpace(STRUCT_IFCENTITY *&st_IfcEnt, string &str_EntsDefinitions, string &str_ContainsName, string &str_InsideContainsName)
{
	int res = 0;

	// Contains
	int int_Level = 32;
	string str_KW = str_ContainsName;
	string str_ValKW = "";
	LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
	//string str_Balise = str_ContainsName;
	//str_EntsDefinitions = str_EntsDefinitions + DEB_KW2_L + str_Balise + KW_R;
	list <STRUCT_IFCENTITY*> ::iterator it_Elem;
	for (it_Elem = (st_IfcEnt->st_Contains).begin(); it_Elem != (st_IfcEnt->st_Contains).end(); it_Elem++)
	{
		if (string((*it_Elem)->ch_Type) == string("IfcProductDefinitionShape"))
		{
			//on saute l'étage "IfcProductDefinitionShape" pour descendre sur les faces
			list <STRUCT_IFCENTITY*> ::iterator it_SsElem;
			for (it_SsElem = ((*it_Elem)->st_Contains).begin(); it_SsElem != ((*it_Elem)->st_Contains).end(); it_SsElem++)
			{
				int int_Level = 40;
				string str_KW = str_InsideContainsName;
				string str_ValKW = (*it_SsElem)->ch_Id;
				LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
				//str_EntsDefinitions = str_EntsDefinitions + DEB_KW3_L + str_InsideContainsName + "=" + (*it_SsElem)->ch_Id + KW_R;
			}// for (it_Elem = (st_IfcEnt->st_Contains).begin(); it_Elem != (st_IfcEnt->st_Contains).end(); it_Elem++)
		}// for (it_SsElem = ((*it_Elem)->st_Contains).begin(); it_SsElem != ((*it_Elem)->st_Contains).end(); it_SsElem++)
	}// for (it_Elem = (st_IfcEnt->st_Contains).begin(); it_Elem != (st_IfcEnt->st_Contains).end(); it_Elem++)
	int_Level = 33;
	str_KW = str_ContainsName;
	str_ValKW = "";
	LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
	//str_EntsDefinitions = str_EntsDefinitions + FIN_KW2_L + str_Balise + KW_R;

	Map_String_String::iterator it_MapVal;
	for (it_MapVal = (st_IfcEnt->map_DefValues)->begin(); it_MapVal != (st_IfcEnt->map_DefValues)->end(); it_MapVal++)
	{
		int_Level = 30;
		str_KW = (*it_MapVal).first;
		str_ValKW = (*it_MapVal).second;
		LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
		//str_EntsDefinitions = str_EntsDefinitions + DEB_KW2_L + (*it_MapVal).first + "=" + (*it_MapVal).second + KW_R;
	}// for (it_MapVal = (st_IfcEnt->map_DefValues)->begin(); it_MapVal != (st_IfcEnt->map_DefValues)->end(); it_MapVal++)

	return res;
}

int LoadDataAtBEMFormat::SpecificConversionOfContainsForFaceAndSubFace(STRUCT_IFCENTITY *&st_IfcEnt, string &str_EntsDefinitions, string &str_ContainsName, string &str_InsideContainsName)
{
	//lire la liste des points et non contains
	int res = 0;

	// Contains
	int int_Level = 32;
	string str_KW = str_ContainsName;
	string str_ValKW = "";
	LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
	//string str_Balise = str_ContainsName;
	//str_EntsDefinitions = str_EntsDefinitions + DEB_KW2_L + str_Balise + KW_R;
	list <list <double*>> ::iterator it_llPt;
	for (it_llPt = (st_IfcEnt->st_PointsDesContours).begin(); it_llPt != (st_IfcEnt->st_PointsDesContours).end(); it_llPt++)
	{
		list <double*> ::iterator it_lPt;
		for (it_lPt = (*it_llPt).begin(); it_lPt != (*it_llPt).end(); it_lPt++)
		{
			int_Level = 42;
			str_KW = "";
			str_ValKW = "point x=\"" + std::to_string(*(*it_lPt)) + "\""; it_lPt++;
			str_ValKW += " y=\"" + std::to_string(*(*it_lPt)) + "\""; it_lPt++;
			str_ValKW += " z=\"" + std::to_string(*(*it_lPt)) + "\"";
			//str_ValKW = std::to_string(*(*it_lPt));
			LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
			//str_EntsDefinitions = str_EntsDefinitions + DEB_KW3_L + std::to_string(*(*it_lPt)) + KW_R;
		}// for (it_lPt = (*it_llPt).begin(); it_lPt != (*it_llPt).end(); it_lPt++)
	}// for (it_llPt = (st_IfcEnt->st_PointsDesContours).begin(); it_llPt != (st_IfcEnt->st_PointsDesContours).end(); it_llPt++)
	int_Level = 33;
	str_KW = str_ContainsName;
	str_ValKW = "";
	LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
	//str_EntsDefinitions = str_EntsDefinitions + FIN_KW2_L + str_Balise + KW_R;

	return res;
}

int LoadDataAtBEMFormat::SpecificConversionOfNorthProject(STRUCT_IFCENTITY *&st_IfcEnt, string &str_EntsDefinitions/*, string &str_ContainsName, string &str_InsideContainsName*/)
{
	//lire la liste des points et non contains
	int res = 0;
	string str_North = "north";
	// Contains
	int int_Level = 32;
	string str_KW = str_North;
	string str_ValKW = str_North;
	LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
	//string str_Balise = str_ContainsName;
	//str_EntsDefinitions = str_EntsDefinitions + DEB_KW2_L + str_Balise + KW_R;
	list <double*> ::iterator it_lPt;
	for (it_lPt = (st_IfcEnt->db_Centroid).begin(); it_lPt != (st_IfcEnt->db_Centroid).end(); it_lPt++)
	{
		//list <double*> ::iterator it_lPt;
		//for (it_lPt = (*it_llPt).begin(); it_lPt != (*it_llPt).end(); it_lPt++)
		//{
			int_Level = 42;
			str_KW = "";
			str_ValKW = "point x=\"" + std::to_string(*(*it_lPt)) + "\""; it_lPt++;
			str_ValKW += " y=\"" + std::to_string(*(*it_lPt)) + "\""; it_lPt++;
			str_ValKW += " z=\"" + std::to_string(*(*it_lPt)) + "\"";
			//str_ValKW = std::to_string(*(*it_lPt));
			LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
			//str_EntsDefinitions = str_EntsDefinitions + DEB_KW3_L + std::to_string(*(*it_lPt)) + KW_R;
		//}// for (it_lPt = (*it_llPt).begin(); it_lPt != (*it_llPt).end(); it_lPt++)
	}// for (it_llPt = (st_IfcEnt->st_PointsDesContours).begin(); it_llPt != (st_IfcEnt->st_PointsDesContours).end(); it_llPt++)
	int_Level = 33;
	str_KW = str_North;
	str_ValKW = "";
	LineForLevel(int_Level, str_EntsDefinitions, str_KW, str_ValKW);
	//str_EntsDefinitions = str_EntsDefinitions + FIN_KW2_L + str_Balise + KW_R;

	return res;
}

//int LoadDataAtBEMFormat::SpecificConversionOfContainsForSubFace(STRUCT_IFCENTITY *&st_IfcEnt, string &str_EntsDefinitions, string &str_ContainsName)
//{
//	//lire la liste des points et non contains
//	int res = 0;
//
//	string str_Balise = str_ContainsName;
//	str_EntsDefinitions = str_EntsDefinitions + DEB_KW2_L + str_Balise + KW_R;
//	list <list <double*>> ::iterator it_llPt;
//	for (it_llPt = (st_IfcEnt->st_PointsDesContours).begin(); it_llPt != (st_IfcEnt->st_PointsDesContours).end(); it_llPt++)
//	{
//		list <double*> ::iterator it_lPt;
//		for (it_lPt = (*it_llPt).begin(); it_lPt != (*it_llPt).end(); it_lPt++)
//			str_EntsDefinitions = str_EntsDefinitions + DEB_KW3_L + std::to_string(*(*it_lPt)) + KW_R;
//	}// for (it_llPt = (st_IfcEnt->st_PointsDesContours).begin(); it_llPt != (st_IfcEnt->st_PointsDesContours).end(); it_llPt++)
//	str_EntsDefinitions = str_EntsDefinitions + FIN_KW2_L + str_Balise + KW_R;
//
//	return res;
//}
//

int LoadDataAtBEMFormat::ConvertIfcProject(STRUCT_IFCENTITY *st_IfcEnt)
{
	int res = 0;

	// Id, Name, Contains
	string str_Balise = _str_LESOSAI_Projet;
	string str_ContainsName = "sites" /*+ _str_LESOSAI_Sites*/;
	string str_InsideContainsName = _str_LESOSAI_Site;
	ConvertIfcEnt(st_IfcEnt, str_Balise, _str_ProjectsDefinitions, str_ContainsName, str_InsideContainsName);

	return res;
}

int LoadDataAtBEMFormat::ConvertIfcSite(STRUCT_IFCENTITY *st_IfcEnt)
{
	int res = 0;

	// Id, Name, Contains
	string str_Balise = _str_LESOSAI_Site;
	string str_ContainsName = "buildings" /*+ _str_LESOSAI_Buildings*/;
	string str_InsideContainsName = _str_LESOSAI_Building;
	ConvertIfcEnt(st_IfcEnt, str_Balise, _str_SitesDefinitions, str_ContainsName, str_InsideContainsName);

	return res;
}

int LoadDataAtBEMFormat::ConvertIfcBuilding(STRUCT_IFCENTITY *st_IfcEnt)
{
	int res = 0;

	// Id, Name, Contains
	string str_Balise = _str_LESOSAI_Building;
	string str_ContainsName = "storeys" /*+ _str_LESOSAI_Storeys*/;
	string str_InsideContainsName = _str_LESOSAI_Storey;
	ConvertIfcEnt(st_IfcEnt, str_Balise, _str_BuildingsDefinitions, str_ContainsName, str_InsideContainsName);

	return res;
}

int LoadDataAtBEMFormat::ConvertIfcBuildingStorey(STRUCT_IFCENTITY *st_IfcEnt)
{
	int res = 0;

	// Id, Name, Contains
	string str_Balise = _str_LESOSAI_Storey;
	string str_ContainsName = "spaces" /*+ _str_LESOSAI_Spaces*/;
	string str_InsideContainsName = _str_LESOSAI_Space;
	//string str_ContainsName = "spaces";
	ConvertIfcEnt(st_IfcEnt, str_Balise, _str_BuildingStoreysDefinitions, str_ContainsName, str_InsideContainsName);

	return res;
}

int LoadDataAtBEMFormat::ConvertIfcSpace(STRUCT_IFCENTITY *st_IfcEnt)
{
	int res = 0;

	// Id, Name, Contains
	string str_Balise = _str_LESOSAI_Space;
	string str_ContainsName = "geo" /*+ _str_LESOSAI_Polygons*/;
	string str_InsideContainsName = _str_LESOSAI_Polygon;
	ConvertIfcEnt(st_IfcEnt, str_Balise, _str_SpacesDefinitions, str_ContainsName, str_InsideContainsName);

	return res;
}

int LoadDataAtBEMFormat::ConvertIfcFace(STRUCT_IFCENTITY *st_IfcEnt)
{
	int res = 0;

	// Id, Name, Contains
	string str_Balise = _str_LESOSAI_Polygon;
	string str_ContainsName = "points" /*+ _str_LESOSAI_Points*/;
	string str_InsideContainsName = "";
	ConvertIfcEnt(st_IfcEnt, str_Balise, _str_FacesDefinitions, str_ContainsName, str_InsideContainsName);

	return res;
}

int LoadDataAtBEMFormat::ConvertTIFCSurface(STRUCT_IFCENTITY *st_IfcEnt)
{
	int res = 0;

	// Id, Name, Contains
	string str_Balise = _str_LESOSAI_Surface;
	string str_ContainsName = "";
	string str_InsideContainsName = "";
	ConvertIfcEnt(st_IfcEnt, str_Balise, _str_TIFCSurfacesDefinitions, str_ContainsName, str_InsideContainsName);

	return res;
}

int LoadDataAtBEMFormat::ConvertTIFCGeo2D(STRUCT_IFCENTITY *st_IfcEnt)
{
	int res = 0;

	// Id, Name, Contains
	string str_Balise = _str_LESOSAI_Geo2D /*+ " (IfcConnectionSurfaceGeometry->SubFace)"*/;
	string str_ContainsName = "poly" /*+ _str_LESOSAI_Polygon*/;
	string str_InsideContainsName = _str_LESOSAI_Polygon ;//SubFace
	ConvertIfcEnt(st_IfcEnt, str_Balise, _str_TIFCGeo2DDefinitions, str_ContainsName, str_InsideContainsName);

	return res;
}

int LoadDataAtBEMFormat::ConvertIfcSubFace(STRUCT_IFCENTITY *st_IfcEnt)
{
	int res = 0;

	// Id, Name, Contains
	string str_Balise = _str_LESOSAI_Polygon;//"SubFace"
	string str_ContainsName = "points" /*+ _str_LESOSAI_Points*/;//"points"
	string str_InsideContainsName = "";
	ConvertIfcEnt(st_IfcEnt, str_Balise, _str_SubFacesDefinitions, str_ContainsName, str_InsideContainsName);

	return res;
}

int LoadDataAtBEMFormat::ConvertIfcConnectionSurfaceGeometry(STRUCT_IFCENTITY *st_IfcEnt)
{
	int res = 0;

	// Id, Name, Contains
	string str_Balise = "IfcConnectionSurfaceGeometry";
	string str_ContainsName = "contains";
	string str_InsideContainsName = "SubFace";
	ConvertIfcEnt(st_IfcEnt, str_Balise, _str_ConnectionSurfaceGeometriesDefinitions, str_ContainsName, str_InsideContainsName);

	return res;
}

int LoadDataAtBEMFormat::ConvertIfcProductDefinitionShape(STRUCT_IFCENTITY *st_IfcEnt)
{
	int res = 0;

	// Id, Name, Contains
	string str_Balise = "IfcProductDefinitionShape";
	string str_ContainsName = "contains";
	string str_InsideContainsName = "";
	ConvertIfcEnt(st_IfcEnt, str_Balise, _str_ProductDefinitionShapesDefinitions, str_ContainsName, str_InsideContainsName);

	return res;
}

