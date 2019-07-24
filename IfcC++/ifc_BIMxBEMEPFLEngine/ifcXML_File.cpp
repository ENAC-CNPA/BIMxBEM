#include <cmath>
#include "ifcXML_File.h"


ifcXML_File::ifcXML_File() :_hRoot(0), _cl_ifcTree(nullptr)/*, st_IfcTree(nullptr)*/
{
}
 
ifcXML_File::~ifcXML_File()
{
	//
	//Desalloc des données membres de ifcXML_File
	if (_cl_ifcTree)
		delete _cl_ifcTree;
	_cl_ifcTree = nullptr;
}

ifc_Tree* ifcXML_File::GetData()
{
	return _cl_ifcTree;
}

int ifcXML_File::LoadFile(char *strFileName)
{
	//
	//http://www.grinninglizard.com/tinyxmldocs/classTiXmlDocument.html
	TiXmlDocument doc(strFileName);
	if (!doc.LoadFile())
		return 1001;//Format erreur: XXXYYY XXX=numero identifiant la routine , YYY=numéro de l'erreur dans cette routine

	TiXmlHandle hDoc(&doc);
	TiXmlElement* pElem = hDoc.FirstChildElement().ToElement();

	// should always have a valid root but handle gracefully if it does
	if (!pElem)
		return 1002;//Format erreur: XXXYYY XXX=numero identifiant la routine , YYY=numéro de l'erreur dans cette routine

	// memo root
	_hRoot = pElem->FirstChild("ex:uos");

	//Chargement de toutes les entités du fichier xml dans un tableau de type "MAP": 
	//	_map_ID_Elmt["i1722"] = TiXmlElement *(<IfcProject id="i1722">)
	int res = LoadIfcEntities(_hRoot);
	if (res != 0)
		return 1003;//Format erreur: XXXYYY XXX=numero identifiant la routine , YYY=numéro de l'erreur dans cette routine

	//Initialisation de la map _map_BE_Quantities
	// => Chargement de toutes les entités du fichier xml dans un tableau de type "MAP" associant à chaque élément de construction (IfcWallStandardCase, IfcSlab, ...) 
	//	  leurs propriétés "IfcElementQuantity" (Length, Width, Height, GrossFootprintArea, ...):
	//	  _map_BE_Quantities[TiXmlElement * Buildingelemet] = TiXmlElement * IfcElementQuantity
	res = ScanIfcRelDefinesByPropertiesForQuantities();
	if (res != 0)
		return 1004;//Format erreur: XXXYYY XXX=numero identifiant la routine , YYY=numéro de l'erreur dans cette routine

	//Recup de l'élément "IfcProject"
	pElem = _hRoot.FirstChild("IfcProject").ToElement();

	// Constitution de l'arbre structure de données BIMxBEM
	_cl_ifcTree = new ifc_Tree();
	if (_cl_ifcTree)
		res = _cl_ifcTree->BuildTreeFromRoot<TiXmlElement, ifcXML_File>(pElem, this);

	return res;
}

//
// La définition d'une entité se compose de lien direct (les attributs) et de liens indirects vers d'autres entités (les entités liées)
//
// Cette classe se décompose en 4 parties principales:
//		1.0: Routines de base de lecture des attributs
//		1.1: Routines spécifiques de lecture des attributs
//		2.0: Routines de base de recherche des entités liés
//		2.1: Routines de recherche par chemin "UN-aire" des entités liées
//		2.2: Routines de recherche par chemin "MULTI-aire" des entités liées
//		3.0: Routines de scan 
//
// Pour chercher des entités depuis leur id => utiliser _map_ID_Elmt (si on a l'id) 
// Pour chercher des entités depuis leur ref => utiliser la routine FindObjectFromRef 
// Pour chercher des entités depuis leur nom de type ifc => utiliser routines de base du parser (par exemple "TiXmlHandle.Child(pKeyword1,..)")
//

//////////////////////////////////////////////////////////////////////////////////////
//  1.0) ROUTINES DE BASE DE LECTURE (DES ATTRIBUTS) DE LA DEFINITION D'UNE ENTITE  //
//////////////////////////////////////////////////////////////////////////////////////

// Lecture de tous les attributs enfants d'une entité 
// En quelque sorte, lecture des liens directs/constitutifs de la def qui ne soient pas des liens vers d'autres entités ifc (liens indirects)
// Ce liens indirects sont associés avec un chemin de mots clés pour obtenir l'entité souhaitée => plutôt dans les routines "Find..."
int ifcXML_File::ReadIdAndTypeOfAnEntity(TiXmlElement *pIfcEntity, Map_String_String &map_messages)
{
	int res = 0;
	
	// Positionnement sur le 1er child de "IfcEntity" 
	TiXmlHandle hLocalRoot(pIfcEntity);
	TiXmlElement *pElem = hLocalRoot.FirstChild().ToElement();

	map_messages["Id"] = pIfcEntity->Attribute("id");
	map_messages["Type"] = pIfcEntity->Value();

	//lecture du contenu des children de "IfcEntity"
	for (pElem; pElem; pElem = pElem->NextSiblingElement())
	{
		const char *pKey = pElem->Value();
		const char *pText = pElem->GetText();
		if (pKey && pText)
		{
			map_messages[pKey] = pText;
		}// if (pKey && pText)
	}// for (pElem; pElem; pElem = pElem->NextSiblingElement())

	return res;
}

// Routines semblable à ReadIdAndTypeOfAnEntity (sans lecture de l'ID et du type) et surtout utilise en argument une liste plutôt que map car 
// le problème est que si les index du tableau "map" sont les mêmes (pour lecture des coordonnées par exemple) cela ecrase alors la précédente valeur
int ifcXML_File::ReadAllValuesOfAnEntity(TiXmlElement *pIfcEntity, list<string> &li_messages)
{
	int res = 0;

	// Positionnement sur le 1er child de "IfcEntity" 
	TiXmlHandle hLocalRoot(pIfcEntity);
	TiXmlElement *pElem = hLocalRoot.FirstChild().ToElement();

	//lecture du contenu des children de "IfcEntity"
	for (pElem; pElem; pElem = pElem->NextSiblingElement())
	{
		//const char *pKey = pElem->Value();
		const char *pText = pElem->GetText();
		if (/*pKey &&*/ pText)
		{
			li_messages.push_back(pText);
		}// if (pKey && pText)
	}// for (pElem; pElem; pElem = pElem->NextSiblingElement())

	return res;
}

// Lecture d'un attribut enfant d'une entité 
int ifcXML_File::ReadOneSpecificValueOfAnEntity(TiXmlElement *pIfcEntity, string &st_Path, string &st_value)
{
	int res = 0;

	// Positionnement sur le 1er child de "IfcEntity" 
	TiXmlHandle hLocalRoot(pIfcEntity);
	TiXmlElement *pElem = hLocalRoot.FirstChild(st_Path.c_str()).ToElement();

	//lecture du contenu des children de "IfcEntity"
	if(pElem)
		st_value = pElem->GetText();

	return res;
}


/////////////////////////////////////////////////////////////////////////////////////////////
//  1.1) ROUTINES DE SPECIFIQUES DE LECTURE (DES ATTRIBUTS) DE LA DEFINITION D'UNE ENTITE  //
/////////////////////////////////////////////////////////////////////////////////////////////

