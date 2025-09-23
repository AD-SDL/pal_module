"""
REST-based node that interfaces with MADSci and provides a USB camera interface
"""

import tempfile
from pathlib import Path
from typing import Optional

from madsci.common.types.action_types import ActionResult, ActionSucceeded
from madsci.node_module.helpers import action
from madsci.node_module.rest_node_module import RestNode

from typing import Union

from madsci.common.types.node_types import RestNodeConfig


class PALConfig(RestNodeConfig):
    """Configuration for the camera node module."""

    pal_ip: str
    """The ip address for the PAL robot"""

class PALNode(RestNode):
    """Node that interfaces with MADSci and provides a USB camera interface"""

    config_model = PALConfig

    @action
    def run_protocol(
        self,  protocol: Annotated[Path, "Protocol File"],
    ) -> ActionResult:
        """Action that takes a picture using the configured camera. The focus used can be set using the focus parameter."""
        

if __name__ == "__main__":
    pal_node = PALNode()
    pal_node.start_node()