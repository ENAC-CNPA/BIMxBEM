#include "ifc_Tree.h"


ifc_Tree::ifc_Tree(): _st_IfcTree(nullptr)
{
}


ifc_Tree::~ifc_Tree()
{
	//
	//Desalloc des données membres de ifc_Tree
	if (_st_IfcTree)
		delete_STRUCT_IFCENTITY(_st_IfcTree);
	_st_IfcTree = nullptr;
}

STRUCT_IFCENTITY *&ifc_Tree::Getstruct()
{
	return _st_IfcTree;
}

void ifc_Tree::delete_STRUCT_IFCENTITY(STRUCT_IFCENTITY* &st_IfcTree, STRUCT_IFCENTITY* st_IfcCurrentFather)
{
	//
	//Descente dans l'arborescence jusqu'aux élément sans enfants (membre "st_Contains" vide)
	list <STRUCT_IFCENTITY*> ::iterator it_Elem;
	for (it_Elem = (st_IfcTree->st_Contains).begin(); it_Elem != (st_IfcTree->st_Contains).end(); it_Elem++)
	{
		if ((*it_Elem))
			delete_STRUCT_IFCENTITY((*it_Elem), st_IfcTree);
	}// for (it_Elem = (st_IfcTree->st_Contains).begin(); it_Elem != (st_IfcTree->st_Contains).end(); it_Elem++)
	st_IfcTree->st_Contains.clear();

	//
	//Désallocations effectives
	//
	delete[] st_IfcTree->ch_GlobalId; st_IfcTree->ch_GlobalId = nullptr;
	delete[] st_IfcTree->ch_Id; st_IfcTree->ch_Id = nullptr;
	delete[] st_IfcTree->ch_Name; st_IfcTree->ch_Name = nullptr;
	delete[] st_IfcTree->ch_Type; st_IfcTree->ch_Type = nullptr;
	delete st_IfcTree->map_DefValues; st_IfcTree->map_DefValues = nullptr;

	list<double*>::iterator it_l_Points;
	for (it_l_Points = (st_IfcTree->db_RelativePlacement).begin(); it_l_Points != (st_IfcTree->db_RelativePlacement).end(); it_l_Points++)
	{
		delete (*it_l_Points);
		*it_l_Points = nullptr;
	}// for (it_l_Points = (st_IfcTree->db_RelativePlacement).begin(); it_l_Points != (st_IfcTree->db_RelativePlacement).end(); it_l_Points++)
	st_IfcTree->db_RelativePlacement.clear();

	for (it_l_Points = (st_IfcTree->db_Centroid).begin(); it_l_Points != (st_IfcTree->db_Centroid).end(); it_l_Points++)
	{
		delete (*it_l_Points);
		*it_l_Points = nullptr;
	}// for (it_l_Points = (st_IfcTree->db_RelativePlacement).begin(); it_l_Points != (st_IfcTree->db_RelativePlacement).end(); it_l_Points++)
	st_IfcTree->db_RelativePlacement.clear();

	list <list<double*>>::iterator it_ll_Points;
	for (it_ll_Points = (st_IfcTree->st_PointsDesContours).begin(); it_ll_Points != (st_IfcTree->st_PointsDesContours).end(); it_ll_Points++)
	{
		for (it_l_Points = (*it_ll_Points).begin(); it_l_Points != (*it_ll_Points).end(); it_l_Points++)
		{
			delete (*it_l_Points);
			*it_l_Points = nullptr;
		}// for (it_l_Points = (*it_ll_Points).begin(); it_l_Points != (*it_ll_Points).end(); it_l_Points++)
		 //
		(*it_ll_Points).clear();
	}// for (it_ll_Points = (st_IfcTree->st_PointsDesContours).begin(); it_ll_Points != (st_IfcTree->st_PointsDesContours).end(); it_ll_Points++)
	st_IfcTree->st_PointsDesContours.clear();

	//
	// Nettoyage des listes référencant l'objet que l'on est en train de détruire
	// Pour les liens non binaires (ternaires ou plus) la structure en cours d'effacement (st_IfcTree) est référencée dans les Contains de plusieurs pères
	// Afin déviter un crash mémoire par la désallocation d'une structure déjà détruite, il faut déréférencer la structure 
	// en cours d'effacement des listes de BelongsTo des autres pères (que celui en cours = st_IfcCurrentFather)
	// Exemple: IfcConnectionSurfaceGeometry est référencé à la fois dans le st_Contains de IfSpace et des BuildingElements (IfcWall,...)
	list <STRUCT_IFCENTITY*> ::iterator it_ElemInBelong;
	for (it_ElemInBelong = (st_IfcTree->st_BelongsTo).begin(); it_ElemInBelong != (st_IfcTree->st_BelongsTo).end(); it_ElemInBelong++)
	{
		if ((*it_ElemInBelong) != st_IfcCurrentFather)
		{
			list <STRUCT_IFCENTITY*> ::iterator it_ElemInBelongContains;
			for (it_ElemInBelongContains = ((*it_ElemInBelong)->st_Contains).begin(); it_ElemInBelongContains != ((*it_ElemInBelong)->st_Contains).end(); it_ElemInBelongContains++)
			{
				if ((*it_ElemInBelongContains) == st_IfcTree)
				{
					(*it_ElemInBelong)->st_Contains.erase(it_ElemInBelongContains);
					break;
				}// if ((*it_ElemInBelongContains) == st_IfcTree)
			}// for (it_ElemInBelongContains = ((*it_ElemInBelong)->st_Contains).begin(); it_ElemInBelongContains != ((*it_ElemInBelong)->st_Contains).end(); it_ElemInBelongContains++)
		}// if ((*it_ElemInBelong) != st_IfcCurrentFather)
	}// for (it_ElemInBelong = (st_IfcTree->st_BelongsTo).begin(); it_ElemInBelong != (st_IfcTree->st_BelongsTo).end(); it_ElemInBelong++)
	st_IfcTree->st_BelongsTo.clear();

	//La liste st_FaceToFace référence des objets désalloués par ailleurs, du coup pas d'action de désallocation spécifique 

	//TIFCSurface
	list <STRUCT_IFCENTITY*> ::iterator it_ElemInTIFCSurfaceContain;
	if (st_IfcTree->st_TIFCSurface)
	{
		for (it_ElemInTIFCSurfaceContain = (st_IfcTree->st_TIFCSurface->st_Contains).begin(); it_ElemInTIFCSurfaceContain != (st_IfcTree->st_TIFCSurface->st_Contains).end(); it_ElemInTIFCSurfaceContain++)
		{
			if ((*it_ElemInTIFCSurfaceContain) != st_IfcTree)
			{
				//(*it_ElemInTIFCSurfaceContain)->st_TIFCSurface.clear();
				(*it_ElemInTIFCSurfaceContain)->st_TIFCSurface = nullptr;
				break;
			}// if ((*it_ElemInTIFCSurfaceContain) != st_IfcTree)
		}// for (it_ElemInTIFCSurfaceContain = (st_IfcTree->st_TIFCSurface->st_Contains).begin(); it_ElemInTIFCSurfaceContain != (st_IfcTree->st_TIFCSurface->st_Contains).end(); it_ElemInTIFCSurfaceContain++)
		delete st_IfcTree->st_TIFCSurface; st_IfcTree->st_TIFCSurface = nullptr;
	}// if (st_IfcTree->st_TIFCSurface)

	delete st_IfcTree; st_IfcTree = nullptr;
}

