# models/assessment.py

class Assessment:
    def __init__(self, id: str, version: str,commit_id: str, commit_date: str, branch_name:str, report_json_url: str):
        self.id = id
        self.version = version
        self.commit_id= commit_id,
        self.commit_date= commit_date,
        self.branch_name= branch_name,
        self.report_json_url = report_json_url

    def to_dict(self):
        return {
            f"ex:{self.id}": { 
                "prov:type": "document",
                "ex:version": self.version,
                "ex:commit_id": self.commit_id,
                "ex:commit_date": self.commit_date,
                "ex:branch_name": self.branch_name,
                "ex:report_json_url": self.report_json_url
            }
        }
