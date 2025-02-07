# models/repository.py

class Repository:
    def __init__(self, id: str, name: str, url: str, commit_id: str , tag:str , is_main_repo:str, avatar_url:str , description:str, languages:str ,  badge_status:str  ):
        self.id = id
        self.name = name
        self.url = url
        self.commit_id = commit_id
        self.tag=tag
        self.is_main_repo=is_main_repo
        self.avatar_url=avatar_url
        self.description=description
        self.languages=languages
        self.badge_status=badge_status

    def to_dict(self):
        return {
            f"ex:{self.id}": {  
                "prov:type": "document",
                "ex:url": self.url,
                "ex:name": self.name,
                "ex:commit_id":self.commit_id,
                "ex:tag":self.tag,
                "ex:is_main_repo":self.is_main_repo,
                "ex:avatar_url":self.avatar_url,
                "ex:description":self.description,
                "ex:languages":self.languages,
                "ex:badge_status":self.badge_status
            }
        }
