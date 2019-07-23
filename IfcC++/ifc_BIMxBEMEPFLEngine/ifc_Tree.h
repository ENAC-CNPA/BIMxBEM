#pragma once


#include <map>

#include <list>
using namespace std;


typedef map<string, string> Map_String_String;

//IMPORTANT: Toute modif de la structure doit assurer son "delete" (cf. ifc_Tree::delete_STRUCT_IFCENTITY)
struct STRUCT_IFCENTITY {
	const char *ch_GlobalId = nullptr;
	const char *ch_Type = nullptr;
	const char *ch_Id = nullptr;
	const char *ch_Name = nullptr;
	list<STRUCT_IFCENTITY*> st_BelongsTo;
	list<STRUCT_IFCENTITY*> st_Contains;
	list<STRUCT_IFCENTITY*> st_FaceToFace;
	//list<STRUCT_IFCENTITY*> st_SideBySide;
	STRUCT_IFCENTITY* st_TIFCSurface = nullptr;
	map<STRUCT_IFCENTITY*, bool> mp_SideBySide;
	list<double*> db_RelativePlacement;
	list<list<double*>> st_PointsDesContours;
	bool bo_ArePointsDesContoursALoop = false;//Si true = les 1er et dernier points de st_PointsDesContours sont identiques 
	list<double*> db_Centroid;
	Map_String_String* map_DefValues = nullptr;// tableau des noms des attributs géométriques (Length, Width,...) et de leur valeur (en string)
};

typedef map<string, STRUCT_IFCENTITY*> Map_String_ptrSTRUCT_IFCENTITY;


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

	//Creation d'entité (TIFCSurface) à partir des autres entités STRUCT_IFCENTITY (IfcConnectionSurfaceGeometry) déjà définies (pas à partir des entités xml comme dans ifc_Tree.template.h) 
	int BuildTIFCSurfaceTreeFrom_STRUCT_IFCENTITY(STRUCT_IFCENTITY* st_IfcTree);

#include "ifc_Tree.template.h"
	STRUCT_IFCENTITY *&Getstruct();

private:
	STRUCT_IFCENTITY *_st_IfcTree;
	Map_String_ptrSTRUCT_IFCENTITY _map_ID_IfcEnt;

};

