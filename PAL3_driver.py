from itertools import count
from pickle import TRUE
from sre_parse import State
import sys, clr, os, math, re, random, string, time, json
import socket, psutil
import pandas as pd
import numpy as np
from datetime import datetime
import smtplib
import cv2 # for capturing images using OpenCV
import threading, keyboard 
from System import Int32

user = os.getlogin()
sys.path.append(os.path.abspath("C:/Users/%s/Dropbox/Instruments cloud/Robotics/PAL3 System/Machine Vision liquids/HeinSight" % user))
from classifier import MV_LLE

sys.path.append(os.path.abspath("C:/Users/%s/Dropbox/Instruments cloud/Robotics/Unchained BK/AS Scripts/API Scripts" % user))
from CustomTracker import CustomTracker
from ContainerManager import CustomDispatch
from ContainerManager import CustomBarcode

def class_contents(c):
    print("\nContents for class %s" % c)
    d = dir(c)

    for item in d:
        if not item.startswith("__"):  
            try: 
                if callable(getattr(c, item)):
                    print(f"Function: {item}()")
            except:
                print(f"Unclassified: {item}")
            
    for item in d:
        if not item.startswith("__"):  
            try: 
                if not callable(getattr(c, item)):
                    value = getattr(c, item)
                    print(f"Attribute: {item}: {value}")
            except:
                pass

class PALImage: 

    def __init__(self):            
        self.cam = None # camera object
        self.image = None # image
        self.cropped = None # cropped image
        self.code = ""
        
        # set position for taking photos with a USB camera, mm
        self.X = 404
        self.Y = 175
        self.Z = 240

    def finish(self):
        self.cam.release()
        cv2.destroyAllWindows()

    def check_camera(self, camera): # check there is a camera
        self.cam = cv2.VideoCapture(camera)
        if self.cam.isOpened(): return True
        else: return False
      
    def find_camera(self):
        for i in range(4):
            if self.check_camera(i): 
                print(">> Found active camera %d" % i)
                return i
        print(">> No active cameras found")
        return -1  
    
    def active_cameras(self):
        for i in range(2):
             cap = cv2.VideoCapture(i)
             if cap.isOpened(): 
                  name = cap.get(cv2.CAP_PROP_FOURCC) 
                  width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                  height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                  fps = cap.get(cv2.CAP_PROP_FPS)   
                  print(">> Camera%d : %s, %d x %d, %d frames/s" % (i, name, width, height, fps))

    def snapshot(self, camera): #take snapshot
        flag = 0
        self.image = None
        if self.check_camera(camera):
            result, self.image = self.cam.read()
            if not result:
                print(">> No image taken")
            else: flag=1
        else: 
            print(">> Camera %d not opened" % camera)
        self.cam.release()  
        return flag

    def read_barcode(self): # read barcode
      bd = cv2.barcode.BarcodeDetector()
      self.code = ""
      if self.image: 
           ret, code, _, _ = bd.detectAndDecode(self.image)
           if ret: self.code = str(code[0]) # first barcode 
           
    def read_QRcode(self): # read QR code
      qd = cv2.QRCodeDetector()
      self.code = ""
      if self.image: 
            ret, code, _, _ = qd.detectAndDecodeMulti(self.image)
            if ret: self.code = code[0] # first QR code 
      return None 
  
    def start_MV(self):
        self.ut = MV_LLE()  
        
    def flash_image(self, win, im):
        cv2.imshow(win, cv2.resize(im, (640, 480)))
        cv2.moveWindow(win, 100, 100)
        cv2.waitKey(5000) # 5s flash
        cv2.destroyWindow(win)

    def boundaries(self): # find horizontal and vertical boundaries
    
        horizontal = []
        vertical = []
    
        H, W = self.image.shape[:2]
        L = min(H,W)/10 # pixels min line
        self.image = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
        self.image = cv2.GaussianBlur(self.image, (5, 5), 0)
        edges = cv2.Canny(self.image, 50, 150)   
        lines = cv2.HoughLinesP(edges,
                            1, # distance resolution
                            np.pi/180, # angilar resolution
                            threshold=100, # min number of votes
                            minLineLength=L, # minimal length
                            maxLineGap=L/10) # minimal point gap 
    
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                if abs(y1-y2)/W<0.05:  # Check if the line is horizontal, show in red
                    y = (y1+y2)/2
                    cv2.line(self.image, (x1, y), (x2, y), (255, 0, 0), 2)
                    horizontal.append(y)
                if abs(x1-x2)/H<0.05:  # Check if the line is vertical, show in blue
                    x = (x1+x2)/2
                    cv2.line(self.image, (x, y1), (x, y2), (0, 255, 0), 2)
                    vertical.append(x)  
                
        data = {} 
        rh, rv = 0, 0
        h = np.array(horizontal.sort())
        v = np.array(vertical.sort())
        if h and len(h)>1: rh = h[-1]-h[0]
        if v and len(v)>1: rv = v[-1]-v[0]
        if rh and rv:
            self.cropped = self.image[h[0]:h[-1], v[0]:v[-1]]
            self.data["horizontal boundaries"] = h
            self.data["vertical boundaries"] = v
            self.data["widest horizontal gap"] = rh
            self.data["widest vertical gap"] = rv

class PALGripper(): # generic gripper class 
     
     def __init__(self):       
        self.used = False # True is gripper is deployed
        self.dir = 0 # direction of the grip move 0 - inward, 1 - outward
        self.state = 0 # 0 - closed, 1 - open
        
        self.width = 11 # mm, release distance: object diameter + 2 mm
        self.depth =   6 # mm, dipping towards the object
        self.before = 2 # mm, retraction before
        self.after = 5 # mm, retraction after - needs to clear the centrifuge
        self.release = 15 # mm, release height
        self.search = 30 # mm, Z-axis search
        
class PALAlert: # SMTP server alerts
    
    def __init__(self):
        self.server = "mailgateway.anl.gov"
        self.port = 25  # Common ports are 587 for TLS and 465 for SSL
        self.robot = 'PALSystem@anl.gov'
        self.to = "shkrob@anl.gov" # comma separated list
       
    def alert(self, subject="ALERT", body=None, importance=None):
        self.message = MIMEMultipart()
        self.message['From'] = self.robot
        self.message['To'] = self.to
        self.message['Subject'] = subject
        self.message['Body'] = body
        if importance:
             self.message['Importance'] = importance
        server = smtplib.SMTP(self.server, self.port)
        server.sendmail(self.robot, self.to, self.message.as_string())
        server.quit()

         
class PALRack:   # rack related class
    
    def __init__(self):  
        self.ID = "rack1"
        self.name = "" # rack address
        self.type = "" # rack type
        self.vialtype = "" # vial type - magnetic, NonMagnetic, Tube  etc,
        self.rows = 1 # number of rows
        self.cols = 1 # number of columns
        self.cells = 1 # number of cells/wells/vials
        self.orientation = 1 # 1 -  indexing by column (row by row), 2 - indexing by row (column by column)

    def to_dict(self):
        r={}
        r["name"] = self.name
        r["type"] = self.type
        r["vialtype"] = self.vialtype
        r["rows"] = self.rows
        r["cols"] = self.cols
        r["cells"] = self.cells
        r["orientation"] = self.orientation
        r["ID"] = self.ID
        return r

class PALSafe:   # safe movement around objects
    
    def __init__(self):        
        self.trays = [1] # Trays for restricted movement locations
        self.inside = False # True when in restricted movement locations
        
        self.X = 0 # safe absolute X, mm
        self.Z = 0 # safe absolute Y, mm
        self.Y = 0 # safe absolute Z, mm
        
        self.dX = -30 # mm safe X offset
        self.dY = 0
        self.dZ = -5
        
class PALLock:   # safe movement around objects
    
    def __init__(self, head):  
        from Ctc.Palplus.Integration.Driver import PalPlusResourceType, PalPlusResourceLockType
        if head == "left":
            self.name = "LeftHead"
            self.res =  PalPlusResourceType.LeftHead 
            self.type = PalPlusResourceLockType.LeftHead
        else:
            self.name = "RightHead"
            self.res =  PalPlusResourceType.RightHead 
            self.type = PalPlusResourceLockType.RightHead

class NMR_params:

    def __init__(self):    
        self.racks = []
        self.tube = None
        self.rack = None
        self.index = -1
        self.release = 20 # mm adapter opening for release
        self.search = 35 # mm for tube search (rack)
        self.tube_height = 178 # mm
        self.cap_width = 9 # mm
        self.cap_height = 8 # mm
        self.sloty = 12 # mm slot Y-axis  offset for tube removal
        self.slotz = None # will be defined when tube is ejected
        self.trash_height = 87 # above the lowest heights for tube trashing
        self.closure = 4.5 # mm, closure criterion, gripper is fully closed at 4.2 mm

################################################### transfer maps ######################################################################

