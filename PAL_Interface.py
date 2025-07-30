from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Optional

from madsci.common.types.action_types import (
    ActionResult,
    ActionSucceeded
)
from madsci.common.types.admin_command_types import AdminCommandResponse
from madsci.common.types.node_types import RestNodeConfig
from madsci.node_module.helpers import action
from madsci.node_module.rest_node_module import RestNode
import json
from PAL_AMEWS_24cells import AMEWS
import os



class PALConfig(RestNodeConfig):
    """Configuration for a PAL Node"""

    


class PALNode(RestNode):
    """Node Module Implementation for the PAL Instruments"""

    config_model = PALConfig


    @action
    def blank(
        self,
    ) -> ActionResult:
        """Copy results for the current container to storage"""
        amews = AMEWS()
        new_info = amews.PAL_blank(amews.to_json())
        log_file = os.path.join(amews.ld.dir, amews.ld.log)
        excerpt_file_name = "%s.csv" % amews.ld.asl.excerpt_name
        excerpt_file = os.path.join(amews.ld.dir, excerpt_file_name)
        digest_vols_name = amews.ld.asl.digest_vol_name
        digest_vols =  os.path.join(amews.ld.dir, digest_vols_name)
        amews.PAL_start
        amews.PAL_blank
        amews.PAL_finish
        return ActionSucceeded(data={"info": new_info}, files={
                                        "raw_log": log_file, 
                                        "excerpt_log": excerpt_file, 
                                        "digest_vols": digest_vols})

    @action
    def fill(
        self,
        info: Annotated[Any, "the json info to run the function"],
    ) -> ActionResult:
        """Copy results for the current container to storage"""
        amews = AMEWS()
        if type(info) == str:
            info = json.loads(info)
        new_info = amews.PAL_fill(info)
        log_file = os.path.join(amews.ld.dir, amews.ld.log)
        excerpt_file_name = "%s.csv" % amews.ld.asl.excerpt_name
        excerpt_file = os.path.join(amews.ld.dir, excerpt_file_name)
        digest_vols_name = amews.ld.asl.digest_vol_name
        digest_vols =  os.path.join(amews.ld.dir, digest_vols_name)
        amews.PAL_start
        amews.PAL_fill
        amews.PAL_finish
        return ActionSucceeded(data={"info": new_info}, files={
                                        "raw_log": log_file, 
                                        "excerpt_log": excerpt_file, 
                                        "digest_vols": digest_vols})
    
    @action
    def calibrate(
        self,
        info: Annotated[Any, "the json info to run the function"],
    ) -> ActionResult:
        """Copy results for the current container to storage"""
        amews = AMEWS()
        new_info = amews.AS_calibrate(info)
        log_file = os.path.join(amews.ld.dir, amews.ld.log)
        excerpt_file_name = "%s.csv" % amews.ld.asl.excerpt_name
        excerpt_file = os.path.join(amews.ld.dir, excerpt_file_name)
        digest_vols_name = amews.ld.asl.digest_vol_name
        digest_vols =  os.path.join(amews.ld.dir, digest_vols_name)
        amews.PAL_start
        amews.PAL_load
        amews.PAL_finish
        return ActionSucceeded(data={"info": new_info}, files={
                                        "raw_log": log_file, 
                                        "excerpt_log": excerpt_file, 
                                        "digest_vols": digest_vols})
    @action
    def sample(
        self,
        info: Annotated[Any, "the json info to run the function"],
        lap: Annotated[int, "the sample lap of the function"]
    ) -> ActionResult:
        """Copy results for the current container to storage"""
        amews = AMEWS()
        new_info = amews.AS_sample(info, lap)
        log_file = os.path.join(amews.ld.dir, amews.ld.log)
        excerpt_file_name = "%s.csv" % amews.ld.asl.excerpt_name
        excerpt_file = os.path.join(amews.ld.dir, excerpt_file_name)
        digest_vols_name = amews.ld.asl.digest_vol_name
        digest_vols =  os.path.join(amews.ld.dir, digest_vols_name)
        amews.PAL_start
        amews.PAL_sample
        amews.PAL_finish
        return ActionSucceeded(data={"info": new_info}, files={
                                        "raw_log": log_file, 
                                        "excerpt_log": excerpt_file, 
                                        "digest_vols": digest_vols})


   @action
    def full_sequence(
        self,
    ) -> ActionResult:
        """Copy results for the current container to storage"""
        amews = AMEWS()
        new_info = amews.PAL_blank(amews.to_json())
        log_file = os.path.join(amews.ld.dir, amews.ld.log)
        excerpt_file_name = "%s.csv" % amews.ld.asl.excerpt_name
        excerpt_file = os.path.join(amews.ld.dir, excerpt_file_name)
        digest_vols_name = amews.ld.asl.digest_vol_name
        digest_vols =  os.path.join(amews.ld.dir, digest_vols_name)
        amews.full_sequence
        return ActionSucceeded(data={"info": new_info}, files={
                                        "raw_log": log_file, 
                                        "excerpt_log": excerpt_file, 
                                        "digest_vols": digest_vols})




if __name__ == "__main__":
    PAL_node = PALNode()
    PAL_node.start_node()