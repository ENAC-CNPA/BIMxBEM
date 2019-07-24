template <class Type_Elmt_Of_Source, class Type_Source>
int ifc_Tree::BuildTreeFromRoot(Type_Elmt_Of_Source *&pElem/*, STRUCT_IFCENTITY *&st_IfcTree*/, Type_Source * const& ifcXmlFile)
{
	int res = 0;

	//lecture des Id et type de "IfcProject"
	Map_String_String m_messages;
	res = ifcXmlFile->ReadIdAndTypeOfAnEntity(pElem, m_messages);
	if (res) return res;

	//Recup du positionnement relatif
	Type_Elmt_Of_Source *lpObjectGeomrepCtx = nullptr;
	res = ifcXmlFile->FindIfcGeometricRepresentationContext(pElem, lpObjectGeomrepCtx);
	if (res) return res;

	//Recup du positionnement relatif
	Type_Elmt_Of_Source *lpObjectPlac = nullptr;
	res = ifcXmlFile->FindIfcAxis2Placement3D(lpObjectGeomrepCtx, lpObjectPlac);
	if (res) return res;

	//Recup de la matrice de position
	double db_LocalMat[3][4];
	res = ifcXmlFile->ReadIfcAxis2Placement3DMatrix(lpObjectPlac, db_LocalMat);
	if (res) return res;

	//Recup du vecteur Nord géographique
	double db_GeoNorth[3];
	res = ifcXmlFile->ReadIfcDirectionVector(lpObjectGeomrepCtx, db_GeoNorth);
	if (res) return res;

	//Création et Remplissage de la structure de "IfcProject"
	_st_IfcTree = new STRUCT_IFCENTITY();
	FillAttributeOf_STRUCT_IFCENTITY(_st_IfcTree, m_messages, db_LocalMat);

	//On met le Nord Géographique dans l'attribut "Centroid" de l'ifcProject 
	FillCentroidOf_STRUCT_IFCENTITY(_st_IfcTree, db_GeoNorth);

	//Recupération chainée des entités successives de "IfcProject"
	res = BuildTreeFrom(pElem, ifcXmlFile, _st_IfcTree);
	if (res) return res;

	return res;
}

template <class Type_Elmt_Of_Source, class Type_Source>
int ifc_Tree::BuildTreeFromRelAggregates(list<Type_Elmt_Of_Source*> &lpRelatedObjects, Type_Source * const& ifcXmlFile, STRUCT_IFCENTITY *st_IfcBelongTo)
{
	int res = 0;

	//Boucle sur les RelatedObjects de IfcRelAggregates en cours
	list <Type_Elmt_Of_Source*> ::iterator it_Elem;
	for (it_Elem = lpRelatedObjects.begin(); it_Elem != lpRelatedObjects.end(); it_Elem++)
	{
		//lecture du contenu des child d'un IfcEntity liés à "IfcProject"
		Map_String_String map_messages;
		res = ifcXmlFile->ReadIdAndTypeOfAnEntity(*it_Elem, map_messages);
		if (res) return res;

		//Recup du positionnement relatif
		Type_Elmt_Of_Source *lpObjectPlac = nullptr;
		res = ifcXmlFile->FindIfcLocalPlacement(*it_Elem, lpObjectPlac);
		if (res) return res;

		//Recup de la matrice de position
		double db_LocalMat[3][4];
		res = ifcXmlFile->ReadIfcAxis2Placement3DMatrix(lpObjectPlac, db_LocalMat);
		if (res) return res;

		////Recup du PredefinedType (soit sous ifcEntity soit sous ifcEntityType via IfcRelDefinesByType de l'ifcEntity)
		//res = ifcXmlFile->ReadPredefinedTypeOfAnEntity(*it_Elem, map_messages);
		//if (res) return res;

		//Création et Remplissage de la structure de "IfcEntity"
		STRUCT_IFCENTITY * st_IfcContain = new STRUCT_IFCENTITY;
		FillAttributeOf_STRUCT_IFCENTITY(st_IfcContain, map_messages, db_LocalMat, &(*st_IfcBelongTo));

		//Appel Récursif 
		res = BuildTreeFrom(*it_Elem, ifcXmlFile, st_IfcContain);
		if (res) return res;
	}// for (it_Elem = lpRelatedObjects.begin(); it_Elem != lpRelatedObjects.end(); it_Elem++)

	return res;
}

