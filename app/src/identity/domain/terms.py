"""The terms of service a promoter accepts before working with student data.

The terms carry the data processing agreement (art. 28 GDPR): Corvus holds
students' theses on the promoter's behalf, and the click that accepts them
is what makes that lawful. The text lives with the frontend
(`frontend/content/legal/`); this is the version it must match.

Bump the version whenever the text changes in substance: every promoter is
then asked again, and the record keeps who accepted which text and when.
"""

CURRENT_TERMS_VERSION = "2026-11-06"

# The `detail` of the 403 a promoter gets before accepting. The frontend
# recognises it and sends them to the terms instead of showing an error.
TERMS_NOT_ACCEPTED = "terms_not_accepted"
