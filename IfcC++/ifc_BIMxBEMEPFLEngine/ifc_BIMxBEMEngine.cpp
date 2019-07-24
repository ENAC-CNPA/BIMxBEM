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

int __stdcall ifcxml_BIMxBEMEPFL_LoadXMLFileForBEM(char *chr_FilePath)
{
	int res = 0;

	//
	//Chargement en mémoire d'une structure générique de données typés BEM (optimisée pour modification)
	_iFile = new ifcXML_File();
	res = _iFile->LoadFile(chr_FilePath);

	return res;
}

void __stdcall ifcxml_BIMxBEMEPFL_UnLoadXMLFileForBEM()
{
	//
	//Desalloc des données membres ifc_BIMxBEMEngine
	if (_iFile)
		delete _iFile;
	_iFile = nullptr;

	return;
}

//Fournit la structure dans une chaine de caractères
int __stdcall ifcxml_BIMxBEMEPFL_GetEntitiesDefinition(const char *&chr_EntDef, const char *&chr_Logfile, double dbl_Minisurf) //Surface mini vue comme nulle pour Lesosai 
{
	int res = 0;

	//
	//Conversion de la structure générique de données typés BEM (optimisée pour modification) au format attendu par Lesosai
	_iLesosaiFormat = new LoadDataAtBEMFormat(dbl_Minisurf);
	res = _iLesosaiFormat->LoadLesosaiFormat(_iFile->GetData());
	if (res) return res;

	//Lecture de la structure Lesosai sous forme de 
	string *str_EntDef = nullptr;
	res = _iLesosaiFormat->GetLesosaiEntitiesDefinition(str_EntDef);
	if (res) return res;

	//Conversion string en const char*
	if (str_EntDef)
		chr_EntDef=str_EntDef->c_str();

	//Lecture de la Log 
	string *str_LogFile = nullptr;
	res = _iLesosaiFormat->GetLesosaiLogFile(str_LogFile);
	if (res) return res;

	//Conversion string en const char*
	if (str_LogFile)
		chr_Logfile = str_LogFile->c_str();

	return res;
}