void ifc_Tree::FillAttributeOf_STRUCT_IFCENTITY(STRUCT_IFCENTITY* st_IfcTree, Map_String_String &map_messages, double db_LocalMat[3][4], STRUCT_IFCENTITY *st_IfcBelongTo, STRUCT_IFCENTITY *st_IfcBelongTo2)
{
	//la structure st_IfcTree est celle que l'on initialise/renseigne dans cette routine
	//les structure st_IfcBelongTo est un pere de st_IfcTree (=> vient de la relation binaire ifcRelAggregates)
	//les structure st_IfcBelongTo2 est un 2nd père de st_IfcTree (=> vient de la relation ternaire IfcRelSpaceBoundary)
	if (st_IfcTree)
	{
		// Pour les tailles: http://www.buildingsmart-tech.org/ifc/IFC2x3/TC1/html/
		FillNameAndIDAttributeOf_STRUCT_IFCENTITY(st_IfcTree, map_messages);

		if (st_IfcBelongTo)
		{
			st_IfcTree->st_BelongsTo.push_back(st_IfcBelongTo);
			st_IfcBelongTo->st_Contains.push_back(st_IfcTree);
		}// if (st_IfcBelongTo)

		if (st_IfcBelongTo2)
		{
			st_IfcTree->st_BelongsTo.push_back(st_IfcBelongTo2);
			st_IfcBelongTo2->st_Contains.push_back(st_IfcTree);
		}// if (st_IfcBelongTo)

		FillRelativePlacementOf_STRUCT_IFCENTITY(st_IfcTree, db_LocalMat);
	}// if (st_IfcTree)
}

