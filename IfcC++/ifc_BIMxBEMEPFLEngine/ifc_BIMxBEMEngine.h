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

//////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////DEBUT/////////////////////////////////////////////////
/////////////////// TEST INTEROPERABILITE Pascal C++ /////////////////////////////////
//////////////////////////////////////////////////////////////////////////////////////
//////////////////////////////////////////////////////////////////////////////////////


//struct STRUCT_IFCENTITY_TEST {
//	const char *ch_GlobalId = nullptr;
//	const char *ch_Type = nullptr;
//	const char *ch_Id = nullptr;
//	const char *ch_Name = nullptr;
//	STRUCT_IFCENTITY_TEST** st_BelongsTo=nullptr;
//	double* db_RelativePlacement;
//	double** st_PointsDesContours;
//};
//
//#ifdef __cplusplus
//extern "C" {
//#endif 
//
//	__declspec(dllexport) int __stdcall functDLL();
//
//	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_GetrefInt(int &int_Indice);
//	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_GetptrInt(int *&int_Indice);
//	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_DelptrInt(int *&int_Indice);
//	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_SetvalInt(int int_Indice);
//	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_SetptrInt(int *int_Indice);
//
//	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_GetrefDbl(double &dbl_Val);
//	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_GetptrDbl(double *&dbl_Val);
//	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_DelptrDbl(double *&dbl_Val);
//	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_SetvalDbl(double dbl_Val);
//	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_SetptrDbl(double *dbl_Val);
//	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_GetptrTabDbl(double *&dbl_Val,int &int_Size);
//
//	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_GetrefChr(const char *&chr_Val);
//	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_GetptrChr(char *&chr_Val);
//	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_DelptrChr(char *&chr_Val);
//	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_SetptrChr(char *chr_Val);
//	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_SetptrptrChr(char **chr_Val);
//
//
//	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_Initstr_IfcEntitiesTree();
//	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_Getstr_IfcEntitiesTree(STRUCT_IFCENTITY_TEST *&st_IfcTree);
//	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_Delstr_IfcEntitiesTree(STRUCT_IFCENTITY_TEST *&st_IfcTree, STRUCT_IFCENTITY_TEST* st_IfcCurrentFather = nullptr);
//
//
//
//
//
//#ifdef __cplusplus
//}
//#endif
//
//void InitStructure(STRUCT_IFCENTITY_TEST *&st_IfcTreeArg, string str_mod);

//////////////////////////////////////////////////////////////////////////////////////
//////////////////////////////////////////////////////////////////////////////////////
/////////////////// TEST INTEROPERABILITE Pascal C++ /////////////////////////////////
//////////////////////////////////FIN/////////////////////////////////////////////////
//////////////////////////////////////////////////////////////////////////////////////
