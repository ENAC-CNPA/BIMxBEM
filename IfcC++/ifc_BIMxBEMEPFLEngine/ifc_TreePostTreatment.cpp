#include "ifc_TreePostTreatment.h"
//#include <vector>
#include <string>

const double db_eps= 0.00001;

ifc_TreePostTreatment::ifc_TreePostTreatment(ifc_Tree* CurrentIfcTree)
{
	_CurrentIfcTree = CurrentIfcTree;
}


ifc_TreePostTreatment::~ifc_TreePostTreatment()
{
}

int ifc_TreePostTreatment::BasifyTree(Map_Basified_Tree *&map_BasifTree)
{
	int Res = 0;

	STRUCT_IFCENTITY* st_IfcTree = nullptr;
	if (_CurrentIfcTree)
	{
		st_IfcTree =_CurrentIfcTree->Getstruct();
		if (st_IfcTree)
			BasifyTreeFrom(st_IfcTree);
		else
			Res = 2;

		map_BasifTree = &_map_BasifTree;
	}// if (_CurrentIfcTree)
	else
		Res = 1;


	return Res;
}

int ifc_TreePostTreatment::BasifyTreeFrom(STRUCT_IFCENTITY *&st_IfcTree)
{
	int Res = 0;
	//Memo adresse pointeur (si existe pas ajout�) et son type "Ifc" 
	// => la map permet de ne pas r�f�rencer de multiple fois une m�me entit� 
	//    dans l'arbre, des entit�s sont r�f�renc�s plusieurs fois car elles appartiennent � plusieurs objets
	_map_BasifTree[st_IfcTree] = st_IfcTree->ch_Type;

	list <STRUCT_IFCENTITY*> ::iterator it_Elem;
	for (it_Elem = (st_IfcTree->st_Contains).begin(); it_Elem != (st_IfcTree->st_Contains).end(); it_Elem++)
	{
		BasifyTreeFrom((*it_Elem));
	}// for (it_Elem = (st_IfcTree->st_Contains).begin(); it_Elem != (st_IfcTree->st_Contains).end(); it_Elem++)

	return Res;
}

int ifc_TreePostTreatment::CompleteBasifiedTreeFromByTIFCSurfaces()
{
	int Res = 0;

	std::map<STRUCT_IFCENTITY*, std::string>::reverse_iterator it_Elem;
	for (it_Elem = _map_BasifTree.rbegin(); it_Elem != _map_BasifTree.rend(); it_Elem++)
	{
		if (it_Elem->first->st_TIFCSurface)
			_map_BasifTree[it_Elem->first->st_TIFCSurface] = it_Elem->first->st_TIFCSurface->ch_Type;
	}// for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)

	return Res;
}

//Retrait dans les contours (st_PointsDesContours) du derniers point lorsqu'il est �gal au 1er (+ consigne bool bo_IsItLoop=true)
int ifc_TreePostTreatment::RemoveLastPointOfLoopContours()
{
	int Res = 0;

	std::map<STRUCT_IFCENTITY*, std::string>::iterator it_Elem;
	for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)
	{
		if (it_Elem->first->st_PointsDesContours.size() != 0)
			Res = RemoveLastPointOfOneLoopContour(it_Elem->first);
	}// for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)

	return Res;
}

//Retrait dans le contour (st_PointsDesContours) du derniers point lorsqu'il est �gal au 1er (+ consigne bool bo_IsItLoop=true)
int ifc_TreePostTreatment::RemoveLastPointOfOneLoopContour(STRUCT_IFCENTITY *st_IfcEnt)
{
	int Res = 0;

	//Boucle sur les diff�rents sous-contours
	list <list <double*>> ::iterator it_llPt;
	for (it_llPt = (st_IfcEnt->st_PointsDesContours).begin(); it_llPt != (st_IfcEnt->st_PointsDesContours).end(); it_llPt++)
	{
		//Verif si 1er pt=dernier pt => si oui retirer le dernier pt (les 3 derni�res coordonn�es) + consigne bool bo_IsItLoop=true
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
		}// if (db_Dist < 0.0000001)
	}// for (it_llPt = (st_IfcEnt->st_PointsDesContours).begin(); it_llPt != (st_IfcEnt->st_PointsDesContours).end(); it_llPt++)

	return Res;
}

//Calcul des surfaces IfcConnectionSurfaceGeometry
int ifc_TreePostTreatment::ComputeIfcConnectionSurfaceGeometrySurface()
{
	int Res = 0;

	std::map<STRUCT_IFCENTITY*, std::string>::iterator it_Elem;
	for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)
	{
		if (it_Elem->second == "IfcConnectionSurfaceGeometry")
			Res = ComputeOneIfcConnectionSurfaceGeometrySurface(it_Elem->first);
	}// for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)

	return Res;
}

//Calcul de la surface d'une IfcConnectionSurfaceGeometry
int ifc_TreePostTreatment::ComputeOneIfcConnectionSurfaceGeometrySurface(STRUCT_IFCENTITY *st_IfcEntCS)
{
	int Res = 0;

	//Recup de toutes les coordonn�es de tous les points du contour
	double db_TotalSurf = 0.0;
	vector<double*> vc_PointCoordCtr1;
	for (list<STRUCT_IFCENTITY *>::iterator it_lEnt = (st_IfcEntCS->st_Contains).begin(); it_lEnt != (st_IfcEntCS->st_Contains).end(); it_lEnt++)
	{
		for (list<list<double*>>::iterator it_llCtr = ((*it_lEnt)->st_PointsDesContours).begin(); it_llCtr != ((*it_lEnt)->st_PointsDesContours).end(); it_llCtr++)
		{
			//Recup du contour
			vc_PointCoordCtr1.insert(vc_PointCoordCtr1.end(), (*it_llCtr).begin(), (*it_llCtr).end());
			
			//Fermer le contour par ajout du premier Pt en dernier (n�cessaire au calcul de la surface)
			vector<double*>::iterator it_CoordPt1_end = vc_PointCoordCtr1.begin(); ++++++it_CoordPt1_end;
			vc_PointCoordCtr1.insert(vc_PointCoordCtr1.end(), vc_PointCoordCtr1.begin(), it_CoordPt1_end);

			//Calcul de la surface d�finie par ce contour + Somme des differentes surfaces d�j� calcul�s
			db_TotalSurf += ComputeSurfaceFromAContour(vc_PointCoordCtr1);
		}// for (list<list<double*>>::iterator it_llCtr = ((*it_lEnt)->st_PointsDesContours).begin(); it_llCtr != ((*it_lEnt)->st_PointsDesContours).end(); it_llCtr++)
	}// for (list<STRUCT_IFCENTITY *>::iterator it_lEnt = (st_IfcEntCS->st_Contains).begin(); it_lEnt != (st_IfcEntCS->st_Contains).end(); it_lEnt++)

	Map_String_String map_messages;
	map_messages["ComputedArea"] = to_string(db_TotalSurf);
	if (_CurrentIfcTree)
		_CurrentIfcTree->FillQuantitiesAttributeOf_STRUCT_IFCENTITY(st_IfcEntCS, map_messages);
	else
		Res = 3;

	return Res;
}

