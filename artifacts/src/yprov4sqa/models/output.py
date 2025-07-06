# models/output.py

class Output:
    def __init__(self, id: str, badge_won: str,
                 Issued_On:str,
                 entityType:str,
                 openBadgeId:str,
                 createdAt:str,
                 badgeclassOpenBadgeId:str,
                 image_URL:str
                 ):
        
        self.id = id
        self.badge_won = badge_won
        self.Issued_On=Issued_On
        self.entityType=entityType
        self.openBadgeId=openBadgeId
        self.createdAt=createdAt
        self.badgeclassOpenBadgeId=badgeclassOpenBadgeId
        self.image_URL=image_URL



    def to_dict(self):
        return {
            f"ex:{self.id}": {  
                "prov:type": "document",
                "ex:badge_won": self.badge_won,
                "ex:Issued_On:str":self.Issued_On,
                "ex:entityType:str":self.entityType,
                "ex:openBadgeId:str":self.openBadgeId,
                "ex:createdAt:str":self.createdAt,
                "ex:badgeclassOpenBadgeId:str":self.badgeclassOpenBadgeId,
                "ex:image:str":self.image_URL
            }
        }
