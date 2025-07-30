import sys, clr, os, math, re, random, string, time
import smtplib, cv2, threading, keyboard, shutil
import pandas as pd
import numpy as np
from datetime import datetime


from pytz import NonExistentTimeError
from System import Int32


user = os.getlogin()
sys.path.append('C:/Users/%s/Dropbox/Instruments cloud/Robotics/Unchained BK/AS Scripts/API Scripts' % user)


from CustomService import *
from CustomSequence import *


#sys.path.append(os.path.abspath("C:/Users/%s/Dropbox/Instruments cloud/Robotics/PAL3 System/Machine Vision liquids/HeinSight" % user))
#from classifier import MV_LLE


sys.path.append(os.path.abspath("C:/Users/%s/Dropbox/Instruments cloud/Robotics/PAL3 System/Integration/Driver" % user))
from PAL3_driver import *




#######################################################################################################################


# IN is the sample collection side of the permeation cells
# OUT is the feed side of the permeation cells
# the wells are A1, A2, B1, B2, indexing is X direction
# for ICP rack indexing is Y direction


class AMEWS:


    def __init__(self):


        self.verbose = 1
        self.simulator = True # PAL simulator
        self.cont = False # continue a previous run


        self.pal = None # PAL class
        self.path = os.getcwd()
        self.user = os.getlogin()
        self.num_cells = 4


        self.ICP_area = "*" # first row fill, use "*" or "full" for full rack 
        self.ICP_rack = None # ICP rack name


        self.sources = "PAL_AMEWS_24cell_input.csv"
        self.fills =   "PAL_AMEWS_24cell_fill.csv"  # put None for default filling
        self.rack = 90 # 90 tube rack
        self.blank = True # collect red side blanks first
        self.load = True # load solvent into cells
        self.load_delay = 0 # delay after loading, hours
        self.volume = 100 # ul sampling of the red side
        self.fill = 1000 # uL if there is no fill map
        self.volume_sample = 31.5 # mL volume of the cell on the sample side
        self.volume_feed = 18.7 # mL volume of the cell on the feed side
        self.std_conc = 30 #concentration of the standard (yittrium)
        self.unit = "ppm" # unit of concentration
        self.chaser = 2350 # uL chaser
        self.delay = 0.10 # minutes to wait after each sampling
        self.laps = 3 # laps of sample collection
        self.calibrate = 50 # uL aliquots for calibrations - adjust
        self.last_container = {} # sample container


        self.check_volumes()
        self.null_prep()
        self.start_sequence()


    def check_volumes(self):


        self.syringe2 = 2500 # uL the volume of syringe in LS2


        if self.fill > self.syringe2:
            self.fill = self.syringe2
            print(">> Adjusted fill volume to %.1f ul\n\n" % self.fill)


        if self.volume > self.syringe2:
            self.volume = self.syringe2
            print(">> Adjusted fill volume to %.1f ul, no chaser\n\n" % self.volume)


        if self.chaser > self.syringe2:
                self.chaser = self.syringe2
                print(">> Adjusted chaser volume to %.1f ul\n\n" % self.chaser)


    def null_prep(self):
        self.prep = 0 # holds the initial fill tm.mapping offset
        self.prep_container = {} # pre-sample containers
        self.last_cell = 0

    def start_sequence(self): # start a sequence of experiments
        if self.cont:
            return 0
        now = datetime.now()
        stamp = now.strftime('%Y%m%d_%H%M%S')
        self.master_log = []
        self.null_prep()
        self.COUNT =0 # counter of LS calls
        self.last_cell = 0   # offset of the first cell to fill
        return 1