//Calcul d'une surface plane � partir de ses contours
double ifc_TreePostTreatment::ComputeSurfaceFromAContour(vector<double*> &vc_PointCoordCtr)
{
	//int Res = 0;

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

//Creation des TIFCSurfaces par concatenation des IfcConnectionSurfaceGeometry en vis-�-vis
int ifc_TreePostTreatment::CreateTIFCSurfaces()
{
	int Res = 0;

	std::map<STRUCT_IFCENTITY*, std::string>::iterator it_Elem;
	for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)
	{
		if (it_Elem->second == "IfcConnectionSurfaceGeometry")
			Res= CreateTIFCSurface(it_Elem->first);
	}// for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)

	return Res;
}

//Creation d'une TIFCSurface par concatenation des 2 IfcConnectionSurfaceGeometry en vis-�-vis
int ifc_TreePostTreatment::CreateTIFCSurface(STRUCT_IFCENTITY *st_IfcEntCS)
{
	int Res = 0;

	//On v�rifie que cette IfcConnectionSurfaceGeometry (st_IfcEntCS) n'a pas d�j� sa TIFCSurface 
	//car � sa cr�ation la m�me TIFCSurface est associ�e � 2 IfcConnectionSurfaceGeometry
	if (st_IfcEntCS && st_IfcEntCS->st_TIFCSurface==nullptr)
	{
		if (_CurrentIfcTree)
			Res = _CurrentIfcTree->BuildTIFCSurfaceTreeFrom_STRUCT_IFCENTITY(st_IfcEntCS);
		else
			Res = 5;
	}
	else
		Res = 4;

	return Res;
}


//Calcul des isobarycentres des IfcConnectionSurfaceGeometry
int ifc_TreePostTreatment::CentroidsComputation()
{
	int Res = 0;

	std::map<STRUCT_IFCENTITY*, std::string>::iterator it_Elem;
	for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)
	{
		if (it_Elem->second == "IfcConnectionSurfaceGeometry")
			Res= CentroidComputation(it_Elem->first);
	}// for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)

	return Res;
}

//Calcul de l'isobarycentre d'une IfcConnectionSurfaceGeometry
int ifc_TreePostTreatment::CentroidComputation(STRUCT_IFCENTITY *st_IfcEntCS)
{
	int Res = 0;

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
			//lire la liste des points (le dernier point est toujours diff�rent du 1er car a �t� enlev� par routine RemoveLastPointOfLoopContours)
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

	//M�mo dans la structure
	if (_CurrentIfcTree)
		_CurrentIfcTree->FillCentroidOf_STRUCT_IFCENTITY(st_IfcEntCS, db_IsoBar);
	else
		Res = 5;

	return Res;
}

int ifc_TreePostTreatment::RelimitSideBySideSurfaces()
{
	int Res = 0;

	std::map<STRUCT_IFCENTITY*, std::string>::iterator it_Elem;
	for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)
	{
		//Traitement des IfcConnectionSurfaceGeometry ayant 2 c�t� � �tendre
		//Recherche des IfcConnectionSurfaceGeometry avec 2 SideBySide
		if (it_Elem->second == "IfcConnectionSurfaceGeometry" /*&& it_Elem->first->st_SideBySide.size()==2*/)
			Res = RelimitSideBySideSurfacesOfMiddleIfcConnectionSurfaceGeometry(it_Elem->first);

		//Traitement des IfcConnectionSurfaceGeometry ayant 1 c�t� � �tendre
		//DEB: SLC A FAIRE 1 sidebyside

	}// for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)

	return Res;
}

//Raccord du IfcConnectionSurfaceGeometry milieu PAS SEULEMENT!!! (entre 2 autres IfcConnectionSurfaceGeometry)
int ifc_TreePostTreatment::RelimitSideBySideSurfacesOfMiddleIfcConnectionSurfaceGeometry(STRUCT_IFCENTITY *st_IfcEntCS)
{
	int Res = 0;

	//Retrouver les 2 IfcConnectionSurfaceGeometry qui sont c�te-�-c�te avec l'IfcConnectionSurfaceGeometry en cours
	map <STRUCT_IFCENTITY*,bool> ::iterator it_SideBySideIfcEntCS;
	//list <STRUCT_IFCENTITY*> ::iterator it_SideBySideIfcEntCS;
	//for (it_SideBySideIfcEntCS = (st_IfcEntCS->st_SideBySide).begin(); it_SideBySideIfcEntCS != (st_IfcEntCS->st_SideBySide).end(); it_SideBySideIfcEntCS++)
	for (it_SideBySideIfcEntCS = (st_IfcEntCS->mp_SideBySide).begin(); it_SideBySideIfcEntCS != (st_IfcEntCS->mp_SideBySide).end(); it_SideBySideIfcEntCS++)
	{
		//retrouver les paires de points les plus proches (chaque point appartenant � l'un ou l'autre des IfcConnectionSurfaceGeometry)
		if (!(*it_SideBySideIfcEntCS).second)
		{
			RelimitOneSideBySideSurfaceOfMiddleIfcConnectionSurfaceGeometry(st_IfcEntCS, (*it_SideBySideIfcEntCS).first);
			(*it_SideBySideIfcEntCS).second = true;
			(*it_SideBySideIfcEntCS).first->mp_SideBySide[st_IfcEntCS] = true;
		}// if (!(*it_SideBySideIfcEntCS).second)
	}// for (it_Elem2 = (it_Elem1->first->st_Contains).begin(); it_Elem2 != (it_Elem1->first->st_Contains).end(); it_Elem2++)

	return Res;
}

