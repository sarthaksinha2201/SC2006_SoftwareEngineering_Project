"""The factors the system scores. To add a factor, write a ScoringStrategy subclass and
list it here; the ETL build and the ScoringEngine pick it up without changes."""
from gowhere.scoring.public_transport import PublicTransportScorer


def default_strategies():
    return [PublicTransportScorer()]