int ifcXML_File::ReadIfcDirectionVector(TiXmlElement *pElement, double Vector[3])
{
	//<IfcGeometricRepresentationContext id = "i1719">
	//	<ContextType>Model</ContextType>
	//	<CoordinateSpaceDimension>3</CoordinateSpaceDimension>
	//	<Precision>1.000000000E-5</Precision>
	//	<WorldCoordinateSystem>
	//		<IfcAxis2Placement3D xsi:nil="true" ref="i1716"/>
	//	</WorldCoordinateSystem>
	//	<TrueNorth>
	//		<IfcDirection xsi:nil="true" ref="i1717"/>
	//	</TrueNorth>
	//</IfcGeometricRepresentationContext>


	string st_Path[2] = { "","" };
	int res = 0;

	//Axe North
	st_Path[0] = "TrueNorth";
	st_Path[1] = "IfcDirection";
	TiXmlElement *lpObjectFound = nullptr;
	res = FindOneSpecificLinkedObjectFromFirstLinkPath(pElement, st_Path, lpObjectFound);

	TiXmlHandle hLocalBaseRoot3(lpObjectFound);
	TiXmlHandle hLocalBaseRoot4(hLocalBaseRoot3.FirstChild("DirectionRatios"));

	//lecture du contenu des child d'un IfcEntity
	list<string> li_messages;
	res = ReadAllValuesOfAnEntity(hLocalBaseRoot4.ToElement(), li_messages);

	// Remplissage Matrice
	list <string>::iterator it_li_messages;
	it_li_messages = li_messages.begin();
	Vector[0] = std::stod((*it_li_messages)); it_li_messages++;
	Vector[1] = std::stod((*it_li_messages)); it_li_messages++;
	if (it_li_messages == li_messages.end())
	{
		Vector[2] = std::stod("0.0");
	}// if (it_li_messages == li_messages.end())
	else
	{
		Vector[2] = std::stod((*it_li_messages)); it_li_messages++;
	}// else if (it_li_messages == li_messages.end())

	return 0;
}

int ifcXML_File::ReadIfcAxis2Placement3DMatrix(TiXmlElement *pElement, double Matrix[3][4])
{
	//<IfcAxis2Placement3D id="i1735">
	//	<Location>
	//		<IfcCartesianPoint xsi:nil="true" ref="i1733"/>
	//	</Location>
	//	<Axis>
	//		<IfcDirection xsi:nil="true" ref="i1731"/>
	//	</Axis>
	//	<RefDirection>
	//		<IfcDirection xsi:nil="true" ref="i1729"/>
	//	</RefDirection>
	//</IfcAxis2Placement3D>

	string st_Path[2] = { "","" };
	int res = 0;

	//Origin
	{
		st_Path[0] = "Location";
		st_Path[1] = "IfcCartesianPoint";
		TiXmlElement *lpObjectFound = nullptr;
		res = FindOneSpecificLinkedObjectFromFirstLinkPath(pElement, st_Path, lpObjectFound);

		TiXmlHandle hLocalBaseRoot3(lpObjectFound);
		TiXmlHandle hLocalBaseRoot4(hLocalBaseRoot3.FirstChild("Coordinates"));

		//lecture du contenu des child d'un IfcEntity liés à "IfcProject"
		list<string> li_messages;
		res = ReadAllValuesOfAnEntity(hLocalBaseRoot4.ToElement(), li_messages);

		// Remplissage Matrice
		list <string>::iterator it_li_messages;
		it_li_messages = li_messages.begin();
		Matrix[0][3] = std::stod((*it_li_messages)); it_li_messages++;
		Matrix[1][3] = std::stod((*it_li_messages)); it_li_messages++;
		Matrix[2][3] = std::stod((*it_li_messages)); it_li_messages++;
	}

	//Axe Z
	{
		st_Path[0] = "Axis";
		st_Path[1] = "IfcDirection";
		TiXmlElement *lpObjectFound = nullptr;
		res = FindOneSpecificLinkedObjectFromFirstLinkPath(pElement, st_Path, lpObjectFound);

		TiXmlHandle hLocalBaseRoot3(lpObjectFound);
		TiXmlHandle hLocalBaseRoot4(hLocalBaseRoot3.FirstChild("DirectionRatios"));

		//lecture du contenu des child d'un IfcEntity liés à "IfcProject"
		list<string> li_messages;
		res = ReadAllValuesOfAnEntity(hLocalBaseRoot4.ToElement(), li_messages);

		// Remplissage Matrice
		list <string>::iterator it_li_messages;
		it_li_messages = li_messages.begin();
		Matrix[0][2] = std::stod((*it_li_messages)); it_li_messages++;
		Matrix[1][2] = std::stod((*it_li_messages)); it_li_messages++;
		Matrix[2][2] = std::stod((*it_li_messages)); it_li_messages++;
	}

	//Axe X
	{
		st_Path[0] = "RefDirection";
		st_Path[1] = "IfcDirection";
		TiXmlElement *lpObjectFound = nullptr;
		res = FindOneSpecificLinkedObjectFromFirstLinkPath(pElement, st_Path, lpObjectFound);

		TiXmlHandle hLocalBaseRoot3(lpObjectFound);
		TiXmlHandle hLocalBaseRoot4(hLocalBaseRoot3.FirstChild("DirectionRatios"));

		//lecture du contenu des child d'un IfcEntity 
		list<string> li_messages;
		res = ReadAllValuesOfAnEntity(hLocalBaseRoot4.ToElement(), li_messages);

		// Remplissage Matrice
		list <string>::iterator it_li_messages;
		it_li_messages = li_messages.begin();
		Matrix[0][0] = std::stod((*it_li_messages)); it_li_messages++;
		Matrix[1][0] = std::stod((*it_li_messages)); it_li_messages++;
		Matrix[2][0] = std::stod((*it_li_messages)); it_li_messages++;
	}

	// The axis is the placement Z axis direction and the ref_direction is an approximation to the placement X axis direction. 
	// 1ere colonne = « RefDirection » ; 2ème colonne = « Axis » X « RefDirection » ; 3ème colonne = « Axis » 
	// Definition from IAI: If the attribute values for Axis and RefDirection are not given, 
	// the placement defaults to P[1] (x-axis) as [1.,0.,0.], P[2] (y-axis) as [0.,1.,0.] and P[3] (z-axis) as [0.,0.,1.].  

	//Axe Y
	// QUESTION: Produit vectoriel zXx ? ou xXz ?
	Matrix[0][1] = Matrix[1][2] * Matrix[2][0] - Matrix[2][2] * Matrix[1][0];
	Matrix[1][1] = Matrix[2][2] * Matrix[0][0] - Matrix[0][2] * Matrix[2][0];
	Matrix[2][1] = Matrix[0][2] * Matrix[1][0] - Matrix[1][2] * Matrix[0][0];

	//Normalisation de Axe Y: 
	// Remarque: à priori x et z sont ortho et normalisés => pas nécessaire de normaliser y?
	double db_Norm = sqrt(Matrix[0][1] * Matrix[0][1] + Matrix[1][1] * Matrix[1][1] + Matrix[2][1] * Matrix[2][1]);
	Matrix[0][1] /= db_Norm;
	Matrix[1][1] /= db_Norm;
	Matrix[2][1] /= db_Norm;

	//
	//QUESTION: Faut-il orthogonaliser l'axe X (car "ref_direction is an approximation to the placement X axis direction")?
	//

	return 0;
}