int ifc_TreePostTreatment::RelimitOneSideBySideSurfaceOfMiddleIfcConnectionSurfaceGeometry(STRUCT_IFCENTITY *&st_IfcEntCS1, STRUCT_IFCENTITY *st_IfcEntCS2)
{
	int Res = 0;

	//Recup de toutes les coordonn�es de tous les points du 1er contour
	vector<double*> vc_PointCoordCtr1;
	for (list<STRUCT_IFCENTITY *>::iterator it_lEnt = (st_IfcEntCS1->st_Contains).begin(); it_lEnt != (st_IfcEntCS1->st_Contains).end(); it_lEnt++)
		for (list<list<double*>>::iterator it_llCtr = ((*it_lEnt)->st_PointsDesContours).begin(); it_llCtr != ((*it_lEnt)->st_PointsDesContours).end(); it_llCtr++)
			vc_PointCoordCtr1.insert(vc_PointCoordCtr1.end(), (*it_llCtr).begin(), (*it_llCtr).end());

	//Recup de toutes les coordonn�es de tous les points du 2�me contour
	vector<double*> vc_PointCoordCtr2;
	for (list<STRUCT_IFCENTITY *>::iterator it_lEnt = (st_IfcEntCS2->st_Contains).begin(); it_lEnt != (st_IfcEntCS2->st_Contains).end(); it_lEnt++)
		for (list<list<double*>>::iterator it_llCtr = ((*it_lEnt)->st_PointsDesContours).begin(); it_llCtr != ((*it_lEnt)->st_PointsDesContours).end(); it_llCtr++)
			vc_PointCoordCtr2.insert(vc_PointCoordCtr2.end(), (*it_llCtr).begin(), (*it_llCtr).end());

	//
	//Calcul des distances entre chaque paire de points appartenant � chacun des contours des IfcConnectionSurfaceGeometry
	//  li_IndPtCtr1_IndPtCtr2_Dist[iterateur debut Pt_J du contour1, iterateur debut Pt_J du contour2]=distance
	//  Utilisation d'une liste pour profiter du tri optimis�e "list::sort()"
	list< pair< pair<vector<double*>::iterator, vector<double*>::iterator>, double>> li_IndPtCtr1_IndPtCtr2_Dist;
	//Boucle sur st_Contains pour retrouver tous les IfcConnectionSurfaceGeometry
	vector<double*>::iterator it_CoordCtr1;
	vector<double*>::iterator it_CoordCtr2;
	for (it_CoordCtr1 = vc_PointCoordCtr1.begin(); it_CoordCtr1 != vc_PointCoordCtr1.end(); ++(++(++it_CoordCtr1)))
	{
		for (it_CoordCtr2 = vc_PointCoordCtr2.begin(); it_CoordCtr2 != vc_PointCoordCtr2.end(); ++(++(++it_CoordCtr2)))
		{
			vector<double*>::iterator it_CoordCtr1_end = it_CoordCtr1; ++++++it_CoordCtr1_end;
			vector<double*>::iterator it_CoordCtr2_end = it_CoordCtr2; ++++++it_CoordCtr2_end;
			vector<double*> vc_Point1(it_CoordCtr1, it_CoordCtr1_end);
			vector<double*> vc_Point2(it_CoordCtr2, it_CoordCtr2_end);
			
			//Calculer distance entre les 2 points des 2 IfcConnectionSurfaceGeometry 
			double db_dist=ComputePtPtDistance(vc_Point1, vc_Point2);

			//Memo de la distance entre les 2 points des 2 IfcConnectionSurfaceGeometry vc_Point1 et vc_Point2
			li_IndPtCtr1_IndPtCtr2_Dist.push_back(std::make_pair(std::make_pair(it_CoordCtr1, it_CoordCtr2), db_dist));
		}// for (vector<double*>::iterator it_CoordCtr2 = vc_PointCoordCtr2.begin(); it_CoordCtr2 != vc_PointCoordCtr2.end(); it_CoordCtr2++)
	}// for (vector<double*>::iterator it_CoordCtr1 = vc_PointCoordCtr1.begin(); it_CoordCtr1 != vc_PointCoordCtr1.end(); it_CoordCtr1++)

	//Trier les paires par proximit� pour trouver les points � rejoindre
	li_IndPtCtr1_IndPtCtr2_Dist.sort([](auto lhs, auto rhs) { return lhs.second < rhs.second; });

	//QUE FAIRE SI des paires de points sont quasi l'un sur l'autre => merger les 2 IfcConnectionSurfaceGeometry?? 
	//  ou verifier que l'une a une surface quasi nulle 
	// => la retirer? => Traitement � faire d�s le d�but apr�s RemoveLastPointOfLoopContours() mais attention au retrait � faire dans IfcSpace et elmt cstruction (Wall,...)
	// En tout cas si la 1ere paire de point est confondue on peut supposer que les 2 surfaces sont d�j� connect�es => pas de raccord � faire
	list< pair< pair<vector<double*>::iterator, vector<double*>::iterator>, double>>::iterator it_IndPtCtr1_IndPtCtr2_Dist = li_IndPtCtr1_IndPtCtr2_Dist.begin();
	if ((*it_IndPtCtr1_IndPtCtr2_Dist).second > db_eps)
	{
		//Memo de la distance de reference
		double db_Distref = (*it_IndPtCtr1_IndPtCtr2_Dist).second;
		for (it_IndPtCtr1_IndPtCtr2_Dist; it_IndPtCtr1_IndPtCtr2_Dist!= li_IndPtCtr1_IndPtCtr2_Dist.end();++it_IndPtCtr1_IndPtCtr2_Dist)
		{
			//
			//Remplacement des points les plus proches appartenant � un m�me c�t� (par leur point milieu)
			// HP: c�t� � peu pr�s parall�le => les points d'un m�me c�t� sont les 1�res paires de m�me ordre de distance (arbitrairement au max 20% de plus que la 1�re distance)
			if ((*it_IndPtCtr1_IndPtCtr2_Dist).second < 1.2*db_Distref)
			{
				//
				//Modification des 2 surfaces => remplacer les paires de points les plus proches par un m�me point milieu 
				//HP: les c�t�s � modifier sont des droites parall�les => remplacement des premi�res paires rep�r�es par une distance similaire
				it_CoordCtr1 = (*it_IndPtCtr1_IndPtCtr2_Dist).first.first;
				it_CoordCtr2 = (*it_IndPtCtr1_IndPtCtr2_Dist).first.second;

				double db_NewCoord_X = ((*it_CoordCtr1)[0] + (*it_CoordCtr2)[0]) / 2.0; ++it_CoordCtr1; ++it_CoordCtr2;
				double db_NewCoord_Y = ((*it_CoordCtr1)[0] + (*it_CoordCtr2)[0]) / 2.0; ++it_CoordCtr1; ++it_CoordCtr2;
				double db_NewCoord_Z = ((*it_CoordCtr1)[0] + (*it_CoordCtr2)[0]) / 2.0;

				*(*((*it_IndPtCtr1_IndPtCtr2_Dist).first.first)) = db_NewCoord_X;
				*(*((*it_IndPtCtr1_IndPtCtr2_Dist).first.second)) = db_NewCoord_X;
				*(*(++(*it_IndPtCtr1_IndPtCtr2_Dist).first.first)) = db_NewCoord_Y;
				*(*(++(*it_IndPtCtr1_IndPtCtr2_Dist).first.second)) = db_NewCoord_Y;
				*(*(++(*it_IndPtCtr1_IndPtCtr2_Dist).first.first)) = db_NewCoord_Z;
				*(*(++(*it_IndPtCtr1_IndPtCtr2_Dist).first.second)) = db_NewCoord_Z;
			}// if ((*it_IndPtCtr1_IndPtCtr2_Dist).second < 1.2*db_Distref)
			else
				break;
		}// for (it_IndPtCtr1_IndPtCtr2_Dist; it_IndPtCtr1_IndPtCtr2_Dist!= li_IndPtCtr1_IndPtCtr2_Dist.end;++it_IndPtCtr1_IndPtCtr2_Dist)
	}// if ((*it_IndPtCtr1_IndPtCtr2_Dist).second > db_eps)

	return Res;
}

