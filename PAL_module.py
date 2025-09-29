from datetime import datetime
import json
from pathlib import Path
from typing import Annotated, Any, Optional

from madsci.common.types.action_types import (
    ActionResult,
    ActionSucceeded,
    ActionFailed
)
from madsci.common.types.admin_command_types import AdminCommandResponse
from madsci.common.types.node_types import RestNodeConfig
from madsci.node_module.helpers import action
from madsci.node_module.rest_node_module import RestNode
from madsci.common.types.auth_types import OwnershipInfo
from madsci.common.types.resource_types.definitions import (
    ContainerResourceDefinition,
    SlotResourceDefinition,
)

from madsci.common.types.resource_types import ContinuousConsumable
from madsci.common.types.resource_types.definitions import ContinuousConsumableResourceDefinition
from PAL_protocol_types import PALtray, PALProtocol, PALAction
from madsci.client.resource_client import ResourceClient
import os
from pathlib import Path
from log_parsing import read_logs, add_timestamps
import PAL3_driver
import time



class PALConfig(RestNodeConfig):
    """Configuration for a PAL Node"""

class PALNode(RestNode):
    """Node Module Implementation for the PAL Instrument"""

    config_model = PALConfig()
    def startup_handler(self):
        self.pal = PAL3_driver.PALService()
        self.pal.std_start("test")
        pass

    def execute_action(self, action: PALAction):
            if action.action_type == "start":
                self.pal.std_start(action.name)
            elif action.action_type == "finish":
                self.pal.finish()
            elif action.action_type == "home":
                self.pal.safe_home()
            elif action.action_type == "wash":
                self.pal.clean_wash()
            elif action.action_type == "transfer":
                kwargs = {"vial_from" : action.source_location,
                        "vial_to" : action.target_location,
                        "volume" : action.volume,
                        "chaser" : action.chaser
                }
                pal.quick_transfer(**kwargs)
            elif action.action_type == "delay":
                time.sleep(action.delay)
            elif action.action_type == "dispense":
                self.pal.safe_move2vial(action.tray, action.slot, action.position)
                self.pal.session.Execute(penetrate)
                self.pal.eh.EmptySyringe()
            elif action.action_type == "withdraw":
                kwargs = {"vial_from" : action.source_cell,
                        "vial_to" : action.target_cell,
                        "volume" : action.volume,
                        "chaser" : action.chaser
                }
                self.pal.quick_withdraw(**kwargs)
            elif action.action_type == "pause":
                self.pal.pause = true
            elif action.action_type == "stir":
                self.pal.set_vortex(action.speed, action.time)
            elif action.action_type == "move":
                self.pal.safe_move2vial(action.tray, action.slot, action.position)
    @action
    def run_protocol(
            self,
            protocol: Path,
        ) -> ActionResult:
            with open(protocol) as f:
                protocol = PALProtocol.model_validate(json.load(f))
            for action in protocol.actions:
                self.execute_action(action)
            return ActionSucceeded()
           

if __name__ == "__main__":
    pal_node = PALNode()
    pal_node.start_node()