int ifcXML_File::ReadKeyWordsAndValuesOfIfcElementQuantity(TiXmlElement *pIfcEntity, Map_String_String &m_messages)
{

// <IfcQuantityLength id="i2474">
//    <Name>Length</Name>
//    <LengthValue>10.07112391</LengthValue>
// </IfcQuantityLength>
//
// OU
//
// <IfcQuantityArea id="i2478">
//    <Name>NetFootprintArea</Name>
//    <AreaValue>4.028449566</AreaValue>
// </IfcQuantityArea>
//
// OU ...
//

	int res = 0;

	//Recup de la definition geométrique (IfcQuantity) de l'entité en cours
	TiXmlElement* pIfcEntityQuant = _map_BE_Quantities[pIfcEntity];

	//Lecture des attributs de la definition
	string st_Path = "Quantities";
	list<TiXmlElement*> llpObject;
	res = FindAllLinkedObjectsFromFirstLinkPath(pIfcEntityQuant, st_Path, llpObject);

	//Boucle sur chaque attribut
	list <TiXmlElement*> ::iterator it_Elem;
	for (it_Elem = llpObject.begin(); it_Elem != llpObject.end(); it_Elem++)
	{
		// Positionnement sur le 1er child de "IfcEntity" 
		TiXmlHandle hLocalRoot((*it_Elem));
		TiXmlElement *pElem1 = hLocalRoot.FirstChild().ToElement();
		if ((*it_Elem))
		{
			TiXmlElement *pElem2 = pElem1->NextSiblingElement();

			m_messages[pElem1->GetText()] = pElem2->GetText();
			//m_messages[pElem1->Value()] = pElem2->Value();
		}// if ((*it_Elem))
	}// for (it_Elem = llpObject.begin(); it_Elem != llpObject.end(); it_Elem++)

	return res;
}


////////////////////////////////////////////////////////////////////////////////////////////
//  2.0) ROUTINES DE BASE DE RECHERCHE (DES ENTITES LIEES) DE LA DEFINITION D'UNE ENTITE  //
////////////////////////////////////////////////////////////////////////////////////////////

// Chargement en mémoire de tous les noeuds enfants de la racine => point d'entrée de toutes les entités ifc (de leur définition)
// Permet une recherche optimisée des définitions des entités à partir de leur "ref" qui se fait par leur "Id" (en index de la map) => cf. FindObjectFromRef
int ifcXML_File::LoadIfcEntities(TiXmlHandle &hroot)
{
	int res = 0;

	int iInd = 0;
	TiXmlElement* pIfcEntity = hroot.Child(iInd).ToElement();
	while (pIfcEntity)
	{
		_map_ID_Elmt[pIfcEntity->Attribute("id")] = pIfcEntity;

		iInd++;
		pIfcEntity = hroot.Child(iInd).ToElement();
	}// while (pIfcEntity)

	return res;
}

// Recherche optimisée de la definition d'une entité référencé dans une autre entité (associé avec la routine LoadIfcEntities)
int ifcXML_File::FindObjectFromRef(TiXmlElement *&RelatedElmt, TiXmlElement *&lpObject)
{
	int res = 0;

	lpObject = _map_ID_Elmt[RelatedElmt->Attribute("ref")];

	return res;
}

//Recherche d'une entité liée de type st_Path[1] sous le "lien" st_Path[0]
int ifcXML_File::FindOneSpecificLinkedObjectFromFirstLinkPath(TiXmlElement *pElement, string st_Path[2], TiXmlElement *&lpObject)
{
	// <pElement>
	//     <st_Path[0]>
	//         <st_Path[1] ref="..."> => lpObject lien vers sa def <st_Path[1] id="...">
	//     </st_Path[0]>
	// </pElement>

	int res = 0;

	TiXmlHandle hLocalBaseRoot1(pElement);
	TiXmlHandle hLocalBaseRoot2(hLocalBaseRoot1.FirstChild(st_Path[0].c_str()));

	//Lecture du seul Specific object souhaité st_Path[1]
	TiXmlElement *lpObjectToSearch1 = hLocalBaseRoot2.FirstChild(st_Path[1].c_str()).ToElement();

	res = FindObjectFromRef(lpObjectToSearch1, lpObject);

	return res;
}

//Recherche de toutes les entités liées de type st_Path[1] sous le "lien" st_Path[0]
int ifcXML_File::FindSeveralSpecificLinkedObjectsFromFirstLinkPath(TiXmlElement *pElement, string st_Path[2], list<TiXmlElement*> &llpObject)
{
	// <pElement>
	//     <st_Path[0]>
	//         <st_Path[1] ref="..."> => lpObject lien vers sa def <st_Path[1] id="...">
	//         <ifcAutreTypeEnt ref="..."> => pas recupéré dans lpObject 
	//         <st_Path[1] ref="..."> => lpObject lien vers sa def <st_Path[1] id="...">
	//     </st_Path[0]>
	// </pElement>

	int res = 0;

	TiXmlHandle hLocalBaseRoot1(pElement);
	TiXmlHandle hLocalBaseRoot2(hLocalBaseRoot1.FirstChild(st_Path[0].c_str()));

	//Lecture de tous les Specific Object du type souhaité st_Path[1]
	int int_Index = 0;
	TiXmlElement *lpObjectToSearch1 = hLocalBaseRoot2.Child(st_Path[1].c_str(), int_Index).ToElement();
	while (lpObjectToSearch1)
	{
		TiXmlElement *lpObject = nullptr;
		res = FindObjectFromRef(lpObjectToSearch1, lpObject);

		llpObject.push_back(lpObject);

		int_Index++;
		lpObjectToSearch1 = hLocalBaseRoot2.Child(st_Path[1].c_str(), int_Index).ToElement();
	}// while (lpObjectToSearch1)

	return res;
}

//Recherche de toutes les entités liées (quelque soit le type ifc) sous le "lien" st_Path[0]
int ifcXML_File::FindAllLinkedObjectsFromFirstLinkPath(TiXmlElement *pElement, string &st_Path, list<TiXmlElement*> &llpObject)
{
	// <pElement>
	//     <st_Path>
	//         <ifcEnt1 ref="..."> => lpObject lien vers sa def <ifcEnt1 id="...">
	//         <ifcEnt2 ref="..."> => lpObject lien vers sa def <ifcEnt2 id="..."> 
	//         <ifcEnt3 ref="..."> => lpObject lien vers sa def <ifcEnt3 id="...">
	//     </st_Path>
	// </pElement>

	int res = 0;

	TiXmlHandle hLocalBaseRoot1(pElement);
	TiXmlHandle hLocalBaseRoot2(hLocalBaseRoot1.FirstChild(st_Path.c_str()));

	//Lecture de tous les Specific Object [pas de type souhaité st_Path[1]]
	int int_Index = 0;
	TiXmlElement *lpObjectToSearch1 = hLocalBaseRoot2.Child(int_Index).ToElement();
	while (lpObjectToSearch1)
	{
		TiXmlElement *lpObject = nullptr;
		res = FindObjectFromRef(lpObjectToSearch1, lpObject);

		llpObject.push_back(lpObject);

		int_Index++;
		lpObjectToSearch1 = hLocalBaseRoot2.Child(int_Index).ToElement();
	}// while (lpObjectToSearch1)

	return res;
}

///////////////////////////////////////////////////////////////////////////////////////////////////
//  2.1) ROUTINES DE RECHERCHE EN LIEN UNAIRE (DES ENTITES LIEES) DE LA DEFINITION D'UNE ENTITE  //
///////////////////////////////////////////////////////////////////////////////////////////////////

