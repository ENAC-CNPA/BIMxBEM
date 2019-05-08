//
//
///////////////////////////////////////////////////
// INTERFACES A APPELER DEPUIS LE CODE "EXTERNE" //
///////////////////////////////////////////////////
//
//
#include "ifc_BIMxBEMEngine.h"

#include <string>
#include <iostream>

#include <windows.h>
#include "ifcXML_File.h"
#include "LoadDataAtBEMFormat.h"

ifcXML_File *_iFile=nullptr;
LoadDataAtBEMFormat* _iLesosaiFormat =nullptr;

void __stdcall ifcxml_BIMxBEMEPFL_LoadXMLFileForBEM(char *chr_FilePath)
{
	//wchar_t buff[64];
	////swprintf(buff, L"%s", *chr_Val);
	//size_t origsize = strlen(chr_FilePath) + 1;
	//mbstowcs(buff, chr_FilePath, origsize);
	//int msgboxID = MessageBox(NULL, buff, L"value=", MB_ICONWARNING | MB_YESNOCANCEL);
	////std::cout << "Valeur *char = " << *chr_Val << " et &char = " << chr_Val << std::endl;

	//Chargement en mémoire d'une structure générique de données typés BEM (optimisée pour modification)
	_iFile = new ifcXML_File();
	int res = _iFile->LoadFile(chr_FilePath);

	//DEB SLC: A FAIRE
	//Application d'un changement de referentiel à tous les points finaux (P/R au ref du projet)

	//Complétude des relations (sous-faces avec les spaces,...)

	//Modification de la géométrie

	//Convertit la structure générique de données typés BEM en structure spécifique/explicite BEM (Attendue pour Lesosai)
	//_iExplicitBEMData = new ifcTree_To_BEMTree();
	//_iExplicitBEMData->TranslateGenericIfcDataToExplicitBEMData(_iFile->GetTree());
	//FIN SLC: A FAIRE

	return;
}

void __stdcall ifcxml_BIMxBEMEPFL_UnLoadXMLFileForBEM()
{
	//wchar_t buff[64];
	////swprintf(buff, L"%s", *chr_Val);
	//size_t origsize = strlen(chr_FilePath) + 1;
	//mbstowcs(buff, chr_FilePath, origsize);
	//int msgboxID = MessageBox(NULL, buff, L"value=", MB_ICONWARNING | MB_YESNOCANCEL);
	//std::cout << "Valeur *char = " << *chr_Val << " et &char = " << chr_Val << std::endl;

	//
	//Desalloc des données membres ifc_BIMxBEMEngine
	if (_iFile)
		delete _iFile;
	_iFile = nullptr;

	return;
}

//Fournit le nombre de chacune des structures à passer
void __stdcall ifcxml_BIMxBEMEPFL_GetNumberOfEachEntities(int &iNb_Project,
														int &iNb_Site,
														int &iNb_Building,
														int &iNb_BuildingStorey,
														int &iNb_Space,
														int &iNb_Face)
{
	// NOT YET IMPLEMENTED
	//Conversion de la structure générique de données typés BEM (optimisée pour modification) au format attendu par Lesosai
	_iLesosaiFormat = new LoadDataAtBEMFormat();
	int res = _iLesosaiFormat->LoadLesosaiFormat(_iFile->GetData());

	//Conversion de la structure générique de données typés BEM (optimisée pour modification) au format attendu par Lesosai
	res = _iLesosaiFormat->GetLesosaiEntitiesNumber();
}
//Fournit la dimension de chacun des attributs de chacune des structures à passer
//Voir à fournir en même temps le noms des attributs, si besoin?
void __stdcall ifcxml_BIMxBEMEPFL_GetNumberOfEachAttributesOfEachEntities(int* &iSizeByAttribute_Project,
																		int* &iSizeByAttribute_Site,
																		int* &iSizeByAttribute_Building,
																		int* &iSizeByAttribute_BuildingStorey,
																		int* &iSizeByAttribute_Space,
																		int* &iSizeByAttribute_Face)
{
	// NOT YET IMPLEMENTED
	int res = _iLesosaiFormat->GetLesosaiEntitiesAttributesSize();
}

