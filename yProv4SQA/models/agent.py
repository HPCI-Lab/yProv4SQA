# models/agent.py

class Agent:
    def __init__(self, id: str, name: str, agent_type: str = "prov:SoftwareAgent", xsd_type: str = "xsd:QName"):
        self.id = id
        self.name = name
        self.agent_type = agent_type
        self.xsd_type = xsd_type

    def to_dict(self):
        return {
            f"ex:{self.id}": { 
                "prov:type": self.agent_type,
                "xsd:type": self.xsd_type
            }
        }