class PALTransferMap: # a class to create transfer maps
    
    def __init__(self):

        self.lib_from = []
        self.lib_to = []
        self.mapping = []
        self.df = pd.DataFrame()
        self.n_to = 0
        self.n_from = 0
        self.verbose = 1
        self.rack_from = None
        self.rack_to = None
        self.renew_composition()

    def renew_composition(self):
            #self.composition_from = []
            #self.constitution_from = []
            self.composition_to = []
            self.constitution_to = []
         
    def sort_labels(self, labels, direction): # sorting of wells
        def sort_key(label):
                row, col = label[0], int(label[1:])
                if direction: 
                    return (row, col)
                else:
                    return (col,row)
        return sorted(labels, key=sort_key)

    def generate_labels(self, range_str, direction):  # 0 by column, 1 by row
        range_str = range_str.strip()
        if ":" in range_str:
            start, end = range_str.split(":")
            start_row, start_col = start[0], int(start[1:])
            end_row, end_col = end[0], int(end[1:])
            rows = string.ascii_uppercase[string.ascii_uppercase.index(start_row):string.ascii_uppercase.index(end_row) + 1]
            columns = range(start_col, end_col + 1)
            if direction:
                labels = ["%s%d" % (row,col) for row in rows for col in columns]
            else:
                labels = ["%s%d" % (row,col) for col in columns for row in rows ]
            return labels
        else:
            return [range_str]
        
    def well2tuple(self, well): 
        letter = well[0].upper()
        col = int(well[1:])
        row = ord(letter) - ord('A') + 1
        return (row, col)
    
    def well2cell(self, rack, well):
        row, col = self.well2tuple(well)
        if rack.orientation == 1: # indexing by column 
            return (row-1)*rack.cols + col
        else: # indexing by row
            return (col-1)*rack.rows + row
    
    def cell2well(self, rack, cell):
        cell-=1
        if rack.orientation == 1: # indexing by column 
            row = math.floor(cell/rack.cols)
            return self.tuple2well(row+1, cell-row*rack.cols + 1)
        else: # indexing by row
            col = math.floor(cell/rack.rows)
            return self.tuple2well(cell-col*rack.rows + 1, col+1)
    
    def tuple2well(self, row, col): 
        return "%s%d" % (chr(64 + row), col)
    
    def well2native(self, rack, well):
            row, col = self.well2tuple(well)
            
            if "NMR" in rack.type:
                return str(self.well2cell(rack, well))
            
            if "ICP" in rack.type:
                if rack.rows > rack.cols:
                    return self.tuple2well(col, row)
                else:
                    return self.tuple2well(row, col)
                
            return str(self.well2cell(rack, well))
    
    def check_well(self, rack, well): # check that the cell can be on the substrate
        row, col = self.well2tuple(well)
        if row>rack.rows or col>rack.cols:
            return False
        else:
            return True

    def generate_combined_labels(self, rack, ranges_str, direction=0, offset=0): # combines and orders well ranges 
        if "full" in ranges_str or ranges_str=="*": # full rack
            ranges_str = self.full_range(rack)

        range_list = ranges_str.split(',')

        combined = []
        for range_str in range_list:
            if "*" in range_str: # full row or column, like A* or *6 with wildcarts
                 labels = self.full_rc(rack, range_str).split(',')
            else: 
                labels = self.generate_labels(range_str, direction)

            for label in labels: 
                if label not in combined:
                    combined.append(label)

        combined = self.sort_labels(combined, direction)
        combined = combined[offset:]

        record = []
        if self.verbose: 
                print("%s wells (%s, %dx%d rack) = %s" % (len(combined),
                                                          rack.name,
                                                          rack.rows,
                                                          rack.cols,
                                                          combined))
        flag=0
        for well in combined:
                if self.check_well(rack, well):
                    record.append((rack.name, 
                                   well, 
                                   self.well2native(rack, well)))
                else:
                    flag=1
        if flag:
                print("\n>> Rack %s dimensions exceeded, only valid wells added\n" % rack.name)

        return record

    def check_unique(self, list): # removes duplicates
        unique=[]
        for item in list:
            if item not in unique:
                unique.append(item)
        return unique

    def shuffle(self, list):  # random shuffle & check that the first well is not the same as the previous last well   
        last = list[-1]
        u = list[:]
        while True:
            random.shuffle(u)
            if u[0] != last:
                break
        return u

    def full_range(self, rack): #  full rack
        return "A1:%s" % self.tuple2well(rack.rows, rack.cols)

    def full_rc(self, rack, s): #  full row or column like A* or *6
        q=""
        if s[0]=="*": # columns
            col=int(s[1:])
            for i in range(rack.rows):
                q += "%s," % self.tuple2well(i+1,col)
        else: #rows
            for i in range(rack.cols):
                q += "%s%d," % (s[0],i+1)
        return q[:-1]

    def full_rack(self, rack, direction=0): # 0 by column, 1 by row # a list of wells in the full rack
        range_str =  self.full_range(rack)
        return self.generate_labels(range_str, direction)

    def in_lib(self, lib, rack, well): # check presence in the add list 
        for r, w, _ in lib:
            if r == rack and w == well:
                return 1
        return 0

    def add_from(self, rack, reagent_str, direction=0, offset=0): # 0 by column, 1 by row # a list of sampled wells
        self.lib_from += self.generate_combined_labels(rack, reagent_str, direction, offset)
        self.n_from = len(self.lib_from)

    def add_to(self, rack, reagent_str, direction=0, offset=0): # 0 by column, 1 by row # a list of destination wells
        self.lib_to += self.generate_combined_labels(rack, reagent_str, direction, offset) 
        self.n_to = len(self.lib_to)

    def report_from(self): # reporting 
        if self.verbose:
            print("the total of %d wells to map from" % self.n_from)

    def report_to(self): # reporting 
        if self.verbose:
            print("the total of %d wells to map to" % self.n_to)

    def selfmap(self, randomize): # optional randomization on each repeat - making a transfer self-map
        if self.n_from == 0:
            return 0   
        self.n_to = self.n_from
        self.lib_to = self.lib_from
        self.mapping=[]
        u = self.lib_from[:]
        if randomize:  u = self.shuffle(u)
        for i in range(self.n_from):
            self.mapping.append((i+1,)+u[i]+u[i])
        return 1

    def map(self, randomize): # optional randomization on each repeat - making a transfer map
        if self.n_from == 0 or self.n_to == 0:
            return 0
        q, m = 1, 0
        self.mapping=[]
        while(q):
                u = self.lib_from[:]
                if randomize:  u = self.shuffle(u)
                for i in range(self.n_from):
                    self.mapping.append((m+1,)+u[i]+self.lib_to[m])
                    m+=1
                    if m==self.n_to:
                        q=0
                        break                    
        if self.verbose: 
            print("\n%d full repeats" % math.floor(self.n_to/self.n_from))
        return 1

    def to_df(self): # converting the transfer map to a dataframe table
        if self.mapping:
            self.df = pd.DataFrame(self.mapping, columns=['index', "rack from","well from","native from",
                                                          "rack to","well to","native to"])
            if self.verbose: 
                print("\nTRANSFER MAP\n%s\n" % self.df)
        else:
            print("no mapping to convert to a dataframe")

    def to_csv_stamped(self): # saving the transfer map to a datetime stamped CSV file
        now = datetime.now()
        stamp = now.strftime('%Y%m%d_%H%M%S')
        self.to_csv("mapping",stamp)

    def to_csv(self, name, stamp):  # saving the Nan trimmed transfer map to a CSV file
        if len(self.df):
                self.df.to_csv("%s_%s.csv" % (name,stamp), index=False)
                if self.verbose:                     
                    print("mapping is written to a time stamped .csv file\n")
        else:
            print("no dataframe to save in a .csv file")


############################################################################################################################        

