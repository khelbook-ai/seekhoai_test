You explain the delta between a course build's estimated and actual token cost. Be
concise and attribute the delta to concrete drivers.

Estimated: ${estimated}
Actual:    ${actual}
Delta:     ${delta_abs} ({delta_pct}%)
Actual cost by phase: {by_phase}
Estimated by phase:   {est_by_phase}
Build notes: {notes}

Return ONLY this JSON:
{{
  "drivers": [
    {{"phase": "scouting|generation|checking|verification", "estimated": 0.0, "actual": 0.0, "reason": "..."}}
  ],
  "summary": "one short paragraph explaining the delta"
}}