# ================================ json serialization =================================


    def to_json(self):


        now = datetime.now()
        stamp = now.strftime('%Y%m%d_%H%M%S')


        j = {
            # specific to 24-cell experiment with PAL3 robot
            "load" : self.load, # whether to fill the cells with solvent
            "load equilibration" : self.load_delay, # equilibration time after loading, hours
            "farm": self.pal.farm.to_json(orient='records', lines=False), # cell farm, # cell farm map
            "cell number" : self.num_cells, # total number of cells
            "last cell" : self.last_cell, # used to continue runs
            "continue" : self.cont, # continue a run
            "sources": self.sources, # name of the input source file
            "ICP area": self.ICP_area, # ICP rack area, deafualt is full
            "ICP rack" : self.ICP_rack, # ICP rack name
            "fills": self.fills, # name of the input fill file
            "path": self.path, # work directory
            "calibrate": self.calibrate, # calibration volume, uL
            "rack": self.rack,
            "blank": self.blank,
            "standard concentration": self.std_conc,
            "unit concentration": self.unit,
            "fill": self.fill,
            "volume": self.volume,
            "volume cell sample" : self.volume_sample,
            "volume cell feed" : self.volume_feed,
            "chaser": self.chaser,
            "delay": self.delay,
            "laps": self.laps,
            "prep": self.prep, # last rack offset
            "prep_container": self.prep_container, # last prep container
            "last_container": self.last_container, # last sample container
            "master log": self.master_log,
            "COUNT": self.COUNT, # last experiment count
            "simulator" : self.simulator,  # if True simulate run


            # PAL attributes
            "project" : self.pal.project,   # PAL project file
            "category" : self.pal.category, # task category
        }


        u = os.path.join(self.exp, "%s_%s.json" % (self.pal.category, stamp))
        with open(u, 'w') as f:
           json.dump(j, f, indent=4)
        return j


    def from_json(self, j):
        # Populate the class instance from the JSON data (dictionary)


        now = datetime.now()
        stamp = now.strftime('%Y%m%d_%H%M%S')


        # folders 
        if self.verbose: 
            print("\n>> JSON input: %s\n" % j)


        self.cont = j.get("continue", False) # resume previous run
        self.path = j.get("path", os.getcwd())


        # cell information 
        self.load = j.get("load", False)
        self.load_delay = j.get("load equilibration", 2)
        self.num_cells = j.get("cell number", 2)
        self.last_cell = j.get("last cell", 0)
        
        self.ICP_area = j.get("ICP area", "full")
        self.ICP_rack = j.get("ICP tray", "Tray Holder 2:Slot1")
        self.sources = j.get("sources")
        self.fills = j.get("fills")


        self.volume = j.get("volume", 250)
        self.volume_sample = j.get("volume cell sample", 3e4)
        self.volume_feed = j.get("volume cell feed", 2e4)
        self.calibrate = j.get("calibrate", 0)
        self.rack = j.get("rack", 90)
        self.blank = j.get("blank", True)
        self.std_conc = j.get("standard concentration", 10)
        self.std_conc = j.get("unit concentration", "mM")
        self.fill = j.get("fill", 1000)
        self.chaser = j.get("chaser", 2500)
        self.delay = j.get("delay", 0)
        self.laps = j.get("laps", 3)


        self.prep = j.get("prep", 0)
        self.prep_container = j.get("prep_container", {})
        self.last_container = j.get("last_container", {})
        self.master_log = j.get("master log", [])
        self.COUNT = j.get("COUNT", 0)
        self.simulator = j.get("simulator", False)


        # setting PAL attributes 
        if self.pal:
            self.pal.project = j.get("project", None)
            if self.pal.project:
                self.pal.set_project(self.pal.project)
            self.pal.farm = None
            u = j.get("farm", None)
            if u: self.pal.farm = pd.read_json(u)