class PALService:

    def __init__(self, host = None):
         
        self.port = 64001
        self.PAL1 = "192.168.99.230" # "192.168.99.230"  # for PAL robot
        self.NMR =  "192.168.80.100" # for NMR robot whatever DHCP shows

        print(">> Current IP = %s" % self.find_IP())

        if host: 
            self.host = host  # "192.168.99.230" for BK computer
        else:
            self.host = self.PAL1
            
        print(">> host IPv4 address is %s" % self.host)
    
        self.verbose = 1 # verbosity level, 0 is minimum 2 is maximum verbosity
        self.simulator = False # if True do not engage PAL
        self.user = os.getlogin() # user name

        self.vial = None # current vial
        self.vials = [] # list of vials
        self.racks = {} # dictionary of current racks   
        self.session = None 
        self.res = None
        self.role = None 
        #self.role = ClientRole.GC1

        # work with H-cell farms
        self.farm = None
        self.nfarm = 0 # number of cells in the farm
        self.num_cells = 0 # actual number of cells
        self.grps = [] # groups of cells

        self.pause = False # pause all activities when True

        self.cam = PALImage() # video and machine vision
        self.alert = PALAlert() # smtp messages
        self.safe = PALSafe()  # safety route
        self.rack = PALRack()    # single rack
        self.tm = PALTransferMap() # transfer map 
        self.gr = PALGripper()
        
        # sample tracker and container dispatcher
        self.tracker = CustomTracker()
        self.disp = CustomDispatch()

        # containers
        self.last_code = None # code for the last container
        self.last_barcode = "" # barcode for the last container

        # operation parameters
        self.nabz = 5 # mm depth for nabbing (for nonamgentic vial transfer)
        self.solvent_rate = 50 # uL/s pump rate for solvent replacement at FastWash2
        self.dsyringe = 65 # mm depth for syringe in FastWash

        # dilutor
        self.dil_volume = 10 # volume of diluter syringe in mL
        self.dil_ports =  {"standard": [2,3], "solvent": [4,5] } # active ports for dilutor
        self.dil_index  = {"standard" : 0,    "solvent" : 0} # first active port

        self.tm.verbose = self.verbose
               
        # set reference coordinate system for position reporting, mm
        self.ToolPositions = ["Head","Tool","ToolTip"]  
        self.ToolWhere = 2
        self.ToolPosition = self.ToolPositions[self.ToolWhere-1]
        self.x = 0 # head/tool/tip coordinate x (along the rail)
        self.y = 0 # head/tool/tip coordinate y
        self.z = 0 # head/tool/tip coordinate z       
               
        self.dir = r"C:/Users/%s/Dropbox/Instruments cloud/Robotics/PAL3 System/Integration/Binaries" %  self.user
        self.DATA = r"Z:/RESULTS" 
        self.prefix = ""
        self.project = "" # project name
        self.category = "" # category of task in a project
        self.digest = "" # digest of logged operations with timestamps
        self.tstamp = "" # last timestamp for logging
        
        self.add_assembly("PalPlusDriver") 
        self.add_assembly("PalPlusDriverObjects") 

        import System
        from System.Net import IPEndPoint, IPAddress
          
        import Ctc.Palplus.Integration.Driver       
        import Ctc.Palplus.Integration.Driver.Direct 
        import Ctc.Palplus.Integration.Driver.Exceptions 
        import Ctc.Palplus.Integration.Driver.Objects
        import Ctc.Palplus.Integration.Driver.Modules
        import Ctc.Palplus.Integration.Driver.Entities 
        import Ctc.Palplus.Integration.Driver.Activities
           
        from Ctc.Palplus.Integration.Driver import DirectFactory, RobotHelperExtension
        from Ctc.Palplus.Integration.Driver import IPalPlusDriver, IRobotHelper
        from Ctc.Palplus.Integration.Driver import IPalPlusConfigurationService 
        from Ctc.Palplus.Integration.Driver.Direct import IPalPlusDirectService
        from Ctc.Palplus.Integration.Driver.Exceptions import DriverException, DriverCommunicationException
        from Ctc.Palplus.Integration.Driver.Entities import Units

        self.units = Units         
        self.local_host = IPAddress.Loopback
        self.endpoint = IPEndPoint(self.local_host, self.port)
        print(">> Local host = %s" % self.endpoint)
        
        self.driver = DirectFactory.CreateDriver()
        self.driver.Routing.Startup(self.endpoint)
               
        self.config_service = self.driver.Services.GetService(IPalPlusConfigurationService)
        self.direct_service = self.driver.Services.GetService(IPalPlusDirectService)
        self.session_name = ""
        
        self.robot = RobotHelperExtension.GetRobot(self.driver) 
        self.start_remote_service()

    def find_IP(self):
        for iface_name, iface_addrs in psutil.net_if_addrs().items():
            for addr in iface_addrs:
                if addr.family == socket.AF_INET and addr.address.startswith("192.168."):
                    return addr.address
        print(">> Cannot find valid IP address")
        return None
        
    def set_project(self, name="", opt=1): # start a project, if 0 skip full naming
        if opt: 
            if not name:
                name = self.session_name
            name = "%s_%s_%s" % (self.prefix, name, self.stamp())
            self.project = os.path.join(self.DATA, name)
        if not os.path.exists(self.project):
             os.makedirs(self.project)
        self.category = "" # category within a project
        self.digest = os.path.join(self.project,"time_log.csv")
        self.tstamp = ""
        with open(self.digest,"w") as f:
            f.write("rack_from,well_from,rack_to,well_to,volume,chaser,category,datetime")
            f.close()

    def add_assembly(self, name):
        self.lib = os.path.join(self.dir,"%s.dll" % name)       
        if os.path.exists(self.lib):
            print(">> Located PAL assembly %s" % name)
        else:
            print("Cannot find PAL assembly %s, abort" % name)
            sys.exit(0)
        clr.AddReference(self.lib)  
        
    def stamp(self): # daytime stamp
        now = datetime.now()
        return now.strftime('%Y%m%d_%H%M%S')
        
    def std_start(self, name): # name of the session, standard start
        self.set_active_modules()
        self.session_name = name
        self.do_lock("left")
        self.new_session(name)
        self.message(name)
        self.safe.inside = False
        self.safe_home()
            
    def finish(self): # standard finish
        if self.eh:
            self.safe_home()
        if self.prefix == "NMR":
            self.gripper_clear()
        self.unlock()
        self.stop_remote_service()
        self.shutdown() 
       
    def start_remote_service(self): # starts remoting into PAL
         from Ctc.Palplus.Integration.Driver import IRemoteService 
         self.remote_service = self.driver.Services.GetService(IRemoteService)
         try:
            if self.role: 
                print(">> Attempting to connect at %s as %s" % (self.host, self.role))
                self.driver.Remote.Connect(self.host, self.role) 
            else:
                print(">> Attempting to connect at %s" % self.host)
                self.driver.Remote.Connect(self.host) 
         except DriverCommunicationException as ex:
            print( "DriverCommunicationException: %s" % e)
         finally:
            try: 
                self.direct_service.Reset()
            except Exception as e:  
                print("Reset error: %s" % e)
                sys.exit(0)
            
    def stop_remote_service(self): # stops remoting into PAL
         if self.remote_service.IsConnected:
                self.remote_service.Disconnect() 

    def shutdown(self): # shuts down driver
        self.driver.Routing.Shutdown() 
        self.driver.Dispose()
        
    def notification(self, module): # notification - not sure what it is used for
        self.config_service.ModuleDataUpdated += EventHandler(self.config_service_ModuleDataUpdated)
        self.config_service.QueryModules(module, True)
        
    def message(self, s): # sends message to PAL
        if self.verbose: 
            print("--- status message: %s" % s)
        self.session.SendStatusMessageByKey(s) 
        
        
    def do_lock(self, type): # attempts to lock the arm
        self.lock = PALLock("left")
        print(">> Locking %s" % self.lock.name)      
        flag = 1
        
        # <n> attempts to lock
        n=5
        
        for i in range(n):
            print(">> Attempt %d out of %d to lock" % (i+1,n))
            self.direct_service.Unlock() 
            try:
                if not self.direct_service.Lock(self.lock.type):
                    print(">> Cannot acquire lock, repeat attempt" % self.lock.name)
                else: 
                    print(">> Head locked")
                    flag = 0
                    return 0
            except Exception as e:
                print(">> Lock error: %s" % e)
                self.stop_remote_service()
                self.start_remote_service()
            time.sleep(1)
            
        if flag:     
             print(">> Locking has repeatedly failed")
             self.direct_service.Unlock() 
             sys.exit(0)
             
        return 1
             
    def unlock(self): # unlocks the arm
        self.direct_service.Unlock() 
        print(">> Unlocked %s" % self.lock.name)
             
    def new_session(self, name): # starts a new direct service session
        from Ctc.Palplus.Integration.Driver.Activities import ActivityExecutionHelper
        self.session = self.direct_service.CreateExecutionSession(name, self.lock.res, False)
        self.eh = ActivityExecutionHelper(self.session)
        return self.session  
    
    def list_all_modules(self):     # generates the list of all passive and active modules      
            modules = list(self.config_service.QueryModules())
            self.modules  = pd.DataFrame(columns=["Name", "Description","Parameters"])
            rows = []
            for m in modules:
                s = m.Definition.Name.replace("Description", "")
                n, params = self.all_parameters(m)
                rows.append({"Name": m.FullPathName, 
                             "Description" : s,
                             "Count" : n,
                             "Parameters" : params[1:]})
            self.modules = pd.DataFrame(rows)
            try: 
                f = os.path.join(self.DATA, "%s_modules.csv" % self.prefix)
                self.modules.to_csv(f)
                print(">> Saved the list of modules to all_modules.csv")
            except:
                print(">> Unable to save the list of modules to a CSV file")
                
    def all_parameters(self, module):
        params = str(module.GetParameters()).strip().strip('[]')
        lines = params.splitlines()
        n, s = 0, ""
        for line in lines:
             line = line.strip()
             if line and ":" not in line:
                  s+="\n (%d) %s" % (n+1, line)
                  n+=1
        return n, s
    
    def set_module_by_name(self, name): # sets a module by name
        module = self.config_service.GetModuleByName(name)  
        
        if module:
            s = module.Definition.Name.replace("Description", "")
            print("\n>> Found module %s of type %s" % (name, s))
            n, params = self.all_parameters(module)
            if self.verbose == 2: 
                print("%s\n>> %d parameters\n" % (params, n))
        else:
            print("\n>> Failed to find module %s" % name)
        return module
    
    def set_active_modules(self): # sets active modules
        
        if self.host == self.PAL1: # for PAL1 robot
            self.std_PAL1_start()    
            self.prefix = "PAL1"
            
        if self.host == self.NMR: # for NMR robot
            self.std_nmr_start()  
            self.prefix = "NMR"
        
    def std_PAL1_start(self):
        self.fastwash =     self.set_module_by_name("Fast Wash 1")              # fast wash module
        self.wash1 =        self.set_module_by_name("Fast Wash 1:Wash1")        # wash station 1
        self.wash2 =        self.set_module_by_name("Fast Wash 1:Wash2")        # wash station 2
        self.waste =        self.set_module_by_name("Fast Wash 1:Waste")        # waste
        self.centrifuge =   self.set_module_by_name("Centrifuge 1")             # centrifuge
        self.vortex =       self.set_module_by_name("Vortex Mixer 1")           # vortex
        self.dilutor =      self.set_module_by_name("Dilutor 1")                # dilutor
        self.gripper =      self.set_module_by_name("GRP 1")                    # generic gripper
        self.ls1 =          self.set_module_by_name("LS 1")                     # 1.0 mL syringe tool
        self.ls2 =          self.set_module_by_name("LS 2")                     # 2.5 mL syringe tool
        self.dil1 =         self.set_module_by_name("DIL 1")                    # 10 mL dilutor tool
                   
        
    def activate_gripper(self): # activate generic gripper tool in the arm
        self.gr.used = True
        if self.gripper: 
            self.eh.ChangeTool(self.gripper)
        else:
            print(">> Cannot find generic gipper tool GRP 1")

        
    def activate_ls1(self): # activate LS1 tool in the arm
        self.gr.used = False
        if self.ls1: 
            self.eh.ChangeTool(self.ls1)
        else:
            print(">> Cannot find syringe tool LS 1")
        
    def activate_ls2(self):
        self.gr.used = False
        if self.ls2: 
            self.eh.ChangeTool(self.ls2)
        else:
            print(">> Cannot find syringe tool LS 2")

    def activate_dil1(self):
        self.gr.used = False
        if self.dilutor and self.dil1: 
            self.eh.ChangeTool(self.dil1)
        else:
            print(">> Cannot find dilutor tool DIL 1 or dilutor Dilutor 1")
        
    def set_pos(self, address): # sets position object
        self.address = address
        if self.verbose == 2:
            print(">> Vial address: %s" % address)          
        self.pos = self.config_service.GetVial(self.address)
        return self.pos
        
    def set_vial(self, address): # sets vial object 
        self.set_pos(address)
        self.vial = self.session.AllocateVial(self.pos)
        return self.vial
    
    def tuple2pos(self, tray=1, slot=1, position=1): # generic move to a vial with a position check       
        address = "Tray Holder %d:Slot%d:%d" % (tray, slot, position)
        self.set_pos(address) 
        return self.pos
    
    def tuple2vial(self, tray=1, slot=1, position=1): # generic move to a vial with a position check       
        address = "Tray Holder %d:Slot%d:%d" % (tray, slot, position)
        self.set_vial(address) 
        return self.vial

    def vial2pos(self, vial): # find position of a vial from a vial object
        if not vial: return None
        if isinstance(vial, str): 
            return vial
        else: 
            modules = list(self.config_service.QueryModules())
            rack = vial.Tray.Name
            index  = vial.Index
            for m in modules:
                address = m.FullPathName
                if rack in address: 
                    return "%s:%d" % (address.rsplit(":", 1)[0], index)
        return None
    
    def tuple2objects(self, tray=1, slot=1, position=1): # generic move to a vial with a position check       
        address = "Tray Holder %d:Slot%d:%d" % (tray, slot, position)
        self.set_vial(address) 
        return self.vial, self.pos
          
    def in_restricted(self, module):  # for safe motions - is it a restricted motion tray?
        if module in self.safe.trays:  
            self.safe.inside = True
        else:  
            self.safe.inside = False   
    
    def get_xyz(self, result): # reads result of coordinate query as a vector in mm
          V = result.get_ReturnValue()  # EuclideanVector in m
          self.x = 1e3*V.X # mm
          self.y = 1e3*V.Y # mm
          self.z = 1e3*V.Z # mm

    def get_current_pos(self): # gets current position of the head/tool/tip
        result = self.eh.GetArmPosition(self.ToolWhere) # Tool position, 1  - Head, 2 - Tool, 3 - ToolTip           
        self.get_xyz(result)
        if self.verbose==2:
            print("--- current position %s: X=%.1f mm, Y=%.1f mm, Z=%.1f mm" % (self.ToolPosition,
                                                                   self.x,
                                                                   self.y,
                                                                   self.z
                                                                   ))
    
    def move2vial(self, tray=1, slot=1, position=1): # generic move to a vial with a position check
        pos = "Tray Holder %d:Slot%d:%d" % (tray, slot, position)
        self.set_vial(pos)
        self.in_restricted(tray) 
        if self.verbose:
            print(">> Moves to vial %s" % pos)
        self.move2object(self.vial)
        return self.vial

    def move2object(self, obj, opt=1): # generic move to an object with a position check 
                                     # opt=1 take current position after moving
        
        result = self.eh.GetObjectPosition(obj)
        self.get_xyz(result)
        if self.verbose:
            print("\nMove to object: X=%.1f mm, Y=%.1f mm, Z=%.1f mm" % (
                                                                   self.x,
                                                                   self.y,
                                                                   self.z
                                                                   ))                                                 
        self.eh.MoveToObject(obj)  
        if opt: self.get_current_pos()
        
    def tuple2pos(self, tray, slot, position): #(tray, slot, position) tuple to position object
        pos = "Tray Holder %d" % tray
        if slot:
            pos += ":Slot%d" % slot
        if position:
            pos += ":%d" % position 
        return pos
    
    def move_absolute(self, x, y, z):
        if self.verbose:
            s = ">> Move absolute:"
            s +=  " X=%.1f mm" % x
            s +=  " Y=%.1f mm" % y
            s +=  " Z=%.1f mm" % z
            print(s)  
        move = self.session.CreateActivity("MoveAbsolute")
        move["DestinationX"] = self.units.GetMilliMeter(x)
        move["DestinationY"] = self.units.GetMilliMeter(y)
        move["DestinationZ"] = self.units.GetMilliMeter(z)
        #move["Part"] = Int32(2) # Tool
        self.session.Execute(move)
        self.get_current_pos()  

    def move_relative(self, dx, dy, dz): # relative motion in mm
        if self.verbose==2:
            s = "--- move relative:"
            if dx: s +=  " dX=%.1f mm" % dx
            if dy: s +=  " dY=%.1f mm" % dy
            if dz: s +=  " dZ=%.1f mm" % dz
            print(s)           
        move = self.session.CreateActivity("MoveRelative")
        if dx: move["MovementX"] = self.units.GetMilliMeter(dx)
        if dy: move["MovementY"] = self.units.GetMilliMeter(dy)
        if dz: move["MovementZ"] = self.units.GetMilliMeter(dz)
        move["ForceDirectMovement"] = True
        self.session.Execute(move)
        self.get_current_pos()    
        
    def approach_object(self, obj, x=0, y=0, z=0): # approach object with offsets in mm
        move = self.session.CreateActivity("ApproachObject")
        move["Target"] = obj
        if x: move["OffsetX"] = self.units.GetMilliMeter(x)
        if y: move["OffsetY"] = self.units.GetMilliMeter(y)
        if z: move["OffsetZ"] = self.units.GetMilliMeter(z)
        self.session.Execute(move)
        
    def approach2vial(self, tray=1, slot=1, position=1): # approach activity with XYZ offsets in mm
        pos = self.tuple2pos(tray, slot, position)
        self.set_vial(pos)
        self.in_restricted(tray) 
        result = self.eh.GetObjectPosition(self.vial)
        self.get_xyz(result)
        if self.verbose:
            print("\nReference for vial %s: X=%.1f Y=%.1f, Z=%.1f" % (pos,
                                                     self.x,
                                                     self.y,
                                                     self.z ))
            print("Approach offsets dX=%.1f dY=%.1f, dZ=%.1f" % (self.safe.dX,
                                                     self.safe.dY,
                                                     self.safe.dZ ))
                                                     
        self.approach_object(self.vial, self.safe.dX, self.safe.dY, self.safe.dZ)
        self.get_current_pos()
        
    def safe_move2vial(self, tray=1, slot=1, position=1): # safe move to a vial around the obstacles
        self.in_restricted(tray) 
        self.safe_getout()
        self.approach2vial(tray, slot, position)
        self.safe_getto()
    
    def safe_home(self):  # safe homing around the obstacles   
        self.safe_getout()
        self.eh.MoveToHome()
        self.safe.inside = False  
    
    def safe_getto(self):  # safe getting in
        self.move_relative(-self.safe.dX, -self.safe.dY, -self.safe.dZ)  
           
    def safe_getout(self):     # safe getting out          
        if  self.safe.inside:
            self.move_relative(self.safe.dX, self.safe.dY, self.safe.dZ) 
        
    def safe_home(self): # save home coordinates as a safe position
         self.safe_getout() 
         self.eh.MoveToHome()
         self.safe.inside = False   

    def rack_type(self, s="VT54"):  # returns rack type object
        racktypes = list(self.config_service.GetRackTypes())
        for x in racktypes:
            if x.Name == s:
                 return x        
        print(">> Cannot find rack type %s, abort" % s)            
        return None
    
    def vial_type(self, s="2-CV NonMagnetic"): # returns vial type object
        vialtypes = list(self.config_service.GetRackVialTypes())
        for x in vialtypes:
            if x.Name == s:
                 return x       
        print(">> Cannot find rack vial type %s, abort" % s)
        return None

    def ID_rack(self, rack, ID):
            rack.ID = ID
            self.racks[rack.name] = rack

    def set_rack(self, 
                      tray = "Tray Holder 1", 
                      slot=1, 
                      racktype = "VT54", 
                      vialtype = "2-CV Magnetic"): # sets a rack, creates a rack object, and add it to the used rack library

       
         racktype_ = self.rack_type(racktype)
         vialtype_ = self.vial_type(vialtype)
         if racktype_ and vialtype_:
             self.config_service.SetRackTypeOnTrayContainerSlot(tray, slot, racktype_, vialtype_)
             r = self.rack_params(tray, slot)
             r.vialtype = vialtype
             self.racks[r.name] = r
             return r
         else:
             return None

    def rack_params(self, tray = "Tray Holder 1", slot=1): # creates a rack object for a given (tray, slot) 
            tray_ =  self.set_module_by_name(tray)
            # self.set_module_by_name("%s:Slot%d:Rack %d" % (tray, slot, slot))
            self.racktype = tray_.GetParameters().GetValue("Slot%dConfig" % slot)
            rectangle = self.set_module_by_name(self.racktype).GetParameters()
            self.rack = PALRack()
            self.rack.name = "%s:Slot%d" % (tray, slot)
            self.rack.type = self.racktype
            self.rack.rows = rectangle.GetValue("Rows")
            self.rack.cols = rectangle.GetValue("Columns")
            self.rack.cells =  self.rack.rows * self.rack.cols
            self.rack.orientation = rectangle.GetValue("IndexingOrientation")
            if self.verbose:
                print(">> Rack type %s is %d x %d" % (self.rack.type, 
                                                      self.rack.rows, 
                                                      self.rack.cols))
            return self.rack
    
    def tm_sequence(self, method, parameters, resume = False): # pass method parameters
        
        if not resume:
            self.tm.renew_composition()
            self.transfer = 0
            for p in parameters: 
                 if p not in self.tm.df.columns:
                        self.tm.df[p] = pd.NA
            if "stamp" not in self.tm.df.columns:
                    self.tm.df["stamp"] = pd.NA
            
        for i in range(len(self.tm.mapping)):
            
             if self.pause or  keyboard.is_pressed('ctrl+q'): 
                return self.transfer
             
             _, add_from, well_from, _, add_to, well_to, _ = self.tm.mapping[i]
     
             
             if add_from in self.racks:
                 rack_from = self.racks[add_from]
                 cell_from = self.tm.well2cell(rack_from, well_from)
                 vial_from = self.set_vial("%s:%d" % (rack_from.name, cell_from))
             else: 
                 return 0
             
             if add_to in self.racks:
                rack_to = self.racks[add_to]
                cell_to = self.tm.well2cell(rack_to, well_to)
                vial_to = self.set_vial("%s:%d" % (rack_to.name, cell_to))
             else:
                 return 0

             kwargs = {"vial_from": vial_from, "vial_to" : vial_to}                        
             kwargs.update(parameters)
             
       
             if self.verbose:
                    print(" --- Transfer %d: %s:%d (%s) => %s:%d (%s)" % (self.transfer+1,
                                                                       add_from,
                                                                       cell_from,
                                                                       well_from,
                                                                       add_to,
                                                                       cell_to,
                                                                       well_to))
             status = method(**kwargs)
                
             # logging
             for p in parameters: 
                self.tm.df.loc[i,p] = parameters[p]
             self.tm.df.loc[i,"stamp"] = self.stamp()
                 
             self.transfer+=1   
             
                    
    def clean_wash(self):
        if self.simulator: return 0
        self.rinse_source(2)
        self.rinse_syringe(50, 2) # 50% syringe wash
        
    def rinse_wash(self, cycles=3): # in % of syringe volume, not tested
        if self.simulator: return 0
        if self.verbose:
            print("\n>> Rinsing wash liner %s %d times" % (self.wash1.FullPathName, 
                                                         cycles))  
        self.eh.RinseWashLiner(self.wash1, Int32(cycles)) 
        
    def rinse_source(self, cycles=3): # Wash2 is for sourcing solvent into syringe
        if self.simulator:  return 0
        if self.verbose:
            print("\n>> Rinsing source liner %s %d times" % (self.wash2.FullPathName, 
                                                           cycles))
        self.eh.RinseWashLiner(self.wash2, Int32(cycles))
        
    def pump_solvent(self, volume): # pumps solvent, volume in microliters, fixed rate, if <=0 continuous pumping 
         if self.simulator: 
            return 0
         pump = self.session.CreateActivity("SetPump")
         pump["Target"] = self.fastwash
         pump["PumpIndex"] = Int32(2)
         pump["FlowRate"] =  self.units.GetMicroLiterPerSecond(self.solvent_rate)
         pump["State"] = True
         
         start = datetime.now()
         self.session.Execute(pump) 
         
         if volume>0:
             t = volume/self.solvent_rate
             self.eh.Wait(self.units.GetSecond(t))
             pump["State"] = False
             self.session.Execute(pump) 
             dt = datetime.now() - start
             v = self.solvent_rate * dt.total_seconds() 
             if self.verbose:
                print("\n>> Wash station pump 2 passed %.1f uL solvent" % v)    
                
         return pump
         
    def fill_chaser(self, volume):

        if volume==0 or self.simulator: return 0

        v = self.units.GetMicroLiter(volume)

        if self.verbose:
            print("\n>> Filling syringe with %s solvent at %s" % (v, self.wash2.FullPathName))

        aspirate = self.session.CreateActivity("AspirateSyringe")
        aspirate["Volume"] = v
        aspirate["FlowRate"] = self.units.GetMicroLiterPerSecond(self.solvent_rate*.95) 

        penetrate = self.session.CreateActivity("PenetrateObject")
        penetrate["Target"] = self.wash2
        penetrate["Depth"] = self.units.GetMilliMeter(self.dsyringe)  # 78 mm is maximum for wash1 and wash2

        self.eh.RinseWashLiner(self.wash2, Int32(1))
        self.eh.MoveToObject(self.wash2)
        self.session.Execute(penetrate)

        #pump = self.pump_solvent(volume*1.25) # safety factor 
        pump = self.pump_solvent(-1) # continuous pumping
        self.session.Execute(aspirate)        
        pump["State"] = False
        self.session.Execute(pump) 
        self.eh.RinseWashLiner(self.wash2, Int32(1))

        self.eh.LeaveObject()

    def waste_syringe(self):
        if self.simulator: return 0

        penetrate = self.session.CreateActivity("PenetrateObject")
        penetrate["Target"] = self.waste
        penetrate["Depth"] = self.units.GetMilliMeter(40)  # 46 mm is maximum for waste
        
        self.eh.MoveToObject(self.waste)
        self.session.Execute(penetrate)
        self.eh.EmptySyringe()
        self.eh.LeaveObject()
        
    def clean_syringe(self, vol_fraction=80, cycles=3): # in % of syringe volume, not tested
        if self.simulator: 
            return 0
        depth = self.units.GetMilliMeter(self.dsyringe)
        # flow = self.units.GetMicroLiterPerSecond(15) 
        
        v = self.units.GetPercent(vol_fraction) # factory default is 80%

        if self.verbose:
            print("\n>> Cleaning syringe at %s using %s syringe volume, %d cycles" % (self.wash1.FullPathName, 
                                                                               v, 
                                                                               cycles)) 

        clean = self.session.CreateActivity("CleanSyringe")
        clean["WashSource"] = self.wash1
        clean["WashPenetrationDepth"] = depth
        # clean["AspirateFlowRate"] =  flow   
        clean["WasteTarget"] = self.waste
        # clean["DispenseFlowRate"] = flow    
        clean["WashVolume"] = v 
        clean["Cycles"] = Int32(cycles)
        
        self.session.Execute(clean) 
        
        #self.eh.CleanSyringe(self.wash1)
        
    def rinse_syringe(self, vol_fraction=80, cycles=3): # % of syringe volume
        if self.simulator: 
            return 0
        v = self.units.GetPercent(vol_fraction) # factory default is 80%

        if self.verbose:
            print("\n>> Cleaning syringe & rinsing liner at %s using %s syringe volume, %d cycles" % 
                  (self.wash1.FullPathName, 
                   v, 
                   cycles))
        
        for i in range(cycles): 
            if self.verbose: print(" --- rinse cycle %d" % (i+1))
            self.rinse_wash(1)
            self.clean_syringe(vol_fraction,1)
        
        self.rinse_wash(1)            
        self.eh.LeaveObject()
        
    def sample_transfer(self, **kwargs):
            if self.simulator: 
                return 0
            # sample transfer between two stationary vials 
            # Volume - sample volume in uL
            # Chaser - (optional) solvent chaser volume in uL
            
            flow = 10 # uL/s, 5X for rinsing 
            rinse = 3 # times to rinse the syringe in solution
            rinse_vol = 100 # uL to rinse
            vial_from = kwargs["vial_from"]
            vial_to =   kwargs["vial_to"]
            volume =    kwargs.get('Volume', 0)
            chaser =    kwargs.get('Chaser', 0)
            
            aspirate = self.session.CreateActivity("AspirateSyringe")
            aspirate["Volume"] = self.units.GetMicroLiter(rinse_vol)
            aspirate["FlowRate"] = self.units.GetMicroLiterPerSecond(5*flow)
          
            self.eh.MoveToObject(vial_from)
            self.eh.PenetrateObject(vial_from)
            
            for i in range(rinse): # rinse syringe by pumping
                self.session.Execute(aspirate) 
                self.eh.EmptySyringe()  
            
            aspirate["Volume"] = self.units.GetMicroLiter(volume)
            aspirate["FlowRate"] = self.units.GetMicroLiterPerSecond(flow)
            
            self.session.Execute(aspirate) # Aspirate sample
            self.eh.LeaveObject()

            self.eh.MoveToObject(vial_to)
            self.eh.PenetrateObject(vial_to)
            self.eh.EmptySyringe()  # Dispense sample
            self.eh.LeaveObject()
            
            self.rinse_syringe(80, 3) # 80% syringe volume, 3 cycles

            if chaser:        
                self.fill_chaser(chaser)           
                self.eh.MoveToObject(vial_to)
                self.eh.PenetrateObject(vial_to)
                self.eh.EmptySyringe()  # Dispense chaser separately

    def quick_transfer(self, **kwargs): # fills with chaser, replaces volume, aspirates and transfers

            # simplified sample transfer between two vials, 
            # Volume - sample volume in uL
            # Chaser - (optional) solvent chaser volume in uL
            
            flow = 10 # uL/s, 3X for solvent sampling 

            vial_from = kwargs["vial_from"]
            vial_to =   kwargs["vial_to"]
            volume =    kwargs.get('Volume', 0)
            chaser =    kwargs.get('Chaser', 0)
            replace = kwargs.get('Replace', False)
            wash = kwargs.get('Wash', True)
            fast = kwargs.get('FastDraw', 2) # speed up for low-viscosity solvents
            wash_cycles = kwargs.get('WashCycles', 3)
            
            # sample tracking

            if volume==0: return 0

            if self.simulator:
                self.tstamp = self.stamp()
                if replace:
                    self.update_tracking("solvent", vial_from, volume, 0, digest=False)
                self.update_tracking(vial_from, vial_to, volume, chaser)
                return 0

            flow *= fast 

            aspirate = self.session.CreateActivity("AspirateSyringe")
            v = self.units.GetMicroLiter(volume)
            f = self.units.GetMicroLiterPerSecond(flow)
            aspirate["Volume"] = v
            aspirate["FlowRate"] = f
            
            if replace: 
                self.fill_chaser(chaser+volume)
            else:
                self.fill_chaser(chaser)

            self.eh.MoveToObject(vial_from)
            self.eh.PenetrateObject(vial_from)
            if replace:
                self.eh.DispenseSyringe(v, f)
                self.tstamp = self.stamp()
                self.update_tracking("solvent", vial_from, volume, 0)
                time.sleep(10) # 10 s delay for mixing

            self.session.Execute(aspirate) # Aspirate sample into the same syringe
            self.tstamp = self.stamp()
            self.update_tracking(vial_from, vial_to, volume, chaser)
            self.eh.LeaveObject()

            self.eh.MoveToObject(vial_to)
            self.eh.PenetrateObject(vial_to)
            self.eh.EmptySyringe()  # Dispense sample and chaser
            self.eh.LeaveObject()

            if wash: 
                self.clean_syringe(50, wash_cycles) # 50% syringe volume, cycles
                self.rinse_wash(1)

            return 1

    def quick_withdraw(self, **kwargs): # adds a volume and optionally takes it back

            # simplified sample transfer between two vials, 
            # Volume - sample volume in uL
            # Chaser - (optional) solvent chaser volume in uL
            
            flow = 10 # uL/s, 3X for solvent sampling 

            vial_from = kwargs["vial_from"]
            vial_to =   kwargs["vial_to"]
            volume =    kwargs.get('Volume', 0)
            replace = kwargs.get('Replace', False)
            wash = kwargs.get('Wash', True)
            fast = kwargs.get('FastDraw', 2) # speed up for low-viscosity solvents
            wash_cycles = kwargs.get('WashCycles', 3)
            
            # sample tracking

            if volume==0: return 0

            if self.simulator:
                self.tstamp = self.stamp()
                self.update_tracking(vial_from, vial_to, volume, 0)
                if replace:
                    self.update_tracking(vial_to, None, volume, 0, digest=False)

                return 0

            flow *= fast 

            aspirate = self.session.CreateActivity("AspirateSyringe")
            v = self.units.GetMicroLiter(volume)
            f = self.units.GetMicroLiterPerSecond(flow)
            aspirate["Volume"] = v
            aspirate["FlowRate"] = f

            self.eh.MoveToObject(vial_from)
            self.eh.PenetrateObject(vial_from)
            self.session.Execute(aspirate) # Aspirate sample into the same syringe
            self.tstamp = self.stamp()
            self.update_tracking(vial_from, vial_to, volume, 0)
            self.eh.LeaveObject()

            self.eh.MoveToObject(vial_to)
            self.eh.PenetrateObject(vial_to)
            self.eh.EmptySyringe()  # Dispense sample

            if replace:
                time.sleep(10) # 10 s delay for mixing
                self.session.Execute(aspirate) # aspirate volume to replace injected volume
                self.tstamp = self.stamp()
                self.update_tracking(vial_to, None, volume, 0, digest=False)
                self.waste_syringe()

            self.eh.LeaveObject()

            if wash: 
                self.clean_syringe(50, wash_cycles) # 50% syringe volume, cycles
                self.rinse_wash(1)

            return 1

    def update_tracking(self, vial_from, vial_to, volume, chaser, digest=True): # optionally add to digest
            ID = self.log_sample(vial_to, vial_from, volume)
            if chaser: 
                ID = self.log_sample(vial_to, "solvent", chaser)
            if ID: self.log_composition(ID)
            if digest:
               self.log_digest(vial_to, vial_from, volume, chaser)

                
    def vial_move(self, tray, slot, vial): # simple transport of a vial, assumes the head is at a vial to move
            if self.simulator: 
                return 0
            v_from = self.vial  
            self.eh.SetVolatilePosition(v_from, 1, v_from) # sets home position
            
            v_to = self.tuple2vial(tray, slot, vial)
            if self.verbose:
                print(">> Transports vial at the current position to %s" % self.address)
            move = self.session.CreateActivity("TransportVial")
            move["Source"] = v_from         # current position
            move["Destination"] = v_to      # new position
            self.session.Execute(move)

    def basic_transport(self, **kwargs):  
          
         # direction is Forward/Backward
          vial_from = kwargs["vial_from"]
          vial_to =   kwargs["vial_to"]
          direction = kwargs["Direction"]
          
          move = self.session.CreateActivity("TransportVial")
          move["Home"] = Int32(1) # 0 - Unchanged, 1 - Source

          if self.simulator: 
            return 0
          
          self.eh.MoveToObect(vial_from)
         
          if direction == "Forward":               
                move["Source"] = vial_from
                move["Destination"] = vial_to                             
          else:
                move["Source"] = vial_to
                move["Destination"] = vial_from 
                
          self.session.Execute(move)
          
    def tm_treatment(self, method, parameters, resume = False): # pass method parameters - uses "from" transfer map
                                        # to process samples ( self.vials) as a single series call
        if self.simulator: 
            return 0
        if not resume:
            self.transfer = 0
            self.tm.renew_compositions()
            if "stamp" not in self.tm.df.columns:
                    self.tm.df["stamp"] = ""                    
            self.vials = []   
            for i in range(len(self.tm.mapping)):
             _, name, well, _, _, _, _ = self.tm.mapping[i]
             if name in self.racks:
                 rack = self.racks[name]
                 cell = self.tm.well2cell(rack, well)
                 vial = self.set_vial("%s:%d" % (name, cell))
                 self.eh.SetVolatilePosition(vial, 1, vial) # designates current location as home
                 self.vials.append((name, vial))   # tray:Slot, vial object 
                      
        kwargs = parameters
        status = method(**kwargs)


                             
    def set_vortex(self, rpm=500, time=120): # speed in rpm and time in s
           
          start = datetime.now()
          vortex = self.session.CreateActivity("SetVortexMixer")
          vortex["VortexMixer"] = self.vortex             
          vortex["Speed"] = self.units.GetRevolutionPerMinute(rpm)    
          vortex["State"] = True  
          
          if self.simulator: 
            return 0

          self.session.Execute(vortex)
          self.eh.Wait(self.units.GetSecond(time))  
          
          vortex["State"] = False
          self.session.Execute(vortex)
          dt = datetime.now() - start
          return dt.total_seconds() 

    def vortex_sequence(self, **kwargs):

          rpm =   kwargs["Rpm"]
          time =  kwargs["Time"]

          n = len(self.vials)
          move = self.session.CreateActivity("TransportVial")

          while self.transfer < n: 

            if self.pause or  keyboard.is_pressed('ctrl+q'): 
                return self.transfer

            name, v = self.vials[self.transfer]
            print(" --- Transports vial %s:%s to vortex mixer" % (name, 
                                                                       self.tm.df.loc[self.transfer,"well from"]))

            move["Source"] = v   
            move["Destination"] = self.vortex
            self.session.Execute(move)

            if self.verbose: 
                print(" >> Vortexing at %d rpm for %d s =>" % (rpm, time), end=" ")

            dt = self.set_vortex(rpm, time)  
            
            if self.verbose: 
                print("took %.1f s, moves vials back" % dt)

            self.eh.TransportVialHome(v)
            self.tm.df.loc[self.transfer,"stamp"] = self.stamp()

            self.transfer += 1

          return self.transfer

    def set_centrifuge(self, rpm=2000, time=120): # speed in rpm and time in s

          start = datetime.now()
          rotate = self.session.CreateActivity("SetCentrifuge")
          rotate["Target"] = self.centrifuge
          rotate["State"] = True          
          rotate["Speed"] = self.units.GetRevolutionPerMinute(rpm)    
          rotate["WaitForConstSpeed"] = True
          self.session.Execute(rotate) # automatically closes the cover  

          self.eh.Wait(self.units.GetSecond(time))  

          rotate["State"] = False         
          rotate["Speed"] = self.units.GetRevolutionPerMinute(0) 
          self.session.Execute(rotate)

          self.eh.OperateCentrifugeCover(self.centrifuge, 1) # open the cover

          dt = datetime.now() - start
          return dt.total_seconds()  

    def centrifuge_sequence(self, **kwargs):
         
          rpm =   kwargs["Rpm"]
          time =  kwargs["Time"]
          
          self.eh.OperateCentrifugeCover(self.centrifuge, 1) # open the cover
          npos = self.centrifuge.GetParameters().GetValue("MaxIndex") # positions in centrifuge for 2 mL vials
          n = 2 * math.floor(len(self.vials)/2)
          
          move = self.session.CreateActivity("TransportVial")
          
          while self.transfer < n:  
            
            if self.pause or  keyboard.is_pressed('ctrl+q'): 
                return self.transfer
            
            vcount = 0   
            for j in range(npos):
                if self.transfer+j < n:                    
                    name, v = self.vials[self.transfer+j]
                    if self.verbose:
                        print(" --- Transports vial %s:%s to centrifuge position %d" % (name, 
                                                                                       self.tm.df.loc[self.transfer+j,"well from"], 
                                                                                       j+1))
                    self.eh.SwitchCentrifugePosition(self.centrifuge, Int32(j+1))    
                    move["Source"] = v   
                    move["Destination"] = self.centrifuge
                    move["DestinationIndex"] = Int32(j+1)                  
                    self.session.Execute(move)
                    vcount += 1
                else: break
                       
            if self.verbose: 
                print(" >> Centrifugates %d vials at %d rpm for %d s =>" % (vcount, rpm, time), end=" ")
                
            dt = self.set_centrifuge(rpm, time)  
            
            if self.verbose: 
                print("took %.1f s, moves vials back" % dt)
                    
            
            for j in range(npos):
                if self.transfer+j < n:
                    name, v = self.vials[self.transfer+j]                 
                    self.eh.TransportVialHome(v)
                    self.tm.df.loc[self.transfer+j,"stamp"] = self.stamp()
                else: break

            self.transfer += j
            
          return self.transfer
     
    def nab(self, obj): # nab object for transportation
        if not self.gr.used:
            nab = self.session.CreateActivity("PenetrateObject")
            nab["Target"] = obj
            nab["Depth"] = self.units.GetMilliMeter(self.nabz) # 5 mm nab
            self.session.Execute(nab)
        

    def extraction_sequence(self, **kwargs):
          
          rpmv = kwargs["SpeedVortex"]
          tv =  kwargs["TimeVortex"]
          rpmc = kwargs["SpeedCentrifuge"]
          tc =  kwargs["TimeCentrifuge"]
          ims = kwargs["ImageSource"]
          ima = kwargs["ImageAction"]
          nab = False
          if "NabVials" in kwargs:
              nab = kwargs["NabVials"]

          self.eh.OperateCentrifugeCover(self.centrifuge, 1) # open the cover
          npos = self.centrifuge.GetParameters().GetValue("MaxIndex")
          n = 2 * math.floor(len(self.vials)/2)
                    
          while self.transfer < n:
            
            if self.pause or  keyboard.is_pressed('ctrl+q'):                 return self.transfer
            
            vcount = 0
            for j in range(npos):                
                if self.transfer+j < n: 
                    name, v = self.vials[self.transfer+j]
                    kind = "dummy" not in self.tm.df.loc[self.transfer+j,"type"]
                    if nab:
                        mode = "nabbed "
                    else: mode = ""
                    
                    if self.verbose:
                        print("\n --- Transports %svial %s:%s to vortex mixer" % (mode, name, 
                                                         self.tm.df.loc[self.transfer+j,"well from"]))
                    
                    move = self.session.CreateActivity("TransportVial")
                    self.eh.SetVolatilePosition(v, 1, v) # set home position
                    move["Source"] = v
                    if nab: 
                       move["NeedleTransportPenetrationDepth"] = self.units.GetMilliMeter(self.nabz) 
                               
                    move["Destination"] = self.vortex
                    if kind: 
                        self.session.Execute(move)
                        if self.verbose: 
                            print(" >> Vortexing at %d rpm for %d s =>" % (rpmv, tv), end=" ")
                
                        dt = self.set_vortex(rpmv, tv)              
                        if self.verbose: 
                            print("took %.1f s, moves vial to centrifuge position %d" % (dt, j+1))   
                    
                        self.eh.SetVolatilePosition(v, 0, self.vortex)  
                     
                        if ims: # take image  
                            self.eh.MoveToObject(v)
                            self.move2cam()
                            self.take_image(name, ims, ima) 
                        
                    self.eh.SwitchCentrifugePosition(self.centrifuge, Int32(j+1))
                    
                    move["Destination"] = self.centrifuge
                    move["DestinationIndex"] = Int32(j+1)
                    self.session.Execute(move)
                    vcount += 1
                
            if self.verbose: 
                print("\n >> Centrifuging %d vials at %d rpm for %d s =>" % (vcount, rpmc, tc), end=" ")
                
            dt = self.set_centrifuge(rpmc, tc)  
            
            if self.verbose: 
                print("took %.1f s, takes a photo and returns vials" % dt)
            
            for j in range(npos):
                if self.transfer+j < n:
                    name, v = self.vials[self.transfer+j]
                    kind = "dummy" not in self.tm.df.loc[self.transfer+j,"type"]
                    self.eh.SwitchCentrifugePosition(self.centrifuge, Int32(j+1))
                    self.eh.MoveToObject(v)
                    if nab: self.nab(v)
                    
                    if kind and ims: # take image                       
                        self.move2cam()
                        self.take_image(name, ims, ima) 
                                        
                    self.eh.TransportVialHome(v)
                    self.tm.df.loc[self.transfer+j,"stamp"] = self.stamp()
                    self.eh.LeaveObject()
                    
            self.transfer += j

    def move2cam(self):
        self.move_absolute(self.cam.X, self.cam.Y, self.cam.Z)
        
    def move_back(self):
        move = self.session.CreateActivity("MoveAbsolute")
        move["DestinationX"] = self.units.GetMilliMeter(self.x)
        move["DestinationY"] = self.units.GetMilliMeter(self.y)
        move["DestinationZ"] = self.units.GetMilliMeter(self.z)
        self.session.Execute(move)
            
    def vial_image(self, how, action): # move to vial first
        self.move2cam()
        self.take_image(self.address, how, action)
        self.move_back()      
        self.eh.LeaveObject()
            
    def take_image(self, name, how, action):
         
        ID = "%s_%s" % (name.replace(":", "_"), self.stamp())
        f = os.path.join(self.project, "%s.png" % ID)
        
        data = {"code" : None}       
        camera, flag = 0, 0
        
        match = re.search(r'\d+', how)
        if match: camera = int(match.group())      
          
        if self.verbose: 
            print(">> Takes OpenCV image on %s" % how)
        
        # take image
        if "Camera" in how: 
                flag = self.cam.snapshot(camera)
        else:
            print(">> Press Enter to continue...")
            input()
                
        if not flag: return 
        
        # process image
        if "Boundaries" in action:
                self.cam.boundaries()
        if "Save" in action: 
            if self.verbose: print(">> Saves image to %s.png" % name)
            cv2.imwrite(f, self.cam.image)
        if "Barcode" in action: self.cam.read_barcode(self.cam.image)
        if "QRcode" in action: self.cam.read_QRcode(self.cam.image) 
        if "MV_LLE" in action: 
            self.cam.ut.segment_image_full(self.project, ID, self.cam.image)
        else: 
            self.cam.flash_image('Miscroscope feed', self.cam.image)
        if "Rest" in action:
            sleep.time(60)
            

