

from madsci.common.types.base_types import BaseModel
from typing import Literal
from pydantic import Field
from pydantic.types import Discriminator, Tag
from typing import Annotated, Union, Optional

    
class PALtray(BaseModel):
    name: str = Field(
        title="tray Name",
        description = "Name of the tray"
    )
    type: str = Field(
        title="tray Type",
        description = "type of the tray"
    )
    position: str = Field(
        title="tray Position",
        description = "Name of the Position"
    )
    cells: int = Field(
            title="tray cells",
            description="The number of cells in the tray"
        )
    source: bool = Field(
        title="Source",
        description="Whether or not the tray is used for source chemicals",
        default=False
    )


class PALAction(BaseModel):
    """a general PAL action"""
    action_type: Literal["action"] = Field(
        title="Action Type",
        description="The type of the action",
        default="action"
        )
    
class PALStart(PALAction):
    action_type: Literal["start"] = Field(
        title="Action Type",
        description="The type of the action",
        default="start"
        )
    name: str = Field(
        title="Name of Session",
        description="The name of the current session"
        )
    
class PALFinish(PALAction):
    action_type: Literal["finish"] = Field(
        title="Action Type",
        description="The type of the action",
        default="finish"
        )
    
class PALHome(PALAction):
    action_type: Literal["home"] = Field(
        title="Action Type",
        description="The type of the action",
        default="home"
        )

class PALWash(PALAction):
    action_type: Literal["wash"] = Field(
        title="Action Type",
        description="The type of the action",
        default="wash"
        )

class PALTransfer(PALAction):
    action_type: Literal["transfer"]  = Field(
        title="Action Type",
        description="The type of the action",
        default="transfer"
        )
    source_location: list[str]  = Field(
        title="Source cell",
        description="The source cell for the transfer"
        )
    target_location: list[str]  = Field(
        title="Target cell",
        description="The target cell for the transfer"
        )
    volume: float = Field(
        title="Transfer Volume",
        description="The volume for the transfer"
        )
    chaser: float = Field(
        title="Chaser Volume",
        description="The volume for the chaser"
        )
    aspirate_timestamp: Optional[str] = Field(
        title="Aspirate Time Stamp",
        description="The timestamp for the transfer aspration",
        default=None
        )
    dispense_timestamp: Optional[str] = Field(
        title="Dispense Time Stamp",
        description="The timestamp for the transfer aspration",
        default=None
        )

class PALWithdraw(PALAction):
    action_type: Literal["withdraw"]  = Field(
        title="Action Type",
        description="The type of the action",
        default="withdraw"
        )
    source_tray: list[str]  = Field(
        title="Source tray",
        description="The source tray for the withdrawl"
        )
    target_tray: list[str]  = Field(
        title="Target tray",
        description="The target tray for the withdrawl"
        )
    source_cell: list[str]  = Field(
        title="Source cell",
        description="The source cell for the withdrawl"
        )
    target_cell: list[str]  = Field(
        title="Target cell",
        description="The target cell for the withdrawl"
        )
    volume: float = Field(
        title="withdrawl Volume",
        description="The volume for the withdrawl"
        )
    chaser: float = Field(
        title="Chaser Volume",
        description="The volume for the chaser"
        )
    aspirate_timestamp: Optional[str] = Field(
        title="Aspirate Time Stamp",
        description="The timestamp for the transfer aspration",
        default=None
        )

class PALPause(PALAction):
     action_type: Literal["pause"] = Field(
        title="Action Type",
        description="The type of the action",
        default="pause"
        )
     
class PALDispense(PALAction):
    action_type: Literal["dispense"] = Field(
        title="Action Type",
        description="The type of the action",
        default="dispense"
        )
    volume: float  = Field(
        title="Code",
        description="The volume for the dispense"
        )
    tray: str = Field(
        title="Target tray",
        description="The target tray for the move"
        )
    slot: str = Field(
        title="Target slot",
        description="The target slot for the move"
        )
    position: str = Field(
        title="Target vial",
        description="The target vial for the move"
        )

class PALDelay(PALAction):
    action_type: Literal["delay"] = Field(
        title="Action Type",
        description="The type of the action",
        default="delay"
        )
    delay: float  = Field(
        title="Code",
        description="The length for the delay"
        )

class PALStir(PALAction):
    action_type: Literal["stir"] = Field(
        title="Action Type",
        description="The type of the action",
        default="stir"
        )
    time: str = Field(
        title="time",
        description="The time length for stirring"
        )
    speed: float  = Field(
        title="Code",
        description="The rate for the stir"
        )
    
class PALMove(PALAction):
    action_type: Literal["move"] = Field(
        title="Action Type",
        description="The type of the action",
        default="move"
        )
    tray: int = Field(
        title="Target tray",
        description="The target tray for the move"
        )
    slot: int = Field(
        title="Target slot",
        description="The target slot for the move"
        )
    position: int = Field(
        title="Target vial",
        description="The target vial for the move"
        )
    
PALActions = Annotated[
    Union[
        Annotated[PALAction, Tag("action")],
        Annotated[PALTransfer, Tag("transfer")],
        Annotated[PALDelay, Tag("delay")],
        Annotated[PALDispense, Tag("dispense")],
        Annotated[PALPause, Tag("pause")],
        Annotated[PALStir, Tag("stir")],
        Annotated[PALMove, Tag("move")],
        Annotated[PALStart, Tag("start")],
        Annotated[PALFinish, Tag("finish")],
        Annotated[PALHome, Tag("home")],
        Annotated[PALWash, Tag("wash")],
        Annotated[PALWithdraw, Tag("withdraw")],
    ],
    Discriminator("action_type"),
]


class PALProtocol(BaseModel):
    name: str = Field(
        title="Protocol Name",
        description="The Name of the Protocol"  
        )
    units: str = Field(
        title="Protocol Units",
        description="The units for the protocol",
        default="ul"
    )
    trays: dict[str, PALtray] =  Field(
        title="trays",
        description="The dictionary of trays for the protocol",
        default_factory=dict
    )
    actions: list[PALActions] = Field(
        title="Actions",
        description="The list of actions for the protocol",
        default_factory=list
    )

    