template <class Type_Elmt_Of_Source, class Type_Source>
int ifc_Tree::BuildTreeFromShapeOfSpace(list<Type_Elmt_Of_Source*> &lpShape, Type_Source * const& ifcXmlFile, STRUCT_IFCENTITY *st_IfcBelongTo)
{
	int res = 0;

	//Boucle sur les IfcProductDefinitionShape de IfcSpace en cours
	list <Type_Elmt_Of_Source*> ::iterator it_ElemShape;
	for (it_ElemShape = lpShape.begin(); it_ElemShape != lpShape.end(); it_ElemShape++)
	{
		//lecture du contenu des child d'un IfcEntity liés à "IfcProject"
		Map_String_String map_messages;
		res = ifcXmlFile->ReadIdAndTypeOfAnEntity(*it_ElemShape, map_messages);
		if (res) return res;

		// !!!! IfcProductDefinitionShape n'a pas de LocalPlacement !!!!

		//Création et Remplissage de la structure de "IfcEntity"
		STRUCT_IFCENTITY * st_IfcContainRep = new STRUCT_IFCENTITY;
		FillAttributeOf_STRUCT_IFCENTITY(st_IfcContainRep, map_messages, nullptr, &(*st_IfcBelongTo));

		//Appel Récursif 
		//IfcConnectionSurfaceGeometry<SurfaceOnRelatingElement<IfcCurveBoundedPlane
		//IfcCurveBoundedPlane<BasisSurface<IfcPlane...
		res = BuildExplicitDataTreeFrom(*it_ElemShape, ifcXmlFile, st_IfcContainRep);
		if (res) return res;
	}// for (it_ElemShape = lpRelatedObjects.begin(); it_ElemShape != lpRelatedObjects.end(); it_ElemShape++)

	return res;
}

template <class Type_Elmt_Of_Source, class Type_Source>
int ifc_Tree::BuildTreeFromRelSpaceBoundary(list<Type_Elmt_Of_Source*> &lpRelatedBuildingElement, list<Type_Elmt_Of_Source*> &lpConnectionSurfaceGeometry, Type_Source * const& ifcXmlFile, STRUCT_IFCENTITY *st_IfcBelongTo)
{
	int res = 0;

	//Boucle à la fois sur les éléments de construction et sur les ConnectionSurfaceGeometry (correspondance unaire 1 <-> 1)
	list <Type_Elmt_Of_Source*> ::iterator it_ElemBE;
	list <Type_Elmt_Of_Source*> ::iterator it_ElemCSG;
	for (it_ElemBE = lpRelatedBuildingElement.begin(), it_ElemCSG = lpConnectionSurfaceGeometry.begin(); it_ElemBE != lpRelatedBuildingElement.end() && it_ElemCSG != lpConnectionSurfaceGeometry.end(); it_ElemBE++, it_ElemCSG++)
	{
		//lecture du contenu des Buildingelements de "IfcSpace"
		Map_String_String map_messages;
		res = ifcXmlFile->ReadIdAndTypeOfAnEntity(*it_ElemBE, map_messages);
		if (res) return res;

		//Création (ou recuperation) et Remplissage de la structure du Building Element "IfcWall..."
		STRUCT_IFCENTITY * st_IfcContainBE = nullptr;
		if (_map_ID_IfcEnt[map_messages["Id"]])
		{
			st_IfcContainBE = _map_ID_IfcEnt[map_messages["Id"]];
			FillAttributeOfExisting_STRUCT_IFCENTITY(st_IfcContainBE, map_messages, nullptr, &(*st_IfcBelongTo));
		}// if (_map_ID_IfcEnt[map_messages["Id"])
		else
		{
			st_IfcContainBE = new STRUCT_IFCENTITY;
			_map_ID_IfcEnt[map_messages["Id"]] = st_IfcContainBE;
			FillAttributeOf_STRUCT_IFCENTITY(st_IfcContainBE, map_messages, nullptr, &(*st_IfcBelongTo));

			//lecture du Quantities des Buildingelements de "IfcSpace"
			map_messages.clear();
			res = ifcXmlFile->ReadKeyWordsAndValuesOfIfcElementQuantity(*it_ElemBE, map_messages);
			if (res) return res;
			FillQuantitiesAttributeOf_STRUCT_IFCENTITY(st_IfcContainBE, map_messages);

			//Fillattribute.... A FAIRE
		}// else if (_map_ID_IfcEnt[map_messages["Id"])

		//lecture du contenu des ConnectionSurfaceGeometry (sous-Faces) de "IfcSpace"
		map_messages.clear();
		res = ifcXmlFile->ReadIdAndTypeOfAnEntity(*it_ElemCSG, map_messages);
		if (res) return res;

		//Création et Remplissage de la structure de "IfcConnectionSurfaceGeometry"
		STRUCT_IFCENTITY * st_IfcContainCSG = new STRUCT_IFCENTITY;
		FillAttributeOf_STRUCT_IFCENTITY(st_IfcContainCSG, map_messages, nullptr, &(*st_IfcBelongTo), &(*st_IfcContainBE));

		//Appel Récursif 
		//IfcConnectionSurfaceGeometry<SurfaceOnRelatingElement<IfcCurveBoundedPlane
		//IfcCurveBoundedPlane<BasisSurface<IfcPlane...
		res = BuildExplicitDataTreeFrom(*it_ElemCSG, ifcXmlFile, st_IfcContainCSG);
		if (res) return res;
	}// for (int int_Index = 0; ppRelatedObjects[int_Index]; int_Index++)

	return res;
}

