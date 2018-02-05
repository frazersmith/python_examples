# Robot libraries
from robot.version import get_version


# Standard libraries
import os
import json
from time import time, sleep
import threading

# Aminorobot Libraries
from AminorobotLibrary import AminorobotLibrary

DEBUG=False
REFRESH_SECS = 5

__version__ = "0.1 beta"

empty_dict = {
    "stack": [],
    "status": None,
    "refresh": None
}

empty_row = {
    "id": None,
    "status": None,
    "refresh": None,
}

class SharedResource(AminorobotLibrary):

    """
    Abstract baseclass for Aminorobot resources that can be shared among many different devices.
    
    The concept of a SharedResource is a piece of test equipment that other test devices share, and presents a single point of access to other test equipment.
    
    An example of this is eight set top boxes connected to a single HDMI switch.  The output of that switch is connected to a single capture device.
    
    Each STB can be tested through the capture device, but only one at a time after the HDMI switch connects that input to it's output.
    If another STB wants that capture device while it's busy it will need to wait.
    
    In our example, the HDMI Switch would need to inherit from this SharedResource class.  Each device that uses the switch would need a unique ID.
    The HDMI Switch would need to make use of SharedResource's `Grab Shared Resource' keyword (grab_shared_resource method) to obtain control during the keyword that actually changes control (Switch HDMI (switch_hdmi) in that library).  At that point it would
    either be successful in locking it for it's own use, or it would see that it is in use and joint the queue.
    Eventually the queue moves up and each device waiting will get it's turn.
    
    'Refresh' values update every REFRESH_SECS seconds.  If any refresh value is older that 3 * REFRESH_SECS it will be assumed to be 'stale' and be removed by a different thread.
    
    The active device has a thread to do this work, so the test can continue without being held up.

    To implement this in a library, this class must be inherited:-
    | from libraries.SharedResource import SharedResource
    | class HDMISwitch(SharedResource):
    |     # library contents

    You must set a lockfile name that is unique to the instance of the shared resource.
    For example, with an HDMI switch it's serial port will be unique so we can use that:-
    |     self.shared_resource_lockfile = self.serialport.split('/')[-1]

    In the method of the library that controls access add a call to grab the resource, using an identifier unique to the device using the resource:-
    |     def switch_hdmi_port(self, port_number):
    |         # In our example the port_number is unique to the device
    |         self.grab_shared_resource(device_id=port_number, waitfor="2 hours")

    In the method of the library that controls the end of the test run add a call to release the resource for this device:-
    |     def unlock_hdmi_switch(self, port_number):
    |         self.release_shared_resource(device_id=port_number)


        
    """


    def _alive_callback(self):
        # this gives the active_refresh_thread a good indication that the main thread is still alive
        return True

    def _active_refresh_thread(self, callback, device_id):
        while not self.kill_active_thread:
            self._log("Active_refresh_thread refreshing for id '%s'" % str(device_id), "debug")
            # Check if the callback is alive
            if callback: # If the main thread is still alive keep looping/refreshing
                self._log("Callback alive, refreshing Lockfile", "debug")
                with self.Lockfile(self.lockfile_fullpath) as lf:
                    lf.read_and_refresh_lockdata(device_id)
            else:
                break

            sleep(REFRESH_SECS)


    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    class Lockfile():
        """
        This class is designed as a generator for 'with'

        For example...
        | with Lockfile(lockfile) as lf:
        |     #do stuff

        ...to prevent keep the lockfile threadsafe

        """

        def __init__(self, lockfile):
            self.lockfile = lockfile
            self.lockfilelockfile = self.lockfile + "_"
            self.attempts = 100
            self._log = AminorobotLibrary._slog

        def __enter__(self):
            # Check if we can grab control of the lockfiles lockfile
            attempt = 1
            success = False
            while attempt < self.attempts:
                # Check if file exists
                if not os.path.isfile(self.lockfilelockfile):
                    sleep(0.1)
                    # Check for a second time after 100ms
                    if not os.path.isfile(self.lockfilelockfile):
                        # create the lockfiles lockfile
                        with open(self.lockfilelockfile, 'w') as ll:
                            json.dump(time(), ll)
                        success = True
                        break

                sleep(0.1)
                attempt += 1

            if not success:
                raise SharedResourceError("Unable to change the lockfile after %s attempts" % self.attempts)
            else:
                return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            # Remove the lockfilelockfile
            os.remove(self.lockfilelockfile)

        def remove_lockfile(self):
            self._log("Deleting lockfile for SharedResource", "info")
            os.remove(self.lockfile)

        def write_lockfile(self, writedata=empty_dict.copy()):
            # Refresh lockdata then write it
            writedata["refresh"] = time()
            self._log("Refreshing and saving lockfile", "debug")

            with open(self.lockfile, 'w') as lockfile:
                json.dump(writedata, lockfile)

        def read_lockfile(self):
            self._log("Reading lockfile...", "debug")
            with open(self.lockfile, 'r') as lockfile:
                lockdata = json.load(lockfile)

            return lockdata

        def read_or_create_lockdata(self):

            # if it doesn't exist, create it
            if not os.path.isfile(self.lockfile):
                # Create empty lockfile
                self.write_lockfile()

            lockdata = self.read_lockfile()

            return lockdata

        def read_and_refresh_lockdata(self, device_id):
            lockdata = self.read_or_create_lockdata()
            pos = self.get_queue_position(lockdata, device_id)

            lockdata["stack"][pos]["refresh"] = time()

            self.write_lockfile(lockdata)
            return lockdata

        def get_queue_position(self, lockdata, device_id):

            for index in range(len(lockdata["stack"])):
                if lockdata["stack"][index]["id"] == device_id:
                    return index

            # Not found
            return -1

    def __init__(self, override_inherit=False):
        self.subclass = self.__class__.__name__
        self.running_outside_robot = None
        super(SharedResource, self).__init__()
        self.lockfile_fullpath = None

        self.stale = (3 * REFRESH_SECS)
        self.kill_active_thread = False
        self.active_thread = threading.Thread()

        if not DEBUG:
            if self.subclass == 'SharedResource' and not override_inherit:
                raise SharedResourceError("This abstract class must be inherited.")
        else:
            self._log("RUNNING SHAREDRESOURCE IN DEBUG MODE", "warn")

        self.resource_lockfile = None


    @property
    def shared_resource_lockfile(self):
        return self.resource_lockfile

    @shared_resource_lockfile.setter
    def shared_resource_lockfile(self, resource_id):
        self.resource_lockfile = "LCK..%s" % resource_id
        self.lockfile_fullpath = os.path.join("/var/lock", self.shared_resource_lockfile)


    def grab_shared_resource(self, device_id, waitfor="5 minutes"): # TODO change the default waitfor to be in excess of the length of a testsuite run
        """
        [Inherited from the SharedResource library]

        This method/keyword will attempt to take control of the shared resource.
        
        If it is available, a lockfile/queue will be created with this instance in control
        
        If it is busy, this instance will add itself to the bottom of the existing queue
        
        The device_id will be a unique identifier among possible devices that will ask for control of the shared resource.

        :param device_id: Unique ID for the device requesting the resource.
        :param waitfor: How long to wait for a change in queue position before giving up (either as a robot time string or integer of seconds)
        :return: True once control is gained.  False if we've given up waiting

        RIDE Example:-
        *This should not be used in RIDE.  It should be used in the class which inherits it*

        Python Example:-
        | self.grab_shared_resource(device_id=device_port, waitfor="12 hours")

        
        """

        waitfor = self.convert_time_to_secs(waitfor)

        with self.Lockfile(self.lockfile_fullpath) as lf:
            lockdata = lf.read_or_create_lockdata()
            queue_position = lf.get_queue_position(lockdata,device_id)

        if queue_position < 0:
            self._log("I'm currently not in the queue, adding myself", "debug")
            # Add myself to the queue
            row = empty_row.copy()
            row["id"] = device_id
            row["status"] = "queued"
            row["refresh"] = time()
            lockdata["stack"].append(row)
            with self.Lockfile(self.lockfile_fullpath) as lf:
                lf.write_lockfile(lockdata)

            return self.grab_shared_resource(device_id,waitfor)

        elif queue_position == 0:
            # My turn
            self._log("Device '%s' is now head the queue for SharedResource '%s'. Taking control" % (str(device_id), str(self.shared_resource_lockfile)), "info")
            lockdata["stack"][queue_position]["status"] = "active"
            lockdata["stack"][queue_position]["refresh"] = time()
            with self.Lockfile(self.lockfile_fullpath) as lf:
                lf.write_lockfile(lockdata)

            self.active_thread = threading.Thread(target=self._active_refresh_thread, args=(self._alive_callback, device_id))
            self.active_thread.daemon = True
            self.active_thread.start()
            return True

        else: #In the queue

            new_queue_position = queue_position

            while new_queue_position > 0:
                queue_position = new_queue_position


                self._log("Device %s is now in position %s" % (device_id,new_queue_position), "debug")
                time_in_position = time()
                while new_queue_position == queue_position:

                    self._log("Device %s is waiting to change position (currently in position %s)" % (device_id, new_queue_position), "debug")
                    if (time_in_position + waitfor) < time():
                        self._log("Device '%s' has waited too long in position '%s'. Removing myself from the queue and abandoning." % (device_id, new_queue_position), "WARN")
                        # We've waited too long
                        lockdata["stack"].pop(new_queue_position)

                        with self.Lockfile(self.lockfile_fullpath) as lf:
                            lf.write_lockfile(lockdata)

                        return False
                    sleep(REFRESH_SECS)
                    with self.Lockfile(self.lockfile_fullpath) as lf:

                        lockdata = lf.read_and_refresh_lockdata(device_id)
                        new_queue_position = lf.get_queue_position(lockdata,device_id)

                        self._log("Read queue position %s, last position was %s" % (new_queue_position, queue_position), "debug")


                    # Check if data for other ID's is stale

                    with self.Lockfile(self.lockfile_fullpath) as lf:
                        lockdata = lf.read_or_create_lockdata()

                        changed = False
                        for item in list(lockdata["stack"]):
                            self._log("Checking item id '%s' to see if it is stale..." % str(item["id"]), "debug")
                            now = time()
                            self._log("Item '%s' refresh is '%s'" % (str(item["id"]), str(item["refresh"])), "debug")
                            self._log("Time now is '%s'" % str(now), "debug")
                            self._log("Difference is '%s'" % str(now - item["refresh"]), "debug")
                            if item["refresh"] < (now - self.stale):
                                self._log("QUEUE ITEM '%s' IS STALE! Removing it.." % str(item["id"]), "info")
                                lockdata["stack"].remove(item)
                                changed = True

                        if changed:
                            lf.write_lockfile(lockdata)


            # Queue position must now be zero
            self._log("I'm now at the head of the queue", "debug")
            return self.grab_shared_resource(device_id,waitfor)






    def release_shared_resource(self, device_id):
        """
        [Inherited from the SharedResource library]

        The library that inherits this must call this method when the device in control is finished with the resource

        :param device_id: Unique id for the device

        RIDE Example:-
        *This should not be used in RIDE.  It should be used in the class which inherits it*

        Python Example:-
        | self.release_shared_resource(device_id=device_port)

        """

        with self.Lockfile(self.lockfile_fullpath) as lf:
            lockdata = lf.read_or_create_lockdata()
            queue_position = lf.get_queue_position(lockdata,device_id)

            if queue_position == 0:
                # It's our resource to release
                self.kill_active_thread = True

                lockdata["stack"].pop(0)
                if len(lockdata["stack"]) == 0:
                    self._log("I'm the last in queue, deleting lockfile.", "debug")
                    lf.remove_lockfile()

                else:
                    self._log("Queue moved up, saving lockfile", "debug")
                    lf.write_lockfile(lockdata)

            else:
                raise SharedResourceError("Trying to release a resource that is not ours")




class SharedResourceError(RuntimeError):
    pass