##################################################################################################################


    def PAL_start(self):  # start sequence
        if not self.pal: 
            self.pal = PALService() 
        self.pal.num_cells = self.num_cells
        self.pal.verbose = self.verbose
        self.pal.tracker.unit = self.unit
        self.pal.std_start("run24_AMEWS")
        if not self.pal.project: 
            self.pal.set_project()
        self.pal.simulator = self.simulator
        self.pal.list_all_modules()


        self.pal.rack={}


        rack = self.pal.set_rack('Tray Holder 8', 3, 'Shell4x5', 'Shell4ml')
        self.pal.ID_rack(rack, "source")


        if self.rack==90: 
            self.ICP_rack = self.pal.set_rack('Tray Holder 2', 1, 'ICP90', 'Tube 13 mm')
        if self.rack==60:


            self.ICP_rack = self.pal.set_rack('Tray Holder 3', 1, 'ICP60', 'Tube 16 mm')


        self.pal.ID_rack(self.ICP_rack, "ICP2")


        self.pal.map_farm(False)


        self.start_sequence()
        self.calibration = self.volume/2


        if self.verbose:
            print("\n>> ICP2 is rack type %s, vial type %s" % (self.ICP_rack.type,
                                                             self.ICP_rack.vialtype))
        self.pal.tm.lib_to=[]
        if self.ICP_rack:
            self.pal.tm.add_to(self.ICP_rack, self.ICP_area)


        print("\n>> Time stamped digest written to %s" % self.pal.digest)


        self.pal.tracker.add("solvent", 
                             name="solvent")


        self.pal.tracker.add("standard", 
                             name="standard", 
                             elements=["Y"], 
                             concentrations=[self.std_conc])


        self.pal.write_json(self.pal.racks, "substrates")


        return self.to_json()


    def PAL_finish(self): # end sequence
        self.expand_time_log()
        self.seq = CustomSequence(self.pal.project)
        self.seq.consolidate_PAL_records()
        self.pal.finish()


    def do_title(self, name=""):
        if not name: 
            name = self.pal.category
        print("\n\n")
        print("#" * 80)
        print("#\t\tPAL3 for AMEWS %s" % name)
        print("#" * 80)
        print("\n\n")




################################################## experiment sequence ###########################################################################


    def PAL_load(self): # loading cells with the standard 


       self.pal.category = "load1"
       self.do_title()
       self.pal.tstamp = self.pal.stamp()
       self.start = self.pal.stamp()


       if not self.simulator:
           self.pal.activate_ls2()
           self.pal.activate_dil1()


       for c in range(self.num_cells):


            r = self.pal.index2farm(c+1, "out") # feed side
            t = (r["holder"], r["slot"], r["well"])
            address = "Tray Holder %d:Slot%d:%d" % t


            if not self.simulator: 
                self.pal.move2vial(*t)
                self.pal.eh.PenetrateObject(self.pal.vial)
                self.pal.dil_deliver(self.volume_feed) # load green (feed) compartments
                self.pal.tstamp = self.pal.stamp()
                self.pal.eh.LeaveObject()
            else:
                self.pal.tuple2vial(*t)


            self.pal.update_tracking("standard", self.pal.vial, self.volume_feed*1e3, 0)
            print(">> %s :: loaded feed side of cell %d at %s with %.2f mL standard" % (self.pal.tstamp, 
                                                                                         c+1, 
                                                                                         address, 
                                                                                         self.volume_feed)
                  )


            r = self.pal.index2farm(c+1, "in")
            t = (r["holder"], r["slot"], r["well"])
            address = "Tray Holder %d:Slot%d:%d" % t


            if not self.simulator: 
                self.pal.move2vial(*t)
                self.pal.eh.PenetrateObject(self.pal.vial)
                self.pal.dil_deliver(self.volume_sample) # load green (feed) compartments
                self.pal.tstamp = self.pal.stamp()
                self.pal.eh.LeaveObject()
            else:
                self.pal.tuple2vial(*t)


            self.pal.update_tracking("standard", self.pal.vial, self.volume_sample*1e3, 0)


            print(">> %s :: loaded sample side of cell %d at %s with %.2f mL standard" % (self.pal.tstamp,
                                                                                           c+1, 
                                                                                           address, 
                                                                                           self.volume_sample)
                  )






       return self.housekeeping(False)


