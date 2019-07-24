#pragma once

#include "ifc_Tree.h"
#include <vector>
//#include <algorithm>

typedef map<STRUCT_IFCENTITY*, string> Map_Basified_Tree;


class ifc_TreePostTreatment
{
public:
	ifc_TreePostTreatment(ifc_Tree* CurrentIfcTree);
	~ifc_TreePostTreatment();

	int BasifyTree(Map_Basified_Tree *&map_BasifTree);
	int CompleteBasifiedTreeFromByTIFCSurfaces();

	//Retrait dans les contours (st_PointsDesContours) du derniers point lorsqu'il est égal au 1er (+ consigne bool bo_IsItLoop=true)
	int RemoveLastPointOfLoopContours(string *&str_LogFile);

	//Calcul des isobarycentres des IfcConnectionSurfaceGeometry
	int CentroidsComputation();

	//Recherche des IfcConnectionSurfaceGeometry en vis-à-vis et côte-à-côte
	int FindFaceToFaceAndSideBySideSurfaces();

	//Relimitation des IfcConnectionSurfaceGeometry en côte-à-côte
	int RelimitSideBySideSurfaces(string *&str_LogFile);

	//Passer dasn le ref du projet
	int TransformEntitiesToWorlCoordFrame();

	//Calcul des surfaces IfcConnectionSurfaceGeometry
	int ComputeIfcConnectionSurfaceGeometrySurface();

	//Creation des TIFCSurfaces (décomposition des éléments de construction en leurs surfaces IfcConnectionSurfaceGeometry vis-à-vis)
	int CreateTIFCSurfaces();

	//Retrait des IfcConnectionSurfaceGeometry de surfaces inférieures à dbl_Minisurf
	int RemoveQuasiNullIfcConnectionSurfaceGeometrySurface(double dbl_Minisurf, string *&str_LogFile);

private:
	int BasifyTreeFrom(STRUCT_IFCENTITY *&st_IfcTree);
	int CentroidComputation(STRUCT_IFCENTITY *st_IfcEntCS);
	int RelimitSideBySideSurfacesOfOneIfcConnectionSurfaceGeometry(STRUCT_IFCENTITY *st_IfcEntCS, string *&str_LogFile);
	int RelimitOneSideBySideSurfaceOfOneIfcConnectionSurfaceGeometry(STRUCT_IFCENTITY *&st_IfcEntCS1, STRUCT_IFCENTITY *st_IfcEntCS2, string *&str_LogFile);
	int FindFaceToFaceAndSideBySideSurfacesOfOneBuildingelement(STRUCT_IFCENTITY *st_IfcEntBE);
	int FindFaceToFaceSurfacesOfOneBuildingelement(STRUCT_IFCENTITY *st_IfcEntBE, map<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *> &map_IfcConn_IfcSpace, list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>> &li_IfcConn_IfcConn_Dist);
	int FindSideBySideSurfacesOfOneBuildingelement(STRUCT_IFCENTITY *st_IfcEntBE, map<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *> &map_IfcConn_IfcSpace, list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>> &li_IfcConn_IfcConn_Dist, map<STRUCT_IFCENTITY *, int> &map_IfcSpace_NbIfcConn);
	int TransformEntityToWorlCoordFrame(STRUCT_IFCENTITY *st_IfcEnt, double *&db_CoordPts, size_t int_Size);
	int RemoveLastPointOfOneLoopContour(STRUCT_IFCENTITY *st_IfcEnt, string *&str_LogFile);
	int ComputeOneIfcConnectionSurfaceGeometrySurface(STRUCT_IFCENTITY *st_IfcEntCS);
	double ComputeSurfaceFromAContour(vector<double*> &vc_PointCoordCtr);
	int CreateTIFCSurface(STRUCT_IFCENTITY *st_IfcEntCS);
	int RemoveOneQuasiNullIfcConnectionSurfaceGeometrySurface(STRUCT_IFCENTITY *st_IfcEntCS, double dbl_Minisurf, string *&str_LogFile);

	double ComputePtPtDistance(vector<double*> &vc_Point1, vector<double*> &vc_Point2);
	//int SortSideBySideSurfacesOfIfcConnectionSurfaceGeometry(STRUCT_IFCENTITY *st_IfcEntCS);
	//int FillSideBySideSurfacesOfOneBuildingelement(STRUCT_IFCENTITY *st_IfcConn_Left, STRUCT_IFCENTITY *st_IfcConn_Middle, STRUCT_IFCENTITY *st_IfcConn_Right, double dbl_Dist_Left_Mid, double dbl_Dist_Mid_Right);
	
	void RecordLog(int &int_Step, string &str_LogFile, string &str_Header, STRUCT_IFCENTITY *&st_IfcEntCS);

	map<STRUCT_IFCENTITY*, pair<bool, double>>::iterator get_Index_Of_Max(map<STRUCT_IFCENTITY*, pair<bool, double>> &x);

	//bool compare_dist(const pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double> &first, const pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double> &second);

	Map_Basified_Tree _map_BasifTree;
	ifc_Tree* _CurrentIfcTree;
};

//template<typename KeyType, typename ValueType>
//map<KeyType, ValueType> get_max(const map<KeyType, ValueType> &x)
//{
//	using pairtype = map<KeyType, ValueType>;
//	return *std::max_element(x.begin(), x.end(), [](const pairtype &p1, const pairtype &p2)
//	{
//		return p1.begin()/*.second.second*/ < p2/*.second.second*/;
//	});
//}

//template<typename KeyType, typename ValueType>
//bool Comp(map<KeyType, ValueType> p1, map<KeyType, ValueType> p2)
//{ 
//	return p1.<j; 
//}

