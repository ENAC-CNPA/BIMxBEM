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

	__declspec(dllexport) int __stdcall ifcxml_BIMxBEMEPFL_LoadXMLFileForBEM(char *chr_FilePath);
	__declspec(dllexport) void __stdcall ifcxml_BIMxBEMEPFL_UnLoadXMLFileForBEM();

	__declspec(dllexport) int __stdcall ifcxml_BIMxBEMEPFL_GetEntitiesDefinition(const char *&chr_EntDef);

#ifdef __cplusplus
}
#endif

