class VideotestError(RuntimeError):
    pass


# Check if STB Tester is installed
try:
    import stbt
    import _stbt.logging
    from stbt import Region
    from stbt import OcrMode
    import cv2
    import numpy

except ImportError:
    stbt = None
    _stbt = None
    Region = None
    OcrMode = None

    raise VideotestError("Required libraries are not installed!  Please run the videotest_install.sh script (if you are using a compatible PC)")


# Robot libraries
from robot.api import logger
from robot.version import get_version
from robot import utils
from robot.libraries.BuiltIn import BuiltIn
from libraries.ESTB import ESTB as ESTBType
from libraries.HDMISwitch import HDMISwitch
import ConfigParser
from pprint import pprint as pp
from AminorobotLibrary import AminorobotLibrary



# Standard libraries
import time
import os
import glob
import subprocess
from contextlib import contextmanager
import re

# Audio test libraries
from numpy import *
from numpy import asarray
from scipy.io import wavfile
from scipy.signal.filter_design import butter, buttord
from scipy.signal import lfilter

import shutil


__version__ = "0.1 beta"
DEBUGSTRING = "from resources.devices.QVT_02_00 import *;uut = QVT_02_00();from libraries.Videotest import *;vt = Videotest();vt.set_uut(uut)"

# this is a tab "	"

DEBUG=False

@contextmanager
def noop_contextmanager():
    yield