void ifc_Tree::FillAttributeOfExisting_STRUCT_IFCENTITY(STRUCT_IFCENTITY* st_IfcTree, Map_String_String &map_messages, double db_LocalMat[3][4], STRUCT_IFCENTITY *st_IfcBelongTo, STRUCT_IFCENTITY *st_IfcBelongTo2)
{
	//la structure st_IfcTree est celle que l'on initialise/renseigne dans cette routine
	//les structure st_IfcBelongTo est un pere de st_IfcTree (=> vient de la relation binaire ifcRelAggregates)
	//les structure st_IfcBelongTo2 est un 2nd père de st_IfcTree (=> vient de la relation ternaire IfcRelSpaceBoundary)
	if (st_IfcTree)
	{
		if (st_IfcBelongTo)
		{
			//Faire boucle pour tester existence du pointeur
			list <STRUCT_IFCENTITY*> ::iterator it_Elem;
			bool bo_IsItInList = false;
			for (it_Elem = (st_IfcTree->st_BelongsTo).begin(); it_Elem != (st_IfcTree->st_BelongsTo).end(); it_Elem++)
			{
				if ((*it_Elem) == st_IfcBelongTo)
				{
					bo_IsItInList = true;
					break;
				}// if ((*it_Elem) == st_IfcBelongTo)
			}// for (it_Elem = (st_IfcTree->st_BelongsTo).begin(); it_Elem != (st_IfcTree->st_BelongsTo).end(); it_Elem++)
			if (!bo_IsItInList)
				st_IfcTree->st_BelongsTo.push_back(st_IfcBelongTo);
			bo_IsItInList = false;
			for (it_Elem = (st_IfcBelongTo->st_Contains).begin(); it_Elem != (st_IfcBelongTo->st_Contains).end(); it_Elem++)
			{
				if ((*it_Elem) == st_IfcTree)
				{
					bo_IsItInList = true;
					break;
				}// if ((*it_Elem) == st_IfcBelongTo)
			}// for (it_Elem = (st_IfcBelongTo->st_Contains).begin(); it_Elem != (st_IfcBelongTo->st_Contains).end(); it_Elem++)
			if (!bo_IsItInList)
				st_IfcBelongTo->st_Contains.push_back(st_IfcTree);
		}// if (st_IfcBelongTo)
	}// if (st_IfcTree)
}

void ifc_Tree::FillNameAndIDAttributeOf_STRUCT_IFCENTITY(STRUCT_IFCENTITY* st_IfcTree, Map_String_String &map_messages)
{
	// Pour les tailles: http://www.buildingsmart-tech.org/ifc/IFC2x3/TC1/html/
	char *ch_copy22 = new char[23];//size+1 pour que strncpy mette'\0'
	strncpy(ch_copy22, map_messages["GlobalId"].c_str(), 23);
	st_IfcTree->ch_GlobalId = ch_copy22;

	if (map_messages.count("LongName"))
	{
		char *ch_copy255 = new char[256];//size+1 pour que strncpy mette'\0'
		strncpy(ch_copy255, map_messages["LongName"].c_str(), 256);
		st_IfcTree->ch_Name = ch_copy255;
	}
	else
	{
		char *ch_copy255 = new char[256];//size+1 pour que strncpy mette'\0'
		strncpy(ch_copy255, map_messages["Name"].c_str(), 256);
		st_IfcTree->ch_Name = ch_copy255;
	}// else if (map_messages.count("LongName"))

	char *ch_copy9 = new char[16];//size+1 pour que strncpy mette'\0'
	strncpy(ch_copy9, map_messages["Id"].c_str(), 16);
	st_IfcTree->ch_Id = ch_copy9;

	char *ch_copy55 = new char[56];//size+1 pour que strncpy mette'\0'
	strncpy(ch_copy55, map_messages["Type"].c_str(), 56);
	st_IfcTree->ch_Type = ch_copy55;

	if (map_messages.count("PredefinedType"))
	{
		char *ch_copy55 = new char[56];//size+1 pour que strncpy mette'\0'
		strncpy(ch_copy55, map_messages["PredefinedType"].c_str(), 56);
		st_IfcTree->ch_PredifinedType = ch_copy55;
	}// if (map_messages.count("PredefinedType"))
}

