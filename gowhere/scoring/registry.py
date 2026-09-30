"""The factors the system scores. To add a factor, write a ScoringStrategy subclass and
list it here; the ETL build and the ScoringEngine pick it up without changes."""
from gowhere.scoring.amenities import AmenitiesScorer
from gowhere.scoring.commute import CommuteScorer
from gowhere.scoring.greenery import GreeneryScorer
from gowhere.scoring.healthcare import HealthcareScorer
from gowhere.scoring.housing import HousingAffordabilityScorer
from gowhere.scoring.public_transport import PublicTransportScorer


def default_strategies(commute_router=None):
    """commute_router: the user session's CommuteRouter (see gowhere.scoring.commute).
    The web app must pass one router per session so routes are cached for that session
    only and the destination never outlives it."""
    return [PublicTransportScorer(), HousingAffordabilityScorer(), AmenitiesScorer(),
            GreeneryScorer(), HealthcareScorer(), CommuteScorer(commute_router)]