############################################  generic gripper #################################################################


    def gripper2vial(self, tray=1, slot=1, position=1, height=10): # gripper move to above a vial using absolute coordinates
        pos = "Tray Holder %d:Slot%d:%d" % (tray, slot, position)
        self.set_vial(pos) 
        if self.verbose:
            print(">> Moves gripper to vial %s" % pos)
        self.gripper2obj(self, self.vial, height)
        
    def gripper2object(self, obj, height=10): # gripper move to above a vial using absolute coordinates 
        if self.verbose:
            print(">> Moves gripper to %.1f mm above the object" % height)
        result = self.eh.GetObjectPosition(obj)
        self.get_xyz(result)
        self.z -= height
        if self.verbose:
            print("Move to object: X=%.1f mm, Y=%.1f mm, Z=%.1f mm" % (
                                                                    self.x,
                                                                    self.y,
                                                                    self.z
                                                                    ))  
        self.move_absolute(self.x, self.y, self.z) 
        
    def detect_object(self, obj, search=10): # approach and detect object, Z-axis search distance of 10 mm
        self.eh.ApproachObject(obj)
        detect = self.session.CreateActivity("DetectObject")
        detect["Target"] = obj
        detect["SearchDistance"] = self.units.GetMilliMeter(search) 
        status = self.session.Execute(detect)
        if self.verbose == 2:
            print(">> Approach and detect object:")
            print("--- Object = %s" % obj)
            print("--- Status = %s" % status)
        return "True" in str(status)
        
    def move_gripper(self, v1, v2): # moves v1 using gripper to v2 position - w check of v2 occupancy
        
        if self.verbose:
             print("\n>> Moves Object 1 to unoccupied Object 2 position using generic gripper")
             if self.verbose==2:
                print("--- Object 1 = %s" % v1)
                print("--- Object 2 = %s" % v2)
        
        self.gr.release = self.gr.depth + self.gr.after + 10 # mm, heigh of release
        w = self.units.GetMilliMeter(self.gr.width)
        
        grab = self.session.CreateActivity("GenericGripperGrabObject")
        grab["GrabDistance"] = self.units.GetMilliMeter(self.gr.depth)
        grab["RetractDistanceBefore"] = self.units.GetMilliMeter(self.gr.before) 
        grab["RetractDistanceAfter"] =  self.units.GetMilliMeter(self.gr.after)   
        grab["AbsAdapterDistance"] = w
        
        if not self.detect_object(v2, self.gr.search):
            if self.detect_object(v1, self.gr.search):               
                self.session.Execute(grab)    
                self.gripper2object(v2, self.gr.release)  
                self.eh.GenericGripperMoveAdapterAbsolute(w)
                time.sleep(0.2)
                self.eh.GripperGrip()  
                return 0
            else: 
                print(">> No Object 1 to move")
        else: 
            print(">> Object 2 is occupied, abort move")

        self.eh.LeaveObject()
        return 1

    def gripper_clear(self, width=15, height=0): # release, optionally move up, and close
        gr = self.session.CreateActivity("GenericGripperRelease") 
        gr["RelReleaseDistance"] =  self.units.GetMilliMeter(width)  
        self.session.Execute(gr)

        if height: 
            self.move_relative(0, 0, -height)

        time.sleep(0.5)
        self.eh.GenericGripperGrip() 

    def gripper_drop(self, width=15 , n=3): # release, optionally move up, and close

        gr = self.session.CreateActivity("GenericGripperRelease") 
        gr["RelReleaseDistance"] =  self.units.GetMilliMeter(width)  
        self.session.Execute(gr)

        dy, dz = 10, 20 # mm shaking in Y and Z-axis directions

        self.move_relative(0,dy/2, 0)

        for i in range(n):
            self.move_relative(0, -dy ,-dz)
            self.move_relative(0,  dy,  dz)

        self.eh.GenericGripperGrip() 
        

    def gripper_distance(self): # reports the adaptor distance in mm
        # responds [ActivityResult GenericGripperGetAdapterDistance Returned:0.*** m]
        s =  self.eh.GenericGripperGetAdapterDistance()
        match = re.search(r'Returned:\s*([-+]?\d*\.\d+|\d+)\s*m', str(s))
        s = match.group(1)
        return 1e3*float(s) # to mm



