from typing import Optional
import pandas as pd
from pydantic import BaseModel
import string
from PAL_protocol_types import PALProtocol
class LiquidStep(BaseModel):
    type: str
    location: str
    row: Optional[str]
    column : Optional[int] 
    timestamp: str
    volume: float

def read_logs(log_file: str):
    with open(log_file) as f:
        log_data = pd.read_csv(f, sep="\t")
    log_data = log_data.fillna("")
    filtered_logs = log_data[(log_data["Action"] == "Move Arm To Substrate") | ( log_data["Parameter Name"].str.contains("Output : Volume" ))]
    current_location = None
    current_row = None
    current_column = None
    steps = []
    for index, row in filtered_logs.iterrows():
        if row["Action"] == "Move Arm To Substrate":
            if row["Parameter Name"] == "Input : Position":
                current_location = row["Parameter Value"]
            if row["Parameter Name"] == "Input : Well Row":
                if row["Parameter Value"] is not "":
                    current_row = string.ascii_uppercase[int(row["Parameter Value"])  - 1]
                else:
                    current_row = None
            if row["Parameter Name"] == "Input : Well Column":
                if row["Parameter Value"] is not "":
                    current_column = row["Parameter Value"]
                else:
                    current_column = None
        elif row["Parameter Name"] == "Output : Volume Filld" or row["Parameter Name"] == "Output : Volume Dispensed":
            steps.append(LiquidStep(type="dispense", location=current_location, row=current_row, column=current_column, timestamp=row["Time"], volume=row["Parameter Value"]))
        elif row["Parameter Name"] == "Output : Volume Aspirated":
            steps.append(LiquidStep(type="aspirate", location=current_location, row=current_row, column=current_column, timestamp=row["Time"], volume=row["Parameter Value"]))
    return steps
def add_timestamps(steps: list, protocol: PALProtocol):
    step_index = 0
    for step in protocol.actions:
        if step.action_type == "transfer" or step.action_type == "dispense" and "SkipMap" not in step.tags:
            while step_index < len(steps) and step.dispense_timestamp is None:
                compare_step = steps[step_index]
                if compare_step.row is not None and compare_step.column is not None:
                    well = compare_step.row + str(compare_step.column)
                else:
                    well = None
                if step.action_type == "transfer" and compare_step.type == "aspirate" and step.source_well == well and compare_step.location == protocol.plates[step.source_plate].deck_position and step.volume == compare_step.volume:
                    step.aspirate_timestamp = compare_step.timestamp
                if step.action_type == "dispense" or (step.action_type == "transfer" and step.aspirate_timestamp is not None) and compare_step.type == "dispense" and step.target_well == well and compare_step.location == protocol.plates[step.target_plate].deck_position and step.volume == compare_step.volume:
                    step.dispense_timestamp = compare_step.timestamp
                step_index += 1
    return protocol
                    



        

        