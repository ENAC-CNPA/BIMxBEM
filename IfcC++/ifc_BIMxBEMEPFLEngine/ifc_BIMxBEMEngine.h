//
//
///////////////////////////////////////////////////
// INTERFACES A APPELER DEPUIS LE CODE "EXTERNE" //
///////////////////////////////////////////////////
//
//
#pragma once
#ifndef __HEADER__IFC_BIMxBEMEPFLENGINE__
#define __HEADER__IFC_BIMxBEMEPFLENGINE__
#endif

#include <list>
using namespace std;

#ifdef __cplusplus
extern "C" {
#endif 

	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_LoadXMLFileForBEM(char *chr_FilePath);
	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_UnLoadXMLFileForBEM();

	//Fournit le nombre de chacune des structures à passer
	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_GetNumberOfEachEntities(int &iNb_Project, 
																					int &iNb_Site, 
																					int &iNb_Building, 
																					int &iNb_BuildingStorey, 
																					int &iNb_Space, 
																					int &iNb_Face);
	//Fournit la dimension de chacun des attributs de chacune des structures à passer
	//Voir à fournir en même temps le noms des attributs, si besoin?
	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_GetNumberOfEachAttributesOfEachEntities(int* &iSizeByAttribute_Project,
																									int* &iSizeByAttribute_Site,
																									int* &iSizeByAttribute_Building,
																									int* &iSizeByAttribute_BuildingStorey,
																									int* &iSizeByAttribute_Space,
																									int* &iSizeByAttribute_Face);
	//Fournit la structure dans une chaine de caractères
	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_GetEntitiesDefinition(const char *&chr_EntDef);
	//__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_GetEntitiesDefinition(const char *&chr_EntDef);


#ifdef __cplusplus
}
#endif