template <class Type_Elmt_Of_Source, class Type_Source>
int ifc_Tree::BuildExplicitDataTreeFromIfcConnectionSurfaceGeometry(Type_Elmt_Of_Source* pElem, Type_Source * const& ifcXmlFile, STRUCT_IFCENTITY *st_IfcBelongTo)
{
	//Pour IfcConnectionSurfaceGeometry => 1 Sous-Face

	//<IfcConnectionSurfaceGeometry id="i3655">
	//  <SurfaceOnRelatingElement>
	//	  <IfcCurveBoundedPlane  ref="i3653"/>
	//  </SurfaceOnRelatingElement>
	//</IfcConnectionSurfaceGeometry>
	//
	//<IfcCurveBoundedPlane id="i3653"> => a mettre dans identifiant sous-face
	//	<BasisSurface>
	//	  <IfcPlane ref="i3636"/>
	//  </BasisSurface>
	//  <OuterBoundary>
	//	  <IfcCompositeCurve ref="i3650"/>
	//	</OuterBoundary>
	//	<InnerBoundaries ex:cType="set"/>
	//</IfcCurveBoundedPlane>
	//
	////// 1)/2) => 1=Plan de ref [2=Sous-Surf dans le plan de ref (=> chgmt ref)]
	//
	//<IfcPlane id="i3636">
	//	<Position>
	//    <IfcAxis2Placement3D xsi:nil="true" ref="i3635"/>
	//  </Position>
	//</IfcPlane>
	//
	//<IfcAxis2Placement3D id="i3635">
	//  <Location>
	//    <IfcCartesianPoint xsi:nil="true" ref="i3633"/>
	//  </Location>
	//  <Axis>
	//    <IfcDirection xsi:nil="true" ref="i3631"/>
	//  </Axis>
	//  <RefDirection>
	//    <IfcDirection xsi:nil="true" ref="i3629"/>
	//  </RefDirection>
	//</IfcAxis2Placement3D>
	//
	//<IfcDirection id="i3631">
	//  <DirectionRatios ex:cType="list">
	//	  <ex:double-wrapper pos="0">0.9999824492</ex:double-wrapper>
	//    <ex:double-wrapper pos="1">0.005924630765</ex:double-wrapper>
	//    <ex:double-wrapper pos="2">0.</ex:double-wrapper>
	//  </DirectionRatios>
	//</IfcDirection>
	//
	////// 2)/2) => 2=Sous-Surf dans le plan de ref (=> chgmt ref) [1=Plan de ref]
	//
	//<IfcCompositeCurve id="i3650">
	//	<Segments ex:cType="list">
	//	  <IfcCompositeCurveSegment ex:pos="0" xsi:nil="true" ref="i3649"/>
	//	</Segments>
	//	<SelfIntersect>false</SelfIntersect>
	//</IfcCompositeCurve>
	//
	//<IfcCompositeCurveSegment id="i3649">
	//	<Transition>continuous</Transition>
	//  <SameSense>false</SameSense>
	//  <ParentCurve>
	//    <IfcPolyline xsi:nil="true" ref="i3647"/>
	//  </ParentCurve>
	//</IfcCompositeCurveSegment>
	//
	//<IfcPolyline id="i3647">
	//	<Points ex:cType="list">
	//    <IfcCartesianPoint ex:pos="0" xsi:nil="true" ref="i3637"/>
	//    <IfcCartesianPoint ex:pos="1" xsi:nil="true" ref="i3639"/>
	//    <IfcCartesianPoint ex:pos="2" xsi:nil="true" ref="i3641"/>
	//    <IfcCartesianPoint ex:pos="3" xsi:nil="true" ref="i3643"/>
	//    <IfcCartesianPoint ex:pos="4" xsi:nil="true" ref="i3645"/>
	//  </Points>
	//</IfcPolyline>
	//
	//<IfcCartesianPoint id="i3645">
	//	<Coordinates ex:cType="list">
	//    <IfcLengthMeasure ex:pos="0">0.</IfcLengthMeasure>
	//    <IfcLengthMeasure ex:pos="1">6.511503496</IfcLengthMeasure>
	//    <IfcLengthMeasure ex:pos="2">0.</IfcLengthMeasure>
	//  </Coordinates>
	//</IfcCartesianPoint>
	//

	int res = 0;

	//Recup de repere local P/R reprere global
	Type_Elmt_Of_Source *lpObjectPlac = nullptr;
	res = ifcXmlFile->FindIfcCurveBoundedPlanePlacemcent(pElem, lpObjectPlac);
	if (res) return res;

	double db_LocalMat[3][4];
	res = ifcXmlFile->ReadIfcAxis2Placement3DMatrix(lpObjectPlac, db_LocalMat);
	if (res) return res;

	FillRelativePlacementOf_STRUCT_IFCENTITY(st_IfcBelongTo, db_LocalMat);

	//Recup des points P/R reprere local
	list<string> lst_Path_For_SubFace;
	lst_Path_For_SubFace.push_back("SurfaceOnRelatingElement");// [1..1]  1 Face => gérer un 1er niveau de listes 
	lst_Path_For_SubFace.push_back("OuterBoundary");//[1..n] M contours => gerer un 2ème niveau de listes => 1er contour externe ensuite internes ("InnerBoundaries"? => utilité en BEM?? => ignorées pour le moment)
	lst_Path_For_SubFace.push_back("Segments"); //[1..n] 1 seul contour (externe) mais contenant plusieurs segments => dans même liste??
	lst_Path_For_SubFace.push_back("ParentCurve");
	list <string>::iterator it_ElemForPath_SubFace;
	it_ElemForPath_SubFace = lst_Path_For_SubFace.begin();

	//
	// "lll" est une liste qui dissocie les IfcPolyline par entités de type (IfcCurveBoundedPlane,...) sous SurfaceOnRelatingElement
	// "ll" est une liste qui dissocie les IfcPolyline par entités de type (IfcCompositeCurve,...) sous OuterBoundary
	// "l" est une liste d'entités (IfcPolyline,...) sous Segments>ParentCurve (cette liste rassemble la multiplicité de ces Segments>ParentCurve)
	list <Type_Elmt_Of_Source*> lpObjectSubFace;
	list <list <list <Type_Elmt_Of_Source*>>> lllBoundaryOfSurface_SubFace;
	res = ifcXmlFile->FindObjectFromRefAndPathBy3(pElem, it_ElemForPath_SubFace, lst_Path_For_SubFace.end(), lllBoundaryOfSurface_SubFace, lpObjectSubFace);
	if (res) return res;

	//Recupération des points définissant chaque face + création des faces et assoc avec les "BelongTo" 
	//Si il y a plus d'une Rep => problème 
	if (lllBoundaryOfSurface_SubFace.size() > 1)
		return 2001;//Format erreur: XXXYYY XXX=numero identifiant la routine , YYY=numéro de l'erreur dans cette routine
	if (lllBoundaryOfSurface_SubFace.size() != lpObjectSubFace.size())
		return 2002;//Format erreur: XXXYYY XXX=numero identifiant la routine , YYY=numéro de l'erreur dans cette routine
	//
	//Recup de la Rep
	list <list <list <Type_Elmt_Of_Source*>>> ::iterator it_BoundaryOfSurface = lllBoundaryOfSurface_SubFace.begin();
	//
	//Boucle sur les faces de la Rep pour récupérer leurs contours
	list <Type_Elmt_Of_Source*> ::iterator it_SubFace;
	list <list <Type_Elmt_Of_Source*>> ::iterator it_SegmentsOfBoundary;
	for (it_SegmentsOfBoundary = (*it_BoundaryOfSurface).begin(), it_SubFace = lpObjectSubFace.begin(); it_SegmentsOfBoundary != (*it_BoundaryOfSurface).end(); it_SegmentsOfBoundary++, it_SubFace++)
	{
		//lecture du contenu des child d'un IfcEntity liés à "IfcProject"
		Map_String_String map_messages;
		res = ifcXmlFile->ReadIdAndTypeOfAnEntity(*it_SubFace, map_messages);
		if (res) return res;

		list<list<double*>> SubFacePtsCoord;//la list<double*> définit un des contours de la face, list<list<double*>> définit les contours de la face
		res = ifcXmlFile->ReadPtsDefiningPolyloopOrPolyline((*it_SegmentsOfBoundary), SubFacePtsCoord);
		if (res) return res;

		//Création et Remplissage de la structure "Sous-Face"
		STRUCT_IFCENTITY * st_IfcSubFacGeomRep = new STRUCT_IFCENTITY;
		FillGeomAttributeOf_STRUCT_IFCENTITY(st_IfcSubFacGeomRep, SubFacePtsCoord, st_IfcBelongTo, map_messages);
	}// for (it_SegmentsOfBoundary = (*it_BoundaryOfSurface).begin(); it_SegmentsOfBoundary != (*it_BoundaryOfSurface).end(); it_SegmentsOfBoundary++)

	return res;
}

