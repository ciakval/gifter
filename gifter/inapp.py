"""Detection of in-app browsers (Messenger, Instagram, ...) where Google refuses sign-in.

Pure function: the user agent is inspected, never logged or stored.
"""

import re

# Tokens are from the Phase 1 research (OPS-04); real-device confirmation happens
# in the live UAT. WhatsApp and Google app browsers are deliberately not matched
# because Google allows sign-in there.
IN_APP_UA_RE = re.compile(
    r"FBAN|FBAV|FB_IAB|FBIOS|FB4A|Messenger|Instagram|BytedanceWebview|musical_ly"
    r"|TikTok|LinkedInApp|Snapchat|; wv\)",
    re.IGNORECASE,
)


def is_in_app_browser(user_agent: str | None) -> bool:
    if not user_agent:
        return False
    return IN_APP_UA_RE.search(user_agent) is not None