int ifcXML_File::FindIfcCurveBoundedPlanePlacemcent(TiXmlElement *pElement, TiXmlElement *&lpObject)
{
	//Pour IfcConnectionSurfaceGeometry => 1 Sous-Face

	//<IfcConnectionSurfaceGeometry id="i3655">
	//  <SurfaceOnRelatingElement>
	//	  <IfcCurveBoundedPlane  ref="i3653"/>
	//  </SurfaceOnRelatingElement>
	//</IfcConnectionSurfaceGeometry>
	//
	//<IfcCurveBoundedPlane id="i3653">
	//	<BasisSurface>
	//	  <IfcPlane ref="i3636"/>
	//  </BasisSurface>
	//  <OuterBoundary>
	//	  <IfcCompositeCurve ref="i3650"/>
	//	</OuterBoundary>
	//	<InnerBoundaries ex:cType="set"/>
	//</IfcCurveBoundedPlane>
	//
	//<IfcPlane id="i3636">
	//	<Position>
	//    <IfcAxis2Placement3D xsi:nil="true" ref="i3635"/>
	//  </Position>
	//</IfcPlane>

	int res = 0;
	string st_Path[2] = { "","" };

	st_Path[0] =  "SurfaceOnRelatingElement";
	st_Path[1] =  "IfcCurveBoundedPlane";
	TiXmlElement *lpObjectFound1 = nullptr;
	res = FindOneSpecificLinkedObjectFromFirstLinkPath(pElement, st_Path, lpObjectFound1);

	st_Path[0] = "BasisSurface";
	st_Path[1] = "IfcPlane";
	TiXmlElement *lpObjectFound2 = nullptr;
	res = FindOneSpecificLinkedObjectFromFirstLinkPath(lpObjectFound1, st_Path, lpObjectFound2);

	st_Path[0] = "Position";
	st_Path[1] = "IfcAxis2Placement3D";
	res = FindOneSpecificLinkedObjectFromFirstLinkPath(lpObjectFound2, st_Path, lpObject);

	return res;
}

int ifcXML_File::FindIfcGeometricRepresentationSubContext(TiXmlElement *pElement, TiXmlElement *&lpObject)
{
	//Pour IfcProductDefinitionShape => n Faces

	//<IfcShapeRepresentation id="i3410">
	//	<ContextOfItems>
	//    <IfcGeometricRepresentationSubContext xsi:nil="true" ref="i1819"/>
	//  </ContextOfItems>
	//  <RepresentationIdentifier>Body</RepresentationIdentifier>
	//  <RepresentationType>Brep</RepresentationType>
	//  <Items ex:cType="set">
	//    <IfcFacetedBrep ex:pos="0" xsi:nil="true" ref="i3400"/>
	//  </Items>
	//</IfcShapeRepresentation>
	//
	//<IfcGeometricRepresentationSubContext id="i1819">
	//  <ContextIdentifier>Body</ContextIdentifier>
	//  <ContextType>Model</ContextType>
	//  <ParentContext>
	//    <IfcGeometricRepresentationContext xsi:nil="true" ref="i1719"/>
	//  </ParentContext>
	//  <TargetView>model_view</TargetView>
	//</IfcGeometricRepresentationSubContext>
	//
	//<IfcGeometricRepresentationContext id="i1719">
	//  <ContextType>Model</ContextType>
	//  <CoordinateSpaceDimension>3</CoordinateSpaceDimension>
	//  <Precision>1.000000000E-5</Precision>
	//  <WorldCoordinateSystem>
	//    <IfcAxis2Placement3D xsi:nil="true" ref="i1716"/>
	//  </WorldCoordinateSystem>
	//  <TrueNorth>
	//    <IfcDirection xsi:nil="true" ref="i1717"/>  => !! 2 ex:double-wrapper et non 3
	//  </TrueNorth>
	//</IfcGeometricRepresentationContext>

	int res = 0;
	string st_Path[2] = { "","" };

	//ATTENTION "ContextOfItems" peut-il avoir plusieurs IfcGeometricRepresentationSubContext?
	//        => multiplicité pas gérée par cette routine 
	st_Path[0] = "ContextOfItems";
	st_Path[1] = "IfcGeometricRepresentationSubContext";
	TiXmlElement *lpObjectFound1 = nullptr;
	res = FindOneSpecificLinkedObjectFromFirstLinkPath(pElement, st_Path, lpObjectFound1);

	st_Path[0] = "ParentContext";
	st_Path[1] = "IfcGeometricRepresentationContext";
	TiXmlElement *lpObjectFound2 = nullptr;
	res = FindOneSpecificLinkedObjectFromFirstLinkPath(lpObjectFound1, st_Path, lpObjectFound2);

	st_Path[0] = "WorldCoordinateSystem";
	st_Path[1] = "IfcAxis2Placement3D";
	res = FindOneSpecificLinkedObjectFromFirstLinkPath(lpObjectFound2, st_Path, lpObject);

	return res;
}

int ifcXML_File::FindIfcGeometricRepresentationContext(TiXmlElement *pElement, TiXmlElement *&lpObject)
{
	//<IfcProject id="i1722">
	//  <RepresentationContexts ex:cType="set">
	//    <IfcGeometricRepresentationContext ex:pos="0" xsi:nil="true" ref="i1719"/>
	//  </RepresentationContexts>
	//</IfcProject>

	int res = 0;
	string st_Path[2] = { "","" };

	//ATTENTION "RepresentationContexts" peut avoir plusieurs IfcGeometricRepresentationContext
	//        => multiplicité pas gérée par cette routine 
	//        A voir si nécessaire au niveau de ifcprojet seul usage de cette routine 
	//		    => quel rôle des IfcGeometricRepresentationContext du ifcproject, est-ce seulement de rassembler les contextes? 
	//			=> impliquerait ne pas appliquer (et de ne pas sauvegarder) matrice de position de ifcproject!!!
	// Pour les faces et sous-faces routine FindIfcGeometricRepresentationSubContext pourlaquelle il n'y a toujours qu'un seul contexte!
	st_Path[0] = "RepresentationContexts";
	st_Path[1] = "IfcGeometricRepresentationContext";
	//TiXmlElement *lpObjectFound1 = nullptr;
	res = FindOneSpecificLinkedObjectFromFirstLinkPath(pElement, st_Path, lpObject);

	return res;
}

int ifcXML_File::FindIfcAxis2Placement3D(TiXmlElement *pElement, TiXmlElement *&lpObject)
{
	//<IfcGeometricRepresentationContext id="i1719">
	//  <WorldCoordinateSystem>
	//    <IfcAxis2Placement3D xsi:nil="true" ref="i1716"/>
	//  </WorldCoordinateSystem>
	//  <TrueNorth>
	//    <IfcDirection xsi:nil="true" ref="i1717"/>
	//  </TrueNorth>
	//</IfcGeometricRepresentationContext>

	int res = 0;
	string st_Path[2] = { "","" };

	st_Path[0] = "WorldCoordinateSystem";
	st_Path[1] = "IfcAxis2Placement3D";
	res = FindOneSpecificLinkedObjectFromFirstLinkPath(pElement, st_Path, lpObject);

	return res;
}

int ifcXML_File::FindIfcLocalPlacement(TiXmlElement *pElement, TiXmlElement *&lpObject)
{
	//<IfcSite id="i1739">
	//	<ObjectPlacement>
	//		<IfcLocalPlacement xsi:nil="true" ref="i1736"/>
	//	</ObjectPlacement>
	//</IfcSite>
	//
	//<IfcLocalPlacement id="i1736">
	//	<RelativePlacement>
	//		<IfcAxis2Placement3D xsi:nil="true" ref="i1735"/>
	//	</RelativePlacement>
	//</IfcLocalPlacement>
	//
	//
	//<IfcBuilding id="i1772">
	//	<ObjectPlacement>
	//		<IfcLocalPlacement xsi:nil="true" ref="i1770"/>
	//	</ObjectPlacement>
	//</IfcBuilding>
	//
	//<IfcLocalPlacement id="i1770">
	//	<PlacementRelTo>
	//		<IfcLocalPlacement xsi:nil="true" ref="i1736"/>
	//	</PlacementRelTo>
	//	<RelativePlacement>
	//		<IfcAxis2Placement3D xsi:nil="true" ref="i1769"/>
	//	</RelativePlacement>
	//</IfcLocalPlacement>
	//
	//
	//<IfcBuildingStorey id="i1794">
	//	<ObjectPlacement>
	//		<IfcLocalPlacement xsi:nil="true" ref="i1792"/>
	//	</ObjectPlacement>
	//</IfcBuildingStorey>
	//
	//<IfcLocalPlacement id="i1792">
	//	<PlacementRelTo>
	//		<IfcLocalPlacement xsi:nil="true" ref="i1770"/>
	//	</PlacementRelTo>
	//	<RelativePlacement>
	//		<IfcAxis2Placement3D xsi:nil="true" ref="i1791"/>
	//	</RelativePlacement>
	//</IfcLocalPlacement>

	int res = 0;
	string st_Path[2] = { "","" };

	st_Path[0] = "ObjectPlacement";
	st_Path[1] = "IfcLocalPlacement";
	TiXmlElement *lpObjectFound1 = nullptr;
	res = FindOneSpecificLinkedObjectFromFirstLinkPath(pElement, st_Path, lpObjectFound1);

	st_Path[0] = "RelativePlacement";
	st_Path[1] = "IfcAxis2Placement3D";
	res = FindOneSpecificLinkedObjectFromFirstLinkPath(lpObjectFound1, st_Path, lpObject);

	return res;
}

