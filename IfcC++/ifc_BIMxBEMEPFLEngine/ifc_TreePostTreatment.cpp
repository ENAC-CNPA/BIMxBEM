#include "ifc_TreePostTreatment.h"
//#include <vector>
#include <string>
#include <functional>
//#include <set>

const double db_eps= 0.00001;
const double db_ep_mur_max = 0.3;

ifc_TreePostTreatment::ifc_TreePostTreatment(ifc_Tree* CurrentIfcTree)
{
	_CurrentIfcTree = CurrentIfcTree;
}


ifc_TreePostTreatment::~ifc_TreePostTreatment()
{
}

int ifc_TreePostTreatment::BasifyTree(Map_Basified_Tree *&map_BasifTree)
{
	int res = 0;

	if (_map_BasifTree.size() != 0)
		_map_BasifTree.clear();

	STRUCT_IFCENTITY* st_IfcTree = nullptr;
	if (_CurrentIfcTree)
	{
		st_IfcTree =_CurrentIfcTree->Getstruct();
		if (st_IfcTree)
			res = BasifyTreeFrom(st_IfcTree);
		else
			res = 4002;//Format erreur: XXXYYY XXX=numero identifiant la routine , YYY=numéro de l'erreur dans cette routine

		map_BasifTree = &_map_BasifTree;
	}// if (_CurrentIfcTree)
	else
		res = 4001;//Format erreur: XXXYYY XXX=numero identifiant la routine , YYY=numéro de l'erreur dans cette routine


	return res;
}

int ifc_TreePostTreatment::BasifyTreeFrom(STRUCT_IFCENTITY *&st_IfcTree)
{
	int res = 0;
	//Memo adresse pointeur (si existe pas ajouté) et son type "Ifc" 
	// => la map permet de ne pas référencer de multiple fois une même entité 
	//    dans l'arbre, des entités sont référencés plusieurs fois car elles appartiennent à plusieurs objets
	_map_BasifTree[st_IfcTree] = st_IfcTree->ch_Type;

	list <STRUCT_IFCENTITY*> ::iterator it_Elem;
	for (it_Elem = (st_IfcTree->st_Contains).begin(); it_Elem != (st_IfcTree->st_Contains).end(); it_Elem++)
	{
		res = BasifyTreeFrom((*it_Elem));
		if (res) return res;
	}// for (it_Elem = (st_IfcTree->st_Contains).begin(); it_Elem != (st_IfcTree->st_Contains).end(); it_Elem++)

	return res;
}

int ifc_TreePostTreatment::CompleteBasifiedTreeFromByTIFCSurfaces()
{
	int res = 0;

	std::map<STRUCT_IFCENTITY*, std::string>::reverse_iterator it_Elem;
	for (it_Elem = _map_BasifTree.rbegin(); it_Elem != _map_BasifTree.rend(); it_Elem++)
	{
		if (it_Elem->first->st_TIFCSurface)
			_map_BasifTree[it_Elem->first->st_TIFCSurface] = it_Elem->first->st_TIFCSurface->ch_Type;
	}// for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)

	return res;
}

//Retrait dans les contours (st_PointsDesContours) du dernier point lorsqu'il est égal au 1er (+ consigne bool bo_IsItLoop=true)
int ifc_TreePostTreatment::RemoveLastPointOfLoopContours(string *&str_LogFile)
{
	int res = 0;

	std::map<STRUCT_IFCENTITY*, std::string>::iterator it_Elem;
	for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)
	{
		if (it_Elem->first->st_PointsDesContours.size() != 0)
			res = RemoveLastPointOfOneLoopContour(it_Elem->first,str_LogFile);
		if (res) return res;
	}// for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)

	return res;
}

//Retrait dans le contour (st_PointsDesContours) du derniers point lorsqu'il est égal au 1er (+ consigne bool bo_IsItLoop=true)
int ifc_TreePostTreatment::RemoveLastPointOfOneLoopContour(STRUCT_IFCENTITY *st_IfcEnt, string *&str_LogFile)
{
	int res = 0;

	//Boucle sur les différents sous-contours
	list <list <double*>> ::iterator it_llPt;
	for (it_llPt = (st_IfcEnt->st_PointsDesContours).begin(); it_llPt != (st_IfcEnt->st_PointsDesContours).end(); it_llPt++)
	{
		//Verif si 1er pt=dernier pt => si oui retirer le dernier pt (les 3 dernières coordonnées) + consigne bool bo_IsItLoop=true
		list <double*> ::iterator it_lPt = it_llPt->begin();
		double X1 = *(*it_lPt); it_lPt++;
		double Y1 = *(*it_lPt); it_lPt++;
		double Z1 = *(*it_lPt);
		it_lPt = it_llPt->end(); it_lPt--;
		double ZN = *(*it_lPt); it_lPt--;
		double YN = *(*it_lPt); it_lPt--;
		double XN = *(*it_lPt);
		double db_Dist = sqrt((X1 - XN)*(X1 - XN)
			+ (Y1 - YN)*(Y1 - YN)
			+ (Z1 - ZN)*(Z1 - ZN));
		if (db_Dist < db_eps)
		{
			(*it_llPt).pop_back();
			(*it_llPt).pop_back();
			(*it_llPt).pop_back();

			st_IfcEnt->bo_ArePointsDesContoursALoop = true;

			//Consigner l'effacement du dernier point enlever dans un fichier "log" (ou mettre en mémoire => même principe que pour le fichier bimxbem)
			int int_Step = 0;
			string str_Header = "Remove Last Point If Equal First Point :";
			RecordLog(int_Step, *str_LogFile, str_Header, st_IfcEnt);

		}// if (db_Dist < 0.0000001)
	}// for (it_llPt = (st_IfcEnt->st_PointsDesContours).begin(); it_llPt != (st_IfcEnt->st_PointsDesContours).end(); it_llPt++)

	return res;
}

//Calcul des surfaces IfcConnectionSurfaceGeometry
int ifc_TreePostTreatment::ComputeIfcConnectionSurfaceGeometrySurface()
{
	int res = 0;

	std::map<STRUCT_IFCENTITY*, std::string>::iterator it_Elem;
	for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)
	{
		if (it_Elem->second == "IfcConnectionSurfaceGeometry")
			res = ComputeOneIfcConnectionSurfaceGeometrySurface(it_Elem->first);
		if (res) return res;
	}// for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)

	return res;
}

//Calcul de la surface d'une IfcConnectionSurfaceGeometry
int ifc_TreePostTreatment::ComputeOneIfcConnectionSurfaceGeometrySurface(STRUCT_IFCENTITY *st_IfcEntCS)
{
	int res = 0;

	//Recup de toutes les coordonnées de tous les points du contour
	double db_TotalSurf = 0.0;
	vector<double*> vc_PointCoordCtr1;
	for (list<STRUCT_IFCENTITY *>::iterator it_lEnt = (st_IfcEntCS->st_Contains).begin(); it_lEnt != (st_IfcEntCS->st_Contains).end(); it_lEnt++)
	{
		for (list<list<double*>>::iterator it_llCtr = ((*it_lEnt)->st_PointsDesContours).begin(); it_llCtr != ((*it_lEnt)->st_PointsDesContours).end(); it_llCtr++)
		{
			//Recup du contour
			vc_PointCoordCtr1.insert(vc_PointCoordCtr1.end(), (*it_llCtr).begin(), (*it_llCtr).end());
			
			//Fermer le contour par ajout du premier Pt en dernier (nécessaire au calcul de la surface)
			vector<double*>::iterator it_CoordPt1_end = vc_PointCoordCtr1.begin(); ++++++it_CoordPt1_end;
			vc_PointCoordCtr1.insert(vc_PointCoordCtr1.end(), vc_PointCoordCtr1.begin(), it_CoordPt1_end);

			//Calcul de la surface définie par ce contour + Somme des differentes surfaces déjà calculés
			db_TotalSurf += ComputeSurfaceFromAContour(vc_PointCoordCtr1);
		}// for (list<list<double*>>::iterator it_llCtr = ((*it_lEnt)->st_PointsDesContours).begin(); it_llCtr != ((*it_lEnt)->st_PointsDesContours).end(); it_llCtr++)
	}// for (list<STRUCT_IFCENTITY *>::iterator it_lEnt = (st_IfcEntCS->st_Contains).begin(); it_lEnt != (st_IfcEntCS->st_Contains).end(); it_lEnt++)

	Map_String_String map_messages;
	map_messages["ComputedArea"] = to_string(db_TotalSurf);
	if (_CurrentIfcTree)
		_CurrentIfcTree->FillQuantitiesAttributeOf_STRUCT_IFCENTITY(st_IfcEntCS, map_messages);
	else
		res = 4003;//Format erreur: XXXYYY XXX=numero identifiant la routine , YYY=numéro de l'erreur dans cette routine

	return res;
}

//Calcul d'une surface plane à partir de ses contours
double ifc_TreePostTreatment::ComputeSurfaceFromAContour(vector<double*> &vc_PointCoordCtr)
{
	//int res = 0;

	double db_Surf = 0.0;
	vector<double*>::iterator it_Coord1Pt1;/*P1_x*/
	for (it_Coord1Pt1 = vc_PointCoordCtr.begin(); it_Coord1Pt1 != ------(vc_PointCoordCtr.end()); ++++++it_Coord1Pt1)
	{
		vector<double*>::iterator it_Coord2Pt1 = it_Coord1Pt1;/*P1_x*/ ++it_Coord2Pt1;/*P1_y*/
		vector<double*>::iterator it_Coord1Pt2 = it_Coord2Pt1;/*P1_y*/ ++it_Coord1Pt2;/*P1_z*/ ++it_Coord1Pt2;/*P2_x*/
		vector<double*>::iterator it_Coord2Pt2 = it_Coord1Pt2;/*P2_x*/ ++it_Coord2Pt2;/*P2_y*/
		db_Surf += (*(*it_Coord1Pt1)*(*(*it_Coord2Pt2)) - *(*it_Coord2Pt1)*(*(*it_Coord1Pt2))) / 2;
	}// for (it_Coord1Pt1 = vc_PointCoordCtr.begin(); it_Coord1Pt1 != vc_PointCoordCtr.end(); ++(++(++it_Coord1Pt1)))

	return db_Surf;
}

//Retrait des IfcConnectionSurfaceGeometry de surfaces inférieures à dbl_Minisurf
int ifc_TreePostTreatment::RemoveQuasiNullIfcConnectionSurfaceGeometrySurface(double dbl_Minisurf, string *&str_LogFile)
{
	int res = 0;

	std::map<STRUCT_IFCENTITY*, std::string>::iterator it_Elem;
	for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)
	{
		if (it_Elem->second == "IfcConnectionSurfaceGeometry")
			res = RemoveOneQuasiNullIfcConnectionSurfaceGeometrySurface(it_Elem->first,dbl_Minisurf, str_LogFile);
		if (res) return res;
	}// for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)

	return res;
}

