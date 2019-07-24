#pragma once


#include <map>

#include <list>
#include <functional>
#include <set>
using namespace std;


typedef map<string, string> Map_String_String;

//IMPORTANT: Toute modif de la structure doit assurer son "delete" (cf. ifc_Tree::delete_STRUCT_IFCENTITY)
struct STRUCT_IFCENTITY {
	const char *ch_GlobalId = nullptr;
	const char *ch_Type = nullptr;
	const char *ch_PredifinedType = nullptr;
	const char *ch_Id = nullptr;
	const char *ch_Name = nullptr;
	list<STRUCT_IFCENTITY*> st_BelongsTo;
	list<STRUCT_IFCENTITY*> st_Contains;
	list<STRUCT_IFCENTITY*> st_FaceToFace;
	//list<STRUCT_IFCENTITY*> st_SideBySide;
	STRUCT_IFCENTITY* st_TIFCSurface = nullptr;
	set<pair<STRUCT_IFCENTITY*, pair<double,bool>>, function<bool(pair<STRUCT_IFCENTITY*, pair<double, bool>>, pair<STRUCT_IFCENTITY*, pair<double, bool>>)>> mp_SideBySide;
//	set<pair<STRUCT_IFCENTITY*, pair<double,bool>>> mp_SideBySide;
	//map<STRUCT_IFCENTITY*, pair<double,bool>> mp_SideBySide;
	//map<STRUCT_IFCENTITY*, bool> mp_SideBySide;
	list<double*> db_RelativePlacement;
	list<list<double*>> st_PointsDesContours;
	bool bo_ArePointsDesContoursALoop = false;//Si true = les 1er et dernier points de st_PointsDesContours sont identiques 
	list<double*> db_Centroid;
	Map_String_String* map_DefValues = nullptr;// tableau des noms des attributs g�om�triques (Length, Width,...) et de leur valeur (en string)
};

typedef function<bool(pair<STRUCT_IFCENTITY*, pair<double, bool>>, pair<STRUCT_IFCENTITY*, pair<double, bool>>)> Comparator;
typedef map<string, STRUCT_IFCENTITY*> Map_String_ptrSTRUCT_IFCENTITY;

//extern Comparator compFunctor;
//Comparator compFunctor =
//	[](pair<STRUCT_IFCENTITY*, pair<double, bool>> elem1, pair<STRUCT_IFCENTITY*, pair<double, bool>> elem2)
//{
//	return elem1.second.first < elem2.second.first;
//};

class ifc_Tree
{
public:
	ifc_Tree();
	~ifc_Tree();

	void FillAttributeOf_STRUCT_IFCENTITY(STRUCT_IFCENTITY* st_IfcTree, Map_String_String &map_messages, double db_LocalMat[3][4] = nullptr, STRUCT_IFCENTITY *st_IfcBelongTo = nullptr, STRUCT_IFCENTITY *st_IfcBelongTo2 = nullptr);
	void FillAttributeOfExisting_STRUCT_IFCENTITY(STRUCT_IFCENTITY* st_IfcTree, Map_String_String &map_messages, double db_LocalMat[3][4] = nullptr, STRUCT_IFCENTITY *st_IfcBelongTo = nullptr, STRUCT_IFCENTITY *st_IfcBelongTo2 = nullptr);
	void FillNameAndIDAttributeOf_STRUCT_IFCENTITY(STRUCT_IFCENTITY* st_IfcTree, Map_String_String &map_messages);
	void FillRelativePlacementOf_STRUCT_IFCENTITY(STRUCT_IFCENTITY* st_IfcTree, double db_LocalMat[3][4]);
	void FillGeomAttributeOf_STRUCT_IFCENTITY(STRUCT_IFCENTITY* st_IfcSubFacGeomRep, list<list<double*>> &SubFacePtsCoord, STRUCT_IFCENTITY *st_IfcBelongTo, Map_String_String &map_messages);
	void FillCentroidOf_STRUCT_IFCENTITY(STRUCT_IFCENTITY* st_IfcTree, double db_CentroidCoord[3]);
	void FillQuantitiesAttributeOf_STRUCT_IFCENTITY(STRUCT_IFCENTITY* st_IfcTree, Map_String_String &map_messages);
	void delete_STRUCT_IFCENTITY(STRUCT_IFCENTITY *&st_IfcTree, STRUCT_IFCENTITY* st_IfcCurrentFather = nullptr);

	//Creation d'entit� (TIFCSurface) � partir des autres entit�s STRUCT_IFCENTITY (IfcConnectionSurfaceGeometry) d�j� d�finies (pas � partir des entit�s xml comme dans ifc_Tree.template.h) 
	int BuildTIFCSurfaceTreeFrom_STRUCT_IFCENTITY(STRUCT_IFCENTITY* st_IfcTree);

	Comparator compFunctor =
		[](pair<STRUCT_IFCENTITY*, pair<double, bool>> elem1, pair<STRUCT_IFCENTITY*, pair<double, bool>> elem2)
	{
		return elem1.second.first < elem2.second.first;
	};

#include "ifc_Tree.template.h"
	STRUCT_IFCENTITY *&Getstruct();

private:
	STRUCT_IFCENTITY *_st_IfcTree;
	Map_String_ptrSTRUCT_IFCENTITY _map_ID_IfcEnt;

};