template <class Type_Elmt_Of_Source, class Type_Source>
int ifc_Tree::BuildExplicitDataTreeFromIfcProductDefinitionShape(Type_Elmt_Of_Source* pElem, Type_Source * const& ifcXmlFile, STRUCT_IFCENTITY *st_IfcBelongTo)
{
	//Pour IfcProductDefinitionShape => n Faces => seul l'IfcShapeRepresentation "Body" est pris en compte!

	//<IfcProductDefinitionShape id="i3431">
	//  <Representations ex:cType="list">
	//    <IfcShapeRepresentation ex:pos="0" xsi:nil="true" ref="i3410"/>
	//    <IfcShapeRepresentation ex:pos="1" xsi:nil="true" ref="i3428"/>
	//  </Representations>
	//</IfcProductDefinitionShape>
	//
	////// 1)/2) => 1=Body (=> 6 faces "Polyloops" pour cube) [et 2=FootPrint (Polylines)]
	//
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
	////// 1.1)/1.2)
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
	//
	////// 1.2)/1.2)
	//
	//<IfcFacetedBrep id="i3400">
	//  <Outer>
	//    <IfcClosedShell xsi:nil="true" ref="i3398"/>
	//  </Outer>
	//</IfcFacetedBrep>
	//
	//<IfcClosedShell id="i3398">
	//  <CfsFaces ex:cType="set">
	//    <IfcFace ex:pos="0" xsi:nil="true" ref="i3363"/> => a mettre dans identifiant face
	//    <IfcFace ex:pos="1" xsi:nil="true" ref="i3372"/> => a mettre dans identifiant face
	//    <IfcFace ex:pos="2" xsi:nil="true" ref="i3379"/> => a mettre dans identifiant face
	//    <IfcFace ex:pos="3" xsi:nil="true" ref="i3386"/> => a mettre dans identifiant face
	//    <IfcFace ex:pos="4" xsi:nil="true" ref="i3391"/> => a mettre dans identifiant face
	//    <IfcFace ex:pos="5" xsi:nil="true" ref="i3396"/> => a mettre dans identifiant face
	//  </CfsFaces>
	//</IfcClosedShell>
	//
	//<IfcFace id="i3396">
	//  <Bounds ex:cType="set">
	//    <IfcFaceOuterBound ex:pos="0" xsi:nil="true" ref="i3395"/>
	//  </Bounds>
	//</IfcFace>
	//
	//<IfcFaceOuterBound id="i3395">
	//  <Bound>
	//    <IfcPolyLoop xsi:nil="true" ref="i3393"/>
	//  </Bound>
	//  <Orientation>true</Orientation>
	//</IfcFaceOuterBound>
	//
	//<IfcPolyLoop id="i3393">
	//  <Polygon ex:cType="list-unique">
	//    <IfcCartesianPoint ex:pos="0" xsi:nil="true" ref="i3367"/>
	//    <IfcCartesianPoint ex:pos="1" xsi:nil="true" ref="i3365"/>
	//    <IfcCartesianPoint ex:pos="2" xsi:nil="true" ref="i3381"/>
	//    <IfcCartesianPoint ex:pos="3" xsi:nil="true" ref="i3374"/>
	//  </Polygon>
	//</IfcPolyLoop>
	//
	////// 2)/2) => 2=FootPrint (Polylines) [et 1=Body (=> 6 faces "Polyloops" pour cube)]
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
	////// 2.1)/2.2)
	//
	//<IfcGeometricRepresentationSubContext id="i3415">
	//  <ContextIdentifier>FootPrint</ContextIdentifier>
	//  <ContextType>Model</ContextType>
	//  <ParentContext>
	//    <IfcGeometricRepresentationContext xsi:nil="true" ref="i1719"/>
	//  </ParentContext>
	//  <TargetView>model_view</TargetView>
	//</IfcGeometricRepresentationSubContext>
	//
	////// 2.2)/2.2)
	//
	//<IfcGeometricCurveSet id="i3426">
	//  <Elements ex:cType="set">
	//    <IfcPolyline ex:pos="0" xsi:nil="true" ref="i3424"/>
	//  </Elements>
	//</IfcGeometricCurveSet>
	//

	int res = 0;

	//
	//Recup de l'IfcShapeRepresentation de type BRep
	Type_Elmt_Of_Source *lpObjectFound = nullptr;
	res = ifcXmlFile->FindIfcShapeRepresentationBrep(pElem, lpObjectFound);
	if (res) return res;

	if (lpObjectFound)
	{
		//Recup de repere local P/R reprere global
		Type_Elmt_Of_Source *lpObjectPlac = nullptr;
		res = ifcXmlFile->FindIfcGeometricRepresentationSubContext(lpObjectFound, lpObjectPlac);
		if (res) return res;

		double db_LocalMat[3][4];
		res = ifcXmlFile->ReadIfcAxis2Placement3DMatrix(lpObjectPlac, db_LocalMat);
		if (res) return res;

		FillRelativePlacementOf_STRUCT_IFCENTITY(st_IfcBelongTo, db_LocalMat);

		//Recup des points P/R reprere local
		list<string> lst_Path_For_BodyFaces;
		lst_Path_For_BodyFaces.push_back("Items"); //[1..n] => HP: 1 seul Item pertinent pour BEM??
		lst_Path_For_BodyFaces.push_back("Outer");
		lst_Path_For_BodyFaces.push_back("CfsFaces"); //[1..n]  N Faces => gérer un 1er niveau de listes  
		lst_Path_For_BodyFaces.push_back("Bounds"); //[1..n] M contours => gerer un 2ème niveau de listes => 1er contour externe ensuite internes?
		lst_Path_For_BodyFaces.push_back("Bound");

		list <string>::iterator it_ElemForPath_BodyFaces;
		it_ElemForPath_BodyFaces = lst_Path_For_BodyFaces.begin();

		//
		// "lll" est une liste qui dissocie les IfcPolyLoop par entités de type (IfcFacetedBrep,...) sous Items
		// "ll" est une liste qui dissocie les IfcPolyLoop par entités de type (IfcFace,...) sous CfsFaces
		// "l" est une liste d'entités (IfcPolyLoop,...) sous Bounds>Bound (cette liste rassemble la multiplicité de ces Bounds>Bound)
		list <Type_Elmt_Of_Source*> lpObjectFace;
		list <list <list <Type_Elmt_Of_Source*>>> lllCFsFacesOfOneItem_Face; // => liste des BRep (1 seule utile pour BEM??) 
		res = ifcXmlFile->FindObjectFromRefAndPathBy3(lpObjectFound, it_ElemForPath_BodyFaces, lst_Path_For_BodyFaces.end(), lllCFsFacesOfOneItem_Face, lpObjectFace);
		if (res) return res;

		//Recupération des points définissant chaque face + création des faces et assoc avec les "BelongTo" 
		//Si il y a plus d'une Rep => problème 
		if (lllCFsFacesOfOneItem_Face.size() > 1)
			return 2003;//Format erreur: XXXYYY XXX=numero identifiant la routine , YYY=numéro de l'erreur dans cette routine
		if ( (*(lllCFsFacesOfOneItem_Face.begin())).size() != lpObjectFace.size())
			return 2004;//Format erreur: XXXYYY XXX=numero identifiant la routine , YYY=numéro de l'erreur dans cette routine
		//
		//Recup de la Rep
		list <list <list <Type_Elmt_Of_Source*>>> ::iterator it_CFsFacesOfOneItem = lllCFsFacesOfOneItem_Face.begin();
		//
		//Boucle sur les faces de la Rep pour récupérer leurs contours
		list <Type_Elmt_Of_Source*> ::iterator it_Face;
		list <list <Type_Elmt_Of_Source*>> ::iterator it_BoundsOfOneCFsFace;
		for (it_BoundsOfOneCFsFace = (*it_CFsFacesOfOneItem).begin(), it_Face = lpObjectFace.begin(); it_BoundsOfOneCFsFace != (*it_CFsFacesOfOneItem).end(); it_BoundsOfOneCFsFace++, it_Face++)
		{
			//lecture du contenu des child d'un IfcEntity liés à "IfcProject"
			Map_String_String map_messages;
			res = ifcXmlFile->ReadIdAndTypeOfAnEntity(*it_Face, map_messages);
			if (res) return res;

			list<list<double*>> FacePtsCoord;//la list<double*> définit un des contours de la face, list<list<double*>> définit les contours de la face
			res = ifcXmlFile->ReadPtsDefiningPolyloopOrPolyline(*it_BoundsOfOneCFsFace, FacePtsCoord);
			if (res) return res;

			//Création et Remplissage de la structure "Face"
			STRUCT_IFCENTITY * st_IfcFacGeomRep = new STRUCT_IFCENTITY;
			FillGeomAttributeOf_STRUCT_IFCENTITY(st_IfcFacGeomRep, FacePtsCoord, st_IfcBelongTo, map_messages);
		}// for (it_BoundsOfOneCFsFace = (*it_CFsFacesOfOneItem).begin(); it_BoundsOfOneCFsFace != (*it_CFsFacesOfOneItem).end(); it_BoundsOfOneCFsFace++)

	}// if(lpObjectFound)

	return res;
}