int ifcXML_File::FindIfcShapeRepresentationBrep(TiXmlElement *pElement, TiXmlElement *&lpObject)
{
	//Pour IfcShapeRepresentation => n Faces

	//<IfcProductDefinitionShape id="i3431">
	//  <Representations ex:cType="list">
	//    <IfcShapeRepresentation ex:pos="0" xsi:nil="true" ref="i3410"/>
	//    <IfcShapeRepresentation ex:pos="1" xsi:nil="true" ref="i3428"/>
	//  </Representations>
	//</IfcProductDefinitionShape>
	//
	//<IfcShapeRepresentation id="i3428">
	//  <ContextOfItems>
	//    <IfcGeometricRepresentationSubContext xsi:nil="true" ref="i3415"/>
	//  </ContextOfItems>
	//  <RepresentationIdentifier>FootPrint</RepresentationIdentifier>
	//  <RepresentationType>GeometricCurveSet</RepresentationType>
	//  <Items ex:cType="set">
	//    <IfcGeometricCurveSet ex:pos="0" xsi:nil="true" ref="i3426"/>
	//  </Items>
	//</IfcShapeRepresentation>
	//
	//<IfcShapeRepresentation id="i3410">
	//  <ContextOfItems>
	//    <IfcGeometricRepresentationSubContext xsi:nil="true" ref="i1819"/>
	//  </ContextOfItems>
	//  <RepresentationIdentifier>Body</RepresentationIdentifier>
	//  <RepresentationType>Brep</RepresentationType>
	//  <Items ex:cType="set">
	//    <IfcFacetedBrep ex:pos="0" xsi:nil="true" ref="i3400"/>
	//  </Items>
	//</IfcShapeRepresentation>

	int res = 0;

	string st_Path = "Representations";
	list<TiXmlElement*> llpObject;
	res = FindAllLinkedObjectsFromFirstLinkPath(pElement, st_Path, llpObject);

	list <TiXmlElement*> ::iterator it_l = llpObject.begin();
	st_Path = "RepresentationType";
	while (*(it_l))
	{
		string st_Value="";
		res = ReadOneSpecificValueOfAnEntity(*(it_l), st_Path, st_Value);
		if (st_Value == string("Brep"))
		{
			lpObject = *(it_l);
			break;
		}//if (lpObjectFound && string(ch_Reptype) == string("Brep"))
		it_l++;
	}// while (*(it_l))

	return res;
}

///////////////////////////////////////////////////////////////////////////////////////////////////////
//  2.2) ROUTINES DE RECHERCHE EN LIEN MULTI-AIRE (DES ENTITES LIEES) DE LA DEFINITION D'UNE ENTITE  //
///////////////////////////////////////////////////////////////////////////////////////////////////////

int ifcXML_File::FindObjectFromRefAndPathBy3(TiXmlElement *&RelatedElmt, list<string>::iterator &lst_Path, list<string>::iterator &lst_PathEnd, list <list <list <TiXmlElement*>>> &lllpObject, list <TiXmlElement*> &lpObjectFace)
{
	int res = 0;
	TiXmlHandle hLocalBaseRoot(RelatedElmt);

	if (lst_Path != lst_PathEnd)
	{
		const char* ch_Name = (*lst_Path).c_str();
		int int_Ind = 0;
		TiXmlElement* lpObjectToSearch = hLocalBaseRoot.FirstChild(ch_Name).Child(int_Ind).ToElement();
		while (lpObjectToSearch)
		{
			TiXmlElement* lpSearchedObject = nullptr;
			if (lpObjectToSearch)
				res = FindObjectFromRef(lpObjectToSearch, lpSearchedObject);

			// Pour IfcConnectionSurfaceGeometry
			// "lll" est une liste qui dissocie les IfcPolyline par entités de type (IfcCurveBoundedPlane,...) sous SurfaceOnRelatingElement
			// "ll" est une liste qui dissocie les IfcPolyline par entités de type (IfcCompositeCurve,...) sous OuterBoundary
			// "l" est une liste d'entités (IfcPolyline,...) sous Segments>ParentCurve (cette liste rassemble la multiplicité de ces Segments>ParentCurve)
			//
			// Pour IfcShapeRepresentation
			// "lll" est une liste qui dissocie les IfcPolyLoop par entités de type (IfcFacetedBrep,...) sous Items
			// "ll" est une liste qui dissocie les IfcPolyLoop par entités de type (IfcFace,...) sous CfsFaces
			// "l" est une liste d'entités (IfcPolyLoop,...) sous Bounds>Bound (cette liste rassemble la multiplicité de ces Bounds>Bound)
			//
			// Si le mot-clé a une multiplicité [1,m] => création d'une liste
			// Si c'est le Nième mot-clé multiple [1,m] => création d'une liste à 3-N profondeur "list <list <..(3-N) fois"
			//
			//Au 1er mot clé "multiple" (N=1)  => on ajoute une liste de (3-1=2) niveaux (llxxx)
			//if (string(ch_Name) == string("CfsFaces")) // liste par CfsFace
			if (string(ch_Name) == string("Items") || string(ch_Name) == string("SurfaceOnRelatingElement")) // liste par Item, par SurfaceOnRelatingElement
			{
				//On descend au niveau N 
				// => au 1er niveau c'est la liste passée en argument (lllpObject) pas d'action

				//On ajoute la liste de niveau 3-N
				list <list <TiXmlElement*>> llNewpObject;
				lllpObject.push_back(llNewpObject);
			}
			// Au 2nd mot clé "multiple" (N=2) => on ajoute une liste de (3-2=1) niveau (lxxx)
			if (string(ch_Name) == string("CfsFaces") || string(ch_Name) == string("OuterBoundary") || string(ch_Name) == string("InnerBoundaries")) // liste par CfsFace, par OuterBoundary/InnerBoundaries
			{
				//On descend au niveau N
				list <list <list <TiXmlElement*>>> ::iterator it_lll = lllpObject.end();
				it_lll--;

				//On ajoute la liste de niveau 3-N
				list <TiXmlElement*> lNewpObject;
				(*it_lll).push_back(lNewpObject);
			}

			if (string(ch_Name) == string("CfsFaces") || string(ch_Name) == string("SurfaceOnRelatingElement")) // liste des Faces (pour CfsFaces) ou Subface (pour SurfaceOnRelatingElement)
			{
				//On ajoute la Face ou Sous-Face qui portera l'identifiant
				lpObjectFace.push_back(lpSearchedObject);
			}

			lst_Path++;
			res = FindObjectFromRefAndPathBy3(lpSearchedObject, lst_Path, lst_PathEnd, lllpObject, lpObjectFace);

			lst_Path--;
			int_Ind++;
			lpObjectToSearch = hLocalBaseRoot.FirstChild(ch_Name).Child(int_Ind).ToElement();
		}// while (lpObjectToSearch)

	}// if (lst_Path != lst_PathEnd)
	else
	{
		//if (string(ch_Name) == string("Segments") || string(ch_Name) == string("Bounds")) // liste par Bound ou Segment => on rassemble en 1 liste car carac d'1 même face!
		// Au N=3ème multiple => on ajoute une liste de (3-3=0) niveau (xxx soit l'objet final)

		//On descend au niveau N
		list <list <list <TiXmlElement*>>> ::iterator it_lll = lllpObject.end();
		it_lll--;
		list <list <TiXmlElement*>> ::iterator it_ll = (*it_lll).end();
		it_ll--;

		//On ajoute la liste de niveau 3-N (pour N=3, c'est l'objet final)
		(*it_ll).push_back(RelatedElmt);// liste de Bounds (IfcFaceOuterBound) ou Segment
	}// else if (lst_Path != lst_PathEnd)

	return res;
}