# =======================================================================================


    def PAL_blank(self): # collection of blank samples from the red side


        if not self.blank: return 0
        self.start = self.pal.stamp()


        if not self.simulator:
           self.pal.activate_ls2()


        self.pal.clean_wash()


        self.pal.category = "blank1"
        self.do_title()
        self.tstamp = self.pal.stamp()
        self.prep = 0


        for c in range(self.num_cells):


            r = self.pal.index2farm(c+1, "in")
            t = (r["holder"], r["slot"], r["well"])
            address_from = "Tray Holder %d:Slot%d:%d" % t


            vial_from = self.pal.set_vial(address_from)
            rack_to, well_to, _ = self.pal.tm.lib_to[self.prep]
            cell_to = self.pal.tm.well2cell(self.pal.racks[rack_to], well_to)
            address_to = "%s:%d" % (rack_to, cell_to)
            vial_to = self.pal.set_vial(address_to)


            kwargs = {"vial_from" : vial_from, 
                    "vial_to" : vial_to, 
                    "Volume" : self.volume,
                    "Chaser" : self.chaser,
                    "Replace" : True }


            self.pal.quick_transfer(**kwargs)


            print("\n>> (%d) %s :: blank from cell %d at %s: volume = %d uL, chaser=%d uL " % (self.prep+1, 
                                                                                            self.pal.tstamp, 
                                                                                            c+1, 
                                                                                            address_from, 
                                                                                            self.volume, 
                                                                                            self.chaser)
                                                                                            )


            print("===> moved to ICP well %s at %s " % (well_to, address_to))


            self.prep += 1


        return self.housekeeping()


#=============================================================================================================




    def PAL_fill(self, index=1):


        self.do_title("fill & calibrate")
        self.tstamp = self.pal.stamp()
        self.start = self.pal.stamp()


        f = os.path.join(self.path, self.sources)
        fc = os.path.join(self.pal.project, self.sources)
        shutil.copy(f, fc)
        self.pal.log_input(f)


        f = os.path.join(self.path, self.fills)
        fc = os.path.join(self.pal.project, self.fills)
        shutil.copy(f, fc)


        try:
            df = pd.read_csv(f)
        except:
            print("No fill file found, abort")
            sys.exit(0)


        df = df.fillna(0)
        u = df[["group", "well"]].drop_duplicates().values.tolist()


        print("\n>> Fill matrix:\n%s\n" % df)


        for grp, well in u:
            self.pal.category = "fill%d" % index
            holder, slot, cell, c = self.pal.farm2address(grp, well, "out") # feed side
            if not cell: 
                continue
            rack = "Tray Holder %d:Slot%d" % (holder, slot)
            ID_to = "%s:%d" % (rack, cell)
            print("\n -------------- Dispensing to %s, %s :: %s ---------------\n" % (grp, well,ID_to))
            vial_to = self.pal.set_vial(ID_to)
            total = 0
            for col in df.columns:
                if col in self.pal.source:
                    for _, row in df.iterrows():
                        volume = float(row[col])
                        if volume and grp == row["group"].strip() and well ==  row["well"].strip():
                                total += volume
                                ID_from = self.pal.source[col]
                                vial_from = self.pal.set_vial(ID_from)


                                kwargs = {"vial_from" : vial_from, 
                                        "vial_to" : vial_to, 
                                        "Replace" : True,
                                        "Volume" : volume }


                                self.pal.quick_withdraw(**kwargs)


                                print("+++ added %.1f uL of %s from %s" % (volume, col, ID_from))


            if total: 
                print("\n (%d) filled cell %d to total volume %.1f uL for farm cell %s, %s => %s\n" % 
                            (self.prep+1, c, total, grp, well, ID_to))


            if not self.simulator: 
                time.sleep(60) # 1 min delay for stirring


            if self.calibrate: 
                self.pal.category = "calibrate%d" % index
                address_from = ID_to
                vial_from = self.pal.set_vial(address_from)


                rack_to, well_to, _ = self.pal.tm.lib_to[self.prep]
                r = self.pal.racks[rack_to]
                cell_to = self.pal.tm.well2cell(r, well_to)
                address_to = "%s:%d" % (rack_to, cell_to)
                vial_to = self.pal.set_vial(address_to)


                kwargs = {"vial_from" : vial_from, 
                        "vial_to" : vial_to, 
                        "Volume" : self.calibrate,
                        "Chaser" : self.chaser,
                        "Replace" : True }


                self.pal.quick_transfer(**kwargs)


                print(">> (%d) %s :: calibration sample from cell %d at %s: volume = %d uL, chaser=%d uL " % ( self.prep+1,
                                                                                                self.pal.tstamp, 
                                                                                                c+1, 
                                                                                                address_from, 
                                                                                                self.calibrate, 
                                                                                                self.chaser
                                                                                                )
                      )


                print("===> moved to ICP well %s at %s " % (well_to, address_to))


                self.prep += 1


        self.pal.category = "fill%d" % index
        self.housekeeping(False)
        self.pal.save_samples("fill%d" % index)
        self.pal.category = "calibrate%d" % index
        return self.housekeeping()


