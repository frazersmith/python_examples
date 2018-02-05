from robot.api import logger
from robot.version import get_version
from robot import utils
from robot.libraries.BuiltIn import BuiltIn
import datetime
from CSVWriter import CSVWriter


__version__ = "0.1 beta"

ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
ROBOT_LIBRARY_VERSION = get_version()

def get_iperf_tcp_data(iperf_data, value="avg_bandwidth"):

    """ Post process iperf tcp bandwidth data

    Possible values:-

    - avg_bandwidth	- Average bandwidth as Mbits/sec.  Will convert if lower value seen
    - total_transfer	- The total amount transferred in the time as MBytes
    - total_time	- Total time of test in secs
    - all_intervals	- A list of interval readings in secs
    - all_transfers	- A list of transfers in MBytes (correspond to intervals)
    - all_bandwidths	- A list of bandwidths in Mbits/sec

    Examples:-
    | ${avgbw}=	| Get iperf tcp data	| ${stb_output}	| 			|
    | @{ints}=	| Get iperf tcp data	| ${stb_output}	| all_intervals		|
    | @{bws}=	| Get iperf tcp data	| ${stb_output}	| all_bandwidths	|
    """

    #Temp data to work with
#    iperf_data = """------------------------------------------------------------
#Client connecting to 10.172.2.22, TCP port 2333
#TCP window size: 0.17 MByte (WARNING: requested 0.08 MByte)
#------------------------------------------------------------
#[  4] local 10.172.249.228 port 2669 connected with 10.172.2.22 port 2333
#[ ID] Interval       Transfer     Bandwidth
#[  4]  0.0- 2.0 sec  18.2 MBytes  76.5 Mbits/sec
#[  4]  2.0- 4.0 sec  18.2 MBytes  76.5 Mbits/sec
#[  4]  4.0- 6.0 sec  18.2 MBytes  76.5 Mbits/sec
#[  4]  6.0- 8.0 sec  18.2 MBytes  76.5 Mbits/sec
#[  4]  8.0-10.0 sec  18.2 MBytes  76.5 Mbits/sec
#[  4] 10.0-12.0 sec  18.2 MBytes  76.5 Mbits/sec
#[  4] 12.0-14.0 sec  18.2 MBytes  76.5 Mbits/sec
#[  4] 14.0-16.0 sec  18.2 MBytes  76.5 Mbits/sec
#[  4] 16.0-18.0 sec  18.2 MBytes  76.5 Mbits/sec
#[  4] 18.0-20.0 sec  18.2 MBytes  76.5 Mbits/sec
#[  4]  0.0-20.0 sec   183 MBytes  76.6 Mbits/sec
#"""




    # Split into lines
    lines = iperf_data.split("\n")
    if len(lines) < 3:
        #raise PostProcessingError("Badly formed iperf data, not long enough")
        return "xxx"
    # Work out which are readings
    goodlines=[]
    for line in lines:
        if line.find("/sec") > -1:
            goodlines.append(line.replace("-"," - ").replace("["," ").replace("]"," "))
    readings=[]
    for line in goodlines:
        allparts=line.split()
        goodparts=[]
        goodparts.append(str(allparts[1]) + "-" + str(allparts[3]))
        goodparts.append(allparts[5])
        goodparts.append(allparts[6])
        goodparts.append(allparts[7])
        goodparts.append(allparts[8])
        readings.append(goodparts)

    if value=="avg_bandwidth":
        return readings[len(readings)-1][3]
    elif value=="total_transfer":
        return readings[len(readings)-1][1]
    elif value=="total_time":
        return readings[len(readings)-1][0]
    elif value=="all_intervals":
        ret = _get_list_from_list(readings,0)
        del ret[-1]
        return ret
    elif value=="all_transfers":
        ret = _get_list_from_list(readings,1)
        del ret[-1]
        return ret
    elif value=="all_bandwidths":
        ret = _get_list_from_list(readings,3)
        del ret[-1]
        return ret

    

def _get_list_from_list(originallist, element):
    ret = []
    for each in originallist:
        ret.append(each[element])
    return ret


def _convert_to_MB(value, label):
    # Converts value to MBytes
    pass


def _convert_to_Mb(value, label):
    # Converts value to Mbits
    pass

def get_channel_change_times(logfile, csvname, family):
    #datetime.datetime.strptime(mys, "%b %d %H:%M:%S.%f")

 
    startstring = "stream_kill: stream_id"
    videostring = "type=84 'VIDEO_STARTED', status=''"
    audiostring = "type=85 'AUDIO_STARTED', status=''"
    clipstring = "stream_begin: options = "
   

    if family=="Ax5x":
        picstring = "vid_first_pts:"
    else:
        picstring = "type=86 'VIDEO_RESOLUTION_CHANGED', status='"



    csv = CSVWriter()
    csv.set_suffix(csvname)
    csv.set_columns("StartClip","EndClip","TimeToAudio","TimeToPic","TimeToVideo")
    csv.writeline()
    with open(logfile) as f:
        lines = f.read().split('\n')


    #lets reformat the debug to ensure lines are right

    lines = _reformat_log(lines)
    lines = _reformat_log(lines)


    start = ""
    pic = ""
    video = ""
    audio = ""
    startclip = "UNKNOWN"
    endclip = ""

    for line in lines:
 
        #print line

        if line.find(startstring) != -1:
            #Need to write out this one and start again
            if endclip <> "":
                csv.item_append("StartClip",startclip)
                csv.item_append("EndClip",endclip)
                csv.item_append("TimeToPic",pic)
                csv.item_append("TimeToVideo",video)
                csv.item_append("TimeToAudio",audio)
                csv.writeline()
   
                startclip = endclip
                endclip = ""
                start = ""
                pic = ""
                video = ""
                audio = ""

            start = _get_datetime(line)
            
        if line.find(clipstring) != -1:
            endclip = line.split("'")[1].strip("src=")

        if line.find(picstring) != -1 and start != "":
            if pic == "":
                diff = _get_datetime(line) - start
                pic = _convert_to_milliseconds(diff)
            else:
                print "SECOND PIC STRING!!"


        if line.find(videostring) != -1 and start != "":
            diff = _get_datetime(line) - start
            video = _convert_to_milliseconds(diff)

        if line.find(audiostring) != -1 and start != "":
            diff = _get_datetime(line) - start
            audio = _convert_to_milliseconds(diff)
       

def _convert_to_milliseconds(delta):
    msd = (delta / 1000)
    ms = msd.microseconds
    return str(ms)



def _reformat_log(lines):
    newlines = []
    for line in lines:
        #Check the start of the line is a timestamp
        goodline=False
        try:
            ts = datetime.datetime.strptime(line[:22], "%b %d %H:%M:%S.%f")
            goodline = True
        except:
            pass

        if goodline:
            #Check there isnt another goodline on the end
            anotherone = line.find(line[:6], 7)
            if anotherone != -1:
                newlines.append(line[:anotherone])
                newlines.append(line[anotherone:])
            else:
                newlines.append(line)
        else:
            pass
    return newlines           
            
               
                
def _get_datetime(line):
    ret = datetime.datetime.strptime(line[:22], "%b %d %H:%M:%S.%f")
    return ret


class PostProcessingError(RuntimeError):
    pass


