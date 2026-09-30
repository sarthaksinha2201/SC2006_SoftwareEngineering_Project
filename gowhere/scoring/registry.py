"""The factors the system scores. To add a factor, write a ScoringStrategy subclass and
list it here; the ETL build and the ScoringEngine pick it up without changes."""
from gowhere.scoring.greenery import GreeneryScorer
from gowhere.scoring.healthcare import HealthcareScorer
from gowhere.scoring.housing import HousingAffordabilityScorer
from gowhere.scoring.public_transport import PublicTransportScorer


def default_strategies():
    return [PublicTransportScorer(), HousingAffordabilityScorer(), GreeneryScorer(),
            HealthcareScorer()]