void ifc_TreePostTreatment::RecordLog(int &int_Step, string &str_LogFile, string &str_Header, STRUCT_IFCENTITY *&st_IfcEnt)
{
	switch (int_Step)
	{
	case 0: 
		str_LogFile = str_LogFile /*+ "\n"*/ + str_Header + "\n";
		str_LogFile = str_LogFile + "\t" + st_IfcEnt->ch_Id + "\n";
		break;
	case 1: 
		str_LogFile = str_LogFile /*+ "\n" */ + str_Header + "\n";
		str_LogFile = str_LogFile + "\t" + st_IfcEnt->ch_Id + " (Surf = " + st_IfcEnt->map_DefValues->at("ComputedArea") + ")\n";
		break;
	case 2: 
		str_LogFile = str_LogFile /*+ "\n" */ + str_Header + "\n";
		break;
	default: return;
	}// switch (int_Step)

	return;
}

int ifc_TreePostTreatment::RemoveOneQuasiNullIfcConnectionSurfaceGeometrySurface(STRUCT_IFCENTITY *st_IfcEntCS, double dbl_Minisurf, string *&str_LogFile)
{
	int res = 0;

	double dbl_Surf = abs(std::stod(st_IfcEntCS->map_DefValues->at("ComputedArea")));
	if (dbl_Surf<dbl_Minisurf)
	{
		//
		//Consigner l'effacement de l'IfcConnectionSurfaceGeometry dans un fichier "log" (ou mettre en mémoire => même principe que pour le fichier bimxbem)
		int int_Step = 1;
		string str_Header = "Remove Quasi Null Surface < "+ std::to_string(dbl_Minisurf)+ ":";
		RecordLog(int_Step, *str_LogFile, str_Header, st_IfcEntCS);
		//
		// Nettoyage des listes référencant l'objet que l'on est en train de détruire
		// Pour les liens non binaires (ternaires ou plus) la structure en cours d'effacement (st_IfcTree) est référencée dans les Contains de plusieurs pères
		// Afin déviter un crash mémoire par la désallocation d'une structure déjà détruite, il faut déréférencer la structure 
		// en cours d'effacement des listes de BelongsTo des autres pères (que celui en cours = st_IfcCurrentFather)
		// Exemple: IfcConnectionSurfaceGeometry est référencé à la fois dans le st_Contains de IfSpace et des BuildingElements (IfcWall,...)
		_CurrentIfcTree->delete_STRUCT_IFCENTITY(st_IfcEntCS);
		st_IfcEntCS = nullptr;
	}

	return res;
}

//Creation des TIFCSurfaces par concatenation des IfcConnectionSurfaceGeometry en vis-à-vis
int ifc_TreePostTreatment::CreateTIFCSurfaces()
{
	int res = 0;

	std::map<STRUCT_IFCENTITY*, std::string>::iterator it_Elem;
	for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)
	{
		if (it_Elem->second == "IfcConnectionSurfaceGeometry")
			res= CreateTIFCSurface(it_Elem->first);
		if (res) return res;
	}// for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)

	return res;
}

//Creation d'une TIFCSurface par concatenation des 2 IfcConnectionSurfaceGeometry en vis-à-vis
int ifc_TreePostTreatment::CreateTIFCSurface(STRUCT_IFCENTITY *st_IfcEntCS)
{
	int res = 0;

	//On vérifie que cette IfcConnectionSurfaceGeometry (st_IfcEntCS) n'a pas déjà sa TIFCSurface 
	//car à sa création la même TIFCSurface est associée à 2 IfcConnectionSurfaceGeometry
	if (st_IfcEntCS && st_IfcEntCS->st_TIFCSurface==nullptr)
	{
		if (_CurrentIfcTree)
			res = _CurrentIfcTree->BuildTIFCSurfaceTreeFrom_STRUCT_IFCENTITY(st_IfcEntCS);
		else
			res = 4005;//Format erreur: XXXYYY XXX=numero identifiant la routine , YYY=numéro de l'erreur dans cette routine
	}
	//else
	//	res = 4004;//Format erreur: XXXYYY XXX=numero identifiant la routine , YYY=numéro de l'erreur dans cette routine

	return res;
}


//Calcul des isobarycentres des IfcConnectionSurfaceGeometry
int ifc_TreePostTreatment::CentroidsComputation()
{
	int res = 0;

	std::map<STRUCT_IFCENTITY*, std::string>::iterator it_Elem;
	for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)
	{
		if (it_Elem->second == "IfcConnectionSurfaceGeometry")
			res= CentroidComputation(it_Elem->first);
		if (res) return res;
	}// for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)

	return res;
}

//Calcul de l'isobarycentre d'une IfcConnectionSurfaceGeometry
int ifc_TreePostTreatment::CentroidComputation(STRUCT_IFCENTITY *st_IfcEntCS)
{
	int res = 0;

	//Init isobarycentre
	double db_IsoBar[3] = { 0.,0.,0. };

	//Compteur "i" qui, au final, sera egal au nombre de points des contours fois 3(=nbre de composantes=x,y,z)
	int i = 0;

	list <STRUCT_IFCENTITY*> ::iterator it_Elem;
	for (it_Elem = (st_IfcEntCS->st_Contains).begin(); it_Elem != (st_IfcEntCS->st_Contains).end(); it_Elem++)
	{
		//Boucle sur les coord pour calculer l'isobarycentre
		list <list <double*>> ::iterator it_llPt;
		for (it_llPt = ((*it_Elem)->st_PointsDesContours).begin(); it_llPt != ((*it_Elem)->st_PointsDesContours).end(); it_llPt++)
		{
			//lire la liste des points (le dernier point est toujours différent du 1er car a été enlevé par routine RemoveLastPointOfLoopContours)
			list <double*> ::iterator it_lPt;
			for (it_lPt = (*it_llPt).begin(); it_lPt != (*it_llPt).end(); it_lPt++)
			{
				db_IsoBar[i % 3] += *(*it_lPt);
				i++;
			}// for (it_lPt = (*it_llPt).begin(); it_lPt != (*it_llPt).end(); it_lPt++)
		}// for (it_llPt = ((*it_Elem)->st_PointsDesContours).begin(); it_llPt != ((*it_Elem)->st_PointsDesContours).end(); it_llPt++)
	}// for (it_Elem = (st_IfcEnt->st_Contains).begin(); it_Elem != (st_IfcEnt->st_Contains).end(); it_Elem++)

	//Finalisation du calcul de l'isobarycentre
	for(int j=0;j<3;j++)
		db_IsoBar[j] /= (i / 3);

	//Mémo dans la structure
	if (_CurrentIfcTree)
		_CurrentIfcTree->FillCentroidOf_STRUCT_IFCENTITY(st_IfcEntCS, db_IsoBar);
	else
		res = 4006;//Format erreur: XXXYYY XXX=numero identifiant la routine , YYY=numéro de l'erreur dans cette routine

	return res;
}

//Recherche des IfcConnectionSurfaceGeometry pouvant avoir des côtés à étendre (i.e. qui ont au moins 1 SideBySide) 
int ifc_TreePostTreatment::RelimitSideBySideSurfaces(string *&str_LogFile)
{
	int res = 0;

	//Traitement des IfcConnectionSurfaceGeometry pouvant avoir des côtés à étendre
	std::map<STRUCT_IFCENTITY*, std::string>::iterator it_Elem;
	for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)
	{
		//Recherche des IfcConnectionSurfaceGeometry qui ont au moins 1 SideBySide
		if (it_Elem->second == "IfcConnectionSurfaceGeometry" && it_Elem->first->mp_SideBySide.size() != 0)
			res = RelimitSideBySideSurfacesOfOneIfcConnectionSurfaceGeometry(it_Elem->first, str_LogFile);
		if (res) return res;
	}// for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)

	return res;
}

//Boucles sur les IfcConnectionSurfaceGeometry côte-àcôte avec l'IfcConnectionSurfaceGeometry en cours (pour extension du IfcConnectionSurfaceGeometry si nécessaire)
int ifc_TreePostTreatment::RelimitSideBySideSurfacesOfOneIfcConnectionSurfaceGeometry(STRUCT_IFCENTITY *st_IfcEntCS, string *&str_LogFile)
{
	int res = 0;

	//Retrouver les IfcConnectionSurfaceGeometry qui sont côte-à-côte avec l'IfcConnectionSurfaceGeometry en cours
	set<pair<STRUCT_IFCENTITY*, pair<double, bool>>>::iterator it_SideBySideIfcEntCS;
	//set<pair<STRUCT_IFCENTITY*, pair<double, bool>>, Comparator>::iterator it_SideBySideIfcEntCS;
	for (it_SideBySideIfcEntCS = (st_IfcEntCS->mp_SideBySide).begin(); it_SideBySideIfcEntCS != (st_IfcEntCS->mp_SideBySide).end(); it_SideBySideIfcEntCS++)
	{
		//retrouver les paires de points les plus proches (chaque point appartenant à l'un ou l'autre des IfcConnectionSurfaceGeometry côte-à-côtes)
		if (!(*it_SideBySideIfcEntCS).second.second)
		{
			RelimitOneSideBySideSurfaceOfOneIfcConnectionSurfaceGeometry(st_IfcEntCS, (*it_SideBySideIfcEntCS).first, str_LogFile);
			//(*it_SideBySideIfcEntCS).second.second = true;
			//(*it_SideBySideIfcEntCS).first->mp_SideBySide[st_IfcEntCS].second = true;
		}// if (!(*it_SideBySideIfcEntCS).second)
	}// for (it_Elem2 = (it_Elem1->first->st_Contains).begin(); it_Elem2 != (it_Elem1->first->st_Contains).end(); it_Elem2++)

	return res;
}

