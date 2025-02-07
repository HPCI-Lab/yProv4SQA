# models/output.py

class Output:
    def __init__(self, id: str, badge_won: str):
        self.id = id
        self.badge_won = badge_won

    def to_dict(self):
        return {
            f"ex:{self.id}": {  
                "prov:type": "document",
                "ex:badge_won": self.badge_won
            }
        }