//Fournit la structure dans une chaine de caractères
void __stdcall ifcxml_BIMxBEMEPFL_GetEntitiesDefinition(const char *&chr_EntDef)
{
	// NOT YET IMPLEMENTED
	//Conversion de la structure générique de données typés BEM (optimisée pour modification) au format attendu par Lesosai
	_iLesosaiFormat = new LoadDataAtBEMFormat();
	int res = _iLesosaiFormat->LoadLesosaiFormat(_iFile->GetData());

	//Lecture de la structure Lesosai sous forme de 
	string *str_EntDef;
	res = _iLesosaiFormat->GetLesosaiEntitiesDefinition(str_EntDef);

	//Conversion string en const char*
	//const char * chr_Tree = str_EntDef->c_str();
	//chr_EntDef = *chr_Tree;
	//chr_EntDef = strdup(chr_Tree);
	//if(str_EntDef && 0!=str_EntDef->size())
		chr_EntDef=str_EntDef->c_str();

	//Ajout du '\0' ? sur const ?
}


//////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////DEBUT/////////////////////////////////////////////////
/////////////////// TEST INTEROPERABILITE Pascal C++ /////////////////////////////////
//////////////////////////////////////////////////////////////////////////////////////
//////////////////////////////////////////////////////////////////////////////////////