//Extension si besoin de l'IfcConnectionSurfaceGeometry en cours et d'un des IfcConnectionSurfaceGeometry côte-à-côtes 
//A priori on a 3 cas: 
// les IfcConnectionSurfaceGeometry en cours et côte-à-côte sont "coller" (Dist des pairs de pts les + proches = 0) => ne rien faire
// les IfcConnectionSurfaceGeometry en cours et côte-à-côte sont "disjoints" avec Dist des pairs de pts les + proches >> épaisseurs murs => ne rien faire
// les IfcConnectionSurfaceGeometry en cours et côte-à-côte sont "disjoints" avec Dist des pairs de pts les + proches ~ épaisseurs murs => jonction par milieu de la dist (cf. schéma):
//
// 2 ifcConn séparées     Raccord des 2 ifcconn 
//  par epaisseur mur        par leur milieu
//      ---  ---                --------
//        |  |          =>         |
//        |  |                     |
//      ---  ---                --------
int ifc_TreePostTreatment::RelimitOneSideBySideSurfaceOfOneIfcConnectionSurfaceGeometry(STRUCT_IFCENTITY *&st_IfcEntCS1, STRUCT_IFCENTITY *st_IfcEntCS2, string *&str_LogFile)
{
	int res = 0;

	//ATTENTION: ne pas lire les pts du ctr1 dans la routine précédente car les coordonnées sont suceptibles d'être modifiées => il faut les relire à chaque passage!
	//Recup de toutes les coordonnées de tous les points du 1er contour (IfcConnectionSurfaceGeometry en cours)
	vector<double*> vc_PointCoordCtr1;
	for (list<STRUCT_IFCENTITY *>::iterator it_lEnt = (st_IfcEntCS1->st_Contains).begin(); it_lEnt != (st_IfcEntCS1->st_Contains).end(); it_lEnt++)
		for (list<list<double*>>::iterator it_llCtr = ((*it_lEnt)->st_PointsDesContours).begin(); it_llCtr != ((*it_lEnt)->st_PointsDesContours).end(); it_llCtr++)
			vc_PointCoordCtr1.insert(vc_PointCoordCtr1.end(), (*it_llCtr).begin(), (*it_llCtr).end());

	//Recup de toutes les coordonnées de tous les points du 2ème contour (IfcConnectionSurfaceGeometry côte-à-côte)
	vector<double*> vc_PointCoordCtr2;
	for (list<STRUCT_IFCENTITY *>::iterator it_lEnt = (st_IfcEntCS2->st_Contains).begin(); it_lEnt != (st_IfcEntCS2->st_Contains).end(); it_lEnt++)
		for (list<list<double*>>::iterator it_llCtr = ((*it_lEnt)->st_PointsDesContours).begin(); it_llCtr != ((*it_lEnt)->st_PointsDesContours).end(); it_llCtr++)
			vc_PointCoordCtr2.insert(vc_PointCoordCtr2.end(), (*it_llCtr).begin(), (*it_llCtr).end());

	//
	//Calcul des distances entre chaque paire de points appartenant à chacun des contours des IfcConnectionSurfaceGeometry
	//  li_IndPtCtr1_IndPtCtr2_Dist[iterateur debut Pt_J du contour1, iterateur debut Pt_J du contour2]=distance
	//  Utilisation d'une liste pour profiter du tri optimisée "list::sort()"
	list< pair< pair<vector<double*>::iterator, vector<double*>::iterator>, double>> li_IndPtCtr1_IndPtCtr2_Dist;
	//Boucle sur tous les points de chacun des contours des IfcConnectionSurfaceGeometry en cours et côte-à-côte
	vector<double*>::iterator it_CoordCtr1;
	vector<double*>::iterator it_CoordCtr2;
	for (it_CoordCtr1 = vc_PointCoordCtr1.begin(); it_CoordCtr1 != vc_PointCoordCtr1.end(); ++(++(++it_CoordCtr1)))
	{
		vector<double*>::iterator it_CoordCtr1_end = it_CoordCtr1; ++++++it_CoordCtr1_end;
		vector<double*> vc_Point1(it_CoordCtr1, it_CoordCtr1_end);

		for (it_CoordCtr2 = vc_PointCoordCtr2.begin(); it_CoordCtr2 != vc_PointCoordCtr2.end(); ++(++(++it_CoordCtr2)))
		{
			vector<double*>::iterator it_CoordCtr2_end = it_CoordCtr2; ++++++it_CoordCtr2_end;
			vector<double*> vc_Point2(it_CoordCtr2, it_CoordCtr2_end);
			
			//Calculer distance entre les 2 points des 2 IfcConnectionSurfaceGeometry 
			double db_dist=ComputePtPtDistance(vc_Point1, vc_Point2);

			//Memo de la distance entre les 2 points des 2 IfcConnectionSurfaceGeometry vc_Point1 et vc_Point2
			li_IndPtCtr1_IndPtCtr2_Dist.push_back(std::make_pair(std::make_pair(it_CoordCtr1, it_CoordCtr2), db_dist));
		}// for (vector<double*>::iterator it_CoordCtr2 = vc_PointCoordCtr2.begin(); it_CoordCtr2 != vc_PointCoordCtr2.end(); it_CoordCtr2++)
	}// for (vector<double*>::iterator it_CoordCtr1 = vc_PointCoordCtr1.begin(); it_CoordCtr1 != vc_PointCoordCtr1.end(); it_CoordCtr1++)

	//Trier les paires par proximité pour trouver les points à rejoindre
	li_IndPtCtr1_IndPtCtr2_Dist.sort([](auto lhs, auto rhs) { return lhs.second < rhs.second; });

	//QUE FAIRE SI des paires de points sont quasi l'un sur l'autre => merger les 2 IfcConnectionSurfaceGeometry?? 
	//  ou verifier que l'une a une surface quasi nulle 
	// => la retirer? => Traitement à faire dès le début après RemoveLastPointOfLoopContours() mais attention au retrait à faire dans IfcSpace et elmt cstruction (Wall,...)
	// En tout cas si la 1ere paire de point est confondue on peut supposer que les 2 surfaces sont déjà connectées => pas de raccord à faire
	list< pair< pair<vector<double*>::iterator, vector<double*>::iterator>, double>>::iterator it_IndPtCtr1_IndPtCtr2_Dist = li_IndPtCtr1_IndPtCtr2_Dist.begin();
	//Si les contours ne sont pas "coller" (Dist > db_eps) et pas "disjoints" avec Dist >> épaisseurs murs max
	//  => on fait la jonction par le milieu des pairs de points distants les plus proches (jusqu'à distance arbitrairement au max 20% de plus que la 1ère distance la plus proche)
	//
	//Si Dist mini > épaisseurs murs max => rien à raccorder (il y a certainement une surface entre l'Ifcconn en cours et celle côte-à-côte) => voir un autre côte-à-côte
	if ((*it_IndPtCtr1_IndPtCtr2_Dist).second < db_ep_mur_max)
	{
		//
		//Si Dist mini < db_eps => rien à raccorder (les 2 surfaces sont connectées)  => voir un autre côte-à-côte
		if ((*it_IndPtCtr1_IndPtCtr2_Dist).second > db_eps)
		{
			//Memo de la distance de reference
			double db_Distref = (*it_IndPtCtr1_IndPtCtr2_Dist).second;

			//ATTENTION: il faut aussi voir si au moins les 2 premières paires de points ont à peu près la même distance:
			// sinon c'est un coin de surf qui est proche d'un autre coin d'une autre surf (pas côte-àcôte sur tout un côté) => ne pas raccorder dans ce cas
			list< pair< pair<vector<double*>::iterator, vector<double*>::iterator>, double>>::iterator it_IndPtCtr1_IndPtCtr2_Dist_Next = it_IndPtCtr1_IndPtCtr2_Dist;
			it_IndPtCtr1_IndPtCtr2_Dist_Next++;
			if ((*it_IndPtCtr1_IndPtCtr2_Dist_Next).second < 1.2*db_Distref)
			{
				//ATTENTION: il faut aussi voir si les 2 paires de points les plus proches ont bien des points distincts entre paires:
				//	pour (P1,P2) et (P3,P4) il faut P1 différent de P3 et P2 different de P4 
				//  sinon comme précédemment c'est un coin de surf qui est proche d'un autre coin d'une autre surf (pas côte-àcôte sur tout un côté) et 
				//  qui en plus est une minuscule surface (quasi-ligne) d'où un 2nd point proche du même coin => ne pas raccorder dans ce cas
				if ((*it_IndPtCtr1_IndPtCtr2_Dist).first.first != (*it_IndPtCtr1_IndPtCtr2_Dist_Next).first.first
					&& (*it_IndPtCtr1_IndPtCtr2_Dist).first.second != (*it_IndPtCtr1_IndPtCtr2_Dist_Next).first.second)
				{
					//
					//ATTENTION: Lorsqu'on a 2 minuscules surfaces (quasi-ligne) en côte-à-côte, on peut avoir en plus des 2 paires les plus proches
					// 2 autres paires qui sont en fait la croisée des points précédents => il ne faut pas modifier les points de ces paires!
					//   ------ ------   ------ ------      
					//        | |      et      X        
					//   ------ ------   ------ ------  
					// Si les points des paires suivants les 2 premières reprennent les points précédents => stopper le raccord
					// test à faire paire après paire (et non par doublons de paires) car par exemple il peut y avoir 3 points côte-à-côtes qui se raccordent)
					// => on compte le nombre de pairs modifiables (ne reprenant pas un des points des paires précédentes)
					int i_MaxNbModifiablePt = 1;

					//
					//REMARQUE: Ce test pourrait peut-être servir aussi au test prcdt équivalent mais en terme 
					//de cas concret le 1er test correspond à un cas identifié un peu différent de celui-ci. 
					//ici côté en côte-à-côte mais hauteur minuscule, dans cas prcdt ce sont les coins qui sont proches
					//De plus le test ici verifie "a posteriori" les raccords, alors que le test prcdt verifie "a priori" pour éviter de commencer un raccord 
					bool bo_IsModifiable = true;
					list< pair< pair<vector<double*>::iterator, vector<double*>::iterator>, double>>::iterator it_IndPtCtr1_IndPtCtr2_Dist_Cur_Tst = it_IndPtCtr1_IndPtCtr2_Dist;
					it_IndPtCtr1_IndPtCtr2_Dist_Cur_Tst++;
					for (it_IndPtCtr1_IndPtCtr2_Dist_Cur_Tst; it_IndPtCtr1_IndPtCtr2_Dist_Cur_Tst != li_IndPtCtr1_IndPtCtr2_Dist.end(); ++it_IndPtCtr1_IndPtCtr2_Dist_Cur_Tst)
					{
						list< pair< pair<vector<double*>::iterator, vector<double*>::iterator>, double>>::iterator it_IndPtCtr1_IndPtCtr2_Dist_Prev_Tst = it_IndPtCtr1_IndPtCtr2_Dist;
						for (it_IndPtCtr1_IndPtCtr2_Dist_Prev_Tst; it_IndPtCtr1_IndPtCtr2_Dist_Prev_Tst != it_IndPtCtr1_IndPtCtr2_Dist_Cur_Tst; ++it_IndPtCtr1_IndPtCtr2_Dist_Prev_Tst)
						{
							if ((*it_IndPtCtr1_IndPtCtr2_Dist_Cur_Tst).first.first == (*it_IndPtCtr1_IndPtCtr2_Dist_Prev_Tst).first.first
								|| (*it_IndPtCtr1_IndPtCtr2_Dist_Cur_Tst).first.second == (*it_IndPtCtr1_IndPtCtr2_Dist_Prev_Tst).first.second)
							{
								bo_IsModifiable = false;
								break;
							}// if ((*it_IndPtCtr1_IndPtCtr2_Dist_Cur_Tst).first.first == (*it_IndPtCtr1_IndPtCtr2_Dist_Prev_Tst).first.first
							//	|| (*it_IndPtCtr1_IndPtCtr2_Dist_Cur_Tst).first.second == (*it_IndPtCtr1_IndPtCtr2_Dist_Prev_Tst).first.second)
						}//for (it_IndPtCtr1_IndPtCtr2_Dist_Prev_Tst; it_IndPtCtr1_IndPtCtr2_Dist_Prev_Tst != it_IndPtCtr1_IndPtCtr2_Dist_Cur_Tst; ++it_IndPtCtr1_IndPtCtr2_Dist_Prev_Tst)
					
						if (bo_IsModifiable)
							i_MaxNbModifiablePt++;
						else 
							break;
					}// for (int icpt = 1; icpt < i_NbModifiedPt; i_NbModifiedPt++)

					//Variable pour compter le nombre de paires de points modifiées
					int i_NbModifiedPt = 0;
					string str_Header = "Join 2 Surfaces <" + std::string(st_IfcEntCS1->ch_Id) + ">--<" + st_IfcEntCS2->ch_Id + "> :";
					for (it_IndPtCtr1_IndPtCtr2_Dist; it_IndPtCtr1_IndPtCtr2_Dist!= li_IndPtCtr1_IndPtCtr2_Dist.end();++it_IndPtCtr1_IndPtCtr2_Dist)
					{
						//
						// 2 ifcConn séparées     Raccord des 2 ifcconn 
						//  par epaisseur mur        par leur milieu
						//      ---  ---                --------
						//        |  |          =>         |
						//        |  |                     |
						//      ---  ---                --------
						//
						//Remplacement des points les plus proches appartenant à un même côté (par leur point milieu)
						// HP: côté à peu près parallèle => les points d'un même côté sont les 1ères paires de même ordre de distance (arbitrairement au max 20% de plus que la 1ère distance)
						if ((*it_IndPtCtr1_IndPtCtr2_Dist).second < 1.2*db_Distref)
						{
							//
							// On incrémente le nombre de paires de points modifiées
							i_NbModifiedPt++;

							//On applique la relimitation sur les pts milieux que sur les pairs modifiables (ne reprenant pas un des points des paires précédentes)
							if (i_NbModifiedPt<=i_MaxNbModifiablePt)
							{
								//On prend un itérateur intermédiaire pour ne pas interférer avec celui (it_IndPtCtr1_IndPtCtr2_Dist) qui est utilisé pour les tests
								list< pair< pair<vector<double*>::iterator, vector<double*>::iterator>, double>>::iterator it_IndPtCtr1_IndPtCtr2_Dist_Cur = it_IndPtCtr1_IndPtCtr2_Dist;
								
								//Modification des 2 surfaces => remplacer les paires de points les plus proches par un même point milieu 
								//HP: les côtés à modifier sont des droites parallèles => remplacement des premières paires repérées par une distance similaire
								it_CoordCtr1 = (*it_IndPtCtr1_IndPtCtr2_Dist_Cur).first.first;
								it_CoordCtr2 = (*it_IndPtCtr1_IndPtCtr2_Dist_Cur).first.second;

								double db_NewCoord_X = ((*it_CoordCtr1)[0] + (*it_CoordCtr2)[0]) / 2.0; ++it_CoordCtr1; ++it_CoordCtr2;
								double db_NewCoord_Y = ((*it_CoordCtr1)[0] + (*it_CoordCtr2)[0]) / 2.0; ++it_CoordCtr1; ++it_CoordCtr2;
								double db_NewCoord_Z = ((*it_CoordCtr1)[0] + (*it_CoordCtr2)[0]) / 2.0;

								*(*((*it_IndPtCtr1_IndPtCtr2_Dist_Cur).first.first)) = db_NewCoord_X;
								*(*((*it_IndPtCtr1_IndPtCtr2_Dist_Cur).first.second)) = db_NewCoord_X;
								*(*(++(*it_IndPtCtr1_IndPtCtr2_Dist_Cur).first.first)) = db_NewCoord_Y;
								*(*(++(*it_IndPtCtr1_IndPtCtr2_Dist_Cur).first.second)) = db_NewCoord_Y;
								*(*(++(*it_IndPtCtr1_IndPtCtr2_Dist_Cur).first.first)) = db_NewCoord_Z;
								*(*(++(*it_IndPtCtr1_IndPtCtr2_Dist_Cur).first.second)) = db_NewCoord_Z;

								str_Header += "\n\tDist(P1,P2)=" + std::to_string((*it_IndPtCtr1_IndPtCtr2_Dist).second) + ";";

							}// if (bo_DoContinue)
							else
							{
								//
								//Consigner le raccord de l'IfcConnectionSurfaceGeometry dans un fichier "log" (ou mettre en mémoire => même principe que pour le fichier bimxbem)
								int int_Step = 2;
								RecordLog(int_Step, *str_LogFile, str_Header, st_IfcEntCS1);

								break;
							}// else if (bo_DoContinue)
						}// if ((*it_IndPtCtr1_IndPtCtr2_Dist).second < 1.2*db_Distref)
						else
						{
							//
							//Consigner le raccord de l'IfcConnectionSurfaceGeometry dans un fichier "log" (ou mettre en mémoire => même principe que pour le fichier bimxbem)
							int int_Step = 2;
							RecordLog(int_Step, *str_LogFile, str_Header, st_IfcEntCS1);

							break;
						}// else if ((*it_IndPtCtr1_IndPtCtr2_Dist).second < 1.2*db_Distref)
					}// for (it_IndPtCtr1_IndPtCtr2_Dist; it_IndPtCtr1_IndPtCtr2_Dist!= li_IndPtCtr1_IndPtCtr2_Dist.end();++it_IndPtCtr1_IndPtCtr2_Dist)
				}//if ((*it_IndPtCtr1_IndPtCtr2_Dist).first.first != (*it_IndPtCtr1_IndPtCtr2_Dist_Next).first.first
				// && (*it_IndPtCtr1_IndPtCtr2_Dist).first.second != (*it_IndPtCtr1_IndPtCtr2_Dist_Next).first.second)
			}// if ((*it_IndPtCtr1_IndPtCtr2_Dist_Next).second < 1.2*db_Distref)
		}// if ((*it_IndPtCtr1_IndPtCtr2_Dist).second > db_eps)
	}// if ((*it_IndPtCtr1_IndPtCtr2_Dist).second < db_ep_mur_max)

	return res;
}

