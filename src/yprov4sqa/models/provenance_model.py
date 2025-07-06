import json
from .agent import Agent
from .repository import Repository
from .assessment import Assessment
from .quality_check import QualityCheck
from .output import Output
from .provenance_relationship import ProvenanceRelationship


class ProvenanceModel:
    def __init__(self):
        self.prefix = {
            "ex": "https://sqaaas.eosc-synergy.eu/",
            "w3": "http://www.w3.org/",
            "tr": "http://www.w3.org/TR/2011/"
        }
        self.agents = {}
        self.entities = {}
        self.activities = {}
        self.relationships = {
            "wasGeneratedBy": {},
            "wasAssociatedWith": {},
            "wasAttributedTo": {},
            "wasDerivedFrom": {},
            "wasAssociatedWith": {},
            "Used": {}
        }

    def add_agent(self, agent: Agent):
        self.agents.update(agent.to_dict())

    def add_entity(self, entity):
        self.entities.update(entity.to_dict())

    def add_QualityCheck(self, activity: QualityCheck):
        self.activities.update(activity.to_dict())

    def add_relationship(self, relationship: ProvenanceRelationship, relationship_type: str):
        if relationship_type in self.relationships:
            self.relationships[relationship_type].update(relationship.to_dict())

    def to_json(self):
        # Build the final dictionary
        prov_dict = {
            "prefix": self.prefix,
            "agent": self.agents,
            "entity": self.entities,
            "activity": self.activities,
        }

        # Add relationships only if they are not empty
        for relationship_type, relationship_data in self.relationships.items():
            if relationship_data:  # Add only if there is data
                prov_dict[relationship_type] = relationship_data

        # Return JSON representation
        return json.dumps(prov_dict, indent=4)