int ifc_TreePostTreatment::TransformEntitiesToWorlCoordFrame()
{
	int Res = 0;

	std::map<STRUCT_IFCENTITY*, std::string>::iterator it_Elem;
	for (it_Elem = _map_BasifTree.begin(); it_Elem != _map_BasifTree.end(); it_Elem++)
	{
		if (it_Elem->first->st_PointsDesContours.size() != 0)
		{
			//D�compte du nombre de coord de points
			size_t i_Size = 0;
			list <list <double*>> ::iterator it_llPt;
			for (it_llPt = (it_Elem->first->st_PointsDesContours).begin(); it_llPt != (it_Elem->first->st_PointsDesContours).end(); it_llPt++)
				i_Size += it_llPt->size();

			//Allocation m�moire pour recueillir les coordonn�es des points � modifier
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

			//Changer les coordonn�es pour les mettre P/R au referentiel projet 
			Res = TransformEntityToWorlCoordFrame(it_Elem->first, db_CoordPts, i_Size);

			//M�moriser dans la structure les points modifi�s
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

	return Res;
}

int ifc_TreePostTreatment::TransformEntityToWorlCoordFrame(STRUCT_IFCENTITY *st_IfcEnt, double *&db_CoordPts, size_t int_Size)
{
	int Res = 0;
	
	//S'il existe db_RelativePlacement sur l'entit� en cours on l'applique
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

		//Coordonn�es dans le nouveau rep�re
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

	//Remonter les BelongsTo pour appliquer � chaque pas le db_RelativePlacement s'il existe
	//IMPORTANT: S'il existe 2 BelongsTo (on se trouve au niveau du IfcConnectionSurfaceGeometry) prendre le ifcSpace et non l'�l�ment de construction
	if (st_IfcEnt->st_BelongsTo.size() == 1)
	{
		TransformEntityToWorlCoordFrame(*(st_IfcEnt->st_BelongsTo.begin()), db_CoordPts, int_Size);
	}// if (st_IfcEnt->st_BelongsTo.size == 1)
	else if (st_IfcEnt->st_BelongsTo.size() == 2)
	{
		list <STRUCT_IFCENTITY*> ::iterator it_Elem = (st_IfcEnt->st_BelongsTo).begin();
		if (string((*it_Elem)->ch_Type) == "IfcSpace")
		{
			TransformEntityToWorlCoordFrame((*it_Elem), db_CoordPts, int_Size);
		}// if ((*it_Elem)->ch_Type = "IfcSpace")
		else 
		{
			it_Elem++;
			if (string((*it_Elem)->ch_Type) == "IfcSpace")
				TransformEntityToWorlCoordFrame((*it_Elem), db_CoordPts, int_Size);
			else
				Res = 2;
		}// else if ((*it_Elem)->ch_Type = "IfcSpace")
	}// if (st_IfcEnt->st_BelongsTo.size == 1)
	else if (st_IfcEnt->st_BelongsTo.size() > 2)
		Res = 1;

	return Res;
}

//Recherche des surfaces IfcConnectionSurfaceGeometry en vis-�-vis et c�te-�-c�te
int ifc_TreePostTreatment::FindFaceToFaceAndSideBySideSurfaces()
{
	int Res = 0;

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
				//HP: Le contains des spaces est compos� de IfcProductDefinitionShape, de IfcConnectionSurfaceGeometry et d'�l�ment de construction
				if (string((*it_Elem2)->ch_Type) != "IfcConnectionSurfaceGeometry" && string((*it_Elem2)->ch_Type) != "IfcProductDefinitionShape")
					map_BuildingElem_Type[(*it_Elem2)] = (*it_Elem2)->ch_Type;
			}// for (it_Elem2 = (it_Elem1->first->st_Contains).begin(); it_Elem2 != (it_Elem1->first->st_Contains).end(); it_Elem2++)
		}// if (it_Elem1->second == "IfcSpace")
	}// for (it_Elem1 = _map_BasifTree.begin(); it_Elem1 != _map_BasifTree.end(); it_Elem1++)

	//Boucle sur les elements de construction 
	std::map<STRUCT_IFCENTITY*, std::string>::iterator it_BuildingElem;
	for (it_BuildingElem = map_BuildingElem_Type.begin(); it_BuildingElem != map_BuildingElem_Type.end(); it_BuildingElem++)
	{
			Res = FindFaceToFaceAndSideBySideSurfacesOfOneBuildingelement(it_BuildingElem->first);
	}// for (it_BuildingElem = map_BuildingElem_Type.begin(); it_BuildingElem != map_BuildingElem_Type.end(); it_BuildingElem++)

	return Res;
}

//Routine pour trouver sur un m�me �l�ment de construction 
//	les surfaces en vis � vis (chacun appartenant � un espace diff�rent)
//	les surfaces c�te � c�te (chacun appartenant � un m�me espace)
int ifc_TreePostTreatment::FindFaceToFaceAndSideBySideSurfacesOfOneBuildingelement(STRUCT_IFCENTITY *st_IfcEntBE)
{
	int Res = 0;
	
	//
	//Pr�parations des �l�ments d'informations n�cessaires aux algo de FaceToFace et SideBySide
	//

	//Mapping entre les IfcConnectionSurfaceGeometry de l'�l�ment de construction et leur IfcSpace
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
	//Calcul des distances entre centre de gravit� de chaque paire de IfcConnectionSurfaceGeometry
	//  li_IfcConn_IfcConn_Dist[IfcConnectionSurfaceGeometry1, IfcConnectionSurfaceGeometry2]=distance
	//  Utilisation d'une liste pour profiter du tri optimis�e "list::sort()"
	list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>> li_IfcConn_IfcConn_Dist;
	//Boucle sur st_Contains pour retrouver tous les IfcConnectionSurfaceGeometry
	for (it_Elem1 = (st_IfcEntBE->st_Contains).begin(); it_Elem1 != (st_IfcEntBE->st_Contains).end(); it_Elem1++)
	{
		//Calculer distance entre chaque IfcConnectionSurfaceGeometry de l'�l�ment de construction 
		//	m�me si appartiennent � m�me ifcspace => utile pour les SideBySide
		it_Elem1++;
		for (it_Elem2 = it_Elem1, it_Elem1--; it_Elem2 != (st_IfcEntBE->st_Contains).end(); it_Elem2++)
		{
			//Calcul distance des isobarycentres
			std::vector<double*> vc_CentroidElem1((*it_Elem1)->db_Centroid.begin(), (*it_Elem1)->db_Centroid.end());
			std::vector<double*> vc_CentroidElem2((*it_Elem2)->db_Centroid.begin(), (*it_Elem2)->db_Centroid.end());
			double db_dist = ComputePtPtDistance(vc_CentroidElem1, vc_CentroidElem2);

			//Init de la carte qui indiquera si la paire d'IfcConnectionSurfaceGeometry en index n'est pas cote � cote
			//map_CanBeSideBySide[std::make_pair((*it_Elem1), (*it_Elem2))] = true;
			//Memo de la distance entre les 2 IfcConnectionSurfaceGeometry (*it_Elem1) et (*it_Elem2)
			li_IfcConn_IfcConn_Dist.push_back(std::make_pair(std::make_pair((*it_Elem1), (*it_Elem2)), db_dist));
			//}// if (map_IfcConn_IfcSpace[(*it_Elem1)] != map_IfcConn_IfcSpace[(*it_Elem2)])
		}// for (it_Elem = (st_IfcEnt->st_Contains).begin(); it_Elem != (st_IfcEnt->st_Contains).end(); it_Elem++)
	}// for (it_Elem = (st_IfcEnt->st_Contains).begin(); it_Elem != (st_IfcEnt->st_Contains).end(); it_Elem++)

	//Trier les paires par proximit� pour trouver les surfaces en "vis � vis" et celles "c�te � c�te" (sur un m�me �l�ment de construction)
	li_IfcConn_IfcConn_Dist.sort([](auto lhs, auto rhs) { return lhs.second < rhs.second; });

	//
	//D�tection des IfcConnectionSurfaceGeometry en vis-�-vis
	FindFaceToFaceSurfacesOfOneBuildingelement(st_IfcEntBE, map_IfcConn_IfcSpace, li_IfcConn_IfcConn_Dist);

	//
	//D�tection des IfcConnectionSurfaceGeometry en c�te-�-c�te
	FindSideBySideSurfacesOfOneBuildingelement(st_IfcEntBE, map_IfcConn_IfcSpace, li_IfcConn_IfcConn_Dist, map_IfcSpace_NbIfcConn);

	return Res;
}

