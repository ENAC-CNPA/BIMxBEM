* [IfcSpace]() :
	* BoundedBy : Référence les IfcRelSpaceBoundary
	* ObjectPlacement : Les IfcRelSpaceBoundary sont placés relativement à ce placement
* [IfcRelSpaceBoundary](https://standards.buildingsmart.org/IFC/RELEASE/IFC4_1/FINAL/HTML/link/ifcrelspaceboundary.htm) :
	* RelatingSpace : Pour obtenir l'IfcSpace
	* RelatedBuildingElement : Pour obtenir l'IfcElement associé (ex. IfcWall)
	* Obtenir la direction normale :
		* Option 1 : Shape.normalAt(0,0) (Fonction FreeCAD).
		Elle pointe vers l'extérieur.
		```python
		for face in doc.findObjects("Part::Feature"):
			face.Placement.move(face.Shape.normalAt(0, 0)*200)
		```
		* Option 2 : Appliquer la matrice à la direction
	* InternalOrExternalBoundary : 'EXTERNAL' ou 'INTERNAL'
	* PhysicalOrVirtualBoundary : Virtual si pas de séparation physique. Comment le traiter ?
	* Nouveauté IFC4 : nouvelle classe avec attributs supplémentaires (ParentBoundary, 
	CorrespondingBoundary) où la face opposée est déjà renseignée ainsi que cas échéant l'éléments
	dans lequel elle est hébergée.
* [IfcWall]() / [IfcDoor]() / [IfcWindow]() :
	* ConnectedTo : Contient les connections avec d'autres éléments tel que IfcWall
		* RelatedElement : Élement correspondant (ex: IfcWall)
		* RelatedConnectionType : 'ATEND', 'START'
		Peu utile étant donné qu'un mur peut être commun à plusieurs locaux. Les extrémités des 
		murs ne sont pas forcément les extrémités des IfcRelSpaceBoundary.
		Peut-être utiles pour repérer les murs intermédiaires qui coupe un IfcRelSpaceBoundary en 
		2 surfaces côte à côte ?
		* HasOpenings : Référence les ouvertures hébergés. Probablement plus pratique de passer par
		l'IfcRelSpaceBoundary référençant
	* ProvidesBoundaries : Référence les IfcRelSpaceBoundary lié à l'élément. 
	Utile pour voir quel élément est en vis à vis ?
	* HasAssociations : Contient notamment les matériaux associés.
	* HasCovering : Certains logiciels pourrait donner l'isolation dans un élément séparé ? 
	(TODO: Vérifier définition schéma IFC)
* GlobalId : uuid à enregistrer pour mise à jour IFC etc…

Vérifier si 2 formes sont coplanaires : Part.Shape.isCoplanar(other_shape)

Concernant les surfaces modifiées :
* Les points coincidants entre les faces doivent le rester après translation. Attention :
	* Pas forcément un segment, 1 seul point peut être coincident avec une autre face
	* 1 point ne coincide pas forcément avec un autre point (ligne / face)
Part.Vertex.Point -> FreeCAD.Vector
1. Repérer les points coincidents 
(méthode d'enregistrement de la coincidence, performance de calcul ?)
2. Calculer la ligne à l'intersection des plans. (Part.Plane.intersectSS)
3. Projeter les points coincidents sur la ligne. (FreeCAD.Vector.projectToLine)
