"""features — candidate feature modules for player_feature_screen_v1.

ALL_CANDIDATES collects the HAVE-tier catalog implementations:
  A (1-6, 8, 10-11), B (12-16, 19, 21-26; #20 skipped, documented),
  D (36-48), E (49-60), F (61-71), G (73-78), H (79, 81-85),
  I (87-89, 92), J (93-98, 100).
"""

from .common import Candidate, Ctx, CHANNELS, assert_quarantine, QuarantineError
from . import fam_a, fam_b, fam_d, fam_e, fam_f, fam_g, fam_h, fam_i, fam_j

ALL_CANDIDATES = (fam_a.CANDIDATES + fam_b.CANDIDATES + fam_d.CANDIDATES
                  + fam_e.CANDIDATES + fam_f.CANDIDATES + fam_g.CANDIDATES
                  + fam_h.CANDIDATES + fam_i.CANDIDATES + fam_j.CANDIDATES)

SKIPPED = [
    {"catalog_number": 20, "name": "production_vs_specific_defender", "family": "B",
     "reason": ("requires a shot-event x stint-window x specific-defender join; "
                "every tractable reduction duplicates #14 (rim protection) or "
                "#57 (competition quality); deferred to a dedicated build if "
                "the lineup family shows life")},
]

__all__ = ["Candidate", "Ctx", "CHANNELS", "ALL_CANDIDATES", "SKIPPED",
           "assert_quarantine", "QuarantineError"]
