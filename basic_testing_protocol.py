import json
from PAL_protocol_types import PALProtocol, PALtray, PALDelay, PALHome, PALMove
import math
import string

protocol = PALProtocol(name="test")
protocol.trays = {
    
            "ICP_rack": PALtray(name="ICP_rack", type="Rack 6x15 ICP robotic", cells=2, position="ICP Rack")
            
}

protocol.actions.append(
 PALDelay(delay=2)   
)
protocol.actions.append(PALHome())

protocol.actions.append(PALMove(tray=1, slot=1, position=1))

protocol.actions.append(PALHome())

with open("test.json", "w") as f:
    json.dump(protocol.model_dump(mode="json"), f)