int ifcXML_File::ReadPtsDefiningPolyloopOrPolyline(list <TiXmlElement*> &lPolyloopOfOneBound_Face, list<list<double*>> &FacePtsCoord)
{
	//<IfcPolyLoop id="i3393">
	//  <Polygon ex:cType="list-unique">
	//    <IfcCartesianPoint ex:pos="0" xsi:nil="true" ref="i3367"/>
	//    <IfcCartesianPoint ex:pos="1" xsi:nil="true" ref="i3365"/>
	//    <IfcCartesianPoint ex:pos="2" xsi:nil="true" ref="i3381"/>
	//    <IfcCartesianPoint ex:pos="3" xsi:nil="true" ref="i3374"/>
	//  </Polygon>
	//</IfcPolyLoop>
	//
	//<IfcPolyline id="i3500">
	//  <Points ex:cType="list">
	//    <IfcCartesianPoint ex:pos="0" xsi:nil="true" ref="i3490"/>
	//    <IfcCartesianPoint ex:pos="1" xsi:nil="true" ref="i3492"/>
	//    <IfcCartesianPoint ex:pos="2" xsi:nil="true" ref="i3494"/>
	//    <IfcCartesianPoint ex:pos="3" xsi:nil="true" ref="i3496"/>
	//    <IfcCartesianPoint ex:pos="4" xsi:nil="true" ref="i3498"/>
	//  </Points>
	//</IfcPolyline>

	//<IfcCartesianPoint id="i3374">
	//  <Coordinates ex:cType="list">
	//    <IfcLengthMeasure ex:pos="0">9.672305351</IfcLengthMeasure>
	//    <IfcLengthMeasure ex:pos="1">6.511389214</IfcLengthMeasure>
	//    <IfcLengthMeasure ex:pos="2">2.67</IfcLengthMeasure>
	//  </Coordinates>
	//</IfcCartesianPoint>

	int res = 0;

	//
	// Boucle sur les contours
	TiXmlElement* lpSearchedObject = nullptr;
	list <TiXmlElement*> ::iterator it_PolyloopOfOneBound;
	for (it_PolyloopOfOneBound = lPolyloopOfOneBound_Face.begin(); it_PolyloopOfOneBound != lPolyloopOfOneBound_Face.end(); it_PolyloopOfOneBound++)
	{
		list<double*> ContoursPtsCoord;
		TiXmlHandle hLocalBaseRoot((*it_PolyloopOfOneBound));
		int int_ind = 0;
		TiXmlElement* pPointofPolyloop = hLocalBaseRoot.FirstChild().Child(int_ind).ToElement();
		while (pPointofPolyloop)
		{
			if (pPointofPolyloop)
				res = FindObjectFromRef(pPointofPolyloop, lpSearchedObject);
			//
			TiXmlHandle hLocalBaseRoot1(lpSearchedObject);
			for (int i = 0; i < 3; i++)
			{
				TiXmlElement* pCoordPointofPolyloop = hLocalBaseRoot1.FirstChild().Child(i).ToElement();
				//Lire IfcLengthMeasure;
				double *coord = nullptr;
				if (pCoordPointofPolyloop)
					coord = new double(stod(pCoordPointofPolyloop->GetText()));
				else
					coord = new double(0.0);
				ContoursPtsCoord.push_back(coord);
			}// for (int i = 0; i < 3; i++)
			 //
			int_ind++;
			pPointofPolyloop = hLocalBaseRoot.FirstChild().Child(int_ind).ToElement();
		}// while (pPointofPolyloop)

		FacePtsCoord.push_back(ContoursPtsCoord);

	}// for (it_PolyloopOfOneBound = (*it_BoundsOfOneCFsFace).begin(); it_PolyloopOfOneBound != (*it_BoundsOfOneCFsFace).end(); it_PolyloopOfOneBound++)

	return res;
}

int ifcXML_File::FindRepresentationInSpace(TiXmlElement* &pElemSpace, list<TiXmlElement*> *lpRelatedObjects)
{
	//<IfcSpace id="i3435">
	//  <Representation>
	//    <IfcProductDefinitionShape xsi:nil="true" ref="i3431"/>
	//  </Representation>
	//</IfcSpace>

	int res = 0;
	string st_Path[2] = { "","" };

	//Retrouver l'IfcProductDefinitionShape
	st_Path[0] = "Representation";
	st_Path[1] = "IfcProductDefinitionShape";
	TiXmlElement *lpObjectFound = nullptr;
	res = FindOneSpecificLinkedObjectFromFirstLinkPath(pElemSpace, st_Path, lpObjectFound);

	if (lpRelatedObjects)
		lpRelatedObjects->push_back(lpObjectFound);

	return res;
}

int ifcXML_File::FindRelatedObjectsInRelAggregatesFromRelatingObject(TiXmlElement *&lpRelatingObj, list<TiXmlElement*> *lpRelatedObjects)
{
	// => ATTENTION La multiplicite sous pKeyword2 n'est pas géré
	//
	// <pKeyword1>
	//     <pKeyword2>
	//         <lpRelatingObj ref="..."> => ATTENTION: lpRelatingObj est en fait un lien vers def <ifcEnt1 id="..."> => l'entité est retrouvé si valeur de ref = valeur de id 
	//     </pKeyword2>
	//     <pKeyword3>
	//         <ifcEnt1 ref="..."> => lpRelatedObjects lien vers sa def <ifcEnt1 id="...">
	//         <ifcEnt2 ref="..."> => lpRelatedObjects lien vers sa def <ifcEnt2 id="..."> 
	//         <ifcEnt3 ref="..."> => lpRelatedObjects lien vers sa def <ifcEnt3 id="...">
	//     </pKeyword3>
	// </pKeyword1>

	int res = 0;

	// Recherche de toutes les ifcentity de type pKeyword1 sur lesquelles se fait le scan
	const char* pKeyword1 = "IfcRelAggregates";

	// Parmi les ifcentity de type pKeyword1 on ne s'interesse qu'à ceux qui ont l'entité lpRelatingObj en attribut pKeyword2 
	const char* pKeyword2 = "RelatingObject";

	// Pour ces ifcentities de type pKeyword1 liées à lpRelatingObj on récupère les entités sous l'attribut pKeyword3 dans lpRelatedObjects
	const char* pKeyword3 = "RelatedObjects";

	res = FindObjectsInRelFromRelatingEnt(lpRelatingObj, lpRelatedObjects, pKeyword1, pKeyword2, pKeyword3);
	return res;
}

