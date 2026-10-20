"""Policy-source candidate discovery (Phase 2).

Discovery finds candidate pages/documents on an institution's own official
domain that might be its AI-guidance policy -- it never selects a final
source. A human researcher reviews data/candidates/source_candidates.csv
and only then adds a chosen row to config/sources_full.csv. See
docs/candidate_discovery.md.
"""

from __future__ import annotations
