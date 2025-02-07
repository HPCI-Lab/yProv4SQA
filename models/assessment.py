# models/assessment.py

class Assessment:
    def __init__(self, id: str, version: str, report_json_url: str):
        self.id = id
        self.version = version
        self.report_json_url = report_json_url

    def to_dict(self):
        return {
            f"ex:{self.id}": { 
                "prov:type": "document",
                "ex:version": self.version,
                "ex:report_json_url": self.report_json_url
            }
        }
