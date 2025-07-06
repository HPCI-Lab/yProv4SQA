# models/repository.py

class Repository:
    def __init__(self, id: str, name: str, url: str,  avatar_url:str , description:str, languages:str):
        self.id = id
        self.name = name
        self.url = url
        self.avatar_url=avatar_url
        self.description=description
        self.languages=languages

    def to_dict(self):
        return {
            f"ex:{self.id}": {  
                "prov:type": "document",
                "ex:url": self.url,
                "ex:name": self.name,
                "ex:avatar_url":self.avatar_url,
                "ex:description":self.description,
                "ex:languages":self.languages
            }
        }
