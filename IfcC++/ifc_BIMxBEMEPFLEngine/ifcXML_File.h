#pragma once

#include <string>
#include <list>
using namespace std;

#include "tinyxml.h"
#include "ifc_Tree.h"

#include <map>

//typedef std::map<std::string, std::string> Map_String_String;
typedef std::map<std::string, TiXmlElement*> Map_String_ptrTiXmlElement;
typedef std::map<TiXmlElement*, TiXmlElement*> Map_ptrTiXmlElement_ptrTiXmlElement;

class ifcXML_File
{
public:
	ifcXML_File();
	~ifcXML_File();

	int LoadFile(char *strFileName);
	int LoadIfcEntities(TiXmlHandle &hroot);

	int FindRelatedBuildingElementAndConnectionGeometryInRelSpaceBoundaryFromRelatingSpace(TiXmlElement* &lpRelatingObj, list<TiXmlElement*> *lpRelatedObjects, list<TiXmlElement*> *lpsecondRelatedObjects);
	int FindRelatedObjectsInRelAggregatesFromRelatingObject(TiXmlElement* &lpRelatingObj, list<TiXmlElement*> *lpRelatedObjects);
	int FindRepresentationInSpace(TiXmlElement* &pElem, list<TiXmlElement*> *lpRelatedObjects);
	int FindObjectsInRelFromRelatingEnt(TiXmlElement* &lpRelatingObj, list<TiXmlElement*> *lpRelatedObjects, const char* pKeyword1, const char* pKeyword2, const char* pKeyword3, const char* pKeyword4 = nullptr, list<TiXmlElement*> *lpsecondRelatedObjects = nullptr);
	int FindObjectFromRef(TiXmlElement* &RelatedElmt, TiXmlElement* &lpObject);
	//int FindObjectFromRefAndPath(TiXmlElement* &RelatedElmt, list<string>::iterator &lst_PathBegin, list<string>::iterator &lst_PathEnd, list <TiXmlElement*> &lpObject);
	int FindObjectFromRefAndPathBy3(TiXmlElement* &RelatedElmt, list<string>::iterator &lst_Path, list<string>::iterator &lst_PathEnd, list <list <list <TiXmlElement*>>> &lllpObject, list <TiXmlElement*> &lpObjectFace);

	int ScanAssociateRelatedAndRelatingEnt(const char* pKeyword1, const char* pKeyword2, const char* pKeyword3, const char* pKeyword4 = nullptr);
	int ScanIfcRelDefinesByPropertiesForQuantities();

	int FindOneSpecificLinkedObjectFromFirstLinkPath(TiXmlElement* pElement, string st_Path[2], TiXmlElement* &lpObject);
	int FindSeveralSpecificLinkedObjectsFromFirstLinkPath(TiXmlElement* pElement, string st_Path[2], list<TiXmlElement*> &lpObject);
	int FindAllLinkedObjectsFromFirstLinkPath(TiXmlElement* pElement, string &st_Path, list<TiXmlElement*> &lpObject);

	int FindIfcLocalPlacement(TiXmlElement* pElement, TiXmlElement* &lpObject);
	int FindIfcGeometricRepresentationContext(TiXmlElement* pElement, TiXmlElement* &lpObject);
	int FindIfcGeometricRepresentationSubContext(TiXmlElement* pElement, TiXmlElement* &lpObject);
	int FindIfcCurveBoundedPlanePlacemcent(TiXmlElement* pElement, TiXmlElement* &lpObject);
	int FindIfcShapeRepresentationBrep(TiXmlElement* pElement, TiXmlElement* &lpObject);

	int ReadOneSpecificValueOfAnEntity(TiXmlElement *pIfcEntity, string &st_Path, string &st_value);
	int ReadIdAndTypeOfAnEntity(TiXmlElement* pElement, Map_String_String &m_messages);
	int ReadAllValuesOfAnEntity(TiXmlElement* pIfcEntity, list<string> &li_messages);
	int ReadIfcAxis2Placement3DMatrix(TiXmlElement* pElement, double Matrix[3][4]);
	int ReadPtsDefiningPolyloopOrPolyline(list <TiXmlElement*> &llBoundsOfOneCFsFace_Face, list<list<double*>> &FacePtsCoord);
	int ReadKeyWordsAndValuesOfIfcElementQuantity(TiXmlElement* pElement, Map_String_String &m_messages);

	ifc_Tree* GetData();
private:
	TiXmlHandle _hRoot;
	Map_String_ptrTiXmlElement _map_ID_Elmt;
	ifc_Tree *_cl_ifcTree;
	Map_ptrTiXmlElement_ptrTiXmlElement _map_BE_Quantities;

};