//STRUCT_IFCENTITY_TEST *st_IfcTreeTest = nullptr;
//
//int __stdcall functDLL()
//{
//	return 12;
//}
//
////
////				char <= short <= int <= long/unsigned ptr <= long long
//// Proc 32bits    1       2       4            4                 8
//// Proc 64bits    1       2       4            8
////
////				float/bool <= double <= long double
//// Proc 32bits    4             8           12
//// Proc 64bits    4             8           12
////
//
////
////	INTEGER: short? int? long? long long?
////
//void __stdcall ifcxml_BIMxBEMEPFL_GetrefInt(int &int_Indice)
//{
//	int_Indice = 1;
//	return;
//}
//
//void __stdcall ifcxml_BIMxBEMEPFL_GetptrInt(int *&int_Indice)
//{
//	if(!int_Indice)
//		int_Indice = new int();
//	*int_Indice = 2;
//	return;
//}
//
//void __stdcall ifcxml_BIMxBEMEPFL_DelptrInt(int *&int_Indice)
//{
//	// condition ternaire=> (y < 10) ? 30 : 40;
//	if (int_Indice)
//		delete int_Indice;
//	int_Indice = nullptr;
//	return;
//}
//
//void __stdcall ifcxml_BIMxBEMEPFL_SetvalInt(int int_Indice)
//{
//	wchar_t buff[64];
//	swprintf(buff, L"%d", int_Indice);
//	int msgboxID = MessageBox(NULL, buff, L"value=", MB_ICONWARNING | MB_YESNOCANCEL);
//	std::cout << "Valeur int = " << int_Indice << std::endl;
//	return;
//}
//
//void __stdcall ifcxml_BIMxBEMEPFL_SetptrInt(int *int_Indice)
//{
//	wchar_t buff[64];
//	swprintf(buff, L"%d", *int_Indice);
//	int msgboxID = MessageBox(NULL, buff, L"value=", MB_ICONWARNING | MB_YESNOCANCEL);
//	std::cout << "Valeur *int = " << *int_Indice << " et &int = " << int_Indice << std::endl;
//	return;
//}
//
////
////	DOUBLE
////
//
//void __stdcall ifcxml_BIMxBEMEPFL_GetrefDbl(double &dbl_Val)
//{
//	dbl_Val = 1.23456789;
//	return;
//}
//
//void __stdcall ifcxml_BIMxBEMEPFL_GetptrDbl(double *&dbl_Val)
//{
//	if (!dbl_Val)
//		dbl_Val = new double();
//	*dbl_Val = 9.87654321;
//	return;
//}
//
//void __stdcall ifcxml_BIMxBEMEPFL_DelptrDbl(double *&dbl_Val)
//{
//	// condition ternaire=> (y < 10) ? 30 : 40;
//	if (dbl_Val)
//		delete dbl_Val;
//	dbl_Val = nullptr;
//	return;
//}
//
//void __stdcall ifcxml_BIMxBEMEPFL_SetvalDbl(double dbl_Val)
//{
//	wchar_t buff[64];
//	swprintf(buff, L"%f", dbl_Val);
//	int msgboxID = MessageBox(NULL, buff, L"value=", MB_ICONWARNING | MB_YESNOCANCEL);
//	std::cout << "Valeur double = " << dbl_Val << std::endl;
//	return;
//}
//
//void __stdcall ifcxml_BIMxBEMEPFL_SetptrDbl(double *dbl_Val)
//{
//	wchar_t buff[64];
//	swprintf(buff, L"%f", *dbl_Val);
//	int msgboxID = MessageBox(NULL, buff, L"value=", MB_ICONWARNING | MB_YESNOCANCEL);
//	std::cout << "Valeur *double = " << *dbl_Val << " et &double = " << dbl_Val << std::endl;
//	return;
//}
//
////
////	CONST CHAR*, CHAR*, CHAR**
////
//
//void __stdcall ifcxml_BIMxBEMEPFL_GetrefChr(const char *&chr_Val)
//{
//	std::string mystring = "Hello"; 
//	chr_Val = mystring.c_str();
//	return;
//}
//
//void __stdcall ifcxml_BIMxBEMEPFL_GetptrChr(char *&chr_Val)
//{
//	if (!chr_Val)
//		chr_Val = new char[5];
//	std::string mystring = "HELL";
//	strncpy(chr_Val, mystring.c_str(), mystring.length());
//	return;
//}
//
//void __stdcall ifcxml_BIMxBEMEPFL_DelptrChr(char *&chr_Val)
//{
//	// condition ternaire=> (y < 10) ? 30 : 40;
//	if (chr_Val)
//		delete [] chr_Val;
//	chr_Val = nullptr;
//	return;
//}
//
//void __stdcall ifcxml_BIMxBEMEPFL_SetptrChr(char *chr_Val)
//{
//	wchar_t buff[64];
//	//swprintf(buff, L"%s", *chr_Val);
//	size_t origsize = strlen(chr_Val) + 1;
//	mbstowcs(buff, chr_Val, origsize);
//	int msgboxID = MessageBox(NULL, buff, L"value=", MB_ICONWARNING | MB_YESNOCANCEL);
//	//std::cout << "Valeur *char = " << *chr_Val << " et &char = " << chr_Val << std::endl;
//	return;
//}
//
//void __stdcall ifcxml_BIMxBEMEPFL_SetptrptrChr(char **chr_Val)
//{
//	std::cout << "Valeur char = " << chr_Val << std::endl;
//	return;
//}
//
//void __stdcall ifcxml_BIMxBEMEPFL_GetptrTabDbl(double *&dbl_Val, int &int_Size)
//{
//	int_Size = 3;
//	if (!dbl_Val)
//		dbl_Val = new double[int_Size];
//	dbl_Val[0] = 9.87654321;
//	dbl_Val[1] = 8.7654321;
//	dbl_Val[2] = 7.654321;
//	return;
//}
//
//
////
////	STRUCTURE
////
//
//void __stdcall ifcxml_BIMxBEMEPFL_Initstr_IfcEntitiesTree()
//{
//	st_IfcTreeTest=new STRUCT_IFCENTITY_TEST;
//	InitStructure(st_IfcTreeTest, "11");
//
//	STRUCT_IFCENTITY_TEST *st_IfcBelongTo = new STRUCT_IFCENTITY_TEST;
//	InitStructure(st_IfcBelongTo, "22");
//
//	STRUCT_IFCENTITY_TEST *st_IfcBelongTo2 = new STRUCT_IFCENTITY_TEST;
//	InitStructure(st_IfcBelongTo2, "33");
//
//	if (st_IfcBelongTo)
//	{
//		STRUCT_IFCENTITY_TEST ** pst_BelongsTo=new STRUCT_IFCENTITY_TEST*[2];
//		pst_BelongsTo[0] = st_IfcBelongTo;
//		pst_BelongsTo[1] = st_IfcBelongTo2;
//
//		st_IfcTreeTest->st_BelongsTo= pst_BelongsTo;
//		//st_IfcBelongTo->st_Contains.push_back(st_IfcTreeTest);
//	}// if (st_IfcBelongTo)
//
//	//if (st_IfcBelongTo2)
//	//{
//	//	st_IfcTreeTest->st_BelongsTo.push_back(st_IfcBelongTo2);
//	//	st_IfcBelongTo2->st_Contains.push_back(st_IfcTreeTest);
//	//}// if (st_IfcBelongTo)
//
//	return;
//}
//
//void __stdcall ifcxml_BIMxBEMEPFL_Getstr_IfcEntitiesTree(STRUCT_IFCENTITY_TEST *&st_IfcTreeTestArg)
//{
//	st_IfcTreeTestArg=st_IfcTreeTest;
//	return;
//}
//
//void __stdcall ifcxml_BIMxBEMEPFL_Delstr_IfcEntitiesTree(STRUCT_IFCENTITY_TEST *&st_IfcTreeTestArg, STRUCT_IFCENTITY_TEST* st_IfcCurrentFather)
//{
//	//
//	//Descente dans l'arborescence jusqu'aux élément sans enfants (membre "st_Contains" vide)
//	//list <STRUCT_IFCENTITY_TEST*> ::iterator it_Elem;
//	//for (it_Elem = (st_IfcTreeTestArg->st_Contains).begin(); it_Elem != (st_IfcTreeTestArg->st_Contains).end(); it_Elem++)
//	//{
//	//	if ((*it_Elem))
//	//		ifcxml_BIMxBEMEPFL_Delstr_IfcEntitiesTree((*it_Elem), st_IfcTreeTestArg);
//	//}// for (it_Elem = (st_IfcTreeTestArg->st_Contains).begin(); it_Elem != (st_IfcTreeTestArg->st_Contains).end(); it_Elem++)
//	//st_IfcTreeTestArg->st_Contains.clear();
//
//	//
//	//Désallocations effectives
//	//
//	delete[] st_IfcTreeTestArg->ch_GlobalId; st_IfcTreeTestArg->ch_GlobalId = nullptr;
//	delete[] st_IfcTreeTestArg->ch_Id; st_IfcTreeTestArg->ch_Id = nullptr;
//	delete[] st_IfcTreeTestArg->ch_Name; st_IfcTreeTestArg->ch_Name = nullptr;
//	delete[] st_IfcTreeTestArg->ch_Type; st_IfcTreeTestArg->ch_Type = nullptr;
//
//	for (int it_l_Points = 0; it_l_Points <2; it_l_Points++)
//	{
//		delete st_IfcTreeTestArg->st_BelongsTo[it_l_Points];
//		st_IfcTreeTestArg->st_BelongsTo[it_l_Points] = nullptr;
//	}// for (it_l_Points = (st_IfcTreeTestArg->db_RelativePlacement).begin(); it_l_Points != (st_IfcTreeTestArg->db_RelativePlacement).end(); it_l_Points++)
//
//	for (int it_l_Points = 0; it_l_Points <12; it_l_Points++)
//	{
//		delete st_IfcTreeTestArg->db_RelativePlacement;
//		st_IfcTreeTestArg->db_RelativePlacement = nullptr;
//	}// for (it_l_Points = (st_IfcTreeTestArg->db_RelativePlacement).begin(); it_l_Points != (st_IfcTreeTestArg->db_RelativePlacement).end(); it_l_Points++)
//
//	//list <list<double*>>::iterator it_ll_Points;
//	//for (it_ll_Points = (st_IfcTreeTestArg->st_PointsDesContours).begin(); it_ll_Points != (st_IfcTreeTestArg->st_PointsDesContours).end(); it_ll_Points++)
//	//{
//	//	for (it_l_Points = (*it_ll_Points).begin(); it_l_Points != (*it_ll_Points).end(); it_l_Points++)
//	//	{
//	//		delete (*it_l_Points);
//	//		*it_l_Points = nullptr;
//	//	}// for (it_l_Points = (*it_ll_Points).begin(); it_l_Points != (*it_ll_Points).end(); it_l_Points++)
//	//	 //
//	//	(*it_ll_Points).clear();
//	//}// for (it_ll_Points = (st_IfcTreeTestArg->st_PointsDesContours).begin(); it_ll_Points != (st_IfcTreeTestArg->st_PointsDesContours).end(); it_ll_Points++)
//	//st_IfcTreeTestArg->st_PointsDesContours.clear();
//
//	////
//	//// Nettoyage des listes référencant l'objet que l'on est en train de détruire
//	//// Pour les liens non binaires (ternaires ou plus) la structure en cours d'effacement (st_IfcTreeTestArg) est référencée dans les Contains de plusieurs pères
//	//// Afin déviter un crash mémoire par la désallocation d'une structure déjà détruite, il faut déréférencer la structure 
//	//// en cours d'effacement des listes de BelongsTo des autres pères (que celui en cours = st_IfcCurrentFather)
//	//// Exemple: IfcConnectionSurfaceGeometry est référencé à la fois dans le st_Contains de IfSpace et des BuildingElements (IfcWall,...)
//	//list <STRUCT_IFCENTITY_TEST*> ::iterator it_ElemInBelong;
//	//for (it_ElemInBelong = (st_IfcTreeTestArg->st_BelongsTo).begin(); it_ElemInBelong != (st_IfcTreeTestArg->st_BelongsTo).end(); it_ElemInBelong++)
//	//{
//	//	if ((*it_ElemInBelong) != st_IfcCurrentFather)
//	//	{
//	//		list <STRUCT_IFCENTITY_TEST*> ::iterator it_ElemInBelongContains;
//	//		for (it_ElemInBelongContains = ((*it_ElemInBelong)->st_Contains).begin(); it_ElemInBelongContains != ((*it_ElemInBelong)->st_Contains).end(); it_ElemInBelongContains++)
//	//		{
//	//			if ((*it_ElemInBelongContains) == st_IfcTreeTestArg)
//	//			{
//	//				(*it_ElemInBelong)->st_Contains.erase(it_ElemInBelongContains);
//	//				break;
//	//			}// if ((*it_ElemInBelongContains) == st_IfcTreeTestArg)
//	//		}// for (it_ElemInBelongContains = ((*it_ElemInBelong)->st_Contains).begin(); it_ElemInBelongContains != ((*it_ElemInBelong)->st_Contains).end(); it_ElemInBelongContains++)
//	//	}// if ((*it_ElemInBelong) != st_IfcCurrentFather)
//	//}// for (it_ElemInBelong = (st_IfcTreeTestArg->st_BelongsTo).begin(); it_ElemInBelong != (st_IfcTreeTestArg->st_BelongsTo).end(); it_ElemInBelong++)
//	//st_IfcTreeTestArg->st_BelongsTo.clear();
//
//	delete st_IfcTreeTestArg; st_IfcTreeTestArg = nullptr;
//	return;
//}
//
//void InitStructure(STRUCT_IFCENTITY_TEST *&st_IfcTreeTestArg, string str_mod)
//{
//	std::string str1("GlobalID_"); str1 += str_mod;
//	char *ch_copy22 = new char[23];//size+1 pour que strncpy mette'\0'
//	strncpy(ch_copy22, str1.c_str(), 23);
//	st_IfcTreeTestArg->ch_GlobalId = ch_copy22;
//
//	std::string str2("LongName_"); str2 += str_mod;
//	char *ch_copy255 = new char[256];//size+1 pour que strncpy mette'\0'
//	strncpy(ch_copy255, str2.c_str(), 256);
//	st_IfcTreeTestArg->ch_Name = ch_copy255;
//
//	std::string str3("Id_"); str3 += str_mod;
//	char *ch_copy9 = new char[10];//size+1 pour que strncpy mette'\0'
//	strncpy(ch_copy9, str3.c_str(), 10);
//	st_IfcTreeTestArg->ch_Id = ch_copy9;
//
//	std::string str4("Type_"); str4 += str_mod;
//	char *ch_copy55 = new char[56];//size+1 pour que strncpy mette'\0'
//	strncpy(ch_copy55, str4.c_str(), 56);
//	st_IfcTreeTestArg->ch_Type = ch_copy55;
//
//	double db_LocalMat[3][4] = { 1,2,3,4,5,6,7,8,9,10,11,12 };
//	double *db_Val = new double[12];
//	int i = 0;
//	if (db_LocalMat)
//	{
//		for (int i_col = 0; i_col < 4; i_col++)
//		{
//			for (int i_lin = 0; i_lin < 3; i_lin++)
//			{
//				/*double *db_Val = new double()*/;
//				db_Val[i] = db_LocalMat[i_lin][i_col];
//				i++;
//			}// for (int i_lin = 0; i_lin < 3; i_lin++)
//		}// for (int i_col = 0; i_col < 4; i_col++)
//		st_IfcTreeTestArg->db_RelativePlacement=db_Val;//(db_LocalMat[i_lin][i_col])
//	}// if (db_LocalMat)
//}

//////////////////////////////////////////////////////////////////////////////////////
//////////////////////////////////////////////////////////////////////////////////////
/////////////////// TEST INTEROPERABILITE Pascal C++ /////////////////////////////////
//////////////////////////////////FIN/////////////////////////////////////////////////
//////////////////////////////////////////////////////////////////////////////////////
