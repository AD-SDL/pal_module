import datetime
from pydantic import BaseModel
from enum import Enum

class AMEWS_tube_type(str, Enum):
    """
    Enumeration for the types of tubes used in the AMEWS experiment.
    """ 
    Blank = "Blank"
    Calibrate = "Calibrate"
    Sample = "Sample"


class AMEWS_tube(BaseModel):
    """
    Represents a tube in a tube rack for the AMEWS experiment.
    """
    
    """type of tube, can be Blank, Calibrate, or Sample"""
    type: AMEWS_tube_type
    

    """The well in the tube rack where the tube is located."""
    well: str

    """The plate from which the sample was taken."""

    sampled_plate: str

    """The well in the sampled plate from which the sample was taken."""
    sampled_well: str

    """The time when the sample was taken."""
    sampled_at: datetime.datetime | None = None