//
///////////////////////////////////////////////////////////////////////////////////
// Routines intermédiaires "d'aiguillage" mais ne créant pas de structure/entité //
///////////////////////////////////////////////////////////////////////////////////
//

template <class Type_Elmt_Of_Source, class Type_Source>
int ifc_Tree::BuildTreeFrom(Type_Elmt_Of_Source* pElem, Type_Source * const& ifcXmlFile, STRUCT_IFCENTITY *st_IfcBelongTo)
{
	int res = 0;

	//
	// IfcRelAggregates
	//
	//Recuperation des IfcEntity liés à pElem ("IfcProject",ifcSite...) par le lien binaire IfcRelAggregates
	list<Type_Elmt_Of_Source*> lpRelatedObjects;
	res = ifcXmlFile->FindRelatedObjectsInRelAggregatesFromRelatingObject(pElem, &lpRelatedObjects);
	if (res) return res;

	// Si lpRelatedObjects est vide il n'y a pas d'autre RelAggreg => à priori à partir des ifcspaces
	// ???Si lpRelatedObjects est vide il n'y a pas d'autre RelAggreg => essayer alors RelProperties...???
	if (lpRelatedObjects.size() != 0)
	{
		res = BuildTreeFromRelAggregates(lpRelatedObjects, ifcXmlFile, &(*st_IfcBelongTo));
		if (res) return res;
	}// if (lpRelatedObjects.size!=0)
	else
	{
		//Test car il peut exister par exemple des IfcBuildingStorey sans espace => ne pas continuer cette branche
		// Par sécurité, test étendu aux entités "pères": IfcProject, IfcSite, IfcBuilding, IfcBuildingStorey
		if (string(pElem->Value()) != string("IfcProject") 
			&& string(pElem->Value()) != string("IfcSite")
			&& string(pElem->Value()) != string("IfcBuilding")
			&& string(pElem->Value()) != string("IfcBuildingStorey")
			)
		{
			//
			//lecture du Quantities des "IfcSpace"
			Map_String_String map_messages;
			res = ifcXmlFile->ReadKeyWordsAndValuesOfIfcElementQuantity(pElem, map_messages);
			if (res) return res;
			FillQuantitiesAttributeOf_STRUCT_IFCENTITY(st_IfcBelongTo, map_messages);

			//
			// IfcProductDefinitionShape
			//
			//récupérer le lien IfcSpace <-> Faces (pas le data geom!) => IfcProductDefinitionShape
			//Recuperation de l'IfcEntity (IfcProductDefinitionShape) de "IfcSpace" consigné dans sa definition
			list<Type_Elmt_Of_Source*> lpShape;
			res = ifcXmlFile->FindRepresentationInSpace(pElem, &lpShape);
			if (res) return res;

			res = BuildTreeFromShapeOfSpace(lpShape, ifcXmlFile, &(*st_IfcBelongTo));
			if (res) return res;

			//
			// IfcRelSpaceBoundary
			// 
			//Recuperation des IfcEntity liés à "IfcSpace" par le lien ternaire IfcRelSpaceBoundary
			list<Type_Elmt_Of_Source*> lpRelatedBuildingElement;
			list<Type_Elmt_Of_Source*> lpConnectionSurfaceGeometry;
			res = ifcXmlFile->FindRelatedBuildingElementAndConnectionGeometryInRelSpaceBoundaryFromRelatingSpace(pElem, &lpRelatedBuildingElement, &lpConnectionSurfaceGeometry);
			if (res) return res;

			if (lpRelatedBuildingElement.size() != 0 && lpRelatedBuildingElement.size() == lpConnectionSurfaceGeometry.size())
			{
				res = BuildTreeFromRelSpaceBoundary(lpRelatedBuildingElement, lpConnectionSurfaceGeometry, ifcXmlFile, &(*st_IfcBelongTo));
				if (res) return res;
			}// if (lpRelatedBuildingElement.size() != 0 && lpRelatedBuildingElement.size() == lpConnectionSurfaceGeometry.size())
		}// if (string(pElem->Value()) != string("IfcProject")
		//  && string(pElem->Value()) != string("IfcSite")
		//	&& string(pElem->Value()) != string("IfcBuilding")
		//	&& string(pElem->Value()) != string("IfcBuildingStorey")
	}// else if (lpRelatedObjects.size!=0)

	return res;
}

