# yprov4sqa/models/output.py
"""
Enriched Output — extends the original model with
badge_path: what criteria are fulfilled/missing per badge level.
Stored in the W3C PROV Output entity.
"""

import json


class Output:
    def __init__(
        self,
        id:                    str,
        badge_won:             str,
        Issued_On:             str,
        entityType:            str,
        openBadgeId:           str,
        createdAt:             str,
        badgeclassOpenBadgeId: str,
        image_URL:             str,
        # ── NEW enriched field ───────────────────────────────
        badge_path:            dict = None,
        verification_url:      str  = '',
        # badge_path = {
        #   'bronze': {'fulfilled': [...], 'missing': [...]},
        #   'silver': {'fulfilled': [...], 'missing': [...]},
        #   'gold':   {'fulfilled': [...], 'missing': [...]},
        # }
    ):
        self.id                    = id
        self.badge_won             = badge_won
        self.Issued_On             = Issued_On
        self.entityType            = entityType
        self.openBadgeId           = openBadgeId
        self.createdAt             = createdAt
        self.badgeclassOpenBadgeId = badgeclassOpenBadgeId
        self.image_URL             = image_URL
        self.badge_path            = badge_path or {}
        self.verification_url      = verification_url
    def to_dict(self) -> dict:
        entity = {
            "prov:type":                  "document",
            "ex:badge_won":               self.badge_won,
            "ex:Issued_On:str":           self.Issued_On,
            "ex:entityType:str":          self.entityType,
            "ex:openBadgeId:str":         self.openBadgeId,
            "ex:createdAt:str":           self.createdAt,
            "ex:badgeclassOpenBadgeId:str": self.badgeclassOpenBadgeId,
            "ex:image:str":               self.image_URL,
        }

        # ── Enriched badge path ───────────────────────────────
        if self.badge_path:
            entity["ex:badge_path"] = json.dumps(self.badge_path)

            # Also store individual missing lists for easy querying
            for level in ('bronze', 'silver', 'gold'):
                path = self.badge_path.get(level, {})
                missing   = path.get('missing',   [])
                fulfilled = path.get('fulfilled', [])
                if missing:
                    entity[f"ex:{level}_missing"]   = missing
                if fulfilled:
                    entity[f"ex:{level}_fulfilled"] = fulfilled

        if self.verification_url:
            entity["ex:verification_url"] = self.verification_url

        return {f"ex:{self.id}": entity}