int ifc_TreePostTreatment::TransformEntitiesToWorlCoordFrame()
{
	int res = 0;

	std::map<STRUCT_IFCENTITY*, std::string>::iterator it_Elem;
	for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)
	{
		if (it_Elem->first->st_PointsDesContours.size() != 0)
		{
			//Décompte du nombre de coord de points
			size_t i_Size = 0;
			list <list <double*>> ::iterator it_llPt;
			for (it_llPt = (it_Elem->first->st_PointsDesContours).begin(); it_llPt != (it_Elem->first->st_PointsDesContours).end(); it_llPt++)
				i_Size += it_llPt->size();

			//Allocation mémoire pour recueillir les coordonnées des points à modifier
			double * db_CoordPts = new double[i_Size];

			//Boucle sur les listes de coord 
			int i = 0;
			for (it_llPt = (it_Elem->first->st_PointsDesContours).begin(); it_llPt != (it_Elem->first->st_PointsDesContours).end(); it_llPt++)
			{
				//lire la liste des points 
				list <double*> ::iterator it_lPt;
				for (it_lPt = (*it_llPt).begin(); it_lPt != (*it_llPt).end(); it_lPt++)
				{
					db_CoordPts[i] = *(*it_lPt);
					i++;
				}// for (it_lPt = (*it_llPt).begin(); it_lPt != (*it_llPt).end(); it_lPt++)
			}// for (it_llPt = (it_Elem->first->st_PointsDesContours).begin(); it_llPt != (it_Elem->first->st_PointsDesContours).end(); it_llPt++)

			//Changer les coordonnées pour les mettre P/R au referentiel projet 
			res = TransformEntityToWorlCoordFrame(it_Elem->first, db_CoordPts, i_Size);
			if (res) return res;

			//Mémoriser dans la structure les points modifiés
			//A FAIRE
			//new liste de liste...
			i = 0;
			for (it_llPt = (it_Elem->first->st_PointsDesContours).begin(); it_llPt != (it_Elem->first->st_PointsDesContours).end(); it_llPt++)
			{
				//new liste...
				//lire la liste des points 
				list <double*> ::iterator it_lPt;
				for (it_lPt = (*it_llPt).begin(); it_lPt != (*it_llPt).end(); it_lPt++)
				{
					//liste...push_back(db_CoordPts[i]); 
					*(*it_lPt) = db_CoordPts[i];
					i++;
				}// for (it_lPt = (*it_llPt).begin(); it_lPt != (*it_llPt).end(); it_lPt++)
				//liste de liste...push_back(liste...);
			}// for (it_llPt = (it_Elem->first->st_PointsDesContours).begin(); it_llPt != (it_Elem->first->st_PointsDesContours).end(); it_llPt++)
			//it_Elem->first->st_PointsDesContoursRefAbs= liste de liste...;

			if (db_CoordPts)
				delete[] db_CoordPts;
			db_CoordPts = nullptr;
		}// if (it_Elem->first->st_PointsDesContours.size != 0)
	}// for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)

	return res;
}