template <class Type_Elmt_Of_Source, class Type_Source>
int ifc_Tree::BuildExplicitDataTreeFrom(Type_Elmt_Of_Source* pElem, Type_Source * const& ifcXmlFile, STRUCT_IFCENTITY *st_IfcBelongTo)
{
	int res = 0;
	
	//Pour IfcConnectionSurfaceGeometry => 1 Sous-Face
	if (string(pElem->Value()) == string("IfcConnectionSurfaceGeometry"))
	{
		res = BuildExplicitDataTreeFromIfcConnectionSurfaceGeometry(pElem, ifcXmlFile, st_IfcBelongTo);
		if (res) return res;
	}// if (string(pElem->Value()) == string("IfcConnectionSurfaceGeometry"))

	 //Pour IfcProductDefinitionShape => n Faces
	 //
	 // IMPORTANT (A CONFIRMER):
	 // HP: 1 Space <=> 1 Shape <=> 1 BRep (utile pour BEM) => N Faces et 1 Face => N contours (1 externe et N-1 internes)????
	 //  => du coup on élimine shape et BRep pour associer 1 Space à N Faces 
	 // Attention: question => 1 Face peut contenir un contour externe et des contours internes??? 
	 //      => gérer liste de listes de points 
	 //           => si en général 1 seul contour externe et n internes alors 1ère liste=contour externe et les autres listes=internes
	 //
	if (string(pElem->Value()) == string("IfcProductDefinitionShape"))
	{
		res=BuildExplicitDataTreeFromIfcProductDefinitionShape(pElem, ifcXmlFile, st_IfcBelongTo);
		if (res) return res;
	}// if (string(pElem->Value()) == string("IfcProductDefinitionShape"))

	return res;
}