void ifc_Tree::FillRelativePlacementOf_STRUCT_IFCENTITY(STRUCT_IFCENTITY* st_IfcTree, double db_LocalMat[3][4])
{
	//la structure st_IfcTree est celle que l'on initialise/renseigne dans cette routine
	//les structure st_IfcBelongTo est un pere de st_IfcTree (=> vient de la relation binaire ifcRelAggregates)
	//les structure st_IfcBelongTo2 est un 2nd père de st_IfcTree (=> vient de la relation ternaire IfcRelSpaceBoundary)
	if (st_IfcTree)
	{
		// Pour les tailles: http://www.buildingsmart-tech.org/ifc/IFC2x3/TC1/html/
		if (db_LocalMat)
		{
			for (int i_col = 0; i_col < 4; i_col++)
			{
				for (int i_lin = 0; i_lin < 3; i_lin++)
				{
					double *db_Val = new double();
					*db_Val = db_LocalMat[i_lin][i_col];
					st_IfcTree->db_RelativePlacement.push_back(db_Val);//(db_LocalMat[i_lin][i_col])
				}// for (int i_lin = 0; i_lin < 3; i_lin++)
			}// for (int i_col = 0; i_col < 4; i_col++)
		}// if (db_LocalMat)
	}// if (st_IfcTree)
}

void ifc_Tree::FillCentroidOf_STRUCT_IFCENTITY(STRUCT_IFCENTITY* st_IfcTree, double db_CentroidCoord[3])
{
	//la structure st_IfcTree est celle que l'on initialise/renseigne dans cette routine
	//les structure st_IfcBelongTo est un pere de st_IfcTree (=> vient de la relation binaire ifcRelAggregates)
	//les structure st_IfcBelongTo2 est un 2nd père de st_IfcTree (=> vient de la relation ternaire IfcRelSpaceBoundary)
	if (st_IfcTree)
	{
		// Pour les tailles: http://www.buildingsmart-tech.org/ifc/IFC2x3/TC1/html/
		if (db_CentroidCoord)
		{
			for (int i_coord = 0; i_coord < 3; i_coord++)
			{
				double *db_Val = new double();
				*db_Val = db_CentroidCoord[i_coord];
				st_IfcTree->db_Centroid.push_back(db_Val);//(db_CentroidCoord[i_coord])
			}// for (int i_coord = 0; i_coord < 3; i_coord++)
		}// if (db_CentroidCoord)
	}// if (st_IfcTree)
}

void ifc_Tree::FillGeomAttributeOf_STRUCT_IFCENTITY(STRUCT_IFCENTITY* st_IfcSubFacGeomRep, list<list<double*>> &SubFacePtsCoord, STRUCT_IFCENTITY *st_IfcBelongTo, Map_String_String &map_messages)
{
	FillNameAndIDAttributeOf_STRUCT_IFCENTITY(st_IfcSubFacGeomRep, map_messages);

	st_IfcSubFacGeomRep->st_PointsDesContours = SubFacePtsCoord;

	if (st_IfcBelongTo)
	{
		st_IfcSubFacGeomRep->st_BelongsTo.push_back(st_IfcBelongTo);
		st_IfcBelongTo->st_Contains.push_back(st_IfcSubFacGeomRep);
	}// if (st_IfcBelongTo)
}

void ifc_Tree::FillQuantitiesAttributeOf_STRUCT_IFCENTITY(STRUCT_IFCENTITY* st_IfcTree, Map_String_String &map_messages)
{
	if (map_messages.size() != 0)
	{
		Map_String_String* mp_copy = new Map_String_String;
		*mp_copy = map_messages;
		if (mp_copy)
			st_IfcTree->map_DefValues = mp_copy;
	}// if (map_messages.size != 0)
}

