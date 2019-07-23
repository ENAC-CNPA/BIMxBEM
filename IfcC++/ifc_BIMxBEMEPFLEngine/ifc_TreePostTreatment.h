#pragma once

#include "ifc_Tree.h"
#include <vector>

typedef map<STRUCT_IFCENTITY*, string> Map_Basified_Tree;


class ifc_TreePostTreatment
{
public:
	ifc_TreePostTreatment(ifc_Tree* CurrentIfcTree);
	~ifc_TreePostTreatment();

	int BasifyTree(Map_Basified_Tree *&map_BasifTree);
	int CompleteBasifiedTreeFromByTIFCSurfaces();

	//Retrait dans les contours (st_PointsDesContours) du derniers point lorsqu'il est égal au 1er (+ consigne bool bo_IsItLoop=true)
	int RemoveLastPointOfLoopContours();

	//Calcul des isobarycentres des IfcConnectionSurfaceGeometry
	int CentroidsComputation();

	//Recherche des IfcConnectionSurfaceGeometry en vis-à-vis et côte-à-côte
	int FindFaceToFaceAndSideBySideSurfaces();

	//Relimitation des IfcConnectionSurfaceGeometry en côte-à-côte
	int RelimitSideBySideSurfaces();

	//Passer dasn le ref du projet
	int TransformEntitiesToWorlCoordFrame();

	//Calcul des surfaces IfcConnectionSurfaceGeometry
	int ComputeIfcConnectionSurfaceGeometrySurface();

	//Creation des TIFCSurfaces (décomposition des éléments de construction en leurs surfaces IfcConnectionSurfaceGeometry vis-à-vis)
	int CreateTIFCSurfaces();

private:
	int BasifyTreeFrom(STRUCT_IFCENTITY *&st_IfcTree);
	int CentroidComputation(STRUCT_IFCENTITY *st_IfcEntCS);
	int RelimitSideBySideSurfacesOfMiddleIfcConnectionSurfaceGeometry(STRUCT_IFCENTITY *st_IfcEntCS);
	int RelimitOneSideBySideSurfaceOfMiddleIfcConnectionSurfaceGeometry(STRUCT_IFCENTITY *&st_IfcEntCS1, STRUCT_IFCENTITY *st_IfcEntCS2);
	int FindFaceToFaceAndSideBySideSurfacesOfOneBuildingelement(STRUCT_IFCENTITY *st_IfcEntBE);
	int FindFaceToFaceSurfacesOfOneBuildingelement(STRUCT_IFCENTITY *st_IfcEntBE, map<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *> &map_IfcConn_IfcSpace, list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>> &li_IfcConn_IfcConn_Dist);
	int FindSideBySideSurfacesOfOneBuildingelement(STRUCT_IFCENTITY *st_IfcEntBE, map<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *> &map_IfcConn_IfcSpace, list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>> &li_IfcConn_IfcConn_Dist, map<STRUCT_IFCENTITY *, int> &map_IfcSpace_NbIfcConn);
	int TransformEntityToWorlCoordFrame(STRUCT_IFCENTITY *st_IfcEnt, double *&db_CoordPts, size_t int_Size);
	int RemoveLastPointOfOneLoopContour(STRUCT_IFCENTITY *st_IfcEnt);
	int ComputeOneIfcConnectionSurfaceGeometrySurface(STRUCT_IFCENTITY *st_IfcEntCS);
	double ComputeSurfaceFromAContour(vector<double*> &vc_PointCoordCtr);
	int CreateTIFCSurface(STRUCT_IFCENTITY *st_IfcEntCS);

	double ComputePtPtDistance(vector<double*> &vc_Point1, vector<double*> &vc_Point2);

	//bool compare_dist(const pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double> &first, const pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double> &second);

	Map_Basified_Tree _map_BasifTree;
	ifc_Tree* _CurrentIfcTree;
};

