import PAL_protocol_types
import math
import string
from AMEWS_types import AMEWS_tube


def generate_PAL_protocol(first_run: bool, num_cells: int = 44, input_chemicals = [], cell_volumes = [], starting_cell=0, total_samples=0, current_samples=0, aliquots = [25], sampling_delay=5):
    num_trays = 6
    tube_rack_info = {}
    reagent_fill_volume = 2000
    full_tube_volume = 2500
    sample_volume = 250
    fill_delay = 10

    if first_run:
        name = "AMEWS PAL 44 Cells Initialize and Sample"
    else:
        name = "AMEWS PAL 44 Cells Sample"
    
    if input_chemicals == []:
        input_chemicals =  ["mixture_1", "mixture_2", "mixture_3", "mixture_4", "mixture_5", "mixture_6"]
    
    tray_locations = [
        "Tray Holder 1",
        "Tray Holder 2",
        "Tray Holder 3",
        "Tray Holder 4",
        "Tray Holder 5",
        "Tray Holder 6"
    ]
    pal_input_cells = ["A1", "A2", "B1", "B2"]
    pal_output_cells = ["C1", "C2", "D1", "D2"]
    tube_rack_cells = []
    for i in range(0, 6):
        for j in range(1, 16):
            tube_rack_cells.append(string.ascii_uppercase[i] + str(j))

    protocol = PAL_protocol_types.PALProtocol(
        name=name,
        units="ul",
        trays={
            "ICP_rack": PAL_protocol_types.PALtray(name="ICP_rack", type="Rack 6x15 ICP robotic", rows=6, columns=15, deck_position="ICP Rack")
            }
        )

    for i in range(num_trays):
        tray_name = f"cell_tray_{i+1}"
        if i != 5:
            protocol.trays[tray_name] = PAL_protocol_types.PALtray(name=tray_name, type="Rack 2x4 Mina H-cell", rows=2, columns=4, deck_position=tray_locations[i])
        else:
            protocol.trays[tray_name] = PAL_protocol_types.PALtray(name=tray_name, type="Rack 2x2 Mina H-cell with tubes", rows=2, columns=2, deck_position=tray_locations[i])
        protocol.actions.append(
         PAL_protocol_types.PALStir(target=tray_name, rate=100)
     )
        for j in range(len(pal_output_cells)):
            protocol.actions.append(
                PAL_protocol_types.PALDispense(source="standard", target=tray_name, cell=pal_output_cells[j], volume=10000)
            )
            protocol.actions.append(
                PAL_protocol_types.PALDispense(source="standard", target=tray_name, cell=pal_input_cells[j], volume=10000)
            )

    cell_index = 0
    #eli said position 5 with the vials will contain the input chemicals
    #in the input file, there are 6 mixtures, however on PAL there are 20 vials
    #easy to change
    if first_run:
        for i in range(len(input_chemicals)):
            number = (i + 1) % 3
            if i > 2:
                icell = "B" + str(number)
            else:
                icell = "A" + str(number)
        protocol.trays["source_tray"] =  PAL_protocol_types.PALtray(name="source_tray", type="Rack 2x4 20mL Vial", position="Position 1", source=True)
        
    """Blank Samples"""
    for i in range(0, num_cells + 4):
            if i == 41 or i == 42 or i == 43 or i == 44:
                continue
            cell_tray = f"cell_tray_{(i / 8) + 1}"
            source_cell = pal_output_cells[i % 8]
            target_cell = tube_rack_cells[cell_index]
            protocol.actions.append(
                PAL_protocol_types.PALDispense(source="solvent", target="ICP_rack", cell=target_cell, volume=full_tube_volume-sample_volume)
            )
            protocol.actions.append(
            PAL_protocol_types.PALTransfer(source_tray=cell_tray, target_tray="ICP_rack", source_well=source_cell, target_well=target_cell, volume=sample_volume)
                )
            protocol.actions.append(
                PAL_protocol_types.PALDispense(source="solvent", target=cell_tray, cell=source_cell, volume=sample_volume)
            )
            tube_rack_info[target_cell] = AMEWS_tube(cell=target_cell, type="Blank", sampled_tray=cell_tray, sampled_cell=source_cell)
            cell_index += 1


    """Fill Reagents"""
    for i in range(len(cell_volumes + 4)):
        if i == 41 or i == 42 or i == 43 or i == 44:
            continue
        tray = f"cell_tray_{math.floor(i / 8)+1}"
        cell = pal_input_cells[i % 8]
        output_cell = pal_output_cells[i % 8]
        filled_volume = 0
        total_fill_volume = len(cell_volumes[i])*reagent_fill_volume
        for chemical, volume in cell_volumes[i].items():
            protocol.actions.append(
            PAL_protocol_types.PALDispense(source="solvent", target=tray, cell=cell, volume=reagent_fill_volume-volume)
            )
            protocol.actions.append(
            PAL_protocol_types.PALDispense(source=chemical, target=tray, cell=cell, volume=volume)
            )
            filled_volume += reagent_fill_volume
        if filled_volume < total_fill_volume:
            protocol.actions.append(
            PAL_protocol_types.PALDispense(source="solvent", target=tray, cell=cell, volume=total_fill_volume-filled_volume)
            )
        protocol.actions.append(
            PAL_protocol_types.PALDispense(source="solvent", target=tray, cell=output_cell, volume=total_fill_volume)
            )

        protocol.actions.append(
            PAL_protocol_types.PALDelay(target="cell_tray_1", delay=fill_delay)
            )
        """Calibrate"""
        for i in range(0, num_cells + 4):
                if i == 41 or i == 42 or i == 43 or i == 44:
                    continue
                for aliquot in aliquots:
                    target_cell = tube_rack_cells[cell_index]
                    source_cell = pal_input_cells[i % 8]
                    cell_tray = f"cell_tray_{math.floor(i / 8)+1}"
                    protocol.actions.append(
                        PAL_protocol_types.PALDispense(source="solvent", target="ICP_rack", cell=target_cell, volume=full_tube_volume-aliquot)
                    )
                    protocol.actions.append(
                        PAL_protocol_types.PALTransfer(source_tray=cell_tray, target_tray="ICP_rack", source_well=source_cell, target_well=target_cell, volume=aliquot)
                    )
                    protocol.actions.append(
                        PAL_protocol_types.PALDispense(source="solvent", target=cell_tray, cell=source_cell, volume=aliquot)
                    )
                    tube_rack_info[target_cell] = AMEWS_tube(cell=target_cell, type="Calibrate", sampled_tray=cell_tray, sampled_cell=source_cell)
                    cell_index += 1
    while cell_index < len(tube_rack_cells) and current_samples < total_samples:
        for i in range(starting_cell, num_cells):
                if cell_index >= len(tube_rack_cells) or current_samples >= total_samples:
                    break
                target_cell = tube_rack_cells[cell_index]
                source_cell = pal_output_cells[i % 8]
                cell_tray = f"cell_tray_{math.floor(i / 8)+1}"
                protocol.actions.append(
                    PAL_protocol_types.PALDispense(source="solvent", target="ICP_rack", cell=target_cell, volume=full_tube_volume-sample_volume)
                )
                protocol.actions.append(
                    PAL_protocol_types.PALTransfer(source_tray=cell_tray, target_tray="ICP_rack", source_well=source_cell, target_well=target_cell, volume=sample_volume)
                )
                protocol.actions.append(
                    PAL_protocol_types.PALDispense(source="solvent", target=cell_tray, cell=source_cell, volume=sample_volume)
                )
                
                tube_rack_info[target_cell] = AMEWS_tube(cell=target_cell, type="Sample", sampled_tray=cell_tray, sampled_cell=source_cell)
                next_cell = i + 1
                cell_index += 1
                current_samples += 1
        if cell_index < len(tube_rack_cells) and current_samples < total_samples:
          protocol.actions.append(
                    PAL_protocol_types.PALDelay(target=cell_tray, delay=sampling_delay)
                )
          next_cell = 0
        starting_cell = 0
        
    return protocol, tube_rack_info, next_cell, current_samples