int ifc_TreePostTreatment::TransformEntityToWorlCoordFrame(STRUCT_IFCENTITY *st_IfcEnt, double *&db_CoordPts, size_t int_Size)
{
	int res = 0;
	
	//S'il existe db_RelativePlacement sur l'entité en cours on l'applique
	if (st_IfcEnt->db_RelativePlacement.size() != 0)
	{
		list <double*> ::iterator it_val = (st_IfcEnt->db_RelativePlacement).begin();
		double U1[3];
		U1[0] = *(*it_val); it_val++;
		U1[1] = *(*it_val); it_val++;
		U1[2] = *(*it_val); it_val++;
		double U2[3];
		U2[0] = *(*it_val); it_val++;
		U2[1] = *(*it_val); it_val++;
		U2[2] = *(*it_val); it_val++;
		double U3[3];
		U3[0] = *(*it_val); it_val++;
		U3[1] = *(*it_val); it_val++;
		U3[2] = *(*it_val); it_val++;
		double O[3];
		O[0] = *(*it_val); it_val++;
		O[1] = *(*it_val); it_val++;
		O[2] = *(*it_val); it_val++;

		//Coordonnées dans le nouveau repère
		for (int iCoord = 0; iCoord < int_Size; iCoord += 3)
		{
			double db_NewCoordPts[3] = { 0, 0, 0 };
			db_NewCoordPts[0] = O[0] + U1[0] * db_CoordPts[iCoord] + U2[0] * db_CoordPts[iCoord + 1] + U3[0] * db_CoordPts[iCoord + 2];
			db_NewCoordPts[1] = O[1] + U1[1] * db_CoordPts[iCoord] + U2[1] * db_CoordPts[iCoord + 1] + U3[1] * db_CoordPts[iCoord + 2];
			db_NewCoordPts[2] = O[2] + U1[2] * db_CoordPts[iCoord] + U2[2] * db_CoordPts[iCoord + 1] + U3[2] * db_CoordPts[iCoord + 2];

			db_CoordPts[iCoord + 0] = db_NewCoordPts[0];
			db_CoordPts[iCoord + 1] = db_NewCoordPts[1];
			db_CoordPts[iCoord + 2] = db_NewCoordPts[2];
		}// for (int iCoord = 0; iCoord < int_Size; iCoord += 3)
	}// if (st_IfcEnt->db_RelativePlacement.size != 0)

	//Remonter les BelongsTo pour appliquer à chaque pas le db_RelativePlacement s'il existe
	//IMPORTANT: S'il existe 2 BelongsTo (on se trouve au niveau du IfcConnectionSurfaceGeometry) prendre le ifcSpace et non l'élément de construction
	if (st_IfcEnt->st_BelongsTo.size() == 1)
	{
		res = TransformEntityToWorlCoordFrame(*(st_IfcEnt->st_BelongsTo.begin()), db_CoordPts, int_Size);
		if (res) return res;
	}// if (st_IfcEnt->st_BelongsTo.size == 1)
	else if (st_IfcEnt->st_BelongsTo.size() == 2)
	{
		list <STRUCT_IFCENTITY*> ::iterator it_Elem = (st_IfcEnt->st_BelongsTo).begin();
		if (string((*it_Elem)->ch_Type) == "IfcSpace")
		{
			res = TransformEntityToWorlCoordFrame((*it_Elem), db_CoordPts, int_Size);
			if (res) return res;
		}// if ((*it_Elem)->ch_Type = "IfcSpace")
		else 
		{
			it_Elem++;
			if (string((*it_Elem)->ch_Type) == "IfcSpace")
			{
				res = TransformEntityToWorlCoordFrame((*it_Elem), db_CoordPts, int_Size);
				if (res) return res;
			}// if (string((*it_Elem)->ch_Type) == "IfcSpace")
			else
				res = 4008;//Format erreur: XXXYYY XXX=numero identifiant la routine , YYY=numéro de l'erreur dans cette routine
		}// else if ((*it_Elem)->ch_Type = "IfcSpace")
	}// if (st_IfcEnt->st_BelongsTo.size == 1)
	else if (st_IfcEnt->st_BelongsTo.size() > 2)
		res = 4007;//Format erreur: XXXYYY XXX=numero identifiant la routine , YYY=numéro de l'erreur dans cette routine

	return res;
}

//Recherche des surfaces IfcConnectionSurfaceGeometry en vis-à-vis et côte-à-côte
int ifc_TreePostTreatment::FindFaceToFaceAndSideBySideSurfaces()
{
	int res = 0;

	//Recherche de tous les elements de construction
	// => sont sous IfcSpace->st_Contains et ce qui n'est ni IfcConnectionSurfaceGeometry ni IfcProductDefinitionShape
	std::map<STRUCT_IFCENTITY*, std::string> map_BuildingElem_Type;
	std::map<STRUCT_IFCENTITY*, std::string>::iterator it_Elem1;
	for (it_Elem1 = _map_BasifTree.begin(); it_Elem1 != _map_BasifTree.end(); it_Elem1++)
	{
		if (it_Elem1->second == "IfcSpace")
		{
			list <STRUCT_IFCENTITY*> ::iterator it_Elem2;
			for (it_Elem2 = (it_Elem1->first->st_Contains).begin(); it_Elem2 != (it_Elem1->first->st_Contains).end(); it_Elem2++)
			{
				//HP: Le contains des spaces est composé de IfcProductDefinitionShape, de IfcConnectionSurfaceGeometry et d'élément de construction
				//Recup des Elements de Construction
				if (string((*it_Elem2)->ch_Type) != "IfcConnectionSurfaceGeometry")
				{
					if(string((*it_Elem2)->ch_Type) != "IfcProductDefinitionShape")
						map_BuildingElem_Type[(*it_Elem2)] = (*it_Elem2)->ch_Type;
				}//
				else
				{
					//On initialise le set mp_SideBySide pour y mettre le comparatur qui ordonne selon la distance croissante
					set<pair<STRUCT_IFCENTITY*, pair<double, bool>>, Comparator> setOfIfcConnSideBySide_Init(_CurrentIfcTree->compFunctor);
					(*it_Elem2)->mp_SideBySide = setOfIfcConnSideBySide_Init;
				}
			}// for (it_Elem2 = (it_Elem1->first->st_Contains).begin(); it_Elem2 != (it_Elem1->first->st_Contains).end(); it_Elem2++)
		}// if (it_Elem1->second == "IfcSpace")
	}// for (it_Elem1 = _map_BasifTree.begin(); it_Elem1 != _map_BasifTree.end(); it_Elem1++)

	//Boucle sur les elements de construction 
	map<STRUCT_IFCENTITY*, std::string>::iterator it_BuildingElem;
	for (it_BuildingElem = map_BuildingElem_Type.begin(); it_BuildingElem != map_BuildingElem_Type.end(); it_BuildingElem++)
	{
		res = FindFaceToFaceAndSideBySideSurfacesOfOneBuildingelement(it_BuildingElem->first);
		if (res) return res;
	}// for (it_BuildingElem = map_BuildingElem_Type.begin(); it_BuildingElem != map_BuildingElem_Type.end(); it_BuildingElem++)

	return res;
}

//Routine pour trouver sur un même élément de construction 
//	les surfaces en vis à vis (chacun appartenant à un espace différent)
//	les surfaces côte à côte (chacun appartenant à un même espace)
int ifc_TreePostTreatment::FindFaceToFaceAndSideBySideSurfacesOfOneBuildingelement(STRUCT_IFCENTITY *st_IfcEntBE)
{
	int res = 0;
	
	//
	//Préparations des éléments d'informations nécessaires aux algo de FaceToFace et SideBySide
	//

	//Mapping entre les IfcConnectionSurfaceGeometry de l'élément de construction et leur IfcSpace
	map<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *> map_IfcConn_IfcSpace;
	map<STRUCT_IFCENTITY *, int> map_IfcSpace_NbIfcConn;
	list <STRUCT_IFCENTITY*> ::iterator it_Elem1;
	list <STRUCT_IFCENTITY*> ::iterator it_Elem2;
	for (it_Elem1 = (st_IfcEntBE->st_Contains).begin(); it_Elem1 != (st_IfcEntBE->st_Contains).end(); it_Elem1++)
	{
		for (it_Elem2 = ((*it_Elem1)->st_BelongsTo).begin(); it_Elem2 != ((*it_Elem1)->st_BelongsTo).end(); it_Elem2++)
		{
			if (string((*it_Elem2)->ch_Type) == "IfcSpace")
			{
				map_IfcConn_IfcSpace[(*it_Elem1)] = (*it_Elem2);
				map_IfcSpace_NbIfcConn[(*it_Elem2)] += 1;
			}// if (string((*it_Elem2)->ch_Type) == "IfcSpace")
		}// for (it_Elem2 = ((*it_Elem1)->st_BelongsTo).begin(); it_Elem2 != ((*it_Elem1)->st_BelongsTo).end(); it_Elem2++)
	}// for (it_Elem1 = (st_IfcEntBE->st_Contains).begin(); it_Elem1 != (st_IfcEntBE->st_Contains).end(); it_Elem1++)

	//
	//Calcul des distances entre centre de gravité de chaque paire de IfcConnectionSurfaceGeometry
	//  li_IfcConn_IfcConn_Dist[IfcConnectionSurfaceGeometry1, IfcConnectionSurfaceGeometry2]=distance
	//  Utilisation d'une liste pour profiter du tri optimisée "list::sort()"
	list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>> li_IfcConn_IfcConn_Dist;
	//Boucle sur st_Contains pour retrouver tous les IfcConnectionSurfaceGeometry
	for (it_Elem1 = (st_IfcEntBE->st_Contains).begin(); it_Elem1 != (st_IfcEntBE->st_Contains).end(); it_Elem1++)
	{
		//Calculer distance entre chaque IfcConnectionSurfaceGeometry de l'élément de construction 
		//	même si appartiennent à même ifcspace => utile pour les SideBySide
		it_Elem1++;
		for (it_Elem2 = it_Elem1, it_Elem1--; it_Elem2 != (st_IfcEntBE->st_Contains).end(); it_Elem2++)
		{
			//Calcul distance des isobarycentres
			std::vector<double*> vc_CentroidElem1((*it_Elem1)->db_Centroid.begin(), (*it_Elem1)->db_Centroid.end());
			std::vector<double*> vc_CentroidElem2((*it_Elem2)->db_Centroid.begin(), (*it_Elem2)->db_Centroid.end());
			double db_dist = ComputePtPtDistance(vc_CentroidElem1, vc_CentroidElem2);

			//Init de la carte qui indiquera si la paire d'IfcConnectionSurfaceGeometry en index n'est pas cote à cote
			//map_CanBeSideBySide[std::make_pair((*it_Elem1), (*it_Elem2))] = true;
			//Memo de la distance entre les 2 IfcConnectionSurfaceGeometry (*it_Elem1) et (*it_Elem2)
			li_IfcConn_IfcConn_Dist.push_back(std::make_pair(std::make_pair((*it_Elem1), (*it_Elem2)), db_dist));
			//}// if (map_IfcConn_IfcSpace[(*it_Elem1)] != map_IfcConn_IfcSpace[(*it_Elem2)])
		}// for (it_Elem = (st_IfcEnt->st_Contains).begin(); it_Elem != (st_IfcEnt->st_Contains).end(); it_Elem++)
	}// for (it_Elem = (st_IfcEnt->st_Contains).begin(); it_Elem != (st_IfcEnt->st_Contains).end(); it_Elem++)

	//Trier les paires par proximité pour trouver les surfaces en "vis à vis" et celles "côte à côte" (sur un même élément de construction)
	li_IfcConn_IfcConn_Dist.sort([](auto lhs, auto rhs) { return lhs.second < rhs.second; });

	//
	//Détection des IfcConnectionSurfaceGeometry en vis-à-vis
	res = FindFaceToFaceSurfacesOfOneBuildingelement(st_IfcEntBE, map_IfcConn_IfcSpace, li_IfcConn_IfcConn_Dist);
	if (res) return res;

	//
	//Détection des IfcConnectionSurfaceGeometry en côte-à-côte
	res = FindSideBySideSurfacesOfOneBuildingelement(st_IfcEntBE, map_IfcConn_IfcSpace, li_IfcConn_IfcConn_Dist, map_IfcSpace_NbIfcConn);

	return res;
}