class Videotest(AminorobotLibrary):

    """ Amino Videotest Library by Frazer Smith.

    This library is designed for use with Robot Framework.

    It provides wrapper functions for the STB Tester (stbt) open source tool, and adds the
    ablity to test for audio presence, something STB Tester can not do.

    With the correct environment* this wrapper library can give access
    to STB Tester keywords, and provide the Aminorobot with an integrated
    way to:-
        -   Assert if an image matches an area of the video output of the STB
        -   Assert if Motion is detected
        -   Assert if 'Black Screen' is detected
        -   OCR areas of the screen
        -   Use FrameObjects to describe and make use of UI elements
        -   Assert if audio is present, either throughout a complete sample or in segments

    This is a subset of what an off-the-shelf Black-Box system test tool
    (such as Stormtest S3) can provide, but at a fraction of the cost.

    == *Environmental Requirements ==

    The version of STB Tester that is approved for this use is v27.  It
    can run in Kubuntu/Ubuntu 16.04 on a 64bit intel based platform.
    NOTE:   Kubuntu is preferred as the Plasma desktop works better with the Aminorobot IDE (RIDE)
            It is possible to install Ubuntu and then install and switch to the KDE Plasma desktop.
            Instructions can be found on confluence:- http://bit.ly/2uwj0KL

    === Hardware Required ===

    === Video Capture ===
    For each UUT you will need (for v4l2 support) one of these 'videotest_capture_device_type's:-

    'easycap':-
    - An HDMI2AV converter
    - - I have tested and recomend the HDMI2AV device by Esynic (http://www.esynic.com/wp-includes/WEB/MiCP1.htm)
    - - There are cheaper alternatives that look exactly the same (without the esynic brand name in them) but I have found they don't work
    - An EASYCAP based USB capture device
    - - I have tested the LogiLink device VG00001A (http://www.logilink.com/Suche/vg0001a) available very cheaply in China and UK
    - - This uses the Fushicai USBTV007 chipset and identifies itself in linux (sudo lsusb) as 'ID 1b71:3002 Fushicai USBTV007 Video Grabber [EasyCAP]'

    'usbhdmi':-
    - An HDV-UH60 UVC USB3.0 Capture device, which is a cheap clone of the Magewell XI100D (see https://goo.gl/AAH7Xr)
    - - This is Full 1080HD and requires no conversion, but it needs a USB3.0 port to reach transfer speeds fast enough for 1080p60
    - - This uses a Cypress Semiconductor chipset and identifies itself in linux (sudo lsusb) as 'ID 04b4:00f9 Cypress Semiconductor Corp'
    - - NOTE: I have had mixed success with getting devices which work.  Out of 5 purchased I have had to return 2.  If this DoA rate persists it may end up cheaper to go for Magewell.

    '4kpro':-
    - A Magewell Pro Capture HDMI 4K Plus PCI-e card (Part No 11150, see http://www.magewell.com/pro-capture-hdmi-4k-plus)
    - - This is a Pro level capture device and is highly configurable.  Unfortunately that means it needs configuring before you can make use of it.

    OPTIONAL: An HDMI Splitter (if you wish to output to Aminorobot and a TV

    IMPORTANT: I have found that with any of these devices (USB2 or 3) you can not have more than one on any single USB bus.  To see your USB bus layout use 'sudo lsusb -t'.
    Normally desktop PC's have a few USB buses, perhaps one that serves ports on the front on the PC, one that serves USB2 ports on the back and one that serves USB3 on the back.
    If you put two devices on any one bus you will get errors like:-
    - 'Cannot allocate memory'
    - 'No space left on device'
    - 'Protocol Error'
    To overcome this, if you wish to run several STB's from one Aminorobot PC I would advise you to install USB3 PCI-e cards.  Again, even with these only one port on it could be
    utilised so there is no point in getting cards with 4 ports on them. Two is more than enough (to capture STB debug and video).

    You can test your video capture device from the command line in several ways:-
    - Check the bus layout using 'sudo lsusb -t'.  REMEMBER do not put more than one capture device on one bus, regardless of it being on a seperate hub.
    - Check the video device mapping using 'ls /dev/video*'.
    - - You should see a /dev/videoX file (where X is a serial number given when the USB device is attached) for each capture device
    - Run 'gst-launch-1.0 v4l2src device=/dev/video0 ! autovideosink' (or /dev/video1 or /dev/video2 etc) to open a window showing what the capture device is able to see

    === Audio Capture ===
    All the 'usbhdmi','easycap' and '4kpro' devices support alsa sound capture. With the right gstreamer settings Videotest can save a sample to disk then analyse it in many ways.
    
    To understand your alsa settings for gstreamer:-
    - Run 'sudo cat /proc/asound/cards'
    - - You will get an output similar to:-
    
    |  0 [PCH            ]: HDA-Intel - HDA Intel PCH
    |                  HDA Intel PCH at 0xf7230000 irq 42
    |  1 [NVidia         ]: HDA-Intel - HDA NVidia
    |                  HDA NVidia at 0xf7080000 irq 17
    |  2 [Video          ]: USB-Audio - USB3.0 Capture Video
    |                  PHIYO USB3.0 Capture Video at usb-0000:05:00.0-1, super speed

    - In this example, your capture device has created an alsa sound card with hw id '2'.
    - If you have many capture devices they will each have their own hw id
    - In our example, the 'videotest_audio_device' will then be '2'
       

    === IR Blasting/Recording ===
    
    For writing tests using STB Tester's built in 'Record' function you will need an IR capture and replay device.
    I have tested and recommend the RedRat3-II (http://www.redrat.co.uk/products/#redrat3)
    LIRC and ir-keytable are dependancies that are installed using the videotest_install script.
    
    The remote codes for the 'Nova' remote will be installed as the default set.
    
    With all hardware working, you can then issue a 'stbt record' command from the cmdline (ensuring you are in a temp folder, not in the aminorobot repo).
    
    The output of the STB (defaulting to /dev/video0) will be displayed and a window explaining which keyboard presses will send which IR codes.
    
    From here, control the STB as you would from the IR remote and the record function will create a 'test.py' file tracking the keypresses and saving screenshots at every key press.
    
    Once complete you can use a utility like 'gimp' to take what you need from the images created (portions of the screem for image matches, regions, masks etc)
    
    Save the assets you create to the videotest_assets directory using the directory structure based on test and capture device.  You can then take the output of the test.py file to quickly prototype the test in Ride, changing stbt.press to uut.send_key where appropriate.
    
    
    == Installation ==

    Run the 'videotest_install.sh' script from inside the Aminorobot root directory.

    This will install all required packages, config files and clone the assets repo into 'videotest_assets' (as long as it is in the site definition file. See 'Assets' later)

    Example:-
    | # ./videotest_install.sh UK
    | # ./videotest_install.sh HK

    NOTE: One of the packages (lirc) requires interaction from the user.  Simply select 'None' for both configs it wants and continue (the config files
    are installed later by the videotest_install script.)

    === Additional install for 4k pro ===

    The magewell PCI-e card must have it's drivers installed before it can be used.

    . At http://www.magewell.com/downloads download the driver for 'Pro Capture Family (linux)' (Linux, x86).
    . Create ~/.magewell and move the downloaded tar file there
    . Untar the file with 'tar zxf [filename]'
    . Run '/.install.sh'

    You can then check if the card is working by checking the new /dev/videox device is now present (will be video0 if this is the only capture device attached)
    You can further interogate the card with 'mwcap-info -i /dev/video0' (or an alternative videox if it's not 0)

    NOTE: You video pipeline must be set up to explicitly configure the video size.  See the 'Device File Properties' example below

    NOTE: I have found that the alsa levels for the device are very low when I first install it.  To change these:-
    . From command line open 'alsamixer'
    . Press F6 then use arrow keys and enter to select the 'Pro Capture HDMI 4k' device
    . Press F4 to view the capture levels.  If these are low use arrow keys to increase and cycle through them
    . Press ESC when you are finished

    TROUBLESHOOTNG:
    I have seen on many occasions that when the PC hosting the 4kpro card is rebooted it is possible that the capture device is no longer present in /dev/video*.  If this occurs try running 'mwcap-repair.sh' and rebooting again.


    == Device File Properties ==

    *Required*

    You must set :-
    | 'videotest_video_device'			| based on the '/dev/video*' filename used to access the device											|
    | 'videotest_audio_device'			| based on the hardware number for your capture device when listed with 'sudo cat /proc/asound/cards'	|
    | 'videotest_capture_device_type'	| limited to 'easycap', 'usbhdmi' or '4kpro'															|

    *Example* Using EASYCAP with HDMI2AV:-
    | # STBT specific options
    | self.set_property("videotest_video_device","/dev/video0")
    | self.set_property("videotest_audio_device","2")
    | self.set_property("videotest_capture_device_type","easycap")

    *Example* Using USBHDMI:-
    | # STBT specific options
    | self.set_property("videotest_video_device","/dev/video1")
    | self.set_property("videotest_audio_device","3")
    | self.set_property("videotest_capture_device_type","usbhdmi")

    *Example* Using Magewell 4kpro:-
    | # STBT specific options
    | self.set_property("videotest_video_device","/dev/video0")
    | self.set_property("videotest_audio_device","2")
    | self.set_property("videotest_capture_device_type","4kpro")

    This allows for more than one capture device to be present on one PC, as long as they do not share the same USB bus.


    === Other Config Values ===

    Each capture device type (easycap, usbhdmi, 4kpro) has it's own oddities that must be overcome with configuration settings.

    These global settings can be found in [aminorobotroot]/resources/configs/videotest as easycap.cfg, usbhdmi.cfg and 4kpro.cfg

    The global values in this file can be overridden using keywords in the test itself (see `Set Match Parameter`, `Set Motion Parameter`, `Set VT Parameter`, `Set OCR Parameter` and `Set Audio Presence Paramater`)

    There is also the option to load in a config file to create an individual instance of MatchParameters, OCRParameters or AudioPresenceParameters, then use this with a test (see `Read Match Parameters`, `Read OCR Parameters` and `Read Audio Presence Parameters`)

    == Assets ==

    The Videotest library tests use many assets of varying types:-
    - Image files (in PNG format) that can be used for:-
    -- Match tests
    -- Screenshots to statically validate match images
    -- As 'mask' objects to include and exclude areas of the screen using black and white flood fill
    - Config files
    -- Text configs that can be used to specify and of the configurable areas such as Match Parameters, Motion Paramaters etc
    - Region files
    -- Text files that describe a region on the video frame using coordinates

    These assets are stored in a git repo of there own, seperate from the aminorobot repo although it exists in the aminorobot directory structure:-
        For example:-
        /home/user/git_repos/aminorobot -> this is the aminorobot repo root
        /home/user/git_repos/aminorobot/videotest_assets  -> this is the videotest_assets repo.  The 'videotest_assets' directory is ignored by the aminorobot repo
        
    This means you can add/modify files in the aminorobot directory tree (with the exception of the 'videotest_assets' directory) without affecting the 'videotest_assets' repo
    Equally you can add/modify files in aminorobot/videotest_assets tree without affecting the aminorobot repo
    
    This does mean you will need to push/pull to the repos separately, and git status will provide each individual repo status depending on which directory you call it from
    
    #siteinfo Version 2017-07-26
    UK;gitolite@git.aminocom.com:/sqa/videotest_assets.git

    Note: This removes the old method of a network share for assets that was unstable and risky.
    
    == Creating Tests ==

    Test functionality comes in 5 different areas:-

    === Blackscreen ===

    Simple assertion when reviewing frames from the capture device to decide that the output has gone black.  The only config item is a float between 0.0 and 1.0 which defines how black 'black' is
    (i.e. 1 = only RGB 0,0,0 will be recognised as black, 0 = anything from full white to black will assert true, so we need to be as close to 1.0 as we can to avoid false positives)

    See `Wait for Blackscreen`, `Set VT Parameter`, `Clear VT Parameters`

    NOTE: Be carefull when using Blackscreen assertions at boot time, since what presents as a black screen for a TV may present as 'loss of video' to the capture device and not actually go black.

    === Video Motion ===

    Simple assertion that video movement is detected bewteen a number of consecutive frames.  You can look for motion anywhere in the full frame OR reduce the areas of interest using a mask image.

    See `Wait for Motion`, `Set Motion Parameter`, `Clear Motion Parameters`

    NOTE: The only parameter to concern your self with is 'consecutive_frames'.  If a capture device is working faster than the output of the STB (as with usbhdmi) it is possible that
    two frames relay the same frame information and give a false negative on motion detection.  Simply reduce the moveframes per frames count from 10/20 to 8/10 (as with the default
    config files)

    NOTE: A mask image is a png format file with the same width and height as the video frame, where areas with white pixels are tested and areas with black pixels are excluded.

    === Image Matching ===

    This is a complex algorythm using matching paramaters from the OpenCV matchTemplate.  It has a two pass system, first is a rough check that is fast which then triggers a second check that takes more processing power.

    You can match your test image to anywhere in the whole frame, or limit it to a specific region.

    It is possible to diagnose mismatches using stbt from the command line.

    See `Wait for Match`, `Wait until No Match`, `Press Key Until Match`, `Set Match Parameter`, `Clear Match Parameters`

    === Optical Character Recognition (OCR) ===

    This is the most complex feature and also the most prone to error.  You can read text from any region on the frame (the whole frame is possible but not advised).

    This feature uses the tesseract utility which has in excess of 150 different configurable parameters.

    OCR on high resolution input is reliable, OCR on low resolution input is not, so easycap testing should avoid OCR tests.

    See `OCR Result`, `Wait Until Match Text`, `Wait Until No Match Text`, `Press Key Until Match Text`, `Set OCR Parameter`

    === Audio Presence Detect ===
    
    Unlike the video tests, Audio Presence occurs in post processing, in other words we must save a sample then analyse it.
    
    This assertion is bespoke to the Videotest library and does not come from STB Tester.
    
    A set of 'AudioPresenceParamaters' is used to define how we capture this sample, how many segments to split it into and then what criteria we consider to be a pass.
    
    The AudioPresenceParameters are:-
    
    | sample_length			| How long in seconds (float) we will sample the capture device audio	|
    | segment_length		| We will segment the full sample to give better resolution.  This defines the segment length in seconds (float)	|
    | rms_threshold			| RMS (Root Mean Square, in decibels (dB)) threshold is the measurement we must exceed to pass.						|
    |						| Example: In tests, loud or constant sounds (like music playing) tend to return an RMS between -20 & -30. Silence	|
    |						|          is normally less than -70.0, but we set the threshold around -50.0										|
    | testcriteria_time		| We have many different criteria that we can check for. This parameter can be:-									|
    |						|          0 = (default) The RMS for the whole sample, ignoring segments, must exceed rms_threshold					|
    |						|          1 to 100 = The percentage if segments who's RMS must exceed the rms_threshold							|
    |						| This allows us to cater for cases where there may be spoken word, and we are happy that 10% of segments have it	|
    | testcriteria_channels	| We have two channels (even if the STB can output more, it will downmix to 2.  Dolby Digital is not supported yet)	|
    | 						| so we need to tell the presence detect algorithm if we want both, any or specific channels to pass, e.g.			|
    |						|          0 or 1 = Specific channel (other channel will be ignored)												|
    |						|          -1     = Any of the two channels can cause a pass (if one fails we ignore it)							|
    |						|          2      = (default) Both channels must pass																|
    |						| *NOTE:  If you want to ignore any criteria and simply return the AudioPresenceData set testcriteria_time to -1*	|
    | testcriteria_tries	| The number of tries to pass the test criteria before conceding to failure. Default = 1							|
    | save_samples			| True or False (default).  Any samples created from live content will either be preserved or deleted immediately	|
    |						| after reading their contents.  NOTE: These are raw PCM wav files so saving them will consume a lot of space		|
    | remove_dcoffset		| True (default for easycap) or False (default for usbhdmi).  If there are earthing issues (as with the easycap		| 
    |						| devices) this will use the command line utility 'sox' to apply a highpass filter removing anything above 10Hz		|
    |						| NOTE: If 'True' this will also snip out the first 200ms which can cause false positives							|
    
    
    See `Check Audio Presence` for further details.


    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    class Region(stbt.Region):
        """
        Extension of the STB Tester Region, with added scaling based on the capture device

        """



        def __new__(cls, x, y, width=None, height=None, right=None, bottom=None):
            return stbt.Region.__new__(cls, x, y, width, height, right, bottom)

        @property
        def device(self):
            return self._device

        @device.setter
        def device(self, device):
            self._device = device




        def scale(self, device):

            if device == self._device:
                ret = Region(x=self.x, y=self.y,right=self.right, bottom=self.bottom)
                ret.device = self._device
                return ret


            # Load in properties of current device




            # Load in properties of target device

            self._log(self.x, 'debug')
            self._log(self.y, 'debug')
            self._log(self.right, 'debug')
            self._log(self.bottom, 'debug')

            ret =  Region(x=10, y=10, right=20, bottom=20)
            ret.device = 'easycap'
            return ret


    def __init__(self, working_directory=None):
        super(Videotest, self).__init__(working_directory)

        self.bounds_data = {
                "_outputpath":
                    {"blacklist": [
                        ["/var/www"],
                    ]}
            }

        #self.source_pipeline = ""
        #self.sink_pipeline = "xvimagesink sync=false"
        #self.audio_pipeline = "alsasrc device=hw:2,0"


        self.control = "test"
        self.uut = None # type:Videotest
        self.match_parameters=stbt.MatchParameters()
        self.motion_parameters=self._default_motion_parameters()
        self.ocr_parameters=self._default_ocr_parameters()
        self.vt_parameters=self._default_vt_parameters()
        self.scaling_parameters=self._default_scaling_parameters()
        #self.capture_device=None - use vt params
        self.config_file_location="resources/configs/videotest/"
        self.builtin = BuiltIn()
        self.hdmi_switch = HDMISwitch()
        self.running = False
        self.audio_presence_parameters=self.AudioPresenceParameters()
        #self.audio_results=[]
        self._videopath = os.path.join(self._outputpath, self._suitename + '_' + '_video').replace(' ','_')


    def create_region(self, filename=None, x=None, y=None, width=None, height=None, right=None, bottom=None):
        """
        Create a region object to use with matching images or OCR

        There are three different ways to create a region
        - Read in from [filename]
        - x,y,width,height (width and height being relative to x,y)
        - x,y,right,bottom (right and bottom being relative to 0,0)

        For example, x,y,width,height of 200,300,50,70 is the same as x,y,right,bottom of 200,300,250,370

        Reading in from a file allows either of the other two methods (i.e. width/height or right/bottom)

        :param filename: Path and filename to read the region object details from.
         - Note: If you specify a filename all other options are ignored.
        :param x: The top left corner x value
        :param y: The top left corner y value
        :param width: The width in pixels relative to the x point for the bottom right corner
        :param height: The height in pixels relative to the y point for the bottom right corner
        :param right: The bottom right corner x value
        :param bottom: The bottom right corner y value
        :return: Returns an instance of a Region object that can then be passed to matching or OCR functions to limit the area if interest

        RIDE Examples:
        | ${region1}=		| VT.Create Region	| filename="${path}/test01.region"	|		| 			|			|
        | ${region2}=		| VT.Create Region	| x=87								| y=95	| width=100	| height=75	|
        | ${region3}=		| VT.Create Region	| x=25								| y=40	| right=50	| bottom=75	|
        | VT.Wait For Match	| ${path}/etv45.png	| region=${region3}					|		|			|			|

        Python Examples:
        | region1 = vt.create_region(filename=path+'/test01.region')
        | region2 = vt.create_region(x=87,y=95,width=100,height=75)
        | region3 = vt.create_region(x=25,y=40,right=50,bottom=75)
        | vt.wait_for_match(path+'/etv45.png', region=region3)


        """

        # Check we have all the info we need
        regiontype = "Error"
        infile = False
        retregion = None

        if filename is not None:
            infile = True
            x,y,width,height,right,bottom = self._read_region_file(filename)


        if x is None or y is None:
            regiontype = "Error"
        elif width is not None:
            if height is None:
                regiontype = "Error"
            else:
                regiontype = "xywh"
        elif right is not None:
            if bottom is None:
                regiontype = "Error"
            else:
                regiontype = "xyrb"


        if regiontype == "Error":
            if infile:
                raise VideotestError(
                    "Must define either 'x,y,width,height' or 'x,y,right,bottom' in the region file")
            else:
                raise VideotestError(
                    "Must define either 'filename', or 'x,y,width,height' or 'x,y,right,bottom' to create a region")
        else:
            if regiontype=="xywh":
                retregion = self.Region(x=int(x), y=int(y), width=int(width), height=int(height))
            elif regiontype=="xyrb":
                retregion = self.Region(x=int(x), y=int(y), right=int(right), bottom=int(bottom))

        if retregion is None:
            raise VideotestError("Error creating region")
        else:
            return retregion

    def rescale(self, asset, source, target=None):
        """

        If we know the original capture device and which one we want to convert it to we should
        be able to rescale images, masks or regions


        :param asset: can be an image file, an image array, a region, or a mask (which is just an image)
        :param source: The capture device originally used for this asset e.g. usbhdmi
        :param target: The new capture device to scale to (None=use the current capture_device)
        :return: the asset rescaled

        RIDE Examples:
        | ${newreg}=	| VT.Rescale	| ${myregion}			| 4kpro		| usbhdmi	|
        | ${image}=		| VT.Rescale	| ${path}/splash.png	| usbhdmi	| 4kpro		|

        Python Examples:
        | scaled_region = vt.rescale(myregion, "4kpro", "usbhdmi")
        | scaled_image = vt.rescale(path+"/splash.png", "usbhdmi", "4kpro")


        """

        self._log("Received asset = %s" % str(asset), "trace")

        # Check scaling params exist for source and target
        for param in [source, target]:
            if "shape_%s" % param not in self.scaling_parameters.keys():
                raise VideotestError("Capture device '%s' has no scaling parameters" % param)


        target = self.scaling_parameters["shape_%s" % target]
        source = self.scaling_parameters["shape_%s" % source]
        self._log("Target shape %s" % str(target), "debug")
        self._log("Source shape %s" % str(source), "debug")

        fx = float(target[1]) / float(source[1])
        fy = float(target[0]) / float(source[0])
        self._log("fx = %s" % str(fx), "debug")
        self._log("fy = %s" % str(fy), "debug")

        ret_asset = None

        # Convert a filename to a numpy array
        if isinstance(asset, str):
            # A filename, try to load it
            self._log("Rescaling a file, loading it first", "debug")
            filename = asset
            asset = cv2.imread(asset)
            if asset is None:
                raise IOError("Rescale of filename '%s' failed.  File not found" % filename)

        if isinstance(asset, numpy.ndarray):
            # It's a cv2.imread array, lets rescale it
            self._log("Rescaling an image array","debug")
            ret_asset = cv2.resize(asset, (0,0), fx=fx, fy=fy)

        elif isinstance(asset, self.Region):
            # It's a region, lets rescale it
            self._log("Rescaling a Region","debug")
            ret_asset = self.Region(x=int(asset.x * fx), y=int(asset.y * fy), right=int(asset.right * fx), bottom=int(asset.bottom * fy))
        else:
            raise TypeError("Rescaling of this assets failed as the type '%s' was not recognised" % type(asset))

        self._log("Returning asset = %s" % str(ret_asset),"trace")
        return ret_asset


    def _read_region_file(self, filename):
        # Read region file (in config file format) and return x,y,width,height,right,bottom
        x = None
        y = None
        width = None
        height = None
        right = None
        bottom = None

        if not os.path.isfile(filename):
            raise VideotestError("Unable to locate region file named '%s'" % filename)

        config = ConfigParser.RawConfigParser()
        try:
            config.read(filename)
        except ConfigParser.MissingSectionHeaderError:
            raise VideotestError("The file '%s' does not look like a valid region file." % filename)

        try:
            options = config.options("region")
            for option in options:
                if option=="x":
                    x=int(config.get('region', option))
                elif option=="y":
                    y = int(config.get('region', option))
                elif option=="width":
                    width=int(config.get('region', option))
                elif option == "height":
                    height = int(config.get('region', option))
                elif option == "right":
                    right = int(config.get('region', option))
                elif option == "bottom":
                    bottom = int(config.get('region', option))
        except ConfigParser.NoSectionError:
            raise VideotestError("No '[region]' is defined in the filename '%s'" % filename)

        return x,y,width,height,right,bottom


    def _default_vt_parameters(self):

        return {
            "black_threshold":75,
            "save_video":True,
            "framewidth":None,
            "frameheight":None,
            "video_source_pipeline":None,
            "audio_source_pipeline":None,
            "video_device":None,
            "capture_device_type":None,
            "video_sink_pipeline":None
        }


    def _default_ocr_parameters(self):

        return {"supported":None,"mode":OcrMode.PAGE_SEGMENTATION_WITHOUT_OSD, "lang":"eng", "tesseract_config":{}, "tesseract_user_words":None, "tesseract_user_patterns":None}


    def _default_motion_parameters(self):
        # Set motion params to default
        return {"consecutive_frames":None, "noise_threshold":None}

    def _default_scaling_parameters(self):
        # Set scaling params to default
        return {
            "autoscaling":"False",
            "autoscale_source":None,
            "autoscale_target":None}


    def check_ocr_support(self):
        """
        Check if the UUT's video pipeline/capture device is suitable for OCR.  Throws a VideotestError if not.

        It is good practice to have this as a first step in any test which contains OCR

        RIDE Example:
        | VT.Check OCR Support	|

        Python Example:
        | vt.check_ocr_support()


        """
        if self.ocr_parameters['supported'] is None:
            raise VideotestError("You must set uut before checking OCR support.")

        if not self.ocr_parameters['supported']:
            raise VideotestError("OCR not supported")
        else:
            self._log("OCR is supported")

    def set_audio_presence_parameter(self, parameter, value):
        """

        The AudioPresenceParameters are:-

        | sample_length			| How long in seconds (float) we will sample the capture device audio	|
        | segment_length		| We will segment the full sample to give better resolution.  This defines the segment length in seconds (float)	|
        | rms_threshold			| RMS (Root Mean Square, in decibels (dB)) threshold is the measurement we must exceed to pass.						|
        |						| Example: In tests, loud or constant sounds (like music playing) tend to return an RMS between -20 & -30. Silence	|
        |						|          is normally less than -70.0, but we set the threshold around -50.0										|
        | testcriteria_time		| We have many different criteria that we can check for. This parameter can be:-									|
        |						|          0 = (default) The RMS for the whole sample, ignoring segments, must exceed rms_threshold					|
        |						|          1 to 100 = The percentage if segments who's RMS must exceed the rms_threshold							|
        |						| This allows us to cater for cases where there may be spoken word, and we are happy that 10% of segments have it	|
        | testcriteria_channels	| We have two channels (even if the STB can output more, it will downmix to 2.  Dolby Digital is not supported yet)	|
        | 						| so we need to tell the presence detect algorithm if we want both, any or specific channels to pass, e.g.			|
        |						|          0 or 1 = Specific channel (other channel will be ignored)												|
        |						|          -1     = Any of the two channels can cause a pass (if one fails we ignore it)							|
        |						|          2      = (default) Both channels must pass																|
        |						| *NOTE:  If you want to ignore any criteria and simply return the AudioPresenceData set testcriteria_time to -1*	|
        | testcriteria_tries	| The number of tries to pass the test criteria before conceding to failure. Default = 1							|
        | save_samples			| True or False (default).  Any samples created from live content will either be preserved or deleted immediately	|
        |						| after reading their contents.  NOTE: These are raw PCM wav files so saving them will consume a lot of space		|
        | remove_dcoffset		| True (default for easycap) or False (default for usbhdmi).  If there are earthing issues (as with the easycap		|
        |						| devices) this will use the command line utility 'sox' to apply a highpass filter removing anything above 10Hz		|
        |						| NOTE: If 'True' this will also snip out the first 200ms which can cause false positives							|

        RIDE Examples:
        | VT.Set Audio Presence Parameter	| rms_threshold			| -60	|
        | VT.Set Audio Presence Parameter	| sample_length			| 4.0	|
        | VT.Set Audio Presence Parameter	| testcriteria_channels	| -1	|

        Python Examples:
        | vt.set_audio_presence_parameters("rms_threshold",-60)
        | vt.set_audio_presence_parameters("sample_length",4.0)
        | vt.set_audio_presence_parameters("testcriteria_channels",-1)
        or to have a single instance of params, rather than editing the default:
        | app = vt.AudioPresenceParameters()
        | app.rms_threshold = -60
        | app.sample_length = 4.0
        ..etc


        """



        exec ("self.audio_presence_parameters.%s=%s" % (parameter, value))


    def set_match_parameter(self, parameter, value):
        """
        Allows the user to set a MatchParameters parameter (as per https://stb-tester.com/manual/python-api#stbt.MatchParameters)

        NOTE: Capture device specific settings that differ from defaults are loaded from resources/configs/videotest/${videotest_capture_device}.cfg

        RIDE Example:
        | VT.Set Match Parameter	| confirm_threshold	| 0.7	|

        Python Example:
        | vt.set_match_parameter("confirm_threshold",0.7)


        """
        # Need to catch string values

        if parameter in ('match_method', 'confirm_method'):
            try:
                exec("x=%s" % value)
            except NameError:
                value = "'%s'" % value

        exec("self.match_parameters.%s=%s" % (parameter, value))

    def set_ocr_parameter(self, parameter, value):
        """
        Allows the user to set an OCR parameter

        NOTE: Capture device specific settings that differ from defaults are loaded from resources/configs/videotest/${videotest_capture_device}.cfg

        OCR Parameters are:
        . lang - Defaults to 'eng'.  You can install other languages with 'sudo apt-get install tesseract-ocr-[lang]'.  These are supported http://bit.ly/2trFfAI
        . tesseract_user_words - A list of words to whitelist
        . tesseract_user_patterns - A whitelisted pattern to use when matching text (see http://bit.ly/2trXjL6)
        . tesseract_config - A dictionary of tesseract config items as keys paired with their values (see http://bit.ly/2trXjL6)
        ' mode - from the stbt.OcrMode object.

        RIDE Example:
        | VT.Set OCR Parameter	| mode	| OcrMode.SINGLE_WORD	|

        Python Examples:
        | vt.set_ocr_parameter["mode"] = OcrMode.SINGLE_WORD
        | vt.set_ocr_parameter["tesseract_config"] = {"tessedit_char_whitelist":"0123456789"}


        """
        if parameter in ('lang'):
            try:
                exec("x=%s" % value)
            except NameError:
                value = "'%s'" % value

        exec("self.ocr_parameters['%s']=%s" % (parameter, value))

    def set_motion_parameter(self, parameter, value):
        """
        Allows runtime alteration of motion parameters 'consecutive_frames' and 'noise_threshold'
        by default these are loaded in from resources/configs/videotest/${videotest_capture_device}

        RIDE Example:
        | VT.Set Motion Parameter	| consecutive_frames	| 8/20	|

        Python Example:
        | vt.set_motion_parameter("consecutive_frames","8/20")


        """

        if parameter in self.motion_parameters.keys():
            self.motion_parameters[parameter]=value
        else:
            raise VideotestError("Unrecognised motion parameter '%s'" % parameter)

    def set_scaling_parameter(self, parameter, value):
        # TODO: Help
        self.scaling_parameters[parameter] = value


    def set_vt_parameter(self, parameter, value):
        """
        Allows runtime alteration of miscellaneous parameters.
        by default these are loaded in from resources/configs/videotest/${videotest_capture_device}

        Parameters include:-
        | *Parameter*		| *Description*															|
        | black_threshold	| Sets what we consider as 'black' for blackscreen assertion.			|
        |					| 0 means only true black triggers it, 255 allows any colour even		|
        |					| white to trigger it.  Default is 100									|
        | save_video		| globally set if a video is created of the test run and stored			|
        |					| in the output directory												|
        | framewidth        | Define the framewidth of the capture device in use (in pixels)		|
        | frameheight		| Define the frameheight of the capture device in use (in pixels)		|



        RIDE Example:
        | VT.Set VT Parameter	| black_threshold	| 80	|

        Python Example:
        | vt.set_vt_parameter('save_video', True)


        """

        if parameter in self.vt_parameters.keys():
            self.vt_parameters[parameter]=value
        else:
            raise VideotestError("Unrecognised VT parameter '%s'" % parameter)


        # Ensure types are correct
        if not isinstance(self.vt_parameters["black_threshold"], float):
            self.vt_parameters["black_threshold"] = float(self.vt_parameters["black_threshold"])

        if not isinstance(self.vt_parameters["save_video"], bool):
            if isinstance(self.vt_parameters["save_video"], str):
                if self.vt_parameters["save_video"] in ["False", "false"]:
                    self.vt_parameters["save_video"] = False
                else:
                    self.vt_parameters["save_video"] = True
            else:
                # Don't know the type, revert to True
                self._log("Unknown type for save_video!  Assuming 'True'", 'warn')
                self.vt_parameters["save_video"] = True

    def clear_match_parameters(self):
        """
        Clear all match parameters back to defaults, abandoning any settings from config file or set at runtime

        RIDE Example:
        | VT.Clear Match Parameters	|

        Python Example:
        | vt.clear_match_parameters()

        """
        self.match_parameters = stbt.MatchParameters()

    def clear_audio_presence_parameters(self):
        """
        Clear all audio presence parameters back to defaults, abandoning any settings from config file or set at runtime

        RIDE Example:
        | VT.Clear Audio Presence Parameters	|

        Python Example:
        | vt.clear_audio_presence_parameters()

        """
        self.audio_presence_parameters = self.AudioPresenceParameters()


    def clear_vt_parameters(self):
        """
        Clear all VT parameters back to defaults, abandoning any settings from config file or set at runtime

        RIDE Example:
        | VT.Clear VT Parameters	|

        Python Example:
        | vt.clear_vt_parameters()


        """
        self.vt_parameters=self._default_vt_parameters()

    def clear_scaling_parameters(self):
        """
        Clear all Scaling parameters back to defaults, abandoning any settings from config file or set at runtime

        RIDE Example:
        | VT.Clear Scaling Parameters	|

        Python Example:
        | vt.clear_scaling_parameters()


        """
        self.scaling_parameters=self._default_scaling_parameters()

    def clear_motion_parameters(self):
        """
        Clear all motion parameters back to defaults, abandoning any settings from config file or set at runtime

        RIDE Example:
        | VT.Clear Motion Parameters	|

        Python Example:
        | vt.clear_motion_parameters()


        """
        self.motion_parameters = self._default_motion_parameters()

    def set_uut(self, uut):
        """
        Set UUT. Required before you can init the run.  Mandatory for your SUITESETUP

        This allows the library to read the properties of the UUT, to set elements such as videotest_video_device and videotest_capture_device

        This is also the point where default configs for 'Match Parameters' and 'Motion Parameters' are read.

        This will also call `Read Config File` for the capture device the device file specifies, so you don't need to explicitly do so in the test unless you wish to load a custom config.

        :param uut: Should be an instance of the UUT object (use the Get Instance keyword)

        RIDE Example:
        | ${uutobject}=	| Get Library Instance	| UUT	|
        | VT.Set UUT	| ${uutobject}			| 		|

        PythonWrapper Example:-
        | def python_suite_setup(self, uut='UUT'):
        |     self.uut = self.get_lib_instance(uut)
        |     self.vt.set_uut(self.uut)
        NOTE: This method allows you to run it inside Aminorobot (using the ${uut} variable as normal) or outside Aminorobot (passing the uut object already created)

        Python Example:
        | from resources.devices.estb_010203 import *
        | uut = estb_010203()
        | vt.set_uut(uut)


        """

        if not isinstance(uut, ESTBType):
            raise VideotestError("You must pass an instance of the UUT")
        else:
            self.uut = uut

        self.vt_parameters["capture_device_type"] = self.uut.get_property("videotest_capture_device_type")

        if self.vt_parameters["capture_device_type"] is None:
            raise VideotestError(
                "The device file for this UUT does not define a 'videotest_capture_device_type' property")

        filename = "%s%s.cfg" % (self.config_file_location, self.vt_parameters["capture_device_type"])

        self.read_config_file(filename)

        self.vt_parameters["video_device"] = uut.get_property("videotest_video_device")

        if self.vt_parameters["video_device"] is None:
            raise VideotestError(
                "The device file for this UUT does not define a 'videotest_video_device' property")

        # TODO remove source_pipeline and use the vt param.  Do we support old device files?
        self.vt_parameters["video_source_pipeline"] = \
            str(self.vt_parameters["video_source_pipeline"]).replace("${video_device}",self.vt_parameters["video_device"])

        audio_device = uut.get_property("videotest_audio_device")
        if audio_device is None:
            raise VideotestError(
                "The device file for this UUT does not define a 'videotest_audio_device' property")

        self.vt_parameters['audio_source_pipeline'] = \
            str(self.vt_parameters['audio_source_pipeline']).replace("${audio_device}",str(audio_device))



        hdmi_switch = self.uut.get_property("hdmi_switch")
        hdmi_switch_type = self.uut.get_property("hdmi_switch_type")

        if hdmi_switch is not None:
            if hdmi_switch_type is None:
                # Default to Aten switch
                hdmi_switch_type = self.hdmi_switch.default_hdmi_switch_type
            self.hdmi_switch.set_hdmi_switch(hdmi_switch, hdmi_switch_type=hdmi_switch_type)



    def read_audio_presence_parameters(self, filename):
        """
        Read a custom AudioPresenceParameters object from a config file.

        :param filename: Full path/name of file to read
        :return: An instance of AudioPresenceParameter class using the config element from the file

        RIDE Example:
        | ${app}=	| VT.Read Audio Presence Parameters	| ${path}/app.config	|

        Python Example:
        | app = vt.read_audio_presence_parameters(path+'/app.config')


        """
        config = None

        if isinstance(filename, ConfigParser.RawConfigParser):
            # This is an open config, return the AudioPresenceParameters from it
            config = filename
        else:
            if not os.path.isfile(filename):
                raise VideotestError("Unable to locate AudioPresenceParameters file named '%s'" % filename)
            else:
                config = ConfigParser.RawConfigParser()
                config.read(filename)


        ret = self.AudioPresenceParameters()


        try:
            options = config.options("audio_presence_parameters")
            for option in options:
                exec ("ret.%s=%s" % (option, config.get('audio_presence_parameters', option)))
            return ret
        except ConfigParser.NoSectionError:
            return None


    def read_match_parameters(self, filename):
        """
        Read a custom 'MatchParameters' object from a config file.

        :param filename: The full path and filename of the config file
        :return: An instance of MatchParameters class based on the details in the config file

        RIDE Example:
        | ${mp}=	| VT.Read Match Parameters	| ${path}/mp.config	|

        Python Example:
        | mp = vt.read_match_parameters(path+'/mp.config')



        """

        config = None

        if isinstance(filename, ConfigParser.RawConfigParser):
            # This is an open config, return the MatchParameters from it
            config = filename
        else:
            if not os.path.isfile(filename):
                raise VideotestError("Unable to locate MatchParameters file named '%s'" % filename)
            else:
                config = ConfigParser.RawConfigParser()
                config.read(filename)


        ret = stbt.MatchParameters()

        try:
            options = config.options("match_parameters")
            for option in options:
                exec ("ret.%s=%s" % (option, config.get('match_parameters', option)))
            return ret
        except ConfigParser.NoSectionError:
            return None

    def read_ocr_parameters(self, filename):
        """
        Read a custom 'OcrParameters' object from a config file.

        :param filename: The full path and filename of the config file
        :return: A dictionary of OCR Parameters based on the details in the config file

        RIDE Example:
        | ${ocrp}=	| VT.Read OCR Parameters	| ${path}/ocrp.config	|

        Python Example:
        | ocrp = vt.read_ocr_parameters(path+'/ocrp.config')


        """

        config = None

        if isinstance(filename, ConfigParser.RawConfigParser):
            # This is an open config, return the Ocr Parameters from it
            config = filename
        else:
            if not os.path.isfile(filename):
                raise VideotestError("Unable to locate OcrParameters file named '%s'" % filename)
            else:
                config = ConfigParser.RawConfigParser()
                config.read(filename)


        ret = self._default_ocr_parameters()

        try:
            options = config.options("ocr_parameters")
            for option in options:
                exec ("ret['%s']=%s" % (option, config.get('ocr_parameters', option)))
            return ret
        except ConfigParser.NoSectionError:
            return None


    def read_config_file(self, filename):
        """
        Read a custom configuration file.

        This allows the library to set default configuration by reading a configuration settings file which contains one or more of:-
        . Match Parameters
        . Motion Parameters
        . OCR Parameters
        . Audio Presence Parameters
        . Videotest (VT) Parameters

        :param filename: Should contain settings for each element.  See config files in resources/configs/videotest for examples

        (NOTE: `Set UUT` will call this itself to read default configuration for the specified capture device.  Only use this keyword explicitly if you want to load a custom config)

        RIDE Example:
        | VT.Read Config File	| custom_config.cfg	|

        Python Example:
        | vt.read_config_file(path+'/custom_config.cfg')

        """

        if not os.path.isfile(filename):
            raise VideotestError("Unable to locate config file named '%s'" % filename)

        config = ConfigParser.RawConfigParser()

        config.read(filename)

        readoptions = False

        # Read MatchParameters
        mp = self.read_match_parameters(config)

        if mp is not None:
            self.match_parameters = mp
            readoptions = True

        # Read AudioPresenceParameters
        app = self.read_audio_presence_parameters(config)

        if app is not None:
            self.audio_presence_parameters = app
            readoptions = True

        # Read OCRParameters
        op = self.read_ocr_parameters(config)
        if op is not None:
            self.ocr_parameters = op
            readoptions = True


        # Read MotionParamaters
        try:
            options = config.options("motion_parameters")
            for option in options:
                self.set_motion_parameter(option, config.get('motion_parameters', option))
            readoptions = True
        except ConfigParser.NoSectionError:
            pass

        # Read VT Paramaters
        try:
            options = config.options("vt_parameters")
            for option in options:
                self.set_vt_parameter(option, config.get('vt_parameters', option))
            readoptions = True
        except ConfigParser.NoSectionError:
            pass

        # Read scaling parameters
        try:
            options = config.options("scaling_parameters")
            for option in options:
                self.set_scaling_parameter(option, eval(config.get('scaling_parameters', option)))
            readoptions = True
        except ConfigParser.NoSectionError:
            pass


        if not readoptions:
            raise VideotestError("The config file '%s' contained no valid config options." % filename)


    def init_run(self, save_video=None):
        """
        Initialise the video source and sink pipelines either ready for testing or to enable screenshot capture, and choose if a video of your run is saved.

        Note: The UUT must be set first using `Set UUT` as the videotest_video_device is device specific and defined in the device file.

        Mandatory for your SUITESETUP

        :param save_video: ${True} (default) or ${False}

        RIDE Examples:
        | VT.Init Run	| 						|
        | VT.Init Run	| save_video=${False}	|

        Python Examples:
        | vt.init_run()
        | vt.init_run(False)


        """

        if save_video is None:
            save_video = self.vt_parameters["save_video"]


        if save_video is False or save_video in ["False", "false"]:
            save_video = None
        else:
            # Work out where to put this video
            save_video=self._videopath


        if self.hdmi_switch.serialport is not None:
            # Try to grab switch and lock it
            hdmi_switched = self.hdmi_switch.switch_hdmi()
            if not hdmi_switched:
                raise VideotestError("Unable to use HDMI switch.  Lockfile exists ('%s')" % self.hdmi_switch.lockfile)

        stbt.init_run(gst_source_pipeline=self.vt_parameters["video_source_pipeline"],
                      gst_sink_pipeline=self.vt_parameters["video_sink_pipeline"],
                      control_uri=self.control,
                      save_video=save_video)

        self.running = True



    def wait_for_motion(self, timeout='30 seconds', consecutive_frames=None, noise_threshold=None, mask=None):

        """

        Wait for motion in the video frame.

        :param timeout: Given as a Robot time string, this is how long we wait for motion to be detected

        :param consecutive_frames: A string representation of a ratio of movement in an overall number of frames.
        For example, 10/20 means movement must be detected in 10 out of 20 consecutive frames.
        NOTE: This has a global setting for each capture device type in resources/configs

        :param noise_threshold: A floating point number between 0 (never detect movement, so pointless) to 1.0 (all noise should count as movement).
        Defaults to 0.84
        NOTE: This has a global setting for each capture device type in resources/configs

        :param mask: A png format image providing areas of the screen to look for movement, where white pixels/areas are included and black is not.
        Defaults to full screen.

        :returns MotionResult object (https://stb-tester.com/manual/python-api#stbt-motionresult)

        RIDE Examples:
        | VT.Wait For Motion	| timeout=2 minutes		|					|
        | VT.Wait For Motion	| noise_threshold=0.7	| mask=${path}/mymask.png	|

        Python Examples:
        | vt.wait_for_motion(timeout="2 minutes")
        | vt.wait_for_motion(noise_threshold=0.7, mask=path+'/mymask.png')

        """

        if mask is not None:
            if not os.path.isfile(mask):
                raise VideotestError("Mask file '%s' not found!" % mask)

        if consecutive_frames is None:
            consecutive_frames = self.motion_parameters['consecutive_frames']

        if noise_threshold is None:
            try:
                noise_threshold = float(self.motion_parameters['noise_threshold'])
            except TypeError:
                noise_threshold = None


        timeout_secs = utils.timestr_to_secs(timeout)
        self.draw_text('Wait for motion...')
        motionresult = stbt.wait_for_motion(timeout_secs=timeout_secs,
                             consecutive_frames=consecutive_frames,
                             noise_threshold=noise_threshold,
                             mask=mask)

        if motionresult.motion:
            self.draw_text("...motion detected")
        else:
            self.draw_text("...motion NOT detected!")

        return motionresult



    def wait_for_match(self, image, timeout='30 seconds', consecutive_matches="1", region=Region.ALL, match_parameters=None):
        """
        Execution waits until a Match operation returns True for an area of the video frame.  A timeout will cause a failure.

        This will use the global Match Parameters that you can set in the config file and at runtime.

        :param image: The .png file you wish to match.  It is good practice to have a .png for each capture device and keep them in a path where the videotest_capture_device can dynamically choose the right one.
        :param timeout: The time Aminorobot will wait for the match, as a Robot Time String.  Defaults to '30 seconds'.
        :param consecutive_matches: How many consecutive frames the match must exist for the assert to be positive. Defaults to 1
        :param region: pass a region of interest, created using `Create Region` keyword.  Defaults to fullscreen (Region.ALL)
        :param match_parameters: pass a custom MatchParamaters object.  Defaults to the global Parameters for this capture device
        :returns MatchResult object when the image is found (https://stb-tester.com/manual/python-api#stbt-matchresult)

        Examples:
        | ${capture_device}=	| UUT.Get Property				| videotest_capture_device			|
        | VT.Wait For Match		| ${capture_device}/match1.png	| timeout=2 minutes					|
        | VT.Wait For Match		| ${capture_device}/match8.png	| consecutive_matches=5				|
        | ${region1}=			| VT.Create Region				| filename="${path}/region1.region	|
        | VT.Wait For Match		| ${capture_device}/match2.png	| region=${region1}					|

        Python Examples:
        | capture_device = uut.get_property("videotest_capture_device")
        | vt.wait_for_match(path+'/'+capture_device+'/match1.png, timeout='2 minutes')
        | vt.wait_for_match(path+'/'+capture_device+'/match8.png, consecutive_matches=5)
        | region1 = vt.create_region(filename=path+'/region1.region')
        | vt.wait_for_match(path+'/'+capture_device+'/match2.png', region=region1)


        """


        consecutive_matches = int(consecutive_matches)
        timeout_secs = utils.timestr_to_secs(timeout) #TODO: once Aminorobotlibrary supports time string conversion


        mp = self.match_parameters

        if match_parameters is not None:
            mp = match_parameters

        self.draw_text("Waiting for match...")
        matchresult = stbt.wait_for_match(image, timeout_secs=timeout_secs, consecutive_matches=consecutive_matches,
                                          match_parameters=mp, region=region)
        if matchresult.match:
            self.draw_text("...matched")
        else:
            self.draw_text("...NOT matched!")


        return matchresult


    def match(self, image, frame=None, region=Region.ALL, match_parameters=None, debug_path=None):
        """
        Perform a single 'STB Tester Match' operation, and return a MatchResult object.

        This is designed for use during test creation from the python console, but could be called as a keyword in RIDE if you can find a use for it.

        Best used when creating tests to validate assertions before using a `Wait For Match` in the test itself.

        This will use the global Match Parameters that you can set in the config file and at runtime.

        - Debugging a Match -

        If you specify a 'debug_path' the verbose match will run and the result will be copied to the debug_path.

        It is better to debug a match against a still frame captured using `Save Screenshot` and then loaded into a variable using cv2's imread:-
        | vt.save_screenshot(path+'/screenshot.png')
        | import cv2
        | frm = cv2.imread(path+'/screenshot.png')
        | vt.match(path+'/channel_icon.png',frame=frm, debug_path=path)

        This will create a directory called stbt-debug in [path] which contains an html index file (index.html) which you should open in a browser.

        The page will give step by step debug to demonstate which element og the match algorithm failed.

        :param image: The .png file you wish to match.  It is good practice to have a .png for each capture device and keep them in a path where the videotest_capture_device can dynamically choose the right one.
        :param region: pass a region of interest, created using `Create Region` keyword.  Defaults to fullscreen (Region.ALL)
        :param frame: A cv2 img format frame, or the live video_pipeline if None
        :param match_parameters: pass a custom MatchParamaters object.  Defaults to the global Parameters for this capture device
        :returns MatchResult object (https://stb-tester.com/manual/python-api#stbt-matchresult)


        """



        if debug_path is not None:
            if not os.path.isdir(debug_path):
                raise VideotestError("Invalid debug_path '%s'" % debug_path)



        mp = self.match_parameters

        if match_parameters is not None:
            mp = match_parameters

        self.draw_text("Checking Matching...")

        with (_stbt.logging.scoped_debug_level(2) if debug_path is not None else noop_contextmanager()):
            matchresult = stbt.match(image, frame=frame, match_parameters=mp, region=region)

        if debug_path is not None:
            if os.path.isdir(os.path.join(debug_path, "stbt-debug")):
                shutil.rmtree(os.path.join(debug_path, "stbt-debug"))

            shutil.move(os.path.join(os.curdir,"stbt-debug"), os.path.join(debug_path, "stbt-debug"))
            print "Debug created at '%s'" % os.path.join(debug_path, "stbt-debug")

        return matchresult



    def draw_text(self, text, duration="10 seconds"):
        """
        Output some text to overlay the video being saved.  Useful for following the test when replaying it's video.

        :param text: String to display - Try keeping it below 30 characters
        :param duration: How long to have it remain overlaid (non blocking) as a Robot time string

        RIDE Examples:
        | VT.Draw Text	| Matching Bootsplash	| 						|
        | VT.Draw Text	| Waiting for motion	| duration=5 seconds	|

        Python Examples:
        | vt.draw_text("Matching Bootsplash")
        | vt.draw_text("Waiting for motion", duration="5 seconds")

        """


        duration_secs = utils.timestr_to_secs(duration)

        try:
            stbt.draw_text(text, duration_secs=duration_secs)
        except AttributeError:
            pass


    def wait_for_blackscreen(self, timeout="30 seconds", mask=None, threshold=None):
        """
        Wait for Blackscreen from the video output of the STB.


        :param timeout: A Robot time string representing how long you wish to wait before failing the assertion
        :param mask: A file containing areas of white (RGB 255:255:255) and black (RGB 0:0:0) which will be used to mask the video output, with only white areas being considered
        :param threshold: As the box does not output actual black (RGB 0:0:0) a threshold between 0 (all is considered black) to 100 (only 0:0:0 is black) is used.  This is set in config file, or during runtime or defaults to 75.

        RIDE Example:-
        | VT.Wait for Blackscreen	| timeout=2 minutes		|
        | VT.Wait for Blackscreen	| threshold=60			|

        Python Examples:
        | vt.wait_for_blackscreen(timeout="2 minutes")
        | vt.wait_for_blackscreen(threshold=60)

        """

        if mask is not None:
            if not os.path.isfile(mask):
                raise VideotestError("Mask file '%s' not found!" % mask)


        timeout_secs = utils.timestr_to_secs(timeout)
        if threshold is None:
            threshold = float(self.vt_parameters["black_threshold"])
        else:
            threshold = float(threshold)

        self.draw_text("Waiting for blackscreen...")
        try:
            assert stbt.wait_until(lambda : stbt.is_screen_black(threshold=threshold, frame=None, mask=mask), timeout_secs=timeout_secs)
            self.draw_text("...blackscreen detected.")

        except AssertionError:
            self.draw_text("...blackscreen timeout!")
            raise VideotestError("Timeout waiting for blackscreen!")


    def wait_until_no_match(self, image, timeout="30 seconds", interval="0.1 seconds", region=Region.ALL, match_parameters=None):
        """
        Execution waits until an image no longer matches an area of the video frame.  A timeout will cause a failure.

        This will use the global Match Parameters that you can set in the config file and at runtime.

        :param image: The .png file you wish to match.  It is good practice to have a .png for each capture device and keep them in a path where the videotest_capture_device can dynamically choose the right one.
        :param timeout: The time Aminorobot will wait for the match to stop, as a Robot Time String.  Defaults to '30 seconds'.
        :param interval: The time period between checks that the match still exists, as a Robot time string.  Defaults to 0.1 seconds.
        :param region: pass a region of interest, created using `Create Region` keyword.  Defaults to fullscreen (Region.ALL)
        :param match_parameters: Pass a custom match parameters object.  Defaults to the global matchparameters for this capture device

        RIDE Examples:-
        | VT.Wait until no match	| ${path}/myimage.png	| timeout=2 minutes		|
        | VT.Wait until no match	| ${path}/myimage.png	| region=${myregion}	|

        Python Examples:
        | vt.wait_until_no_match(path+'/myimage.png', timeout="2 minutes")
        | vt.wait_until_no_match(path+'/myimage.png',region=myregion)

        """

        timeout_secs = utils.timestr_to_secs(timeout)
        interval_secs = utils.timestr_to_secs(interval)

        mp = self.match_parameters

        if match_parameters is not None:
            mp = match_parameters

        self.draw_text("Wait for 'no match'...")
        try:
            assert stbt.wait_until(lambda: not stbt.match(image,
                                                          frame=None,
                                                          match_parameters=mp,
                                                          region=region),
                                   timeout_secs=timeout_secs,
                                   interval_secs=interval_secs)
            self.draw_text("...'no match' successful.")
        except AssertionError:
            self.draw_text("...'no match' timed out!")
            raise VideotestError("No match timed out for image '%s' within %s." % (image, timeout))



    def teardown_run(self):
        """
        Required to safely close the gstreamer object.

        Mandatory for your SUITETEARDOWN

        RIDE Example:-
        | VT.Teardown Run	|

        Python Example:
        | vt.teardown_run()

        """

        stbt.teardown_run()

        if self.hdmi_switch.serialport is not None:
            self.hdmi_switch.unlock_switch()

    def __del__(self):
        if self.running:
            self.teardown_run()
            self.running = False



    def press_key_until_match(self, key, image, interval="0.5 seconds", max_presses="30", consecutive_matches="1", region=Region.ALL):
        """
        Repeatedly send a single key to the UUT until a match criteria is met, or a max_presses value is exceeded

        Uses the global MatchParameters object

        Sends the key to HNRKey by default, but will use a supported IR Blaster if it is configured in device file

        :param key: The key value to press
        :param image: The image (file) to match
        :param interval: Time between press and match and next iteration
        :param max_presses: How many times to press the key before giving up
        :param consecutive_matches: How many consecutive frames must match to assert as true match
        :param region: A 'Region' object (created or loaded from file using `Create Region`) to limit the search area of the frame
        :return: MatchResult object if successful, None if it fails

        RIDE Example:-
        | VT.Press Key Until Match	| RIGHT	| ${path}/myimage.png	| region=${myregion}	|

        Python Example:
        | vt.press_key_until_match("RIGHT", path+'/myimage.png',region=myregion)


        """

        interval_secs = utils.timestr_to_secs(interval)
        max_presses = int(max_presses)
        match_parameters = self.match_parameters


        presscount=0
        self.draw_text("Press key until match...")
        while presscount <= max_presses:
            #Press key
            self.uut.send_key(key)
            #Wait interval
            time.sleep(interval_secs)
            #Check match
            ret = stbt.match(image, match_parameters=match_parameters, region=region)
            if ret:
                self.draw_text("...matched after %s presses" % str(presscount))
                return ret
            presscount+=1

        self.draw_text("...failed to match after %s presses!" % str(presscount))
        raise VideotestError("Failed to match after %s presses!" % str(presscount))


    def wait_until_match_text(self, text, timeout="30 seconds", interval="0.1 seconds", case_sensitive=False, region=Region.ALL, ocr_parameters=None):
        """
        Execution waits until a text string is seen using OCR in a region of the video frame.  A timeout will cause a failure.


        :param text: The text string you wish to match.
        :param timeout: The time Aminorobot will wait for the match before failing, as a Robot Time String.  Defaults to '30 seconds'.
        :param interval: The time period between checks for the text, as a Robot time string.  Defaults to 0.1 seconds.
        :param case_sensitive: Set text match case sensitivity.  Defaults to False/${False}
        :param region: pass a region of interest, created using `Create Region` keyword.  Defaults to fullscreen (Region.ALL)
        :param ocr_parameters: pass a custom ocr_parameters object, defaults to the global ocr_parameters

        RIDE Examples:-
        | VT.Wait until match text	| Network starting		| timeout=2 minutes			|
        | VT.Wait until match text	| DTV					| case_sensitive=${True}	|

        Python Examples:
        | vt.wait_until_match_text("Network starting",timeout="2 minutes")
        | vt.wait_until_match_text("DTV",case_sensitive=True)


        """

        timeout_secs = utils.timestr_to_secs(timeout)
        interval_secs = utils.timestr_to_secs(interval)

        op = self.ocr_parameters
        if ocr_parameters is not None:
            op = ocr_parameters


        match_parameters = self.match_parameters
        self.draw_text("Wait for OCR match...")
        try:
            assert stbt.wait_until(lambda: stbt.match_text(text,
                                                           frame=None,
                                                           case_sensitive=case_sensitive,
                                                           region=region,
                                                           mode=op['mode'],
                                                           lang=op['lang'],
                                                           tesseract_config=op['tesseract_config']),
                                   timeout_secs=timeout_secs,
                                   interval_secs=interval_secs)

            self.draw_text("...OCR match successful.")
        except AssertionError:
            self.draw_text("...OCR match failed!")
            raise VideotestError("Failed to find text '%s' within %s." % (text, timeout))


    def wait_until_no_match_text(self, text, timeout="30 seconds", interval="0.1 seconds", case_sensitive=False, region=Region.ALL, ocr_parameters=None):
        """
        Execution waits for a text string, seen using OCR in a region of the video frame, to disappear.  A timeout will cause a failure.

        :param text: The text string you wish to check no match for.
        :param timeout: The time Aminorobot will wait for the match to disappear before failing, as a Robot Time String.  Defaults to '30 seconds'.
        :param interval: The time period between checks for the text, as a Robot time string.  Defaults to 0.1 seconds.
        :param case_sensitive: Set text match case sensitivity.  Defaults to False/${False}
        :param region: pass a region of interest, created using `Create Region` keyword.  Defaults to fullscreen (Region.ALL)
        :param ocr_parameters: pass a custom ocr paramater object, defaults to global ocr paramaters

        Example:-
        | VT.Wait until no match text	| Network starting		| timeout=2 minutes			|
        | VT.Wait until no match text	| DTV					| case_sensitive=${True}	|

        Python Examples:
        | vt.wait_until_no_match_text("Network starting",timeout="2 minutes")
        | vt.wait_until_no_match_text("DTV",case_sensitive=True)

        """

        timeout_secs = utils.timestr_to_secs(timeout)
        interval_secs = utils.timestr_to_secs(interval)


        op = self.ocr_parameters
        if ocr_parameters is not None:
            op = ocr_parameters

        self.draw_text("Wait until OCR match has gone...")
        try:
            assert stbt.wait_until(lambda: not stbt.match_text(text,
                                                               frame=None,
                                                               case_sensitive=case_sensitive,
                                                               region=region,
                                                               mode=op['mode'],
                                                               lang=op['lang'],
                                                               tesseract_config=op['tesseract_config']),
                                   timeout_secs=timeout_secs,
                                   interval_secs=interval_secs)
            self.draw_text("...OCR match gone successfully.")
        except AssertionError:
            self.draw_text("...OCR 'no match' timed out!")
            raise VideotestError("Failed no match of text '%s' within %s." % (text, timeout))


    def ocr_result(self, frame=None, region=Region.ALL, ocr_parameters=None, draw=True):
        """
        OCR a region of the screen and return the findings.

        The OCR function is very complex and fully customisable.  See the following resources for help:-
        . `Set OCR Parameter`
        . STB Tester OCR Tips - http://bit.ly/2trXjL6
        . Tesseract manual - http://bit.ly/2uNNta3

        :param frame: A frame obtained from a previous Match or Motion result, or None to use live stream from UUT (defaults to None)
        :param region: A 'Region' object (created or loaded from file using `Create Region`) to limit the search area of the frame
        :param ocr_parameters: Pass a custome OCR Parameter object. Defaults to global ocr parameters
        :param draw: Draws a message to video capture display if True
        :return: String representation of what was interpretted by OCR

        RIDE Example:-
        | ${ipaddress}=	| VT.OCR Result	| region=${ipregion}	|

        Python Examples:
        | ipaddress = vt.ocr_result(region=ipregion)

        """

        op = self.ocr_parameters
        if ocr_parameters is not None:
            op = ocr_parameters

        # returns a string
        if draw:
            self.draw_text("Performing OCR read.")


        ret = stbt.ocr(frame=frame, region=region, mode=op['mode'], lang=op['lang'],tesseract_config=op['tesseract_config'],tesseract_user_words=op['tesseract_user_words'],tesseract_user_patterns=op['tesseract_user_patterns'])
        return ret

    def press_key_until_match_text(self, key, text, interval="0.5 seconds", max_presses="30", consecutive_matches="1", region=Region.ALL, ocr_parameters=None):
        """
        Repeatedly send a single key to the UUT until a match text criteria is met, or a max_presses value is exceeded

        Uses HNRKey by default but will use IR Blaster if configured in device file

        :param key: The key value to press
        :param text: The text to match
        :param interval: Time between press and match text assertion
        :param max_presses: How many times to press the key before giving up
        :param consecutive_matches: How many consecutive frames must match to assert as true match
        :param region: A 'Region' object (created or loaded from file using `Create Region`) to limit the search area of the frame
        :return: MatchResult object if successful, None if it fails

        RIDE Example:-
        | VT.Press Key Until Match	| RIGHT	| ${path}/myimage.png	| region=${myregion}	|

        Python Example:
        | vt.press_key_until_match_text("RIGHT",path+'/myimage.png',region=myregion)


        """

        interval_secs = utils.timestr_to_secs(interval)
        max_presses = int(max_presses)
        match_parameters = self.match_parameters


        presscount=0
        self.draw_text("Press key until match text...")
        while presscount <= max_presses:
            #Press key
            self.uut.send_key(key)
            #Wait interval
            time.sleep(interval_secs)
            #Check match
            #ret = stbt.match_text(image, match_parameters=match_parameters, region=region)
            op = self.ocr_parameters
            if ocr_parameters is not None:
                op = ocr_parameters
            ret = stbt.match_text(text, frame=None, region=region,mode=op['mode'], lang=op['lang'],tesseract_config=op['tesseract_config'])

            if ret:
                self.draw_text("...matched text after %s presses." % str(presscount))
                return ret
            presscount+=1

        self.draw_text("...failed to match text within %s presses!" % str(presscount))
        raise VideotestError("Failed to match text within %s presses!" % str(presscount))


    def _convert_freq(self, freq, rate):
        return freq * 2.0 / (rate * 1.0)

    def _lowpass_filter(self, freq, samples, rate):
        pass_gain = 3.0
        stop_gain = 60.0
        pass_freq = self._convert_freq(freq, rate)
        stop_freq = self._convert_freq(freq * 2, rate)
        ord, wn = buttord(pass_freq, stop_freq, pass_gain, stop_gain)
        b, a = butter(ord, wn, btype='low')
        filtered = lfilter(b,a,samples)
        return filtered


    def _bandpass_filter(self, freq, width, samples, rate): # doesn't work
        pass_gain = 3.0
        stop_gain = 60.0
        pass_freq = [self._convert_freq((freq-(width/2)), rate), self._convert_freq((freq+(width/2)), rate)]
        width = width + 500
        stop_freq = [self._convert_freq((freq-(width/2)), rate), self._convert_freq((freq+(width/2)), rate)]
        ord, wn = buttord(pass_freq, stop_freq, pass_gain, stop_gain)
        b, a = butter(ord, wn, btype='bandpass')
        filtered = lfilter(b,a,samples)

        return filtered


    def _read_wav(self, filename, segment_length):
        try:
            sample_freq, samples = wavfile.read(filename)
        except IOError:
            raise VideotestError("File '%s' was not found" % filename)

        try:
            if samples.shape[1] != 2:
                raise VideotestError("Unable to work with %s channels.  Only support 2 channels." % str(samples.shape[1]))
        except IndexError:
                raise VideotestError("Malformed audio.  Must be 16bit PCM, 2 channels")

        if samples.dtype==dtype('int16'):
            # Convert to float from -1 to +1
            sndarray = samples / (2.**15)
        else:
            raise VideotestError("I need 16 bit samples")

        # Concatenate to the last whole segment
        secsnip = sndarray[:(len(sndarray) - len(sndarray) % int(sample_freq * segment_length))]

        # split into seconds
        secs = array_split(secsnip,(float(len(secsnip))/int(sample_freq * segment_length)))

        # Return the sample rate, the full sound array and a list of each second of sound array data
        return sample_freq, sndarray, secs, samples

    def _get_rms(self, sndarray, channel=0):

        channel = sndarray[:,channel]

        self._log("""get_rms channel data:- '%s'""" % channel, 'debug')

        # Calculate RMS
        rms = sqrt(mean(channel**2))

        self._log("""get_rms rms linear:- '%s'""" % rms, 'debug')

        #Convert to dB

        try:
            rms = 20 * math.log10(rms)
            self._log("""get_rms rms db:- '%s'""" % rms, 'debug')
        except ValueError:
            raise VideotestError("'No Input' detected when testing Audio")

        return rms

    def _get_next_audiofile(self, outputpath):

        count = len(glob.glob(os.path.join(outputpath,"audio_sample-???.wav")))

        return "audio_sample-%03d.wav" % (count+1)

    class AudioPresenceParameters(AminorobotLibrary):

        def __init__(self, sample_length=5.0,
                     segment_length=0.5,
                     rms_threshold=-50.0,
                     testcriteria_time=0, # Full sample RMS
                     testcriteria_channels=2, # All channels
                     testcriteria_tries=1,
                     save_samples=False,
                     remove_dcoffset=False):
            super(Videotest.AudioPresenceParameters, self).__init__()

            # Create data boundaries
            self.bounds_data = {
                "testcriteria_channels":
                    {"whitelist": [
                        range(-1, 3),
                    ]},
                "testcriteria_time":
                    {"whitelist": [
                        range(-1,101),
                    ]},
                "sample_length":
                    {"truthtable": [
                        "{value} <= 60.0 and {value} > 0"
                    ]},
                "save_samples":
                    {"truthtable": [
                        "True if {value} is None else ({value} == True or {value} == False)"
                    ]},

            }



            self.sample_length=sample_length
            self.segment_length=segment_length
            self.rms_threshold=rms_threshold
            self.testcriteria_time = testcriteria_time
            self.testcriteria_channels=testcriteria_channels
            self.testcriteria_tries=testcriteria_tries
            self.save_samples=save_samples
            self.remove_dcoffset=remove_dcoffset



        def __repr__(self):
            return (
                "AudioPresenceParameters(sample_length=%r, segment_length=%r, "
                "rms_threshold=%r, testcriteria_time=%r, "
                "testcriteria_channels=%r, testcriteria_tries=%r, save_samples=%r, "
                "remove_dcoffset=%r)"
                % (self.sample_length, self.segment_length,
                   self.rms_threshold, self.testcriteria_time,
                   self.testcriteria_channels, self.testcriteria_tries,
                   self.save_samples, self.remove_dcoffset)
            )






    class AudioPresenceData(object):
        def __init__(self, sample_freq=None,
                     sample_sndarray=None,
                     segment_sndarrays=None,
                     samples=None,
                     sample_channels_rms=None,
                     segment_channels_rms=None,
                     sample_results=None,
                     segment_results=None,
                     segment_pct=None,
                     overall_result=None,
                     result_comment=None):
            self.sample_freq=sample_freq
            self.sample_sndarray=sample_sndarray
            self.segment_sndarrays=segment_sndarrays
            self.samples=samples
            self.sample_channels_rms=sample_channels_rms
            self.segment_channels_rms=segment_channels_rms
            self.sample_results=sample_results
            self.segment_results=segment_results
            self.segment_pct=segment_pct
            self.overall_result=overall_result
            self.result_comment=result_comment

        def __repr__(self):
            return (
                "AudioPresenceData(sample_freq=%r, "
                "sample_sndarray.shape=%r, "
                "segment_sndarrays.count=%r, "
                "samples.shape=%r, "
                "sample_channels_rms=%r, "
                "segment_channels_rms=%r, "
                "sample_results=%r, "
                "segment_results=%r, "
                "segment_pct=%r, "
                "overall_result=%r, "
                "result_comment=%r)"
                % (self.sample_freq, self.sample_sndarray.shape,
                   self.segment_sndarrays.__len__(), self.samples.shape, self.sample_channels_rms,
                   self.segment_channels_rms, self.sample_results, self.segment_results,
                   self.segment_pct, self.overall_result, self.result_comment)
            )



    def _create_sample(self, audio_pipeline=None, app = None, filename=None, outputdir=None):

        if outputdir is None:
            outputpath = self._outputpath
        else:
            outputpath = outputdir

        if audio_pipeline is None:
            audio_pipeline = self.vt_parameters["audio_source_pipeline"]

        audio_pipeline = audio_pipeline.split(" ")


        if app is None:
            app = self.audio_presence_parameters

        if filename is None:

            fullname = os.path.join(outputpath, self._get_next_audiofile(outputpath))

        else:
            fullname = os.path.join(outputpath, filename)
            if os.path.isfile(fullname):
                os.remove(fullname)
            if app.remove_dcoffset and os.path.isfile(fullname + "dc"):
                os.remove(fullname + "dc")




        # Create sample called `fullname`
        with open(os.path.join(outputpath, "audio_presence_debug.txt"), "a") as output:
            proc = subprocess.Popen(["gst-launch-1.0", "-e", audio_pipeline[0], audio_pipeline[1],
                                     "!", "queue", "!", "audioconvert", "!", "wavenc", "!", "filesink",
                                     "location=%s" % (fullname + "dc" if app.remove_dcoffset else fullname)],
                                    stdout=output, stderr=output)

        # wait for app.sample_length
        time.sleep(app.sample_length + app.segment_length + (0.2 if app.remove_dcoffset else 0.0)) # Add an extra segment + 200ms (if we are removeing DC) to act as a guard period
        # Now close it nicely
        os.kill(proc.pid, subprocess.signal.SIGINT)
        time.sleep(1)

        if app.remove_dcoffset:
            # Pass the temp file through sox for highpass 10
            try:
                self._log("Removing DC offset and initial 200ms spike from captured audio")
                process = subprocess.Popen(["sox", fullname + "dc", fullname, "highpass", "10", "trim", "0.2" ])
                process.wait()
            except OSError:
                raise VideotestError("Utility 'sox' not installed.  Please re-run ./videotest_install.sh")

        return fullname


    def check_audio_presence(self, audio_presence_parameters=None, filename=None, outputdir=None):
        """
        Check for Audio Presence in a sample or number of segments, in 1 or both channels (left and right).
        
        When testing live content, you will specify a sample length (the full time of the capture) and segment length (a portion of that sample to have creater resolution).
        
        For example, the standard AudioPresenceParamaters (APP) for sample and segment length are 5 seconds and 0.5 seconds respectively.
        This gives you a 5 second audio capture (2 channel stereo) which is then subdevided into 10 half second segements.
        
        You can alter these values for your own particular needs, for example you could have a sample length of 4.2 seconds with segments of 0.2 (so there would be 22 segments).
        
        The other main criteria (in APP) is the rms_threshold.  This defines a boundary that the calculated RMS dB value must exceed for audio presence, or be below for audio silence.
         
        RMS stands for Root Mean Square and is a standard way to quantify the amplitude of maveforms over time.
        
        In our application (audio frequency) we convert it to a logarithmic decibel value (dB), where 0 dB represents a theoretical maximum (as we normalise our 16bit data between 1 and -1)
        
        This is also the way many amplifiers or other Hi-Fi components measure sound energy, so should be familiar to most.
        
        The default threshold we set for RMS is -50.0dB.  Anything less than this we consider to be silence.
        
        We can also check for many different critera when asserting for Audio Presence.  These are chosen with setting values for
        testcriteria_time and testcriteria_channel in the APP.
        
        Time:  Either the RMS of the full sample must exceed the RMS threshold, or any percentage of the samples we wish
        Channels: We can ensure both channels pass, any channel passes or a single particular channel passes.
        And any combination of time/channel is allowed.
        
        For example: If we only care about half of the samples passing for either of the audio channels, we set time to 50, and channels to -1
        
        Default values for testcritera_time and testcriteria_channels are 0 (full sample), and 2 (both channels).
        
        Finally, you can use APP to set the amount of tries you will allow the capture before you give up and accept a fail result.
        
        RIDE Examples:-
        | ${apd}=	| VT.Check Audio Presence				|										|
        | ${app}=	| VT.Read Audio Presence Parameters	| ${path}/audio.params					|
        | ${apd}=	| VT.Check Audio Presence				| audio_presence_parameters = ${app}	|

        Python Examples:
        | apd = vt.check_audio_presence()
        | app = vt.read_audio_presence_parameters(path+'/audio.params')
        | apd = vt.check_audio_presence(audio_presence_parameters=app)
        
        :param audio_presence_parameters: See `Create Audio Presence Parameters`.
        If none are specified the global values will be used.
        :param filename: If you would rather analyse a saved file specify the name (relative to the aminorobot root folder or absolute).
        If no filename is specified a live capture will be taken.
        NOTE: The file must be in uncompressed 16bit PCM, 2 channel format. (wav of aiff).
        :return: An instance of AudioPresenceData
        """
        apd = self._check_audio(audio_presence_parameters, filename, presence=True, outputdir=outputdir)
        return apd

    def make_thumbnail(self, frame, max_width=500):
        """
        Resize a frame to a thumbnail with a max_width (maintaining ratio)

        RIDE Example:-
        | ${frame}=	| VT.Grab Screenshot	|			|
        | ${thumb}=	| VT.Make Thumbnail		| ${frame}	|

        Python Example:
        | match = vt.wait_for_match(image_file)
        | thumb = vt.make_thumbnail(match.frame)


        """

        factor = float(max_width)/frame.shape[1]

        return cv2.resize(frame, (0,0), fx=factor, fy=factor)

    def save_screenshot(self, region=Region.ALL, filename=None, as_thumbnail=False, frame=None):

        """
        Save a screenshot directly from the video pipeline.
        
        You can crop to a specific region.
        
        :param region: Defaults to full frame (Region.ALL) or you can limit the region to save with a Region class
        :param filename: If 'None' (default) the screenshot will be in the output directory called 'screenshot_xxxxx.png' where xxxxx is an auto incrementing serial number

        RIDE Example:-
        | VT.Save Screenshot	| filename=${path}/screen1.png	|
        | VT.Save Screenshot	| region=${myregion}			|

        Python Examples:
        | vt.save_screenshot(filename=path+'/screen1.png')
        | vt.save_screenshot(region=myregion)

        """
        if frame is None:
            img = self.grab_screenshot(region=region)
        else:
            img = frame

        fileprefix = "screenshot"

        if as_thumbnail:
            img=self.make_thumbnail(img)
            fileprefix = "thumbnail"

        self._log("img size = %s" % int(img.size),'debug')

        # if no filename provided, work out the next one

        if filename is None:
            i = 1
            while os.path.exists(os.path.join(self._outputpath, "%s_%05d.png" % (fileprefix,i))):
                i += 1
                if i > 99999:
                    raise VideotestError("Too many %ss in this folder" % fileprefix)

            filename = os.path.join(self._outputpath, "%s_%05d.png" % (fileprefix,i))
            self._log("Filename will be '%s'" % filename,'debug')



        try:
            if filename[-4:]!=".png":
                filename = filename + ".png"
            ret = cv2.imwrite(filename, img)
            if ret:
                self._log("Saved file '%s' successfully" % filename,'debug')
            else:
                raise VideotestError("Unable to save %s to '%s'" % (fileprefix,filename))
        except:
            raise VideotestError("Unable to save %s to '%s'" % (fileprefix,filename))


    def grab_screenshot(self, region=Region.ALL):
        """
        Returns a screenshot of the live video pipeline in cv2 image format (numpy array of RGB values)

        :param region:
        :return: returns the image captured as a numpy array if required (for further processing)

        RIDE Example:
        | ${img}=	| VT.Grab Screenshot	|

        Python Example:
        | img = vt.grab_screenshot()


        """


        img = stbt.get_frame()

        if region!=Region.ALL:

            # Crop the image

            img = img[region.y:region.bottom, region.x:region.right]  # Crop from x, y, w, h -> 100, 200, 300, 400

            if img.size == 0:
                raise VideotestError("Resizing to region '%s' caused an error" % str(region))

        return img




    def check_audio_silence(self, audio_presence_parameters=None, filename=None, outputdir=None):
        """
        Performs in a very similar way to `Check Audio Presence` with the exception that we are looking for silence.

        For examples and parameters see `Check Audio Presence`
        
        """
        apd = self._check_audio(audio_presence_parameters, filename, presence=False, outputdir=outputdir)
        return apd


    def _check_audio(self, audio_presence_parameters=None, filename=None, presence=True, outputdir=None):
        if self.running:
            # We have a Videotest running, lets write some info to the screen
            self.draw_text("Checking audio %s" % "presence" if presence else "silence")
        if audio_presence_parameters is None:
            audio_presence_parameters = self.audio_presence_parameters

        # If you specify a filename only try once (it won't change!) and don't delete it
        if filename is None:
            tries = audio_presence_parameters.testcriteria_tries
        else:
            tries = 1
            audio_presence_parameters.save_samples=True

        for thistry in range(0,tries):
            if self.running:
                self.draw_text("...try %s..." % str(thistry+1))
            # Create the sample, store it in the run folder,
            if filename is None:
                thisfile = self._create_sample(app=audio_presence_parameters, outputdir=outputdir)
            else:
                thisfile = filename

            apd = self._get_audio_presence_data(audio_presence_parameters, filename=thisfile)


            if audio_presence_parameters.save_samples == False:
                os.remove(thisfile)
                if audio_presence_parameters.remove_dcoffset:
                    os.remove(thisfile + "dc")

            apd = self._complete_apd_data(apd, audio_presence_parameters)


            if presence:
                apd = self._check_apd_against_presence_criteria(apd, audio_presence_parameters)
            else:
                apd = self._check_apd_against_silence_criteria(apd, audio_presence_parameters)


            #self.audio_results.append(apd)

            if not apd.overall_result:
                if thistry+1 < tries:
                    self._log("Check Audio %s: Try %s failed\n%s"
                                % (("Presence" if presence else "Silence"), str(thistry+1), apd.result_comment), 'warn')
            else:
                self._log("Check Audio %s: Try %s passed"
                            % (("Presence" if presence else "Silence"),str(thistry+1)))
                if self.running:
                    self.draw_text("Audio %s passed test criteria." % "presence" if presence else "silence")
                break

        if not apd.overall_result:
            try:
                if self.running:
                    self.draw_text("Audio %s FAILED test criteria." % "presence" if presence else "silence")
                raise VideotestError("Failed Check Audio %s\n%s" % (("Presence" if presence else "Silence"),apd.result_comment))
            finally:
                self._log(apd, 'debug')

        return apd

    def _get_audio_presence_data(self, audio_presence_parameters=None, filename=None):

        if audio_presence_parameters is None:
            audio_presence_parameters = self.audio_presence_parameters

        apd = self.AudioPresenceData()


        if filename is None:
            # Automatically create one, and use gstreamer to capture it
            pass

        apd.sample_freq, apd.sample_sndarray, \
        apd.segment_sndarrays, apd.samples = self._read_wav(filename,
                                                            audio_presence_parameters.segment_length)

        apd = self._calculate_rms(apd, audio_presence_parameters)

        return apd

    def _calculate_rms(self, audio_presence_data, audio_presence_parameters = None):
        apd = audio_presence_data

        if audio_presence_parameters is None:
            app = self.audio_presence_parameters
        else:
            app = audio_presence_parameters

        # Sample RMS per channel
        apd.sample_channels_rms = zeros(apd.sample_sndarray.shape[1])

        for channel in range (0,len(apd.sample_channels_rms)):
            apd.sample_channels_rms[channel] = self._get_rms(apd.sample_sndarray,channel)

        # RMS per segment per channel

        apd.segment_channels_rms = zeros((len(apd.segment_sndarrays), apd.sample_sndarray.shape[1]))

        for segment in range (0,len(apd.segment_sndarrays)):
            for channel in range(0,apd.sample_sndarray.shape[1]):
                apd.segment_channels_rms[segment][channel] = self._get_rms(apd.segment_sndarrays[segment], channel)

        return apd

    def _complete_apd_data(self, apd, app):
        # Presence with define if we want audio presence or not

        apd.overall_result = True
        apd.result_comment = ""

        apd.sample_results = zeros(2)
        apd.segment_results = zeros((len(apd.segment_sndarrays),2))
        apd.segment_pct = zeros(2)

        # Complete the APD data by calculating booleans and pct for exceeding RMS
        count_ch = zeros(2)
        for channel in range(0,2):
            apd.sample_results[channel] = (apd.sample_channels_rms[channel] > app.rms_threshold)
            for segment in range(0,len(apd.segment_sndarrays)):
                apd.segment_results[segment][channel] = (apd.segment_channels_rms[segment][channel] > app.rms_threshold)
                if apd.segment_results[segment][channel]:
                    count_ch[channel]+=1
            apd.segment_pct[channel] = (count_ch[channel]/len(apd.segment_sndarrays))*100

        return apd


    def _check_apd_against_presence_criteria(self, apd, app):

        # Return if we set no criteria
        if app.testcriteria_time == -1:
            self._log("Ignoring test criteria, returning apd only")
            apd.result_comment="No criteria"
            return apd

        # Test elements against criteria
        if app.testcriteria_time == 0:
            # Full sample
            if app.testcriteria_channels == 2:
                # Both channels must exceed RMST
                if not (apd.sample_results[0] and apd.sample_results[1]):
                    apd.overall_result = False
                    if not apd.sample_results[0] and not apd.sample_results[1]:
                        apd.result_comment += "In the full sample, neither channel exceeds RMS threshold."
                    elif not apd.sample_results[0]:
                        apd.result_comment += "In the full sample, channel 0 (left) does not exceed RMS threshold."
                    else:
                        apd.result_comment += "In the full sample, channel 1 (right) does not exceed RMS threshold."
            elif app.testcriteria_channels == -1:
                # Either channel can be above RMST
                if not (apd.sample_results[0] or apd.sample_results[1]):
                    apd.overall_result = False
                    apd.result_comment += "In the full sample, neither channel exceeds RMS threshold"
            elif app.testcriteria_channels == 0 or app.testcriteria_channels == 1:
                # Specific channel must be above RMST
                if not (apd.sample_results[app.testcriteria_channels]):
                    apd.overall_result = False
                    apd.result_comment += "In the full sample, the channel '%s' exceeds RMS threshold" % str(app.testcriteria_channels)
            else:
                # Incorrect testcriteria_channel
                raise VideotestError("Invalid testcriteria_channel setting '%s'" % str(app.testcriteria_channel))

        elif app.testcriteria_time <= 100 and app.testcriteria_time >= 1:
            # Percentage of segments
            if app.testcriteria_channels == 2:
                # Both channels must exceed the percentage threshold
                if not (apd.segment_pct[0] >= app.testcriteria_time and apd.segment_pct[1] >= app.testcriteria_time):
                    apd.overall_result = False
                    if not apd.segment_pct[0] >= app.testcriteria_time and not apd.segment_pct[1] >= app.testcriteria_time:
                        apd.result_comment += "Neither channel exceeds RMS thresholds for the required percentage of segments."
                    elif not apd.segment_pct[0] >= app.testcriteria_time:
                        apd.result_comment += "Channel 0 (left) fails to exceed RMS threshold for the required percentage of segments."
                    else:
                        apd.result_comment += "Channel 1 (right) fails to exceed RMS threshold for the required percentage of segments."
            elif app.testcriteria_channels == -1:
                # Either channel can
                if not (apd.segment_pct[0] >= app.testcriteria_time or apd.segment_pct[1] >= app.testcriteria_time):
                    apd.overall_result = False
                    apd.result_comment += "In the full sample, neither channel exceeds RMS thresholds for the required percentage of segments."
            elif app.testcriteria_channels == 0 or app.testcriteria_channels == 1:
                # A specific channel must
                if not apd.segment_pct[app.testcriteria_channels] >= app.testcriteria_time:
                    channel = "0 (left)" if (app.testcriteria_channels == 0) else "1 (right)"
                    apd.overall_result = False
                    apd.result_comment += "Channel %s fails to exceed RMS threshold for the required percentage of segments." % channel
            else:
                # Incorrect testcriteria_channel
                raise VideotestError("Invalid testcriteria_channel setting '%s'" % str(app.testcriteria_channel))
        else:
            # Incorrect testcriteria_time
            raise VideotestError("Invalid testcriteria_time setting '%s'" % str(app.testcriteria_time))

        return apd

    def _check_apd_against_silence_criteria(self, apd, app):
        # Return if we set no criteria
        if app.testcriteria_time == -1:
            self._log("Ignoring test criteria, returning apd only")
            apd.result_comment = "No criteria"
            return apd

        # Silence criteria is simpler.  To achieve silence, both channels must drop below
        # the RMS threshold for the full sample

        if (apd.sample_results[0] or apd.sample_results[1]):
            apd.overall_result = False
            if apd.sample_results[0] and apd.sample_results[1]:
                apd.result_comment += "Neither channel was silent for the duration of the sample."
            else:
                apd.result_comment += "Channel %s was not silent for the duration of the sample." % "0 (left)" if apd.sample_results[0] else "1 (right)"

        return apd

    def read_magewell_info(self, device='/dev/video0', debug=True):

        # TODO:Help
        # TODO:Turn off debug by default

        """
        HELP
        :param device: defaults to '/dev/video0'
        :return:
        """

        testdata = 'Device\n  Family name ............................ Pro Capture\n  Product name ........................... Pro Capture HDMI 4K+\n  Firmware name .......................... High Performance Firmware\n  Serial number .......................... D115161208019  \n  Hardware version ....................... D\n  Firmware version ....................... 1.27\n  Driver version ......................... 1.2.3269\n  Board ID ............................... 0\n  Channel ID ............................. 0\n  Bus address ............................ bus 6, device 0\n  PCIe speed ............................. gen 2\n  PCIe width ............................. x4\n  Max playload size ...................... 128 Bytes\n  Max read request szie .................. 256 Bytes\n  Total memory size ...................... 512 MB\n  Free memory size ....................... 169 MB\n  Max input resolution ................... 4096x2160\n  Max output resolution .................. 4096x2160\n  Chipset temperature .................... 61.5\xc2\xbaC\n\nInput common\n  Video input ............................ HDMI\n  Audio input ............................ HDMI\n  Auto scan .............................. Yes\n  AV Link ................................ Yes\n\nInput video\n  Signal state ........................... Locked\n  Resolution ............................. 720x576p 50.00 Hz\n  Aspect ................................. 4:3\n  Total size ............................. 864x625\n  X offset ............................... 0\n  Y offset ............................... 0\n  Color space ............................ YUV BT.601\n  Quantization ........................... Limited\n  Saturation ............................. Limited\n\nInput audio\n  Audio format ........................... 48000 Hz, 16 bit, LPCM\n  Channel 1 & 2 .......................... Valid\n  Channel 3 & 4 .......................... Invalid\n  Channel 5 & 6 .......................... Invalid\n  Channel 7 & 8 .......................... Invalid\n  Status data ............................ 04 00 00 02 01 00 00 00\n                                           00 00 00 00 00 00 00 00\n                                           00 00 00 00 00 00 00 00\n\nInput specific\n  Signal status .......................... Valid\n  Mode ................................... HDMI\n  HDCP ................................... No\n  Color depth ............................ 8 bits\n  Pixel encoding ......................... Y/U/V 4:4:4\n  VIC .................................... 17\n  IT content ............................. False\n  Timing - Scanning format ............... Progressive\n  Timing - Frame rate .................... 50.00\n  Timing - H Total ....................... 864\n  Timing - H Active ...................... 720\n  Timing - H Front porch ................. 12\n  Timing - H Sync width .................. 64\n  Timing - H back porch .................. 68\n  Timing - H field 0 V total ............. 625\n  Timing - H field 0 V active ............ 576\n  Timing - H field 0 V front porch ....... 5\n  Timing - H field 0 V sync width ........ 5\n  Timing - H field 0 V back porch ........ 39\n  Timing - H field 1 V total ............. 620\n  Timing - H field 1 V active ............ 576\n  Timing - H field 1 V front porch ....... 0\n  Timing - H field 1 V sync width ........ 5\n  Timing - H field 1 V back porch ........ 39\n\nHDMI information frame - AVI\n  Type ................................... 0x00\n  Version ................................ 0x02\n  Length ................................. 0x0d\n  Checksum ............................... 0xb5 (Failed)\n  Data ................................... 51 58 00 11 00 00 00 00\n                                           00 00 00 00 00\n\nHDMI information frame - AUDIO\n  Type ................................... 0x84\n  Version ................................ 0x01\n  Length ................................. 0x0a\n  Checksum ............................... 0x70 (Ok)\n  Data ................................... 01 00 00 00 00 00 00 00\n                                           00 00\n\nHDMI information frame - SPD\n  Type ................................... 0x83\n  Version ................................ 0x01\n  Length ................................. 0x19\n  Checksum ............................... 0xb1 (Ok)\n  Data ................................... 42 72 6f 61 64 63 6f 6d\n                                           53 54 42 20 52 65 66 73\n                                           77 20 44 65 73 69 67 6e\n                                           01\n\nHDMI information frame -- MS\n  N/A\n\nHDMI information frame - VS\n  Type ................................... 0x81\n  Version ................................ 0x01\n  Length ................................. 0x04\n  Checksum ............................... 0x6b (Ok)\n  Data ................................... 03 0c 00 00\n\nHDMI information frame -- ACP\n  N/A\n\nHDMI information frame -- ISRC1\n  N/A\n\nHDMI information frame -- ISRC2\n  N/A\n\nHDMI information frame -- GAMUT\n  N/A\n\n'

        output = ''

        if debug:
            output = testdata

        # Work through lines
        lines = output.split('\n')

        mwcap_info = {}
        group = ''

        linecount = 0
        lastinfo = ""

        for line in lines:
            linecount+=1
            try:
                if line != '':

                    if line[0] != ' ':
                        group = line
                        mwcap_info[group.lower()] = {}

                    else:
                        line = line.lstrip(' ')
                        if line == 'N/A':
                            mwcap_info[group.lower()] = line.lower()
                        else:

                            elements = [s for s in line.split('..') if s]
                            if len(elements) == 2:
                                lastinfo = elements[0].strip(' ').lower()
                                mwcap_info[group.lower()][lastinfo] = elements[1].strip('.').strip(' ').lower()

                            else:
                                if re.match("[0-9 ]+",line) is not None:
                                    mwcap_info[group.lower()][lastinfo]+=" %s" % line.strip(" ")

            except:
                print "This line caused an error '%s' (line number %s)" % (line, str(linecount))

        return mwcap_info

    def validate_magewell_info_item(self, group, item, value=None):
        # TODO: Help
        """

        :param group:
        :param item:
        :param value:
        :return:
        """

        mwinfo = self.read_magewell_info()

        group = group.lower()

        item = item.lower()

        if value is not None:
            value = value.lower()

        ret = None

        try:
            ret = mwinfo[group][item]
        except KeyError:
            try:
                ret = mwinfo[group]
                print ret
                if ret!="N/A":
                    raise LookupError("Item '%s' not found in Magewell group '%s'" % (item, group))
            except KeyError:
                raise KeyError("Group '%s' not found in Magewell info" % group)

        if value is None:
            return ret
        else:
            return True if value==ret else False