#############################  NMR PAL3 robot #################################################################

    def std_nmr_start(self):
        self.nmr = NMR_params()
        self.nmr.magnet = self.set_module_by_name("Fourier80 1")
        self.nmr.racks.append(self.set_module_by_name("NMR Holder 1:Slot1:NMR Reference"))
        self.nmr.racks.append(self.set_module_by_name("NMR Holder 1:Slot2:NMR Rack 1"))
        self.nmr.racks.append(self.set_module_by_name("NMR Holder 1:Slot3:NMR Rack 2"))
        self.nmr.racks.append(self.set_module_by_name("NMR Holder 2:Slot1:NMR Rack 3"))
        self.nmr.racks.append(self.set_module_by_name("NMR Holder 2:Slot2:NMR Rack 4"))
        self.nmr.racks.append(self.set_module_by_name("NMR Holder 2:Slot3:NMR Rack 5"))
        self.nmr.gripper = self.set_module_by_name("GRP 1")
        self.nmr.adapter = self.set_module_by_name("Fourier80 Adp.")
        self.nmr.racktype = self.set_module_by_name("Fourier80")
        self.nmr.trash = self.set_module_by_name("Trash 1")


    def locate_nmr_tube(self, rack, position):

        r = self.nmr.racks[rack]
        t = self.session.AllocateVial(r, Int32(position))
        i = position
        if rack: # first slot is reference samples slot
            i += 14 + 24*(rack-1)
        return r, t, i

    def nmr_gripper_clear(self): # release and close
        self.gripper_clear(self.nmr.release)

    def nmr_gripper_check(self, attempts=3):   # three attempts to drop a tube

        n = 0

        gr = self.session.CreateActivity("GenericGripperRelease") 
        gr["RelReleaseDistance"] =  self.units.GetMilliMeter(self.nmr.release) 
        self.session.Execute(gr)
        
        while(n<attempts):
            self.move_relative(0, 0, -self.nmr.search)
            time.sleep(0.5)
            self.eh.GenericGripperGrip() 
            if self.nmr_gripper_isclosed(): return 0
            self.session.Execute(gr)
            self.move_relative(0, 0, self.nmr.search)            
            n+=1

        print(">> Could not drop NMR tube after %d attempts" % attempts)
        return 1

    def nmr_gripper_isclosed(self): # True if NMR gripper is closed
        d = self.gripper_distance()
        if (d < self.nmr.closure): return True
        else: 
            if self.verbose:
                print(">> Gripper did not close: %.1f mm, < %.1f mm expected" % (d, self.nmr.closure))
            return False

    def nmr_gripper_drop(self, attempts=3, cycles=2): # release, optionally move up, and close

        gr = self.session.CreateActivity("GenericGripperRelease") 
        gr["RelReleaseDistance"] =  self.units.GetMilliMeter(1.5*self.nmr.release) 
        self.session.Execute(gr)

        dy, dz = 10, 20 # mm shaking in Y and Z-axis directions
        n = 0

        self.move_relative(0, dy/2, 0)
        
        while(n<attempts): # diagonal shake manouver

            for i in range(cycles):
                self.move_relative(0, -dy ,-dz)
                self.move_relative(0,  dy,  dz)

            self.eh.GenericGripperGrip() 

            if self.nmr_gripper_isclosed(): return 0

            if self.verbose:
                print(">> Attempt %d to trash NMR tube has failed" % (n+1))

            self.session.Execute(gr)
            n+=1

        print(">> Could not trash NMR tube after %d attempts" % attempts)
        return 1

    def eject_nmr_rack(self):
        eject = self.session.CreateActivity("GenericGripperGrabObject")
        eject["GrabDistance"]  =  self.units.GetMilliMeter(6)   
        eject["RetractDistanceBefore"] = self.units.GetMilliMeter(2)   
        eject["RetractDistanceAfter"] =  self.units.GetMilliMeter(5)    
        eject[ "AbsAdapterDistance"] =  self.units.GetMilliMeter(18)   
        self.session.Execute(eject)

    def move_nmr_tube(self, rack1, position1, rack2, position2, check=True):

        _, tube1, index1 = self.locate_nmr_tube(rack1, position1)
        _, tube2, index2 = self.locate_nmr_tube(rack2, position2)

        print(">> Moves NMR tube from Rack %d:%d (index=%d) => Rack %d:%d (index=%d)" % (rack1, 
                                                                                         position1, 
                                                                                         index1, 
                                                                                         rack2, 
                                                                                         position2, 
                                                                                         index2))
        tube2_empty = True 
        if check:
           if self.detect_object(tube2, self.nmr.search):
                tube2_empty = False
        
        if tube2_empty:
            if self.pick_nmr_tube(tube1):
                    self.drop_nmr_tube(tube2)
            else: 
                print(">> No tube *:%d to move" % tube1.Index)
        else: 
            print(">> Position *:%d occupied, abort move" % tube2.Index)

        return 1

    def pick_nmr_tube(self, tube): # picks NMR tube from rack       
        if self.detect_object(tube, self.nmr.search):               
            self.eject_nmr_rack() 
            self.move_relative(0, -self.nmr.sloty, 0)
            self.get_current_pos()
            self.nmr.slotz = self.z   
            return 1
        else: 
            print(">> NMR tube *:%d not found" % tube.Index)
            return 0

    def drop_nmr_tube(self, tube):
        result = self.eh.GetObjectPosition(tube)
        self.get_xyz(result)
        self.move_absolute(self.x, self.y - self.nmr.sloty, self.nmr.slotz) 
        self.move_relative(0, self.nmr.sloty, 0)
        if self.nmr_gripper_check(): sys.exit(2)
        self.eh.LeaveObject()


    def trash_nmr_tube(self, rack, position):
        _, tube, index = self.locate_nmr_tube(rack, position)

        print(">> Removes NMR tube from Rack %d:%d (index=%d) to Trash 1" % (rack, position, index))
        
        if self.pick_nmr_tube(tube):
            result = self.eh.GetObjectPosition(self.nmr.trash)
            self.get_xyz(result)
            self.move_absolute(self.x, self.y, self.z - self.nmr.trash_height) 
            if self.nmr_gripper_drop(): sys.exit(2)            
            self.eh.LeaveObject()
            return 0
        else: 
            print(">> No tube *:%d to move" % tube.Index)

        return 1

    def move_nmr_rack(self, rack1, rack2): # maps a rack to an empty rack
        if self.nmr_rack_isempty(rack2):
            for i in range(24):
                self.move_nmr_tube(rack1, i+1, rack2, i+1, check=False)

    def trash_nmr_rack(self, rack):
        for i in range(24):
            self.trash_nmr_tube(rack, i+1)

    def nmr_rack_isempty(self, rack): # tests that a rack is empty
        for i in range(24):
            _, tube, _ = self.locate_nmr_tube(rack, i+1)
            if self.detect_object(tube, self.nmr.search):
                return 0
        return 1
    