//Algo pour détecter les IfcConnectionSurfaceGeometry en vis-à-vis
//  st_IfcEntBE est l'élément de construction en cours (on utilise son épaisseur pour éviter des faux positifs)
//  map_IfcConn_IfcSpace associe un IfcConnectionSurfaceGeometry (de l'élément de construction en cours) avec son IfcSpace (utiliser pour ne pas associer 2 IfcConnectionSurfaceGeometry du même IfcSpace)
//  li_IfcConn_IfcConn_Dist: liste de paire d'IfcConnectionSurfaceGeometry ORDONNEE en fonction de leur distance (permet de déterminer les vis-à-vis)
int ifc_TreePostTreatment::FindFaceToFaceSurfacesOfOneBuildingelement(STRUCT_IFCENTITY *st_IfcEntBE, map<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *> &map_IfcConn_IfcSpace, list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>> &li_IfcConn_IfcConn_Dist)
{
	int res = 0;

	//Surfaces en vis à vis (sur un même élément de construction) 
	//Repérer les surfaces les plus proches et en vis à vis (=distance centre de gravite < 2*epaisseur mur)
	std::map<STRUCT_IFCENTITY*, bool> map_IsEntityFound;
	for (list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>>::iterator it = li_IfcConn_IfcConn_Dist.begin(); it != li_IfcConn_IfcConn_Dist.end(); ++it)
	{
		//Si les 2 IfcConnectionSurfaceGeometry appartiennent à des ifcspace différent=> on continue (sinon on passe à une autre pair)
		if (map_IfcConn_IfcSpace[(*it).first.first] != map_IfcConn_IfcSpace[(*it).first.second])
		{
			//Si les 2 IfcConnectionSurfaceGeometry n'ont pas encore touvé leur vis à vis => on continue (sinon on passe à une autre pair)
			if (!map_IsEntityFound[(*it).first.first] && !map_IsEntityFound[(*it).first.second])
			{
				//la distance entre 2 surfaces en vis a vis est environ l'epaisseur du mur
				//par contre s'il n'y a pas de mur en vis a vis (mur exterieur) les plus proches peuvent etre des surface cote à cote et non en vis a vis
				// => le "if" qui suit permet d'exclure ce genre de faux positifs (cra distance des centre de gravité sont de distance > à epaisseur)
				double db_cp = (*it).second;
				double db_rd = std::stod(st_IfcEntBE->map_DefValues->at("Width"));
				if ((*it).second < 2 * std::stod(st_IfcEntBE->map_DefValues->at("Width")))
				{
					(*it).first.first->st_FaceToFace.push_back((*it).first.second);
					(*it).first.second->st_FaceToFace.push_back((*it).first.first);

					map_IsEntityFound[(*it).first.first] = true;
					map_IsEntityFound[(*it).first.second] = true;
				}// if ((*it).second < 2*std::stod(st_IfcEnt->map_DefValues->at("Width"))) 
			}// if (!map_IsEntityFound[(*it).first.first] && !map_IsEntityFound[(*it).first.second])
		}// if (map_IfcConn_IfcSpace[(*it).first.first] != map_IfcConn_IfcSpace[(*it).first.second])
	}// for (list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>>::iterator it = li_IfcConn_IfcConn_Dist.begin(); it != li_IfcConn_IfcConn_Dist.end(); ++it)

	return res;
}

//Algo pour détecter les IfcConnectionSurfaceGeometry côte-à-côte
//  st_IfcEntBE est l'élément de construction en cours (n'est pas utilisé mais si besoin pourrait l'être...)
//  map_IfcConn_IfcSpace associe un IfcConnectionSurfaceGeometry (de l'élément de construction en cours) avec son IfcSpace (utiliser pour ne pas associer des IfcConnectionSurfaceGeometry d'IfcSpaces différents)
//  li_IfcConn_IfcConn_Dist: liste de paire d'IfcConnectionSurfaceGeometry (de l'élément de construction en cours) ORDONNEE en fonction de leur distance (permet de déterminer les côte-à-côte)
//  map_IfcSpace_NbIfcConn détermine le nombre d'IfcConnectionSurfaceGeometry par IfcSpace (permet à la fois de boucler sur les ifcSpaces et de déterminer "l'algo" en fonction du nombre d'IfcConnectionSurfaceGeometry)
int ifc_TreePostTreatment::FindSideBySideSurfacesOfOneBuildingelement(STRUCT_IFCENTITY *st_IfcEntBE, map<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *> &map_IfcConn_IfcSpace, list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>> &li_IfcConn_IfcConn_Dist, map<STRUCT_IFCENTITY *, int> &map_IfcSpace_NbIfcConn)
{
	int res = 0;

	//Surfaces côte à côte (sur un même élément de construction)
	//Paires de Surfaces les plus proches qui ne soient pas en vis à vis et appartenant à un même espace
	//Repérer les paires de surfaces appartenant à même espace
	map<STRUCT_IFCENTITY *, int> ::iterator mp_Space;
	for (mp_Space = map_IfcSpace_NbIfcConn.begin(); mp_Space != map_IfcSpace_NbIfcConn.end(); mp_Space++)
	{
		for (list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>>::iterator it = li_IfcConn_IfcConn_Dist.begin(); it != li_IfcConn_IfcConn_Dist.end(); ++it)
		{
			//Si les 2 IfcConnectionSurfaceGeometry appartiennent à 1 même ifcspace => on continue
			if (map_IfcConn_IfcSpace[(*it).first.first] == map_IfcConn_IfcSpace[(*it).first.second])
			{
				//Si les 2 IfcConnectionSurfaceGeometry appartiennent au même ifcspace en cours => on continue
				if (map_IfcConn_IfcSpace[(*it).first.first] == (*mp_Space).first)
				{
					(*it).first.first->mp_SideBySide.insert(std::make_pair((*it).first.second, std::make_pair((*it).second, false)));
					(*it).first.second->mp_SideBySide.insert(std::make_pair((*it).first.first, std::make_pair((*it).second, false)));

					//REMARQUE:
					// Si besoin d'optimiser on peut mettre un compteur ici pour compter le nombre de pairs trouvées.
					// et mettre un test, pour faire un break, sur le nombre de pairs car il doit y en avoir : ((*mp_Space).second-1)*(*mp_Space).second)/2 
					// Pour rappel, map_IfcConn_IfcSpace contient les ifcConn appartenant à un seul mur
					//break;
				}// if (map_IfcConn_IfcSpace[(*it).first.first] == (*mp_Space).first)
			}// if (map_IfcConn_IfcSpace[(*it).first.first] == map_IfcConn_IfcSpace[(*it).first.second])
		}//for (list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>>::iterator it = li_IfcConn_IfcConn_Dist.begin(); it != li_IfcConn_IfcConn_Dist.end(); ++it)
	}// for (mp_Elem1 = map_IfcSpace_NbIfcConn.begin(); mp_Elem1 != map_IfcSpace_NbIfcConn.end(); mp_Elem1++)

	return res;
}

double ifc_TreePostTreatment::ComputePtPtDistance(vector<double*> &vc_Point1, vector<double*> &vc_Point2)
{
	double db_dist = sqrt((*vc_Point2[0] - *vc_Point1[0])*(*vc_Point2[0] - *vc_Point1[0])
						+ (*vc_Point2[1] - *vc_Point1[1])*(*vc_Point2[1] - *vc_Point1[1])
						+ (*vc_Point2[2] - *vc_Point1[2])*(*vc_Point2[2] - *vc_Point1[2]));
	return db_dist;
}

map<STRUCT_IFCENTITY*, pair<bool, double>>::iterator ifc_TreePostTreatment::get_Index_Of_Max(map<STRUCT_IFCENTITY*, pair<bool, double>> &x)
{
	map<STRUCT_IFCENTITY*, pair<bool, double>>::iterator first = x.begin();
	map<STRUCT_IFCENTITY*, pair<bool, double>>::iterator last = x.end();

	map<STRUCT_IFCENTITY*, pair<bool, double>>::iterator largest = first;
	if (first == last) return largest;
	while (++first != last)
		if ((*largest).second.second<(*first).second.second)
			largest = first;
	return largest;
}

//int ifc_TreePostTreatment::SortSideBySideSurfacesOfIfcConnectionSurfaceGeometry(STRUCT_IFCENTITY *st_IfcEntCS)
//{
//	int i_Res = 0;
//
//	// Declaring the type of Predicate that accepts 2 pairs and return a bool
//	//typedef function<bool(pair<STRUCT_IFCENTITY*, pair<double, bool>>, pair<STRUCT_IFCENTITY*, pair<double, bool>>)> Comparator;
//
//	// Defining a lambda function to compare two pairs. It will compare two pairs using second field
//	//Comparator compFunctor =
//	//	[](pair<STRUCT_IFCENTITY*, pair<double, bool>> elem1, pair<STRUCT_IFCENTITY*, pair<double, bool>> elem2)
//	//{
//	//	return elem1.second.first < elem2.second.first;
//	//};
//
//	// Declaring a set that will store the pairs using above comparision logic
//	//map<STRUCT_IFCENTITY*, pair<double, bool>, Comparator> mapOfIfcConnSideBySide(st_IfcEntCS->mp_SideBySide.begin(), st_IfcEntCS->mp_SideBySide.end(), compFunctor);
//	set<pair<STRUCT_IFCENTITY*, pair<double, bool>>, Comparator> setOfIfcConnSideBySide(st_IfcEntCS->mp_SideBySide.begin(), st_IfcEntCS->mp_SideBySide.end(), _CurrentIfcTree->compFunctor);
//
//	st_IfcEntCS->mp_SideBySide.swap(setOfIfcConnSideBySide);
//
//	// Iterate over a set using range base for loop
//	// It will display the items in sorted order of values
//	//for (pair<STRUCT_IFCENTITY*, pair<double, bool>> element : setOfIfcConnSideBySide)
//	//{
//	//	st_IfcEntCS->mp_SideBySide.insert(element);
//	//}// for (pair<STRUCT_IFCENTITY*, pair<double, bool>> element : setOfIfcConnSideBySide)
//
//	return i_Res;
//}

