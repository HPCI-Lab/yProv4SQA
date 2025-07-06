# models/provenance_relationship.py

class ProvenanceRelationship:
    def __init__(self, RelFrom: str, RelTo: str, relationship_type: str):
        self.RelFrom = RelFrom  
        self.RelTo = RelTo  
        self.relationship_type = relationship_type  

    def to_dict(self):
        # Handle relationships dynamically based on relationship type
        if self.relationship_type == "wasAttributedTo":
            return self._was_attributed_to()
        elif self.relationship_type == "wasGeneratedBy":
            return self._was_generated_by()
        elif self.relationship_type == "wasDerivedFrom":
            return self._was_derived_from()
        elif self.relationship_type == "Used":
            return self._Used_()
        elif self.relationship_type == "wasAssociatedWith":
            return self._was_assosiated_by()
        # Additional relationship types can be handled here

    def _Used_(self):
        return {
            f"_:U_{self.RelFrom}_{self.RelTo}": {
                "prov:agent": f"ex:{self.RelFrom}",
                "prov:entity": f"ex:{self.RelTo}"
            }
        }
    
    def _was_attributed_to(self):
        return {
            f"_:wat_{self.RelFrom}_{self.RelTo}": {
                "prov:agent": f"ex:{self.RelFrom}",
                "prov:entity": f"ex:{self.RelTo}"
            }
        }

    def _was_generated_by(self):
        return {
            f"_:wGB_{self.RelFrom}_{self.RelTo}": {
                "prov:activity": f"ex:{self.RelFrom}",
                "prov:entity": f"ex:{self.RelTo}"
            }
        }
    def _was_assosiated_by(self):
        return {
            f"_:wGB_{self.RelFrom}_{self.RelTo}": {
                "prov:activity": f"ex:{self.RelFrom}",
                "prov:entity": f"ex:{self.RelTo}"
            }
        }

    def _was_derived_from(self):
        return {
            f"_:id_{self.RelFrom}_{self.RelTo}": {
                "prov:generatedEntity": f"ex:{self.RelTo}",
                "prov:usedEntity": f"ex:{self.RelFrom}"
            }
        }