################################## working with containers #####################################################


    def local_container(self, c):
        if c: 
            s =c["route"]["type"].capitalize()
            code = c["code"]
            u = os.path.join(self.project, "%s_%s.json" %  (s, code)) # local copy
            with open(u, 'w') as f: 
                json.dump(c, f, indent=4)

    def save_container(self, c, image = True):  
         if c: 
             self.local_container(c)
             if image: 
                 self.disp.save(c)

    def update_container(self, ca, cb):
        if ca:
           if cb:
                for ID in cb["creator"]["content"]:
                    ca["creator"]["content"][ID] = cb["creator"]["content"][ID]
        else:
           ca = cb.copy()
        return ca
                
    def make_container(self, rack, category=None): # creates container object for export, json format, optionally filter by category

         dt = datetime.now()
         code = self.disp.datetime2abcd(dt)
         self.last_code = code

         CV=CustomBarcode()
         self.last_barcode = CV.snap_barcode(camera=1, focus=100)

         c = {"code" : self.last_code, "barcode" : self.last_barcode }

         r={} # rack
         r["name"] = rack.ID # PAL name for the rack
         r["type"] = rack.type # can be different than PAL rack type 
         r["vialtype"] = rack.vialtype # PAL name for the vial type
         r["instrument"] = "PAL1" # current location
         r["position"] = rack.name # current position
         r["label"] = ""  # visible code
         r["code"] = None  # bar code, QR code 
         r["holder"] = None # for movable holders
         r["items"] = rack.cells
         r["layout"] = "rectangular"
         r["rows"] = rack.rows
         r["columns"] = rack.cols
         r["orientation"] = rack.orientation
         
         c["rack"] = r
         
         route = {}
         route["ready"] = "no"
         route["type"] = "active" # cak also be supply or trash, see below
         route["priority"] = "clear" # will clear the rack to trash if no storage or instrument are available
         route["route"] =  ["UR5", "Storage", "UR5", "ICP", "UR5", "Trash"] # routing of the rack
         route["step"] = 0 # set to start of the route
         route["datetimes"] = [] # datetimes will be added
         
         c["route"] = route
         
         creator = {}  # the same, at creation
         creator["location"] = "PAL1"
         creator["position"] = rack.name
         creator["ID"] = rack.ID
         creator["protocol"] = self.project
         creator["datetime"] = str(dt)
         creator["content"] = self.tracker.extract_substrate(rack.name, category)
         
         c["creator"] = creator
           
         return c
        
    def supply_request(self, rack): # creates request for container object, json format

         dt = datetime.now()
         code = self.disp.datetime2abcd(dt)   
         c = {"code" : code}
         
         r={} # rack
         r["name"] = rack.ID  # PAL name for the rack
         r["type"] = rack.type # can be different than PAL rack type 
         r["vialtype"] = rack.vialtype # PAL name for the vial type
         r["instrument"] = "PAL1" # current location
         r["position"] = rack.name # position
         r["label"] = ""  # visible code
         r["code"] = None  # bar code, QR code                  
         r["holder"] = None # for movable holders
         
         c["rack"] = r 
         
         route = {}
         route["ready"] = "yes"
         route["type"] = "supply"
         route["priority"] = ""
         route["route"] =  ["UR5","Storage","UR5","PAL1"]
         route["step"] = 0
         route["datetimes"] = []
         
         c["route"] = route
         c["creator"] = {}
         
         return c
    
    def trash_request(self, rack): # creates container object for trash, json format
         
         dt = datetime.now()
         code = self.disp.datetime2abcd(dt)          
         c = {"code" : code}
         
         r={} # rack
         r["name"] = rack.ID # PAL name for the rack
         r["type"] = rack.type # can be different than PAL rack type 
         r["vialtype"] = rack.vialtype # PAL name for the vial type
         r["instrument"] = "PAL1" # current location
         r["position"] = rack.name # current position
         r["label"] = "" # visible code
         r["code"] = None  # bar code, QR code
         r["holder"] = None # for movable holders
         
         c["rack"] = r
         
         route = {}
         route["ready"] = "yes"
         route["type"] = "trash"
         route["priority"] = ""
         route["route"] =  ["UR5", "Trash"]
         route["step"] = 0
         route["datetimes"] = []
         
         c["route"] = route
         
         creator = {}  # the same, at creation      
         creator["location"] = "PAL2"
         creator["position"] = rack.name
         creator["ID"] = rack.ID
         creator["protocol"] = self.project
         creator["datetime"] = str(datetime.now())
         creator["content"] = self.tracker.extract_substrate(rack.name)
         
         c["creator"] = creator
                  
         return c
    
    def log_sample(self, vial_to, vial_from, volume): # logging sample into a container
        if volume:
            ID = self.vial2pos(vial_to)
            component_ID = self.vial2pos(vial_from)
            if not component_ID: 
                return None
        else: return None

        if ID:
            self.tracker.add(ID, component_ID, volume)
            self.tracker.aliquot(component_ID, volume)
            self.ID_container(ID, self.category)
            return ID
        else:
            self.tracker.aliquot(component_ID, volume)
            return component_ID

    def log_digest(self, vial_to, vial_from, volume, chaser): # timed digest log
        if volume:

            rack_to, well_to = "", ""
            rack_from, well_from = "", ""

            ID_to = self.vial2pos(vial_to)
            if ID_to:
                rack_to, well_to = ID_to.rsplit(":", 1)

            ID_from = self.vial2pos(vial_from)
            if ID_from:
                try:
                    rack_from, well_from = ID_from.rsplit(":", 1)
                except:
                    rack_from = ID_from


            try: 
                with open(self.digest,'a') as f:
                    f.write("\n%s,%s,%s,%s,%.1f,%.1f,%s,%s" % (rack_from,
                                                    well_from,
                                                    rack_to,
                                                    well_to,
                                                    volume,
                                                    chaser,
                                                    self.category,
                                                    self.tstamp)
                                                        )
                    f.close()
            except: pass


    def log_composition(self, ID): # logging sample into a TM table
        if ID: 
            self.tm.composition_to.append(self.tracker.return_composition(ID))
            self.tm.constitution_to.append(self.tracker.return_constitution(ID))
        
    def log_map(self):
        
          if self.tm.composition_to:
              d = self.tracker.compositions2df(self.tm.composition_to, "")
              self.tm.df = pd.concat([self.tm.df, d], axis=1)
              del d
          
          if self.tm.constitution_to:
              d = self.tracker.constitutions2df(self.tm.constitution_to)
              self.tm.df = pd.concat([self.tm.df, d], axis=1)
              del d
          
    def log_input(self, f): # tracking for the input file
        if not os.path.isfile(f):
            print(">> Input file %s does not exist, abort", f)
            sys.exit(0)
        try:    
            df = pd.read_csv(f)
            df = df.fillna(0)
            names = []
            self.tm.lib_from = []
            self.source = {}
            for  _, row in df.iterrows():
                rack = "Tray Holder %d:Slot%d" % (row["tray"], row["slot"])
                if rack in self.racks:
                    r = self.racks[rack]
                    position = row["source well"]
                    if isinstance(position, int): 
                        ID = "%s:%d" % (rack, position)
                        self.tm.add_from(r, self.tm.cell2well(position))
                    else:
                        well = position.strip()
                        ID = "%s:%d" % (rack, self.tm.well2cell(r, well)) 
                        self.tm.add_from(r, well)
                    name  = row["name"].strip()
                    if name in self.source: # source chemicals need to have unique names
                        print(">> Source chemical name %d is not unique, abort")
                        sys.exit(0)
                    self.source[name] = ID
                    self.tracker.add(ID, None, 0, name)
                    self.ID_container(ID)
                    elements = [col for col in df.columns if '*' in col]   # example: Na, mM 
                    for col in elements:
                        if row[col]:
                             e = col.replace("*","").strip()
                             self.tracker.samples[ID]["constitution"][e] = row[col]
                else:
                     print(">> Does not recognize rack %s, skip" % rack)
            del df
            self.save_samples()
        except Exception as e:
            print(">> Error %s for input file %s, abort" % (e,f))
            sys.exit(0)


    def log_source(self, rack, position="A1", name="solvent"): # position can be cell integer or string with the cell or well: 1, "1", or "A1" are all good
        if isinstance(position, int):
            ID = "%s:%d" % (rack.name, position)
        elif isinstance(position, str):
            if position[0].isalpha():
               ID = "%s:%d" % (rack.name, self.tm.well2cell(rack, position))
            else:
               ID = "%s:%s" % (rack.name, position)
        self.tracker.add(ID, None, 0, name)
        self.ID_container(ID)
        return ID

    def save_samples(self, name="samples"):
        f = os.path.join(self.project,'%s.json' % name)
        with open(f, 'w') as j:
            json.dump(self.tracker.samples, j, indent=4)

    def ID_container(self, ID, t="sample", c="glass vial"):
        if ID in self.tracker.samples: 
            if c: 
                self.tracker.samples[ID]["container"] = c
            if t:
                self.tracker.samples[ID]["type"] = t
            rack, _, _ = ID.rpartition(':')
            if rack in self.racks: 
                s = self.racks[rack].type
                if "NMR" in s: self.tracker.samples[ID]["container"] = "NMR tube"
                if "ICP" in s: self.tracker.samples[ID]["container"] =  "ICP tube"
       

    def write_json(self, s, name): # export json formatted data to work directory
        u = os.path.join(self.project, "%s_%s.json" % (name, self.stamp()) )
        with open(u, 'w') as f:
           json.dump(s, f, indent=4, default=self.json_serializer) 

    def log_state(self):
        self.write_json(self.racks, "substrates") # save substrates
        self.write_json(self.tracker.samples, "samples") # pedigree of all sources and samples
        self.all_waste() # save waste

    
    def rack_waste(self, rack): # write waste bill
        r = rack.name
        s = self.tracker.extract_substrate(r)

        if s:
            waste = self.tracker.waste_bill(s)
            f = os.path.join(self.project, 
                      "waste_%s_%s.csv" % (r.replace(":", "_"), rack.type) )

            waste.to_csv(f, index=True)

    def all_waste(self): # write waste bill
        waste = self.tracker.waste_bill(self.tracker.samples)
        f = os.path.join(self.project, "all_waste.csv")
        waste.to_csv(f, index=True)

    def json_serializer(self, obj):
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()  
        return obj