////
//// POUR MEMO (1/2)...
////
//
//Algo pour détecter les côte-à-côtes (cette détection permet de repérer les surfaces qui sont espacé de l'épaisseurs d'un mur pour les prolonger l'un vers l'autre)
// => ATTENTION: Algo pas fiable si les surfaces ne sont pas distribuer "selon une direction" i.e. s'il y a des surfaces à droite/gauche (1 direction) mais aussi en haut/en bas (2nde direction)!!!
// Par exemple le problème arrive avec les "surfaces quasi-nulles" qui sont bien souvent des quasi-lignes sur différents bords!
//int ifc_TreePostTreatment::FillSideBySideSurfacesOfOneBuildingelement(STRUCT_IFCENTITY *st_IfcConn_Left, STRUCT_IFCENTITY *st_IfcConn_Middle, STRUCT_IFCENTITY *st_IfcConn_Right, double dbl_Dist_Left_Mid, double dbl_Dist_Mid_Right)
//{
//	int iRes = 0;
//
//	// ajouter systematiquement les 2 plus proches et retirer les max si plus de 2 proches!
//	//S1->sideBySide(S2)
//	st_IfcConn_Left->mp_SideBySide[st_IfcConn_Middle] = std::make_pair(false, dbl_Dist_Left_Mid);
//	//S2->sideBySide(S1)
//	st_IfcConn_Middle->mp_SideBySide[st_IfcConn_Left] = std::make_pair(false, dbl_Dist_Left_Mid);
//	//S2->sideBySide(S3)
//	st_IfcConn_Middle->mp_SideBySide[st_IfcConn_Right] = std::make_pair(false, dbl_Dist_Mid_Right);
//	//S3->sideBySide(S2)
//	st_IfcConn_Right->mp_SideBySide[st_IfcConn_Middle] = std::make_pair(false, dbl_Dist_Mid_Right);
//
//	//retirer le max si plus de 2 proches!
//	if (st_IfcConn_Middle->mp_SideBySide.size() > 2)
//	{
//		map<STRUCT_IFCENTITY*, pair<bool, double>>::iterator max_it_f_s = get_Index_Of_Max(st_IfcConn_Middle->mp_SideBySide);
//		(*max_it_f_s).first->mp_SideBySide.erase(st_IfcConn_Middle);
//		st_IfcConn_Middle->mp_SideBySide.erase(max_it_f_s);
//	}// if (st_IfcConn_Middle->mp_SideBySide.size() > 1)
//
//	 //retirer le max si plus de 2 proches!
//	if (st_IfcConn_Left->mp_SideBySide.size() > 2)
//	{
//		map<STRUCT_IFCENTITY*, pair<bool, double>>::iterator max_it_f_s = get_Index_Of_Max(st_IfcConn_Left->mp_SideBySide);
//		(*max_it_f_s).first->mp_SideBySide.erase(st_IfcConn_Left);
//		st_IfcConn_Left->mp_SideBySide.erase(max_it_f_s);
//	}// if (st_IfcConn_Left->mp_SideBySide.size() > 1)
//
//	 //retirer le max si plus de 2 proches!
//	if (st_IfcConn_Right->mp_SideBySide.size() > 2)
//	{
//		map<STRUCT_IFCENTITY*, pair<bool, double>>::iterator max_it_f_s = get_Index_Of_Max(st_IfcConn_Right->mp_SideBySide);
//		(*max_it_f_s).first->mp_SideBySide.erase(st_IfcConn_Right);
//		st_IfcConn_Right->mp_SideBySide.erase(max_it_f_s);
//	}// if (st_IfcConn_Right->mp_SideBySide.size() > 1)
//
//	return iRes;
//}
////
//// POUR MEMO (2/2)...
////
////Algo pour détecter les IfcConnectionSurfaceGeometry côte-à-côte
////  st_IfcEntBE est l'élément de construction en cours (n'est pas utilisé mais si besoin pourrait l'être...)
////  map_IfcConn_IfcSpace associe un IfcConnectionSurfaceGeometry (de l'élément de construction en cours) avec son IfcSpace (utiliser pour ne pas associer des IfcConnectionSurfaceGeometry d'IfcSpaces différents)
////  li_IfcConn_IfcConn_Dist: liste de paire d'IfcConnectionSurfaceGeometry (de l'élément de construction en cours) ORDONNEE en fonction de leur distance (permet de déterminer les côte-à-côte)
////  map_IfcSpace_NbIfcConn détermine le nombre d'IfcConnectionSurfaceGeometry par IfcSpace (permet à la fois de boucler sur les ifcSpaces et de déterminer "l'algo" en fonction du nombre d'IfcConnectionSurfaceGeometry)
//int ifc_TreePostTreatment::FindSideBySideSurfacesOfOneBuildingelement(STRUCT_IFCENTITY *st_IfcEntBE, map<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *> &map_IfcConn_IfcSpace, list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>> &li_IfcConn_IfcConn_Dist, map<STRUCT_IFCENTITY *, int> &map_IfcSpace_NbIfcConn)
//{
//	int res = 0;
//
//	//Surfaces côte à côte (sur un même élément de construction)
//	//Paires de Surfaces les plus proches qui ne soient pas en vis à vis et appartenant à un même espace
//	//Repérer les paires de surfaces appartenant à même espace
//	//Cas triviaux: 
//	//   - S'il n'y a que 1 surface pas de côte à côte
//	//   - S'il n'y a que 2 surfaces => 1 seule paire côte à côte
//	//   - S'il y a strictement plus que 2 surfaces 
//	//      => A1) prendre la 1ere paire la plus proche à "iso-espace" = (S1 et S2)
//	//      => A2) prendre la 2ème paire la plus proche contenant S1 = (S1 et S3) 
//	//      => A3) prendre la 3ème paire (S2 et S3)
//	//         A1 et A2 => dist (S1 et S3) > (S1 et S2)
//	//         A3 => soit dist (S2 et S3) > (S1 et S3) implique S1 au milieu de S2 et S3 
//	//            => soit dist (S2 et S3) < (S1 et S3) implique S2 au milieu de S1 et S3 (dans ce cas S2 aura 2 SideBySide, S1 et S3 1 SideBySide)
//	//
//	//    A2.1)                  S1-------S3  => dans ce cas S2 aura 2 SideBySide, S1 et S3 1 SideBySide (ATTENTION: il faut ajouter les sideBySide car S1 et S3 peuvent avoir un autre SideBySide S4) 
//	//    A1)                    S1--S2
//	//    A2.2)         S3-------S1           => dans ce cas S1 aura 2 SideBySide, S2 et S3 1 SideBySide (ATTENTION: il faut ajouter les sideBySide car S2 et S3 peuvent avoir un autre SideBySide S4) 
//	//
//	//	Le processus A1, A2 et A3 est à répéter en excluant la surface ayant déjà ses 2 SideBySide
//	//   => a priori pour 3 surfaces d'un même espace processus à faire 1 fois, pour 4 surfaces 2 fois, pour N surfaces N-2 fois
//	map<STRUCT_IFCENTITY *, int> ::iterator mp_Space;
//	for (mp_Space = map_IfcSpace_NbIfcConn.begin(); mp_Space != map_IfcSpace_NbIfcConn.end(); mp_Space++)
//	{
//		//
//		//USECASE à 2 IfcConnectionSurfaceGeometry par ifcSpace
//		if ((*mp_Space).second == 2)
//		{
//			for (list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>>::iterator it = li_IfcConn_IfcConn_Dist.begin(); it != li_IfcConn_IfcConn_Dist.end(); ++it)
//			{
//				//Si les 2 IfcConnectionSurfaceGeometry appartiennent à 1 même ifcspace => on continue
//				if (map_IfcConn_IfcSpace[(*it).first.first] == map_IfcConn_IfcSpace[(*it).first.second])
//				{
//					//Si les 2 IfcConnectionSurfaceGeometry appartiennent au même ifcspace en cours => on continue
//					if (map_IfcConn_IfcSpace[(*it).first.first] == (*mp_Space).first)
//					{
//						//(*it).first.first->st_SideBySide.push_back((*it).first.second);
//						//(*it).first.second->st_SideBySide.push_back((*it).first.first);
//
//						(*it).first.first->mp_SideBySide[(*it).first.second] = std::make_pair(false, (*it).second);
//						(*it).first.second->mp_SideBySide[(*it).first.first] = std::make_pair(false, (*it).second);
//
//						//Il n'y a que 2 IfcConnectionSurfaceGeometry => on peut arrêter la boucle sur les pairs
//						break;
//					}// if (map_IfcConn_IfcSpace[(*it).first.first] == (*mp_Space).first)
//				}// if (map_IfcConn_IfcSpace[(*it).first.first] == map_IfcConn_IfcSpace[(*it).first.second])
//			}//for (list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>>::iterator it = li_IfcConn_IfcConn_Dist.begin(); it != li_IfcConn_IfcConn_Dist.end(); ++it)
//		}// if ((*mp_Space).second == 2)
//		 //
//		 //USECASE à plus de 2 IfcConnectionSurfaceGeometry par ifcSpace
//		else if ((*mp_Space).second > 2)
//		{
//			//Recherche des 3 pairs it, it2 et it3 d'IfcConnectionSurfaceGeometry appartenant au même IfcSpace en cours
//			//BOUCLE POUR CHERCHER it
//			list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>>::iterator it;
//			list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>>::iterator it2;
//			list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>>::iterator it3;
//			for (it = li_IfcConn_IfcConn_Dist.begin(); it != li_IfcConn_IfcConn_Dist.end(); it++)
//			{
//				bool bo_AreTheTwoPairsFound = false;
//				//it=S1-S2?
//				//Si les 2 IfcConnectionSurfaceGeometry appartiennent au même ifcspace en cours => on continue
//				//bool bo_CanBeSideBySide = map_CanBeSideBySide[std::make_pair((*it).first.first, (*it).first.second)];
//				if ((map_IfcConn_IfcSpace[(*it).first.first] == map_IfcConn_IfcSpace[(*it).first.second]) && (map_IfcConn_IfcSpace[(*it).first.first] == (*mp_Space).first))
//				{
//					//A ce stade, on a la 1ere paire d'ifcConn it=S1-S2, on cherche la prochaine paire la plus proche (it2=S1-S3 ou it2=S3-S1)
//					//BOUCLE POUR CHERCHER it2
//					//it++;
//					//for (it2 = it, it--; it2 != li_IfcConn_IfcConn_Dist.end(); it2++)
//					for (it2 = li_IfcConn_IfcConn_Dist.begin(); it2 != li_IfcConn_IfcConn_Dist.end(); it2++)
//					{
//						//it2=S1-S3?
//						//Si la 1ere IfcConnectionSurfaceGeometry de it2 est S1 et si la 2nde IfcConn (S3) appartient au même ifcspace => on continue
//						if ((it2 != it) && (*it2).first.first == (*it).first.first && map_IfcConn_IfcSpace[(*it2).first.second] == (*mp_Space).first)
//						{
//							//A ce stade, on a les 2 paires d'ifcConn it=S1-S2 et it2=S1-S3, on cherche la derniere paire it3=S2-S3 ou it3=S3-S2
//							//BOUCLE POUR CHERCHER it3
//							//it2++;
//							//for (it3 = it2, it2--; it3 != li_IfcConn_IfcConn_Dist.end(); it3++)
//							for (it3 = li_IfcConn_IfcConn_Dist.begin(); it3 != li_IfcConn_IfcConn_Dist.end(); it3++)
//							{
//								//it3=S2-S3?
//								//Si la 1ere IfcConnectionSurfaceGeometry de it3 est S2 et la 2nde de it3 est S3 => on a les 3 paires pour renseigner les SideBySide
//								if ((*it3).first.first == (*it).first.second && (*it3).first.second == (*it2).first.second)
//								{
//									//A ce stade, on a les 3 paires d'ifcConn it=S1-S2 , it2=S1-S3, it3=S2-S3 
//									//avec les conditions: S1-S2 < S1-S3 
//									//    A2.1)                  S1-------S3  => dans ce cas S2 aura 2 SideBySide, S1 et S3 1 SideBySide (ATTENTION: il faut ajouter les sideBySide car S1 et S3 peuvent avoir un autre SideBySide S4) 
//									//    A1)                    S1--S2
//									//    A2.2)         S3-------S1           => dans ce cas S1 aura 2 SideBySide, S2 et S3 1 SideBySide (ATTENTION: il faut ajouter les sideBySide car S2 et S3 peuvent avoir un autre SideBySide S4) 
//
//									// Si S2-S3 < S1-S3 => S2 entre S1 et S3 (S1-S2-S3)
//									if ((*it3).second < (*it2).second)
//									{
//										//S1---S2---S3
//										int res = FillSideBySideSurfacesOfOneBuildingelement((*it).first.first, (*it).first.second, (*it2).first.second, (*it).second, (*it3).second);
//
//										//Indication que S1 et S3 ne peuvent pas être cote à cote
//										//map_CanBeSideBySide[std::make_pair((*it).first.first, (*it2).first.second)] = false;
//										bo_AreTheTwoPairsFound = true;
//									}// if ((*it3).second<(*it2).second)
//
//									 // Si S2-S3 > S1-S3 => S1 entre S2 et S3 (S3-S1-S2)
//									if ((*it3).second>(*it2).second)
//									{
//										//S3---S1---S2
//										int res = FillSideBySideSurfacesOfOneBuildingelement((*it2).first.second, (*it).first.first, (*it).first.second, (*it2).second, (*it).second);
//
//										//Indication que S2 et S3 ne peuvent pas être cote à cote
//										//map_CanBeSideBySide[std::make_pair((*it).first.second, (*it2).first.second)] = false;
//										bo_AreTheTwoPairsFound = true;
//									}// if ((*it3).second>(*it2).second)
//								}// if ((*it3).first.first == (*it).first.second && (*it3).first.second == (*it2).first.second)
//
//								 //it3=S3-S2?
//								 //Si la 1ere IfcConnectionSurfaceGeometry de it3 est S3 et la 2nde de it3 est S2 => on a les 3 paires pour renseigner les SideBySide
//								if ((*it3).first.first == (*it2).first.second && (*it3).first.second == (*it).first.second)
//								{
//									//A ce stade, on a les 3 paires d'ifcConn it=S1-S2 , it2=S1-S3, it3=S3-S2 
//									//avec les conditions: S1-S2 < S1-S3 
//									//    A2.1)                  S1-------S3  => dans ce cas S2 aura 2 SideBySide, S1 et S3 1 SideBySide (ATTENTION: il faut ajouter les sideBySide car S1 et S3 peuvent avoir un autre SideBySide S4) 
//									//    A1)                    S1--S2
//									//    A2.2)         S3-------S1           => dans ce cas S1 aura 2 SideBySide, S2 et S3 1 SideBySide (ATTENTION: il faut ajouter les sideBySide car S2 et S3 peuvent avoir un autre SideBySide S4)
//
//									// Si S3-S2 < S1-S3 => S2 entre S1 et S3 (S1-S2-S3)
//									if ((*it3).second<(*it2).second)
//									{
//										//S1---S2---S3
//										int res = FillSideBySideSurfacesOfOneBuildingelement((*it).first.first, (*it).first.second, (*it2).first.second, (*it).second, (*it3).second);
//
//										//Indication que S1 et S3 ne peuvent pas être cote à cote
//										//map_CanBeSideBySide[std::make_pair((*it).first.first, (*it2).first.second)] = false;
//										bo_AreTheTwoPairsFound = true;
//									}// if ((*it3).second<(*it2).second)
//
//									 // Si S3-S2 > S1-S3 => S1 entre S2 et S3 (S3-S1-S2)
//									if ((*it3).second>(*it2).second)
//									{
//										//S3---S1---S2
//										int res = FillSideBySideSurfacesOfOneBuildingelement((*it2).first.second, (*it).first.first, (*it).first.second, (*it2).second, (*it).second);
//
//										//Indication que S2 et S3 ne peuvent pas être cote à cote
//										//map_CanBeSideBySide[std::make_pair((*it).first.second, (*it2).first.second)] = false;
//										bo_AreTheTwoPairsFound = true;
//									}// if ((*it3).second>(*it2).second)
//								}// if ((*it3).first.first == (*it2).first.second && (*it3).first.second == (*it).first.second)
//
//								if (bo_AreTheTwoPairsFound) break;
//							}// for (list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>>::iterator it3 = it2, it2--; it3 != li_IfcConn_IfcConn_Dist.end(); ++it3)
//						}// if ((it2 != it) && (*it2).first.first == (*it).first.first && map_IfcConn_IfcSpace[(*it2).first.second] == (*mp_Space).first)
//
//						 //it2=S3-S1?
//						 //Si la 2nde IfcConnectionSurfaceGeometry de it2 est S1 et si la 1ere IfcConn (S3) appartient au même ifcspace => on continue
//						if ((it2 != it) && (*it2).first.second == (*it).first.first && map_IfcConn_IfcSpace[(*it2).first.first] == (*mp_Space).first)
//						{
//							//A ce stade, on a les 2 paires d'ifcConn it=S1-S2 et it2=S3-S1, on cherche la derniere paire it3=S2-S3 ou it3=S3-S2
//							//BOUCLE POUR CHERCHER it3
//							it2++;
//							for (it3 = it2, it2--; it3 != li_IfcConn_IfcConn_Dist.end(); it3++)
//							{
//								//it3=S2-S3?
//								//Si la 1ere IfcConnectionSurfaceGeometry de it3 est S2 et la 2nde de it3 est S3 => on a les 3 paires pour renseigner les SideBySide
//								if ((*it3).first.first == (*it).first.second && (*it3).first.second == (*it2).first.first)
//								{
//									//A ce stade, on a les 3 paires d'ifcConn it=S1-S2 , it2=S3-S1, it3=S2-S3 
//									//avec les conditions: S1-S2 < S3-S1 
//									//    A2.1)                  S1-------S3  => dans ce cas S2 aura 2 SideBySide, S1 et S3 1 SideBySide (ATTENTION: il faut ajouter les sideBySide car S1 et S3 peuvent avoir un autre SideBySide S4) 
//									//    A1)                    S1--S2
//									//    A2.2)         S3-------S1           => dans ce cas S1 aura 2 SideBySide, S2 et S3 1 SideBySide (ATTENTION: il faut ajouter les sideBySide car S2 et S3 peuvent avoir un autre SideBySide S4) 
//
//									// Si S2-S3 < S3-S1 => S2 entre S1 et S3 (S1-S2-S3)
//									if ((*it3).second<(*it2).second)
//									{
//										//S1---S2---S3
//										int res = FillSideBySideSurfacesOfOneBuildingelement((*it).first.first, (*it).first.second, (*it2).first.first, (*it).second, (*it3).second);
//
//										//Indication que S1 et S3 ne peuvent pas être cote à cote
//										//map_CanBeSideBySide[std::make_pair((*it).first.first, (*it2).first.first)] = false;
//										bo_AreTheTwoPairsFound = true;
//									}// if ((*it3).second<(*it2).second)
//
//									 // Si S2-S3 > S3-S1 => S1 entre S2 et S3 (S3-S1-S2)
//									if ((*it3).second>(*it2).second)
//									{
//										//S3---S1---S2
//										int res = FillSideBySideSurfacesOfOneBuildingelement((*it2).first.first, (*it).first.first, (*it).first.second, (*it2).second, (*it).second);
//
//										//Indication que S2 et S3 ne peuvent pas être cote à cote
//										//map_CanBeSideBySide[std::make_pair((*it).first.second, (*it2).first.first)] = false;
//										bo_AreTheTwoPairsFound = true;
//									}// if ((*it3).second>(*it2).second)
//								}// if ((*it3).first.first == (*it).first.second && (*it3).first.second == (*it2).first.first)
//								 //it3=S3-S2?
//								 //Si la 1ere IfcConnectionSurfaceGeometry de it3 est S3 et la 2nde de it3 est S2 => on a les 3 paires pour renseigner les SideBySide
//								if ((*it3).first.first == (*it2).first.first && (*it3).first.second == (*it).first.second)
//								{
//									//A ce stade, on a les 3 paires d'ifcConn it=S1-S2 , it2=S3-S1, it3=S3-S2 
//									//avec les conditions: S1-S2 < S3-S1 
//									//    A2.1)                  S1-------S3  => dans ce cas S2 aura 2 SideBySide, S1 et S3 1 SideBySide (ATTENTION: il faut ajouter les sideBySide car S1 et S3 peuvent avoir un autre SideBySide S4) 
//									//    A1)                    S1--S2
//									//    A2.2)         S3-------S1           => dans ce cas S1 aura 2 SideBySide, S2 et S3 1 SideBySide (ATTENTION: il faut ajouter les sideBySide car S2 et S3 peuvent avoir un autre SideBySide S4)
//
//									// Si S3-S2 < S3-S1 => S2 entre S1 et S3 (S1-S2-S3)
//									if ((*it3).second<(*it2).second)
//									{
//										//S1---S2---S3
//										int res = FillSideBySideSurfacesOfOneBuildingelement((*it).first.first, (*it).first.second, (*it2).first.first, (*it).second, (*it3).second);
//
//										//Indication que S1 et S3 ne peuvent pas être cote à cote
//										//map_CanBeSideBySide[std::make_pair((*it).first.first, (*it2).first.first)] = false;
//										bo_AreTheTwoPairsFound = true;
//									}// if ((*it3).second<(*it2).second)
//
//									 // Si S3-S2 > S3-S1 => S1 entre S2 et S3 (S3-S1-S2)
//									if ((*it3).second>(*it2).second)
//									{
//										//S3---S1---S2
//										int res = FillSideBySideSurfacesOfOneBuildingelement((*it2).first.first, (*it).first.first, (*it).first.second, (*it2).second, (*it).second);
//
//										//Indication que S2 et S3 ne peuvent pas être cote à cote
//										//map_CanBeSideBySide[std::make_pair((*it).first.second, (*it2).first.first)] = false;
//										bo_AreTheTwoPairsFound = true;
//									}// if ((*it3).second>(*it2).second)
//								}// if ((*it3).first.first == (*it2).first.first && (*it3).first.second == (*it).first.second)
//
//								if (bo_AreTheTwoPairsFound) break;
//							}// for (list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>>::iterator it3 = it2, it2--; it3 != li_IfcConn_IfcConn_Dist.end(); ++it3)
//						}// if ((*it2).first.second == (*it).first.first && map_IfcConn_IfcSpace[(*it2).first.first] == (*mp_Space).first)
//
//						if (bo_AreTheTwoPairsFound) break;
//					}// for (list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>>::iterator it2 = it, it--; it2 != li_IfcConn_IfcConn_Dist.end(); ++it2)
//				}// if (map_IfcConn_IfcSpace[(*it).first.first] == map_IfcConn_IfcSpace[(*it).first.second])
//			}//for (list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>>::iterator it = li_IfcConn_IfcConn_Dist.begin(); it != li_IfcConn_IfcConn_Dist.end(); ++it)
//		}// else if ((*mp_Space).second > 2)
//	}// for (mp_Elem1 = map_IfcSpace_NbIfcConn.begin(); mp_Elem1 != map_IfcSpace_NbIfcConn.end(); mp_Elem1++)
//
//	return res;
//}