//bool compare_dist(const pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double> &first, const pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double> &second)
//bool ifc_TreePostTreatment::compare_dist(const pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double> &first, const pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double> &second)
//{
//	if (first.second < second.second)
//		return true;
//	return false;
//}

//Algo pour d�tecter les IfcConnectionSurfaceGeometry en vis-�-vis
//  st_IfcEntBE est l'�l�ment de construction en cours (on utilise son �paisseur pour �viter des faux positifs)
//  map_IfcConn_IfcSpace associe un IfcConnectionSurfaceGeometry (de l'�l�ment de construction en cours) avec son IfcSpace (utiliser pour ne pas associer 2 IfcConnectionSurfaceGeometry du m�me IfcSpace)
//  li_IfcConn_IfcConn_Dist: liste de paire d'IfcConnectionSurfaceGeometry ORDONNEE en fonction de leur distance (permet de d�terminer les vis-�-vis)
int ifc_TreePostTreatment::FindFaceToFaceSurfacesOfOneBuildingelement(STRUCT_IFCENTITY *st_IfcEntBE, map<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *> &map_IfcConn_IfcSpace, list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>> &li_IfcConn_IfcConn_Dist)
{
	int Res = 0;

	//Surfaces en vis � vis (sur un m�me �l�ment de construction) 
	//Rep�rer les surfaces les plus proches et en vis � vis (=distance centre de gravite < 2*epaisseur mur)
	std::map<STRUCT_IFCENTITY*, bool> map_IsEntityFound;
	for (list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>>::iterator it = li_IfcConn_IfcConn_Dist.begin(); it != li_IfcConn_IfcConn_Dist.end(); ++it)
	{
		//Si les 2 IfcConnectionSurfaceGeometry appartiennent � des ifcspace diff�rent=> on continue (sinon on passe � une autre pair)
		if (map_IfcConn_IfcSpace[(*it).first.first] != map_IfcConn_IfcSpace[(*it).first.second])
		{
			//Si les 2 IfcConnectionSurfaceGeometry n'ont pas encore touv� leur vis � vis => on continue (sinon on passe � une autre pair)
			if (!map_IsEntityFound[(*it).first.first] && !map_IsEntityFound[(*it).first.second])
			{
				//la distance entre 2 surfaces en vis a vis est environ l'epaisseur du mur
				//par contre s'il n'y a pas de mur en vis a vis (mur exterieur) les plus proches peuvent etre des surface cote � cote et non en vis a vis
				// => le "if" qui suit permet d'exclure ce genre de faux positifs (cra distance des centre de gravit� sont de distance > � epaisseur)
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

	return Res;
}

//Algo pour d�tecter les IfcConnectionSurfaceGeometry c�te-�-c�te
//  st_IfcEntBE est l'�l�ment de construction en cours (n'est pas utilis� mais si besoin pourrait l'�tre...)
//  map_IfcConn_IfcSpace associe un IfcConnectionSurfaceGeometry (de l'�l�ment de construction en cours) avec son IfcSpace (utiliser pour ne pas associer des IfcConnectionSurfaceGeometry d'IfcSpaces diff�rents)
//  li_IfcConn_IfcConn_Dist: liste de paire d'IfcConnectionSurfaceGeometry ORDONNEE en fonction de leur distance (permet de d�terminer les c�te-�-c�te)
//  map_IfcSpace_NbIfcConn d�termine le nombre d'IfcConnectionSurfaceGeometry par IfcSpace (permet � la fois de boucler sur les ifcSpaces et de d�terminer "l'algo" en fonction du nombre d'IfcConnectionSurfaceGeometry)
int ifc_TreePostTreatment::FindSideBySideSurfacesOfOneBuildingelement(STRUCT_IFCENTITY *st_IfcEntBE, map<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *> &map_IfcConn_IfcSpace, list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>> &li_IfcConn_IfcConn_Dist, map<STRUCT_IFCENTITY *, int> &map_IfcSpace_NbIfcConn)
{
	int Res = 0;

	//Surfaces c�te � c�te (sur un m�me �l�ment de construction)
	//Paires de Surfaces les plus proches qui ne soient pas en vis � vis et appartenant � un m�me espace
	//Rep�rer les paires de surfaces appartenant � m�me espace
	//Cas triviaux: 
	//   - S'il n'y a que 1 surface pas de c�te � c�te
	//   - S'il n'y a que 2 surfaces => 1 seule paire c�te � c�te
	//   - S'il y a strictement plus que 2 surfaces 
	//      => A1) prendre la 1ere paire la plus proche � "iso-espace" = (S1 et S2)
	//      => A2) prendre la 2�me paire la plus proche contenant S1 = (S1 et S3) 
	//      => A3) prendre la 3�me paire (S2 et S3)
	//         A1 et A2 => dist (S1 et S3) > (S1 et S2)
	//         A3 => soit dist (S2 et S3) > (S1 et S3) implique S1 au milieu de S2 et S3 
	//            => soit dist (S2 et S3) < (S1 et S3) implique S2 au milieu de S1 et S3 (dans ce cas S2 aura 2 SideBySide, S1 et S3 1 SideBySide)
	//
	//    A2.1)                  S1-------S3  => dans ce cas S2 aura 2 SideBySide, S1 et S3 1 SideBySide (ATTENTION: il faut ajouter les sideBySide car S1 et S3 peuvent avoir un autre SideBySide S4) 
	//    A1)                    S1--S2
	//    A2.2)         S3-------S1           => dans ce cas S1 aura 2 SideBySide, S2 et S3 1 SideBySide (ATTENTION: il faut ajouter les sideBySide car S2 et S3 peuvent avoir un autre SideBySide S4) 
	//
	//	Le processus A1, A2 et A3 est � r�p�ter en excluant la surface ayant d�j� ses 2 SideBySide
	//   => a priori pour 3 surfaces d'un m�me espace processus � faire 1 fois, pour 4 surfaces 2 fois, pour N surfaces N-2 fois
	map<STRUCT_IFCENTITY *, int> ::iterator mp_Space;
	for (mp_Space = map_IfcSpace_NbIfcConn.begin(); mp_Space != map_IfcSpace_NbIfcConn.end(); mp_Space++)
	{
		//
		//USECASE � 2 IfcConnectionSurfaceGeometry par ifcSpace
		if ((*mp_Space).second == 2)
		{
			for (list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>>::iterator it = li_IfcConn_IfcConn_Dist.begin(); it != li_IfcConn_IfcConn_Dist.end(); ++it)
			{
				//Si les 2 IfcConnectionSurfaceGeometry appartiennent � 1 m�me ifcspace => on continue
				if (map_IfcConn_IfcSpace[(*it).first.first] == map_IfcConn_IfcSpace[(*it).first.second])
				{
					//Si les 2 IfcConnectionSurfaceGeometry appartiennent au m�me ifcspace en cours => on continue
					if (map_IfcConn_IfcSpace[(*it).first.first] == (*mp_Space).first)
					{
						//(*it).first.first->st_SideBySide.push_back((*it).first.second);
						//(*it).first.second->st_SideBySide.push_back((*it).first.first);

						(*it).first.first->mp_SideBySide[(*it).first.second]=false;
						(*it).first.second->mp_SideBySide[(*it).first.first]=false;

						//Il n'y a que 2 IfcConnectionSurfaceGeometry => on peut arr�ter la boucle sur les pairs
						break;
					}// if (map_IfcConn_IfcSpace[(*it).first.first] == (*mp_Space).first)
				}// if (map_IfcConn_IfcSpace[(*it).first.first] == map_IfcConn_IfcSpace[(*it).first.second])
			}//for (list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>>::iterator it = li_IfcConn_IfcConn_Dist.begin(); it != li_IfcConn_IfcConn_Dist.end(); ++it)
		}// if ((*mp_Space).second == 2)
		 //
		 //USECASE � plus de 2 IfcConnectionSurfaceGeometry par ifcSpace
		else if ((*mp_Space).second > 2)
		{
			//Recherche des 3 pairs it, it2 et it3 d'IfcConnectionSurfaceGeometry appartenant au m�me IfcSpace en cours
			//BOUCLE POUR CHERCHER it
			list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>>::iterator it;
			list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>>::iterator it2;
			list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>>::iterator it3;
			for (it = li_IfcConn_IfcConn_Dist.begin(); it != li_IfcConn_IfcConn_Dist.end(); it++)
			{
				bool bo_AreTheTwoPairsFound = false;
				//it=S1-S2?
				//Si les 2 IfcConnectionSurfaceGeometry appartiennent au m�me ifcspace en cours => on continue
				//bool bo_CanBeSideBySide = map_CanBeSideBySide[std::make_pair((*it).first.first, (*it).first.second)];
				if ((map_IfcConn_IfcSpace[(*it).first.first] == map_IfcConn_IfcSpace[(*it).first.second]) && (map_IfcConn_IfcSpace[(*it).first.first] == (*mp_Space).first))
				{
					//A ce stade, on a la 1ere paire d'ifcConn it=S1-S2, on cherche la prochaine paire la plus proche (it2=S1-S3 ou it2=S3-S1)
					//BOUCLE POUR CHERCHER it2
					//it++;
					//for (it2 = it, it--; it2 != li_IfcConn_IfcConn_Dist.end(); it2++)
					for (it2 = li_IfcConn_IfcConn_Dist.begin(); it2 != li_IfcConn_IfcConn_Dist.end(); it2++)
					{
						//it2=S1-S3?
						//Si la 1ere IfcConnectionSurfaceGeometry de it2 est S1 et si la 2nde IfcConn (S3) appartient au m�me ifcspace => on continue
						if ((it2 != it) && (*it2).first.first == (*it).first.first && map_IfcConn_IfcSpace[(*it2).first.second] == (*mp_Space).first)
						{
							//A ce stade, on a les 2 paires d'ifcConn it=S1-S2 et it2=S1-S3, on cherche la derniere paire it3=S2-S3 ou it3=S3-S2
							//BOUCLE POUR CHERCHER it3
							//it2++;
							//for (it3 = it2, it2--; it3 != li_IfcConn_IfcConn_Dist.end(); it3++)
							for (it3 = li_IfcConn_IfcConn_Dist.begin(); it3 != li_IfcConn_IfcConn_Dist.end(); it3++)
							{
								//it3=S2-S3?
								//Si la 1ere IfcConnectionSurfaceGeometry de it3 est S2 et la 2nde de it3 est S3 => on a les 3 paires pour renseigner les SideBySide
								if ((*it3).first.first == (*it).first.second && (*it3).first.second == (*it2).first.second)
								{
									//A ce stade, on a les 3 paires d'ifcConn it=S1-S2 , it2=S1-S3, it3=S2-S3 
									//avec les conditions: S1-S2 < S1-S3 
									//    A2.1)                  S1-------S3  => dans ce cas S2 aura 2 SideBySide, S1 et S3 1 SideBySide (ATTENTION: il faut ajouter les sideBySide car S1 et S3 peuvent avoir un autre SideBySide S4) 
									//    A1)                    S1--S2
									//    A2.2)         S3-------S1           => dans ce cas S1 aura 2 SideBySide, S2 et S3 1 SideBySide (ATTENTION: il faut ajouter les sideBySide car S2 et S3 peuvent avoir un autre SideBySide S4) 

									// Si S2-S3 < S1-S3 => S2 entre S1 et S3 (S1-S2-S3)
									if ((*it3).second<(*it2).second)
									{

										////S1->sideBySide(S2)
										//(*it).first.first->st_SideBySide.push_back((*it).first.second);

										////S2->sideBySide(S1)
										//(*it).first.second->st_SideBySide.push_back((*it).first.first);
										////S2->sideBySide(S3)
										//(*it).first.second->st_SideBySide.push_back((*it2).first.second);

										////S3->sideBySide(S2)
										//(*it2).first.second->st_SideBySide.push_back((*it).first.second);

										//S1->sideBySide(S2)
										(*it).first.first->mp_SideBySide[(*it).first.second]=false;

										//S2->sideBySide(S1)
										(*it).first.second->mp_SideBySide[(*it).first.first] = false;
										//S2->sideBySide(S3)
										(*it).first.second->mp_SideBySide[(*it2).first.second] = false;

										//S3->sideBySide(S2)
										(*it2).first.second->mp_SideBySide[(*it).first.second] = false;

										//Indication que S1 et S3 ne peuvent pas �tre cote � cote
										//map_CanBeSideBySide[std::make_pair((*it).first.first, (*it2).first.second)] = false;
										bo_AreTheTwoPairsFound = true;
									}// if ((*it3).second<(*it2).second)

									 // Si S2-S3 > S1-S3 => S1 entre S2 et S3 (S3-S1-S2)
									if ((*it3).second>(*it2).second)
									{
										////S3->sideBySide(S1)
										//(*it2).first.second->st_SideBySide.push_back((*it).first.first);

										////S1->sideBySide(S3)
										//(*it).first.first->st_SideBySide.push_back((*it2).first.second);
										////S1->sideBySide(S2)
										//(*it).first.first->st_SideBySide.push_back((*it).first.second);

										////S2->sideBySide(S1)
										//(*it).first.second->st_SideBySide.push_back((*it).first.first);

										//S3->sideBySide(S1)
										(*it2).first.second->mp_SideBySide[(*it).first.first] = false;

										//S1->sideBySide(S3)
										(*it).first.first->mp_SideBySide[(*it2).first.second] = false;
										//S1->sideBySide(S2)
										(*it).first.first->mp_SideBySide[(*it).first.second] = false;

										//S2->sideBySide(S1)
										(*it).first.second->mp_SideBySide[(*it).first.first] = false;

										//Indication que S2 et S3 ne peuvent pas �tre cote � cote
										//map_CanBeSideBySide[std::make_pair((*it).first.second, (*it2).first.second)] = false;
										bo_AreTheTwoPairsFound = true;
									}// if ((*it3).second>(*it2).second)
								}// if ((*it3).first.first == (*it).first.second && (*it3).first.second == (*it2).first.second)
								 //it3=S3-S2?
								 //Si la 1ere IfcConnectionSurfaceGeometry de it3 est S3 et la 2nde de it3 est S2 => on a les 3 paires pour renseigner les SideBySide
								if ((*it3).first.first == (*it2).first.second && (*it3).first.second == (*it).first.second)
								{
									//A ce stade, on a les 3 paires d'ifcConn it=S1-S2 , it2=S1-S3, it3=S3-S2 
									//avec les conditions: S1-S2 < S1-S3 
									//    A2.1)                  S1-------S3  => dans ce cas S2 aura 2 SideBySide, S1 et S3 1 SideBySide (ATTENTION: il faut ajouter les sideBySide car S1 et S3 peuvent avoir un autre SideBySide S4) 
									//    A1)                    S1--S2
									//    A2.2)         S3-------S1           => dans ce cas S1 aura 2 SideBySide, S2 et S3 1 SideBySide (ATTENTION: il faut ajouter les sideBySide car S2 et S3 peuvent avoir un autre SideBySide S4)

									// Si S3-S2 < S1-S3 => S2 entre S1 et S3 (S1-S2-S3)
									if ((*it3).second<(*it2).second)
									{
										////S1->sideBySide(S2)
										//(*it).first.first->st_SideBySide.push_back((*it).first.second);

										////S2->sideBySide(S1)
										//(*it).first.second->st_SideBySide.push_back((*it).first.first);
										////S2->sideBySide(S3)
										//(*it).first.second->st_SideBySide.push_back((*it2).first.second);

										////S3->sideBySide(S2)
										//(*it2).first.second->st_SideBySide.push_back((*it).first.second);

										//S1->sideBySide(S2)
										(*it).first.first->mp_SideBySide[(*it).first.second] = false;

										//S2->sideBySide(S1)
										(*it).first.second->mp_SideBySide[(*it).first.first] = false;
										//S2->sideBySide(S3)
										(*it).first.second->mp_SideBySide[(*it2).first.second] = false;

										//S3->sideBySide(S2)
										(*it2).first.second->mp_SideBySide[(*it).first.second] = false;

										//Indication que S1 et S3 ne peuvent pas �tre cote � cote
										//map_CanBeSideBySide[std::make_pair((*it).first.first, (*it2).first.second)] = false;
										bo_AreTheTwoPairsFound = true;
									}// if ((*it3).second<(*it2).second)

									 // Si S3-S2 > S1-S3 => S1 entre S2 et S3 (S3-S1-S2)
									if ((*it3).second>(*it2).second)
									{
										////S3->sideBySide(S1)
										//(*it2).first.second->st_SideBySide.push_back((*it).first.first);

										////S1->sideBySide(S3)
										//(*it).first.first->st_SideBySide.push_back((*it2).first.second);
										////S1->sideBySide(S2)
										//(*it).first.first->st_SideBySide.push_back((*it).first.second);

										////S2->sideBySide(S1)
										//(*it).first.second->st_SideBySide.push_back((*it).first.first);

										//S3->sideBySide(S1)
										(*it2).first.second->mp_SideBySide[(*it).first.first] = false;

										//S1->sideBySide(S3)
										(*it).first.first->mp_SideBySide[(*it2).first.second] = false;
										//S1->sideBySide(S2)
										(*it).first.first->mp_SideBySide[(*it).first.second] = false;

										//S2->sideBySide(S1)
										(*it).first.second->mp_SideBySide[(*it).first.first] = false;

										//Indication que S2 et S3 ne peuvent pas �tre cote � cote
										//map_CanBeSideBySide[std::make_pair((*it).first.second, (*it2).first.second)] = false;
										bo_AreTheTwoPairsFound = true;
									}// if ((*it3).second>(*it2).second)
								}// if ((*it3).first.first == (*it2).first.second && (*it3).first.second == (*it).first.second)

								if (bo_AreTheTwoPairsFound) break;
							}// for (list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>>::iterator it3 = it2, it2--; it3 != li_IfcConn_IfcConn_Dist.end(); ++it3)
						}// if ((it2 != it) && (*it2).first.first == (*it).first.first && map_IfcConn_IfcSpace[(*it2).first.second] == (*mp_Space).first)
						 //it2=S3-S1?
						 //Si la 2nde IfcConnectionSurfaceGeometry de it2 est S1 et si la 1ere IfcConn (S3) appartient au m�me ifcspace => on continue
						if ((it2 != it) && (*it2).first.second == (*it).first.first && map_IfcConn_IfcSpace[(*it2).first.first] == (*mp_Space).first)
						{
							//A ce stade, on a les 2 paires d'ifcConn it=S1-S2 et it2=S3-S1, on cherche la derniere paire it3=S2-S3 ou it3=S3-S2
							//BOUCLE POUR CHERCHER it3
							it2++;
							for (it3 = it2, it2--; it3 != li_IfcConn_IfcConn_Dist.end(); it3++)
							{
								//it3=S2-S3?
								//Si la 1ere IfcConnectionSurfaceGeometry de it3 est S2 et la 2nde de it3 est S3 => on a les 3 paires pour renseigner les SideBySide
								if ((*it3).first.first == (*it).first.second && (*it3).first.second == (*it2).first.first)
								{
									//A ce stade, on a les 3 paires d'ifcConn it=S1-S2 , it2=S3-S1, it3=S2-S3 
									//avec les conditions: S1-S2 < S3-S1 
									//    A2.1)                  S1-------S3  => dans ce cas S2 aura 2 SideBySide, S1 et S3 1 SideBySide (ATTENTION: il faut ajouter les sideBySide car S1 et S3 peuvent avoir un autre SideBySide S4) 
									//    A1)                    S1--S2
									//    A2.2)         S3-------S1           => dans ce cas S1 aura 2 SideBySide, S2 et S3 1 SideBySide (ATTENTION: il faut ajouter les sideBySide car S2 et S3 peuvent avoir un autre SideBySide S4) 

									// Si S2-S3 < S3-S1 => S2 entre S1 et S3 (S1-S2-S3)
									if ((*it3).second<(*it2).second)
									{
										////S1->sideBySide(S2)
										//(*it).first.first->st_SideBySide.push_back((*it).first.second);

										////S2->sideBySide(S1)
										//(*it).first.second->st_SideBySide.push_back((*it).first.first);
										////S2->sideBySide(S3)
										//(*it).first.second->st_SideBySide.push_back((*it2).first.first);

										////S3->sideBySide(S2)
										//(*it2).first.first->st_SideBySide.push_back((*it).first.second);

										//S1->sideBySide(S2)
										(*it).first.first->mp_SideBySide[(*it).first.second] = false;

										//S2->sideBySide(S1)
										(*it).first.second->mp_SideBySide[(*it).first.first] = false;
										//S2->sideBySide(S3)
										(*it).first.second->mp_SideBySide[(*it2).first.first] = false;

										//S3->sideBySide(S2)
										(*it2).first.first->mp_SideBySide[(*it).first.second] = false;

										//Indication que S1 et S3 ne peuvent pas �tre cote � cote
										//map_CanBeSideBySide[std::make_pair((*it).first.first, (*it2).first.first)] = false;
										bo_AreTheTwoPairsFound = true;
									}// if ((*it3).second<(*it2).second)

									 // Si S2-S3 > S3-S1 => S1 entre S2 et S3 (S3-S1-S2)
									if ((*it3).second>(*it2).second)
									{
										////S3->sideBySide(S1)
										//(*it2).first.first->st_SideBySide.push_back((*it).first.first);

										////S1->sideBySide(S3)
										//(*it).first.first->st_SideBySide.push_back((*it2).first.first);
										////S1->sideBySide(S2)
										//(*it).first.first->st_SideBySide.push_back((*it).first.second);

										////S2->sideBySide(S1)
										//(*it).first.second->st_SideBySide.push_back((*it).first.first);

										//S3->sideBySide(S1)
										(*it2).first.first->mp_SideBySide[(*it).first.first] = false;

										//S1->sideBySide(S3)
										(*it).first.first->mp_SideBySide[(*it2).first.first] = false;
										//S1->sideBySide(S2)
										(*it).first.first->mp_SideBySide[(*it).first.second] = false;

										//S2->sideBySide(S1)
										(*it).first.second->mp_SideBySide[(*it).first.first] = false;

										//Indication que S2 et S3 ne peuvent pas �tre cote � cote
										//map_CanBeSideBySide[std::make_pair((*it).first.second, (*it2).first.first)] = false;
										bo_AreTheTwoPairsFound = true;
									}// if ((*it3).second>(*it2).second)
								}// if ((*it3).first.first == (*it).first.second && (*it3).first.second == (*it2).first.first)
								 //it3=S3-S2?
								 //Si la 1ere IfcConnectionSurfaceGeometry de it3 est S3 et la 2nde de it3 est S2 => on a les 3 paires pour renseigner les SideBySide
								if ((*it3).first.first == (*it2).first.first && (*it3).first.second == (*it).first.second)
								{
									//A ce stade, on a les 3 paires d'ifcConn it=S1-S2 , it2=S3-S1, it3=S3-S2 
									//avec les conditions: S1-S2 < S3-S1 
									//    A2.1)                  S1-------S3  => dans ce cas S2 aura 2 SideBySide, S1 et S3 1 SideBySide (ATTENTION: il faut ajouter les sideBySide car S1 et S3 peuvent avoir un autre SideBySide S4) 
									//    A1)                    S1--S2
									//    A2.2)         S3-------S1           => dans ce cas S1 aura 2 SideBySide, S2 et S3 1 SideBySide (ATTENTION: il faut ajouter les sideBySide car S2 et S3 peuvent avoir un autre SideBySide S4)

									// Si S3-S2 < S3-S1 => S2 entre S1 et S3 (S1-S2-S3)
									if ((*it3).second<(*it2).second)
									{
										////S1->sideBySide(S2)
										//(*it).first.first->st_SideBySide.push_back((*it).first.second);

										////S2->sideBySide(S1)
										//(*it).first.second->st_SideBySide.push_back((*it).first.first);
										////S2->sideBySide(S3)
										//(*it).first.second->st_SideBySide.push_back((*it2).first.first);

										////S3->sideBySide(S2)
										//(*it2).first.first->st_SideBySide.push_back((*it).first.second);

										//S1->sideBySide(S2)
										(*it).first.first->mp_SideBySide[(*it).first.second] = false;

										//S2->sideBySide(S1)
										(*it).first.second->mp_SideBySide[(*it).first.first] = false;
										//S2->sideBySide(S3)
										(*it).first.second->mp_SideBySide[(*it2).first.first] = false;

										//S3->sideBySide(S2)
										(*it2).first.first->mp_SideBySide[(*it).first.second] = false;

										//Indication que S1 et S3 ne peuvent pas �tre cote � cote
										//map_CanBeSideBySide[std::make_pair((*it).first.first, (*it2).first.first)] = false;
										bo_AreTheTwoPairsFound = true;
									}// if ((*it3).second<(*it2).second)

									 // Si S3-S2 > S3-S1 => S1 entre S2 et S3 (S3-S1-S2)
									if ((*it3).second>(*it2).second)
									{
										////S3->sideBySide(S1)
										//(*it2).first.first->st_SideBySide.push_back((*it).first.first);

										////S1->sideBySide(S3)
										//(*it).first.first->st_SideBySide.push_back((*it2).first.first);
										////S1->sideBySide(S2)
										//(*it).first.first->st_SideBySide.push_back((*it).first.second);

										////S2->sideBySide(S1)
										//(*it).first.second->st_SideBySide.push_back((*it).first.first);

										//S3->sideBySide(S1)
										(*it2).first.first->mp_SideBySide[(*it).first.first] = false;

										//S1->sideBySide(S3)
										(*it).first.first->mp_SideBySide[(*it2).first.first] = false;
										//S1->sideBySide(S2)
										(*it).first.first->mp_SideBySide[(*it).first.second] = false;

										//S2->sideBySide(S1)
										(*it).first.second->mp_SideBySide[(*it).first.first] = false;

										//Indication que S2 et S3 ne peuvent pas �tre cote � cote
										//map_CanBeSideBySide[std::make_pair((*it).first.second, (*it2).first.first)] = false;
										bo_AreTheTwoPairsFound = true;
									}// if ((*it3).second>(*it2).second)
								}// if ((*it3).first.first == (*it2).first.first && (*it3).first.second == (*it).first.second)

								if (bo_AreTheTwoPairsFound) break;
							}// for (list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>>::iterator it3 = it2, it2--; it3 != li_IfcConn_IfcConn_Dist.end(); ++it3)
						}// if ((*it2).first.second == (*it).first.first && map_IfcConn_IfcSpace[(*it2).first.first] == (*mp_Space).first)

						if (bo_AreTheTwoPairsFound) break;
					}// for (list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>>::iterator it2 = it, it--; it2 != li_IfcConn_IfcConn_Dist.end(); ++it2)
				}// if (map_IfcConn_IfcSpace[(*it).first.first] == map_IfcConn_IfcSpace[(*it).first.second])
			}//for (list< pair< pair<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>, double>>::iterator it = li_IfcConn_IfcConn_Dist.begin(); it != li_IfcConn_IfcConn_Dist.end(); ++it)
		}// else if ((*mp_Space).second > 2)
	}// for (mp_Elem1 = map_IfcSpace_NbIfcConn.begin(); mp_Elem1 != map_IfcSpace_NbIfcConn.end(); mp_Elem1++)

	////
	////Retrait des redondances dans le membre SideBySide des IfcConnectionSurfaceGeometry
	//for (map<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>::iterator it_Elem1 = map_IfcConn_IfcSpace.begin(); it_Elem1 != map_IfcConn_IfcSpace.end(); it_Elem1++)
	//{
	//	((*it_Elem1).first)->st_SideBySide.sort();
	//	((*it_Elem1).first)->st_SideBySide.unique();
	//}// for (map<STRUCT_IFCENTITY *, STRUCT_IFCENTITY *>::iterator it_Elem1 = map_IfcConn_IfcSpace.begin(); it_Elem1 != map_IfcConn_IfcSpace.end(); it_Elem1++)

	return Res;
}

double ifc_TreePostTreatment::ComputePtPtDistance(vector<double*> &vc_Point1, vector<double*> &vc_Point2)
{
	double db_dist = sqrt((*vc_Point2[0] - *vc_Point1[0])*(*vc_Point2[0] - *vc_Point1[0])
						+ (*vc_Point2[1] - *vc_Point1[1])*(*vc_Point2[1] - *vc_Point1[1])
						+ (*vc_Point2[2] - *vc_Point1[2])*(*vc_Point2[2] - *vc_Point1[2]));
	return db_dist;
}