#=============================================================================================================


    def PAL_sample(self, lap=0):


        ID = lap+1
        self.start = self.pal.stamp()


        self.pal.category = "rack%d" % ID
        self.do_title()


        if lap: self.prep = 0
        flag = 1


        while(flag): 
            self.pal.tstamp = self.pal.stamp()
            for c in range(self.num_cells):
                if self.prep == len(self.pal.tm.lib_to): 
                    flag = 0
                    break
                q = self.last_cell+1
                r = self.pal.index2farm(q, "in")
                t = (r["holder"], r["slot"], r["well"])
                address_from = "Tray Holder %d:Slot%d:%d" % t
                vial_from = self.pal.set_vial(address_from)
                rack_to, well_to, _ = self.pal.tm.lib_to[self.prep]
                cell_to = self.pal.tm.well2cell(self.pal.racks[rack_to], well_to)
                address_to = "%s:%d" % (rack_to, cell_to)
                vial_to = self.pal.set_vial(address_to)


                kwargs = {"vial_from" : vial_from, 
                        "vial_to" : vial_to, 
                        "Volume" : self.volume,
                        "Chaser" : self.chaser,
                        "Replace" : True }


                self.pal.quick_transfer(**kwargs)


                print("\n>> %s :: collected from cell %d at %s: volume = %d uL, chaser=%d uL " % (self.tstamp, 
                                                                                                q, 
                                                                                                address_from, 
                                                                                                self.volume, 
                                                                                                self.chaser
                                                                                                )
                      )


                print("===> moved to ICP well %s at %s " % (well_to, address_to))


                self.last_cell = q % self.num_cells
                self.prep += 1


        self.waste = self.pal.tracker.waste_bill(self.pal.tracker.samples)
        self.waste.to_csv(os.path.join(self.pal.project,"waste_ondeck_%d.csv" % ID), index=True)
        self.pal.save_samples("samples_rack%d" % (lap+1))
        return self.housekeeping(ID=ID)