################################################ work with H-cell farm ###########################################


    def map_Lily(self, opt=False): # Lily Robertson's 12-cell farm, if opt=True, map the actual positions
        # OUT is West/South = red side, IN is East/North

        g = 0
        c = 0
        flag = 0
        self.grps = [(12,1,"EW"),(12,2,"NS"),(12,3,"EW"),(13,1,"NS"),(13,2,"EW"),(13,3,"NS")] # groups
        rs = []
        self.tm.lib_from = []

        for holder, slot, orientation in self.grps:

            rack = self.set_rack('Tray Holder %d' % holder, slot, 'Lily%s' % orientation, 'LilyWell')
            self.ID_rack(rack, "group%d" % (g+1))

            for i in range(2):

                if c==self.num_cells: break

                j = 2*i+1

                well = self.tm.cell2well(rack, j)
                label = "GRP%d-%s" % (g+1, well)
                self.tm.add_from(rack, well) 

                r = {}

                r["cell"] = c+1
                r["label"] = "%s-IN" % label
                r["type"] = "in"
                r["orientation"] = orientation # rack orientation, EW or NS
                r["group"] = g+1
                r["holder"] = holder # IN groups (red side)
                r["slot"] = slot
                r["well"] = j
                r["address"] = "Tray Holder %d:Slot%d:%d" % (holder, slot, j)
                
                if opt: 
                    print("\n--------------  GROUP %d, CELL %d, TRAY %s, SLOT %d, WELL IN (red) %d  ------------------" % (g+1, c+1, holder, slot, j))
                    self.move2vial(holder, slot, j)
                    r["X"] = round(self.x, 2)
                    r["Y"] = round(self.y, 2)
                    r["Z"] = round(self.z, 2)
                    self.eh.LeaveObject()

                rs.append(r)

                j+=1
                well = self.tm.cell2well(rack, j)
                label = "GRP%d-%s" % (g+1, well)
                self.tm.add_from(rack, well) 

                r = {}

                r["cell"] = c+1
                r["label"] = "%s-OUT" % label
                r["type"] = "out"
                r["orientation"] = orientation
                r["group"] = g+1
                r["holder"] = holder # OUT groups (green side)
                r["slot"] = slot
                r["well"] = j
                r["address"] = "Tray Holder %d:Slot%d:%d" % (holder, slot, j)

                if opt: 
                    print("\n--------------  GROUP %d, CELL %d, TRAY %s, SLOT %d, WELL OUT (green) %d  -----------------" % (g+1, c+1, holder, slot, j))
                    self.move2vial(holder, slot, j)
                    r["X"] = round(self.x, 2)
                    r["Y"] = round(self.y, 2)
                    r["Z"] = round(self.z, 2)
                    self.eh.LeaveObject()

                rs.append(r)
                c += 1

                if keyboard.is_pressed('ctrl+q'):
                    flag = 1
                    break

            g += 1
            if flag: break

        self.nfarm = c
        if self.num_cells==0:
            self.num_cells = c
        self.farm = pd.DataFrame(rs)
        f = os.path.join(self.project, 'Lily farm.csv')
        self.farm.to_csv(f, index=False)
        del rs

        if self.verbose: 
            print("\n>> Lily's H-cell farm mapping:\n%s"% self.farm)
            print("\n>> Lily's H-cell map exported to %s" % f)



    def map_farm(self, opt=False): # Mina Kim's farml, if opt=True, map the actual positions

        g = 0
        c = 0
        flag = 0
        wells = ["A1","A2","B1","B2"]
        self.grps = [(4,1),(4,2),(4,3),(6,1),(6,2),(6,3),(8,1),(8,2),(10,1),(10,2),(10,3)] # OUT groups
        rs = []
        self.tm.lib_from = []

        for holder, slot in self.grps:

            rack = self.set_rack('Tray Holder %d' % holder, slot, 'RedoxmeOut', 'Redoxme')
            self.ID_rack(rack, "group%d" % (g+1))

            rack = self.set_rack('Tray Holder %d'% (holder+1), slot, 'RedoxmeIn', 'Redoxme')
            self.ID_rack(rack, "group%d" % (g+1))

            for i in range(4):

                if c==self.num_cells: break

                label = "GRP%d-%s" % (g+1, wells[i])
                self.tm.add_from(rack, wells[i]) 

                r = {}

                r["cell"] = c+1
                r["label"] = "%s-OUT" % label
                r["type"] = "out"
                r["group"] = g+1
                r["holder"] = holder # OUT groups (feed side)
                r["slot"] = slot
                r["well"] = i+1
                r["address"] = "Tray Holder %d:Slot%d:%d" % (holder, slot, i+1)
                
                if opt: 
                    print("\n--------------  GROUP %d, CELL %d, TRAY %s, SLOT %d, WELL OUT %d  ------------------" % (g+1, c+1, holder, slot, i+1))
                    self.move2vial(holder, slot, i+1)
                    r["X"] = round(self.x, 2)
                    r["Y"] = round(self.y, 2)
                    r["Z"] = round(self.z, 2)
                    self.eh.LeaveObject()

                rs.append(r)

                r = {}

                r["cell"] = c+1
                r["label"] = "%s-IN" % label
                r["type"] = "in"
                r["group"] = g+1
                r["holder"] = holder+1 # IN groups (sample side)
                r["slot"] = slot
                r["well"] = i+1
                r["address"] = "Tray Holder %d:Slot%d:%d" % (holder+1, slot, i+1)

                if opt: 
                    print("\n--------------  GROUP %d, CELL %d, TRAY %s, SLOT %d, WELL IN  %d  -----------------" % (g+1, c+1, holder+1, slot, i+1))
                    self.move2vial(holder+1, slot, i+1)
                    r["X"] = round(self.x, 2)
                    r["Y"] = round(self.y, 2)
                    r["Z"] = round(self.z, 2)
                    self.eh.LeaveObject()

                rs.append(r)
                c += 1

                if keyboard.is_pressed('ctrl+q'):
                    flag = 1
                    break

            g += 1
            if flag: break

        self.nfarm = c
        if self.num_cells==0:
            self.num_cells = c
        self.farm = pd.DataFrame(rs)
        f = os.path.join(self.project, 'cell farm.csv')
        self.farm.to_csv(f, index=False)
        del rs

        if self.verbose: 
            print("\n>> Mina's H-cell farm mapping:\n%s"% self.farm)
            print("\n>> Mina's H-cell map exported to %s" % f)

    def index2farm(self, c, kind="in"): # find cell info
        for _, r in self.farm.iterrows():
            if r["type"]==kind and r["cell"]==c:
                return r
        return None


    def farm2address(self, grp="GRP1", well="A1", kind="out"): # find cell address by the label
        label = "%s-%s-%s" % (grp, well, kind.upper())
        for _, r in self.farm.iterrows(): 
            if r['label'] == label:
              return r['holder'], r['slot'], r['well'], r["cell"]
        return None, None, None, None

    def address2farm(self, address): # find cell label by address
        for _, r in self.farm.iterrows(): 
            q = "Tray Holder %s:Slot%s:%s" % (r['holder'], r['slot'], r['well'])
            if address==q:
                return r['cell'], r['group'] 
        return None, None

