"""CrewAI integration for MultiTrust.

Requires: pip install crewai
"""

from multitrust.integrations.crewai.callbacks import TrustTaskCallback
from multitrust.integrations.crewai.middleware import TrustMiddleware

__all__ = ["TrustMiddleware", "TrustTaskCallback"]
