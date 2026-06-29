# models/assessment.py

class Assessment:
    def __init__(
        self,
        id:                str,
        version:           str,
        commit_id:         str,
        commit_date:       str,
        branch_name:       str,
        report_json_url:   str,
        report_permalink:  str  = '',
        is_main_repo:      bool = None,
        is_partial_run:    bool = False,
    ):
        self.id               = id
        self.version          = version
        self.commit_id        = commit_id
        self.commit_date      = commit_date
        self.branch_name      = branch_name
        self.report_json_url  = report_json_url
        self.report_permalink = report_permalink
        self.is_main_repo     = is_main_repo
        self.is_partial_run   = is_partial_run

    def to_dict(self):
        entity = {
            "prov:type":           "document",
            "ex:version":          self.version,
            "ex:commit_id":        self.commit_id,
            "ex:commit_date":      self.commit_date,
            "ex:branch_name":      self.branch_name,
            "ex:report_json_url":  self.report_json_url,
            "ex:is_partial_run":   self.is_partial_run,
        }
        if self.report_permalink:
            entity["ex:report_permalink"] = self.report_permalink
        if self.is_main_repo is not None:
            entity["ex:is_main_repo"] = self.is_main_repo
        return {f"ex:{self.id}": entity}