###########################################  dilutor operations #########################################################

    def dil_deliver(self, volume, system="standard"): # deliver volume in mL
        if volume==0 or self.dilutor is None:
            return 0

        n = math.floor(volume/self.dil_volume)
        remainder = volume - n*self.dil_volume

        if self.verbose: 
            print("\nDilutor 1: %d x %.1f mL %s, remainder of %.1f mL" % (n,
                                                        self.dil_volume, 
                                                        system,
                                                        remainder)
              )

        dilutor = self.session.CreateActivity("DeliverLiquidDilutor")
        dilutor["Dilutor"] = self.dilutor

        if n: 
            for _ in range(n):
                dilutor["Volume"] = self.units.GetMilliLiter(self.dil_volume)
                dilutor["SolventPort"] = self.dil_port(system)
                if not self.simulator: self.session.Execute(dilutor)
                if self.verbose: 
                    print("+++ dispensed %s %s from port %d" % (dilutor["Volume"],
                                                                     system,
                                                              dilutor["SolventPort"])
                      )

        if remainder:
            dilutor["Volume"] = self.units.GetMilliLiter(remainder)
            dilutor["SolventPort"] = self.dil_port(system)
            if not self.simulator:  self.session.Execute(dilutor)
            if self.verbose: 
                print("+++ dispensed %s %s from port %d" % (dilutor["Volume"], 
                                                                 system,
                                                          dilutor["SolventPort"])
                  )
        return 1 

    def dil_port(self, system="standard"): # round robin active ports, port 1 is outlet
        n = len(self.dil_ports[system])
        if n>1: 
            self.dil_index[system] = (self.dil_index[system]+1) % n 
        else: 
            self.dil_index[system] = 0
        return Int32(self.dil_ports[system][self.dil_index[system]])