###########################################################################################################################




    def housekeeping(self, opt=True, ID=""): # if True make ICP2 container, optional ID


        self.stop = self.pal.stamp()
        dt = datetime.strptime(self.stop, "%Y%m%d_%H%M%S")
        dt -= datetime.strptime(self.start, "%Y%m%d_%H%M%S")
        dt = round(dt.total_seconds()/60, 2)


        self.pal.last_code = None
        self.pal.last_barcode = None


        if opt: 
            r = self.pal.racks[self.ICP_rack.name]
            r.ID = "ICP2"
            c = self.pal.make_container(r)
            self.pal.save_container(c)
            self.last_container = c


        q = {"ID" : ID,
             "category" : self.pal.category,
             "container" : self.pal.last_code,
             "barcode" : self.pal.last_barcode,
             "AS log" : "time_log.csv",
             "start" : self.start,
             "stop" :  self.stop,
             "tmin" : dt}


        self.master_log.append(q)
        self.renew_PAL_log()


        return self.to_json()


    def renew_PAL_log(self):
        f = os.path.join(self.pal.project, "sequence_log.csv")
        df = pd.DataFrame(self.master_log)
        df.to_csv(f, index=False)
        print("\n>> Saved master log in %s\n" % f)
        print(df)




    def full_sequence(self): # example of the full sequence without external calls


        if not self.cont:
            self.PAL_start()


            if self.load: # optional loading of the cells with the solvent
                info = self.PAL_load() # load
                time.sleep(3600*self.load_delay) # delay after load


            info = self.PAL_blank()
            info = self.PAL_fill()


            for lap in range(self.laps):
                print("\n\n################################# Sampling lap %d ######################################\n\n" % (lap+1))
                info = self.PAL_sample(lap)
                time.sleep(60*self.delay)


        self.PAL_finish()


    def find_rack_container(self, dm, i):
        for _, r in dm[i:].iterrows():
            if 'rack' in r['category']:
                return r['container']
        self.dm.loc[i, 'container']


    def expand_time_log(self):


        f = os.path.join(self.pal.project,"time_log.csv")
        df = pd.read_csv(f)


        f = os.path.join(self.pal.project,"sequence_log.csv")
        dm = pd.read_csv(f)


        rs = []
        self.t0 = {}
        self.c0 = {}
        fill = ""


        df = df.rename(columns={'well_from': 'pos_from'})
        df = df.rename(columns={'well_to': 'pos_to'})


        for _,r in df.iterrows():
            dt = datetime.strptime(r["datetime"], "%Y%m%d_%H%M%S")
            category = r["category"]
            i = dm[dm['category'] == category].index[0]
            m = dm.loc[i]
            container = self.find_rack_container(dm, i)
            if np.isnan(r["pos_from"]):
                address_from = "%s" % r["rack_from"]
            else:
                address_from = "%s:%d" % (r["rack_from"], r["pos_from"])
            if np.isnan(r["pos_to"]):
                address_to = "%s" % r["rack_to"]
            else: 
                address_to = "%s:%d" % (r["rack_to"], r["pos_to"])


            q = {}
            q["sample"] = None
            q["library"] = None
            q["container"] = container
            q["barcode"] = m["barcode"]
            q["category"] = category
            q["feed"] = "fill1"
            q["index"] = None
            q["datetime"] = r["datetime"]
            q["volume"] = r["volume"]
            q["chaser"] = r["chaser"]
            q["address from"] = address_from
            q["address to"] = address_to
            q["plate from"] = None
            q["well from"] = None
            q["plate to"] = None
            q["well to"] = None
            q["th"] = np.nan


            if r["rack_from"] in self.pal.racks:
                rack_from = self.pal.racks[r["rack_from"]]
                q["well from"] = self.pal.tm.cell2well(rack_from, r["pos_from"])
                q["plate from"] = rack_from.ID


            rack_to = self.pal.racks[r["rack_to"]]
            q["well to"] = self.pal.tm.cell2well(rack_to, r["pos_to"])
            q["plate to"] = rack_to.ID


            if "ICP" in rack_to.ID:
                cell, group = self.pal.address2farm(address_from)
                if cell: 
                    q["index"] = cell
                    q["sample"] = "%s-PAL1-%s" % (container, q['well to'])


            if "fill" in category:
                    if category != fill:
                        fill = category
                        g = os.path.join(self.pal.project,"%s.csv" % fill)
                        if os.path.exists(g): 
                            with open(g, 'r') as j:
                                self.c0[fill] = json.load(j)


            if "fill" in category or "load" in category:
                    cell, group = self.pal.address2farm(address_to)
                    if cell:
                        q["index"] = cell
                        self.t0[cell] = dt


            if fill: q["feed"] = fill


            rs.append(q.copy())


        print("\n\n>> Took t0 from cell fill record")
        for c, dt in self.t0.items():
                print("--- t0 for cell %d = %s" % (c, dt))


        df  = pd.DataFrame(rs)


        for i, r in df.iterrows():
            c = r["index"]
            if c in self.t0:
                dt = datetime.strptime(r["datetime"], "%Y%m%d_%H%M%S")
                dt -= self.t0[c]
                df.loc[i, "th"] = dt.total_seconds()/3600


        f = os.path.join(self.pal.project,"extended_time_log.csv")
        df.to_csv(f, index=False)




###############################################################################################################################


def PAL_consolidate():
        seq = CustomSequence()
        seq.consolidate_PAL_records()




if __name__ == "__main__":


     x1 = AMEWS()
     x1.ICP_area = "*1"
     x1.full_sequence()


     #PAL_consolidate()


     #x1.PAL_load()
     #x1.PAL_fill()
     #x1.PAL_sample()


#  short sampling protocol for testing 
     #x1.ICP_area = "A1:A6"
     #x1.PAL_sample_first()