int ifcXML_File::FindRelatedBuildingElementAndConnectionGeometryInRelSpaceBoundaryFromRelatingSpace(TiXmlElement *&lpRelatingObj, list<TiXmlElement*> *lpRelatedObjects, list<TiXmlElement*> *lpsecondRelatedObjects)
{
	// => ATTENTION La multiplicite sous pKeyword2 n'est pas géré
	//
	// <pKeyword1>
	//     <pKeyword2>
	//         <lpRelatingObj ref="..."> => ATTENTION: lpRelatingObj est en fait un lien vers def <ifcEnt1 id="..."> => l'entité est retrouvé si valeur de ref = valeur de id 
	//     </pKeyword2>
	//     <pKeyword3>
	//         <ifcEnt1 ref="..."> => lpRelatedObjects lien vers sa def <ifcEnt1 id="...">
	//         <ifcEnt2 ref="..."> => lpRelatedObjects lien vers sa def <ifcEnt2 id="..."> 
	//         <ifcEnt3 ref="..."> => lpRelatedObjects lien vers sa def <ifcEnt3 id="...">
	//     </pKeyword3>
	//     <pKeyword4>
	//         <ifcEnt_1 ref="..."> => lpsecondRelatedObjects lien vers sa def <ifcEnt_1 id="...">
	//         <ifcEnt_2 ref="..."> => lpsecondRelatedObjects lien vers sa def <ifcEnt_2 id="..."> 
	//         <ifcEnt_3 ref="..."> => lpsecondRelatedObjects lien vers sa def <ifcEnt_3 id="...">
	//     </pKeyword4>
	// </pKeyword1>

	int res = 0;

	// Recherche de toutes les ifcentity de type pKeyword1 sur lesquelles se fait le scan
	const char* pKeyword1 = "IfcRelSpaceBoundary";

	// Parmi les ifcentity de type pKeyword1 on ne s'interesse qu'à ceux qui ont l'entité lpRelatingObj en attribut pKeyword2 
	const char* pKeyword2 = "RelatingSpace";

	// Pour ces ifcentities de type pKeyword1 liées à lpRelatingObj on récupère les entités sous l'attribut pKeyword3 dans lpRelatedObjects
	const char* pKeyword3 = "RelatedBuildingElement";

	// Parallèlement, pour ces ifcentities de type pKeyword1 liées à lpRelatingObj on récupère les entités sous l'attribut pKeyword4 dans lpsecondRelatedObjects
	const char* pKeyword4 = "ConnectionGeometry";

	res = FindObjectsInRelFromRelatingEnt(lpRelatingObj, lpRelatedObjects, pKeyword1, pKeyword2, pKeyword3, pKeyword4, lpsecondRelatedObjects);
	return res;
}

int ifcXML_File::FindObjectsInRelFromRelatingEnt(TiXmlElement *&lpRelatingObj, list<TiXmlElement*> *lpRelatedObjects, const char* pKeyword1, const char* pKeyword2, const char* pKeyword3, const char* pKeyword4, list<TiXmlElement*> *lpsecondRelatedObjects)
{
	// => ATTENTION La multiplicite sous pKeyword2 n'est pas géré
	//
	// <pKeyword1>
	//     <pKeyword2>
	//         <lpRelatingObj ref="..."> => ATTENTION: lpRelatingObj est en fait un lien vers def <ifcEnt1 id="..."> => l'entité est retrouvé si valeur de ref = valeur de id 
	//     </pKeyword2>
	//     <pKeyword3>
	//         <ifcEnt1 ref="..."> => lpRelatedObjects lien vers sa def <ifcEnt1 id="...">
	//         <ifcEnt2 ref="..."> => lpRelatedObjects lien vers sa def <ifcEnt2 id="..."> 
	//         <ifcEnt3 ref="..."> => lpRelatedObjects lien vers sa def <ifcEnt3 id="...">
	//     </pKeyword3>
	// </pKeyword1>
	//
    //  OU [les arguments pKeyword4 et lpsecondRelatedObjects sont optionnels]
	//
	// <pKeyword1>
	//     <pKeyword2>
	//         <lpRelatingObj ref="..."> => ATTENTION: lpRelatingObj est en fait un lien vers def <ifcEnt1 id="..."> => l'entité est retrouvé si valeur de ref = valeur de id 
	//     </pKeyword2>
	//     <pKeyword3>
	//         <ifcEnt1 ref="..."> => lpRelatedObjects lien vers sa def <ifcEnt1 id="...">
	//         <ifcEnt2 ref="..."> => lpRelatedObjects lien vers sa def <ifcEnt2 id="..."> 
	//         <ifcEnt3 ref="..."> => lpRelatedObjects lien vers sa def <ifcEnt3 id="...">
	//     </pKeyword3>
	//     <pKeyword4>
	//         <ifcEnt_1 ref="..."> => lpsecondRelatedObjects lien vers sa def <ifcEnt_1 id="...">
	//         <ifcEnt_2 ref="..."> => lpsecondRelatedObjects lien vers sa def <ifcEnt_2 id="..."> 
	//         <ifcEnt_3 ref="..."> => lpsecondRelatedObjects lien vers sa def <ifcEnt_3 id="...">
	//     </pKeyword4>
	// </pKeyword1>

	int res = 0;
	TiXmlHandle hLocalBaseRoot(_hRoot);

	std::string str_SearchedID(lpRelatingObj->Attribute("id"));

	int int_nbcount = 0;
	bool boo_IsItTheEnd = false;
	while (!boo_IsItTheEnd)
	{
		// Pour une recherche à partir du nom d'entité, 
		// à priori le plus optimisé est d'utiliser les routines de base du parser: "TiXmlHandle.Child(pKeyword1,..)"
		TiXmlHandle hLocalVariableRoot1(hLocalBaseRoot.Child(pKeyword1, int_nbcount));//"IfcRelAggregates", "IfcRelSpaceBoundary"
		TiXmlHandle hLocalVariableRoot2(hLocalVariableRoot1.FirstChild(pKeyword2));//"RelatingObject", "RelatingSpace"
		TiXmlHandle hLocalVariableRoot3(hLocalVariableRoot2.FirstChild(/*"IfcProject"*/));
		if (nullptr != hLocalVariableRoot3.ToElement())
		{
			//DEB: A REVOIR en terme de perfo si judicieux d'utiliser le _map_ID_Elmt plutôt que 
			// comparaison de string  std::string str_SearchedID(lpRelatingObj->Attribute("id")) en dehors boucle puis if (str_SearchedID == std::string(ch_ID))
			//FIN:
			//if (_map_ID_Elmt[lpRelatingObj->Attribute("id")]== _map_ID_Elmt[hLocalVariableRoot3.ToElement()->Attribute("ref")])
			if (str_SearchedID == std::string(hLocalVariableRoot3.ToElement()->Attribute("ref")))
			{
				if (pKeyword3)
				{
					//Recup des entités sous pKeyword3
					TiXmlHandle hLocalVariableRoot4(hLocalVariableRoot1.FirstChild(pKeyword3));//"RelatedObjects", "RelatedBuildingElement"
					int int_Index = 0;
					TiXmlElement *RelatedElmt = hLocalVariableRoot4.Child(int_Index).ToElement();
					while (RelatedElmt)
					{
						// Recuperation de la def de l'élément dont la ref est RelatedElmt
						TiXmlElement *RelatedElmt2 = nullptr;
						res = FindObjectFromRef(RelatedElmt, RelatedElmt2);

						if (lpRelatedObjects)
							lpRelatedObjects->push_back(RelatedElmt2);

						int_Index++;
						RelatedElmt = hLocalVariableRoot4.Child(int_Index).ToElement();
					}// while (RelatedElmt)
				}// if(pKeyword3)

				if (pKeyword4)
				{
					//Recup des entités sous pKeyword4
					//A REVOIR... Attention à voir comment ca marche s il y a plusieurs "RelatingObject", "RelatingSpace" pour généraliser la routine
					TiXmlHandle hLocalVariableRoot4(hLocalVariableRoot1.FirstChild(pKeyword4));//"ConnectionGeometry"
					int int_Index = 0;
					TiXmlElement *RelatedElmt = hLocalVariableRoot4.Child(int_Index).ToElement();
					while (RelatedElmt)
					{
						// Recuperation de la def de l'élément dont la ref est RelatedElmt
						TiXmlElement *RelatedElmt2 = nullptr;
						res = FindObjectFromRef(RelatedElmt, RelatedElmt2);

						if (lpsecondRelatedObjects)
							lpsecondRelatedObjects->push_back(RelatedElmt2);

						int_Index++;
						RelatedElmt = hLocalVariableRoot4.Child(int_Index).ToElement();
					}// while (RelatedElmt)
				}// if(pKeyword4)
			}// if (nullptr != ch_ID &&  str_SearchedID == std::string(ch_ID))

			int_nbcount++;
		}// if (nullptr != hLocalVariableRoot3.ToElement())
		else
			boo_IsItTheEnd = true;
	}//while (!boo_IsItFound)

	return res;
}

