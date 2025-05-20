# models/quality_check.py

class QualityCheck:
    def __init__(self, id: str, description: str, is_output: str, percentage: str, total_subcriteria: int, success_subcriteria: int):
        self.id = id
        self.description = description
        self.is_output = is_output
        self.percentage = percentage
        self.total_subcriteria = total_subcriteria
        self.success_subcriteria = success_subcriteria

    def to_dict(self):
        return {
            f"ex:{self.id}": {  # Directly map the unique ID without wrapping
                "prov:type": "activity",
                "ex:description": self.description,
                "ex:output": self.is_output,
                "ex:percentage": self.percentage,
                "ex:total_subcriteria": self.total_subcriteria,
                "ex:success_subcriteria": self.success_subcriteria
            }
        }