int ifc_Tree::BuildTIFCSurfaceTreeFrom_STRUCT_IFCENTITY(STRUCT_IFCENTITY* st_IfcEntCS1)
{
	int res = 0;
	
	//On vérifie qu'il n'y a qu'une IfcConnectionSurfaceGeometry en vis-à-vis
	// car la TIFCSurface associe des paires de IfcConnectionSurfaceGeometry (pas plus)
	//A REVOIR: Par contre il peut ne pas y avoir de vis-à-vis (dans ce cas, c'est geoExt = mur exterieur, il est quand même en vis-à-vis?????) 
	if (st_IfcEntCS1 && st_IfcEntCS1->st_FaceToFace.size()==1)
	{
		//Recup de la 2nde IfcConnectionSurfaceGeometry (en vis-à-vis)
		STRUCT_IFCENTITY* st_IfcEntCS2 = *(st_IfcEntCS1->st_FaceToFace.begin());

		//On vérifie que cette IfcConnectionSurfaceGeometry (st_IfcEntCS2) n'a pas déjà sa TIFCSurface 
		//car à sa création la même TIFCSurface est associée à 2 IfcConnectionSurfaceGeometry
		// => sinon erreur
		if (st_IfcEntCS2 && st_IfcEntCS2->st_TIFCSurface == nullptr)
		{
			// ATTENTION: la taille du nom "Ch_Id" est limité à 16 dans FillNameAndIDAttributeOf_STRUCT_IFCENTITY
			Map_String_String map_messages;
			map_messages["Id"] = string(st_IfcEntCS1->ch_Id) + string(st_IfcEntCS2->ch_Id);
			map_messages["Type"] = "TIFCSurface";
			// Indiquer le type du TIFCSurface (ifcWall...) : map_messages["Type"] = ...

			//Création et Remplissage de la structure de "TIFCSurface"
			STRUCT_IFCENTITY * st_TIFCSurface = new STRUCT_IFCENTITY;
			FillNameAndIDAttributeOf_STRUCT_IFCENTITY(st_TIFCSurface, map_messages);

			//FillAttributeOf_STRUCT_IFCENTITY(st_IfcContain, map_messages, db_LocalMat, &(*st_IfcBelongTo));
			st_IfcEntCS1->st_TIFCSurface = st_TIFCSurface;
			st_IfcEntCS2->st_TIFCSurface = st_TIFCSurface;
			if (st_TIFCSurface)
			{
				st_TIFCSurface->st_Contains.push_back(st_IfcEntCS1);
				st_TIFCSurface->st_Contains.push_back(st_IfcEntCS2);
			}// if (st_TIFCSurface)

		}// if (st_IfcEntCS2 && st_IfcEntCS2->st_TIFCSurface==nullptr)
		else
			res = 3001;//Format erreur: XXXYYY XXX=numero identifiant la routine , YYY=numéro de l'erreur dans cette routine
	}// if (st_IfcEntCS1 && st_IfcEntCS1->st_FaceToFace.size()==1)
	else 
	{
		if (st_IfcEntCS1 && st_IfcEntCS1->st_FaceToFace.size() == 0)
		{
			//SOIT MUR exterieur 
			//SOIT dalle entre étage => pas sûr car dalles devraientt se traiter comme les murs intérieurs??!!?? 

			// ATTENTION: la taille du nom "Ch_Id" est limité à 16 dans FillNameAndIDAttributeOf_STRUCT_IFCENTITY
			Map_String_String map_messages;
			map_messages["Id"] = string(st_IfcEntCS1->ch_Id) + "------";
			map_messages["Type"] = "TIFCSurface";
			// Indiquer le type du TIFCSurface (ifcWall...) : map_messages["Type"] = ...

			//Création et Remplissage de la structure de "TIFCSurface"
			STRUCT_IFCENTITY * st_TIFCSurface = new STRUCT_IFCENTITY;
			FillNameAndIDAttributeOf_STRUCT_IFCENTITY(st_TIFCSurface, map_messages);

			//FillAttributeOf_STRUCT_IFCENTITY(st_IfcContain, map_messages, db_LocalMat, &(*st_IfcBelongTo));
			st_IfcEntCS1->st_TIFCSurface = st_TIFCSurface;
			//st_IfcEntCS2->st_TIFCSurface = st_TIFCSurface;
			if (st_TIFCSurface)
			{
				st_TIFCSurface->st_Contains.push_back(st_IfcEntCS1);
				//st_TIFCSurface->st_Contains.push_back(st_IfcEntCS2);
			}// if (st_TIFCSurface)

		}// if (st_IfcEntCS1 && st_IfcEntCS1->st_FaceToFace.size() == 0)
	}// else if (st_IfcEntCS1->st_FaceToFace.size()==1)

	return res;
}