////////////////////////////////////////////////////////////////////////////////////////////
//  3.0) ROUTINES DE BASE POUR UN SCAN GLOBAL (SANS RECHERCHE D'UNE ENTITE SPECIFIQUE)    //
////////////////////////////////////////////////////////////////////////////////////////////


int ifcXML_File::ScanAssociateRelatedAndRelatingEnt(const char* pKeyword1, const char* pKeyword2, const char* pKeyword3, const char* pKeyword4)
{
	// => ATTENTION La multiplicite sous pKeyword2 est gérée, mais suppose l'unicité sous pKeyword3
	//
	// <pKeyword1> => IfcRelDefinesByProperties
	//     <pKeyword2> => RelatedObjects
	//         <lpRelatingObj ref="..."> => ATTENTION: lpRelatingObj est en fait un lien vers def <ifcEnt1 id="..."> => l'entité est retrouvé si valeur de ref = valeur de id 
	//         <lpRelatingObj ref="..."> => ATTENTION: lpRelatingObj est en fait un lien vers def <ifcEnt2 id="..."> => l'entité est retrouvé si valeur de ref = valeur de id 
	//     </pKeyword2>
	//     <pKeyword3> => RelatingPropertyDefinition ATTENTION multiplicité pas gérée
	//         <ifcEnt1 ref="..."> => lpRelatedObjects lien vers sa def <ifcEnt1 id="..."> => IfcElementQuantity
	//     </pKeyword3>
	// </pKeyword1>
	//

	int res = 0;
	TiXmlHandle hLocalBaseRoot(_hRoot);

	//std::string str_SearchedID(lpRelatingObj->Attribute("id"));

	int int_nbcount = 0;
	TiXmlHandle hNullHandle=nullptr;
	TiXmlHandle hLocalVariableRoot1(hLocalBaseRoot.Child(pKeyword1, int_nbcount));//"IfcRelDefinesByProperties"
																				  //bool boo_IsItTheEnd = false;
	//while (!boo_IsItTheEnd)
	while (hLocalVariableRoot1.ToNode() != nullptr)
	{
		// Pour une recherche à partir du nom d'entité, 
		// à priori le plus optimisé est d'utiliser les routines de base du parser: "TiXmlHandle.Child(pKeyword1,..)"
		TiXmlHandle hLocalVariableRoot2(hLocalVariableRoot1.FirstChild(pKeyword2));//"RelatingPropertyDefinition"
		TiXmlElement *RelatingElmt = hLocalVariableRoot2.Child(0).ToElement();
		if (nullptr != RelatingElmt)
		{
			if (string(RelatingElmt->Value()) == string(pKeyword3)) //"IfcElementQuantity"
			{
				// Recuperation de la def de l'élément dont la ref est RelatingElmt
				TiXmlElement *RelatingElmt2 = nullptr;
				res = FindObjectFromRef(RelatingElmt, RelatingElmt2);

				TiXmlHandle hLocalVariableRoot3(hLocalVariableRoot1.FirstChild(pKeyword4));//"RelatedObjects"
				int int_Index = 0;
				TiXmlElement *RelatedElmt = hLocalVariableRoot3.Child(int_Index).ToElement();
				while (RelatedElmt)
				{
					// Recuperation de la def de l'élément dont la ref est RelatedElmt
					TiXmlElement *RelatedElmt2 = nullptr;
					res = FindObjectFromRef(RelatedElmt, RelatedElmt2);

					_map_BE_Quantities[RelatedElmt2] = RelatingElmt2;// pIfcEntity->Attribute("id");

					int_Index++;
					RelatedElmt = hLocalVariableRoot3.Child(int_Index).ToElement();
				}// while (RelatedElmt)
			}// if (hLocalVariableRoot3.ToElement()->Value() == pKeyword3)
		}// if (nullptr != RelatingElmt)

		int_nbcount++;
		hLocalVariableRoot1=hLocalBaseRoot.Child(pKeyword1, int_nbcount);//"IfcRelDefinesByProperties"
	}//while (hLocalVariableRoot1)
	//	}// if (nullptr != hLocalVariableRoot3.ToElement())
	//	else
	//		boo_IsItTheEnd = true;
	//}//while (!boo_IsItFound)

	return res;
}

int ifcXML_File::ScanIfcRelDefinesByPropertiesForQuantities()
{

	//<IfcRelDefinesByProperties id="i2485">
	//	<GlobalId>1JljiXweR195uhzlxzvQeN</GlobalId>
	//	<OwnerHistory>
	//		<IfcOwnerHistory xsi:nil="true" ref="i1666"/>
	//	</OwnerHistory>
	//	<RelatedObjects ex:cType="set">
	//		<IfcWallStandardCase ex:pos="0" xsi:nil="true" ref="i2342"/>
	//	</RelatedObjects>
	//	<RelatingPropertyDefinition>
	//		<IfcElementQuantity xsi:nil="true" ref="i2483"/>
	//	</RelatingPropertyDefinition>
	//</IfcRelDefinesByProperties>
	//
	// OU
	//
	//<IfcRelDefinesByProperties id="i2552">
	//	<GlobalId>1ctrdyLJ_$SL9WtGdfK2n1</GlobalId>
	//	<OwnerHistory>
	//		<IfcOwnerHistory xsi:nil="true" ref="i1666"/>
	//	</OwnerHistory>
	//	<RelatedObjects ex:cType="set">
	//		<IfcWallStandardCase ex:pos="0" xsi:nil="true" ref="i2533"/>
	//	</RelatedObjects>
	//	<RelatingPropertyDefinition>
	//		<IfcPropertySet xsi:nil="true" ref="i2550"/>
	//	</RelatingPropertyDefinition>
	//</IfcRelDefinesByProperties>

	int res = 0;

	// Recherche de toutes les ifcentity de type pKeyword1 sur lesquelles se fait le scan
	const char* pKeyword1 = "IfcRelDefinesByProperties";

	// Parmi les ifcentity de type pKeyword1 on ne s'interesse qu'à ceux qui ont l'entité "RelatingPropertyDefinition" en attribut pKeyword2 
	// et comme sous-type "IfcElementQuantity" en attribut pKeyword3
	const char* pKeyword2 = "RelatingPropertyDefinition";
	const char* pKeyword3 = "IfcElementQuantity";

	// Pour ces ifcentities de type pKeyword1 liées à "RelatingPropertyDefinition"->"IfcElementQuantity" on récupère les entités sous l'attribut pKeyword4 dans "RelatedObjects"
	const char* pKeyword4 = "RelatedObjects";

	// Chargement en mémoire de toutes les associations => _map_BE_Quantities[TiXmlElement "BuildingElement"]=TiXmlElement "IfcElementQuantity"
	// Permet une recherche optimisée des définitions des entités à partir de leur "ref" qui se fait par leur "Id" (en index de la map) => cf. FindObjectFromRef
	res = ScanAssociateRelatedAndRelatingEnt(pKeyword1, pKeyword2, pKeyword3, pKeyword4);

	return res;
}

