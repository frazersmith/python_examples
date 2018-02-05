# Robot libraries
from robot.api import logger
from robot.version import get_version
from robot import utils
from resources.configs.WiFiRouterConfig import TPLINK_WDR3600 as DefaultWiFiConfig
import operator
import time

from libraries.LinuxBox import LinuxBox

__version__ = "0.1 beta"

class WiFiRouter(LinuxBox):
    """ Amino WiFiRouter Library by Frazer Smith.

    This library is designed for use with Robot Framework.

    This is an extension of the LinuxBox library with specific OpenWRT commands.

    
    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self):
        
        LinuxBox.__init__(self)


        # Note, active_radio is a string integer that represents the RADIOS entry that is current
        # it is not set here but is automatically set to the default in the config object
        # when the set_config command is called
        self.active_radio = None

        self.set_config(DefaultWiFiConfig())

        self.restart_wifi = True

    def set_active_radio(self, radio):
        """ TODO
        """

        # Check support of that radio
        if str(radio) in self.config.RADIOS.values():
            self.active_radio = int(radio)
        else:
            raise WiFiRouterError("'%s' is not a valid radio. Supported radios are :%s" % (str(radio), str(self.config.RADIOS)))

    def get_active_radio(self):
        """ TODO
        """

        return str(self.active_radio)

    def get_config_item(self, config_item):
        """  Get a WiFiRouter config item at runtime

        Note: To get interface attributes you must use `Get Interface Attribute`

        Examples:
        | ${radios}=	| Get config item	| RADIOS	|
        | ${modes5g}=	| Get config item	| MODES_1	|

        """
        #config_item = 'config.' + config_item
        return getattr(self.config, config_item)



    def get_router_settings(self, setting=None):

        """ Get router settings : returns a dictionary of all settings

        TODO

        """

        # Get current config for this radio
        uci = self.send_router_command_and_return_output("uci show wireless")
        uci = uci.split('\n')
        uci_dict = {}
        for u in uci:
            us = u.split('=')
            uci_dict[us[0]]=us[1]

        if setting is None:
            return uci_dict
        else:
            try:
                ret = uci_dict[setting]
                return ret
            except KeyError:
                return 'NOTSET'

    



    def check_ping_stats(self, targetip, packets=10):
        """ TODO
        """
        
        packets = int(packets)
        self._login()        
        output, error = self._conn.execute_command("ping -c %s %s" % (str(packets), targetip) , return_stderr=True)
        packet_loss = ""
        rtmin = ""
        rtavg = ""
        rtmax = ""
        for line in output.split("\n"):
            if "packets transmitted," in line:
                packet_loss = line.split()[6]
            elif "round-trip min/avg/max" in line:
                rt = line.split()[3]
                rtmin = rt.split("/")[0]
                rtavg = rt.split("/")[1]
                rtmax = rt.split("/")[2]

        return packet_loss, rtmin, rtavg, rtmax
                
    def set_config(self, config_instance):
        """ TODO
        """

        if (isinstance(config_instance, DefaultWiFiConfig)):
            self.config = config_instance
            self.set_active_radio(self.config.DEFAULTS['RADIO'])
            #self.active_radio = int(self.config.RADIOS['default'])

        else:
            raise WiFiRouterError("Incorrect object type passed for `config`")
        

    def check_link_stability(self, interface, targetmac, howlong="2 minutes"):
        """ TODO
        
        """
        
        howmanytimes = int(utils.timestr_to_secs(howlong) / 5)
        #self.send_commands_over_debug("echo '' > /tmp/linktemp.txt")
        rc = []
        signal = []
        self._login()
        for x in range(howmanytimes):
            nowtime = time.time()
            output, error = self._conn.execute_command("iw dev %s station get %s | grep signal: | awk '{print $2}'" % (interface, targetmac) , return_stderr=True)
            if 'command failed' in error:
                rc.append(1)
            else:
                rc.append(0)
                signal.append(int(output))
            if time.time() < nowtime+5:
                time.sleep((nowtime+5)-time.time())
        self._conn.close_all_connections()

        stability = ""
        avgsig = ""
        
        if 0 in rc:
            stability = "SOLID"
        if 1 in rc:
            if stability=="SOLID":
                stability="UNSTABLE"
            else:
                stability="DEAD"
        
        if stability=="SOLID":
            avgsig = str(sum(signal)/len(signal))

        return stability, avgsig

    def send_router_command_and_return_output(self, command):

        """  Send a command to the router and return the output

        The return code will be checked and a warning raised if it is non zero.

        Examples:
        | ${output}=	| Send router command and return output	| iw list 	|
        
        """


        alloutput = self.execute_command(command, return_rc=True)
        if alloutput[1] <> 0:
            logger.warn("Router command failed to execute correctly!  Return code was " + str(alloutput[1]))
        
        return alloutput[0]


    def set_country(self, countrycode, radioid="active"):
        """ TODO
        """

        if radioid == 'active':
            radioid = self.active_radio

        self._checkvalid_configkey("REGIONS_%s" % str(radioid), countrycode)

        self.commit_uci_commands("wireless.radio%s.country=%s" % (str(radioid), countrycode))

    def switch_radio(self, radio, state):
        """ Switch radio on or off

        Examples:
        | Switch radio	| 0	| On	|
        | Switch radio	| ${id}	| Off   |

        """

        command = ''

        if state.lower() == "on":
            command = "wireless.radio%s.disabled=" % str(radio)
        elif state.lower() == "off":
            command = "wireless.radio%s.disabled=1" % str(radio)
        else:
            raise WiFiRouterError("Radio state '%s' not valid.  Please use 'On' or 'Off'." % state)

        self.commit_uci_commands(command)
        

    def set_radio_parameters(self, *args, **kwargs):
        """ Set the radio parameters

        This gives access, through keywords, to all elements of the radio interface

        Supported keywords:-
            radio       Integer representing to physical radio instance.  If empty the active radio is assumed
            disabled    1 or 0 representing radio no or off
            channel     Integer representing to channel number
            country     String representing the country code
            txpower     Integer representing the transmit power
            htmode      String representing the 'High Throughput' mode (e.g. HT20, VHT80 etc)
            hwmode      String representing the hardware mode (e.g. 11ng, 11g, 11na etc)

        All values will be checked for support in the router config

        Examples:
        | Set Radio Parameters	| radio=0	| channel=9	| htmode=HT20	|
        | Set Radio Parameters	| channel=11	| hwmode=11g	| txpower=0	|

        """


        commands = []

        # enabled

        # radio
        if 'radio' in kwargs:
            radio = int(kwargs['radio'])
        else:
            radio = self.active_radio

        # disabled
        if 'disabled' in kwargs:
            new_state = str(kwargs['disabled'])
            if new_state == '0':
                new_state = ''
            # Get current state
            ret_code = self.execute_command("uci show wireless.radio%s.disabled" % str(radio), return_stdout=False, return_rc=True)

            #old_state = self.send_router_command_and_return_output("uci show wireless.@wifi-iface[%s].disabled" % str(radio))
            if ret_code:
                old_state = ''
            else:
                old_state = '1'

            if str(old_state) <> str(new_state):
                commands.append("wireless.radio%s.disabled=%s" % (str(radio), str(new_state)))

                

        # Get current config for this radio
        uci = self.send_router_command_and_return_output("uci show wireless.radio%s" % str(radio))
        uci = uci.split('\n')
        uci_dict = {}
        for u in uci:
            us = u.split('=')
            uci_dict[us[0]]=us[1]

        # country
        if 'country' in kwargs:
            commands, uci_dict = self.__validate_key_and_add_command(uci_dict, commands, "wireless.radio%s.country" % radio, kwargs['country'], "REGIONS_%s" % str(radio))

        # hwmode
        if 'hwmode' in kwargs:
            commands, uci_dict = self.__validate_key_and_add_command(uci_dict, commands, "wireless.radio%s.hwmode" % radio, kwargs['hwmode'], "MODES_%s" % str(radio))

        # channel
        if 'channel' in kwargs:
            commands, uci_dict = self.__validate_key_and_add_command(uci_dict, commands, "wireless.radio%s.channel" % radio, kwargs['channel'], "CHANNELS_%s" % str(radio))

        # txpower
        if 'txpower' in kwargs:
            uci_command = "wireless.radio%s.txpower" % radio
            new_value = str(kwargs['txpower'])
            if new_value <> str(uci_dict[uci_command]):
                self._checkvalid_configvalue("CHANNELS_%s" % str(radio), uci_dict["wireless.radio%s.channel" % radio], 1, new_value)
                commands.append("%s=%s" % (uci_command, new_value))


        # htmode
        if 'htmode' in kwargs:
            uci_command = "wireless.radio%s.htmode" % radio
            new_value = str(kwargs['htmode'])
            
            changeit = False

            # It's possible that no HTMODE is set (if the HWMODE doesn't support it)
            
            try:
                if new_value <> str(uci_dict[uci_command]):
                    # HT MODE is set and different to the new value
                    changeit = True
            except KeyError:
                # HTMODE not set
                changeit = True

            if changeit:
                self._checkvalid_configvalue("CHANNELS_%s" % str(radio), uci_dict["wireless.radio%s.channel" % radio], 0, new_value)
                self._checkvalid_configvalue("MODES_%s" % str(radio), uci_dict["wireless.radio%s.hwmode" % radio], 1, new_value)

                commands.append("%s=%s" % (uci_command, new_value))

        #print commands
        self.commit_uci_commands(*commands)
        

    def __sort_dict_keys(self, conf):
        # Take a config key and sort the options available
        sorted_dict = sorted(conf.items(), key=operator.itemgetter(0))

        sorted_keys = []
        for key in sorted_dict:
            if self.__is_int(key[0]):
                # Check if it's an int
                sorted_keys.append(int(key[0]))
                sorted_keys.sort(key=float)
            else:
                sorted_keys.append(key[0])

        return sorted_keys



    def __validate_key_and_add_command(self, uci_dict, commands, uci_command, new_value, config_key):
        # Check if the new value is already set
        if str(new_value) <> str(uci_dict[uci_command]):
            # It's not, so now check the validity of the new value
            self._checkvalid_configkey(config_key, new_value)
            # It's valid (or an error would have been raised) so add the command to the list of commands
            commands.append("%s=%s" % (uci_command, new_value))
            # In addition, amend the entry in the uci_dict so we can refer to the correct key for suplimental settings
            uci_dict[uci_command] = new_value

        return commands, uci_dict
    

    def _checkvalid_configkey(self, config, key):
        # Look through config keys to ensure support, returning the value

        # Check if this is a valid config item first
        try:
            conf = eval("self.config.%s" % config)
        except AttributeError:
            raise WiFiRouterError("'%s' is not a valid config entry" % config)

        # Now check if the key exists as an option for this config item
        # If not return the options
        try:
            value = eval("conf['%s']" % key)
            return value
        except KeyError:
            raise WiFiRouterError("Config item '%s' has no key '%s' in supported list: %s" % (config, key, self.__sort_dict_keys(conf)))
        

    def _checkvalid_configvalue(self, config, key, position, value):
        # Check if the value is present in the position specified of a given key
        # For example config.CHANNELS_1['36'] = [['HT20','HT40+','VHT40','VHT80'],['17','16','15','14','13','12','11','10','9','8','7','6','5','4','0']]
        #       _checkvalue_configvalue('CHANNELS_1','36',0, 'HT20') will return true
        #       _checkvalue_configvalue('CHANNELS_1','36',1, '9') will return true

        # Check the key first
        supported_value = self._checkvalid_configkey(config, key)


        # Key is good so check the value
        if str(value) in supported_value[position]:
            return True
        else:
            # Not found, raise error and let the user know the supported values
            raise WiFiRouterError("'%s' not supported in key '%s' of config item '%s'. Supported values:'%s'" % (str(value), str(key), str(config), supported_value[position]))
        

    def __is_int(self, value):
        try:
            int(value)
            return True
        except ValueError:
            return False






    def set_access_parameters(self, ssid, passphrase, radioid='active', securitymode='wpa2-psk', hiddenssid=False):

        """  Sets the Wi-Fi access parameters, SSID, Passphrase and SecurityMode
        
        Examples:
        | Set Access	| 0	| MYSSID	| MyP4ssphrase	| securitymode=wpa2-psk		|			|
        | Set Access	| 1	| newssid	| testPassw0rd	| securitymode=wpa2-tkip	| hiddenssid=${True}	|

        """

        if radioid == 'active':
            radioid = self.active_radio
            
      
        commands = []


        encryption = self._checkvalid_encryption(securitymode)


        commands.append('wireless.@wifi-iface[%s].encryption=%s' % (str(radioid), encryption)) 
        commands.append('wireless.@wifi-iface[%s].ssid=%s' % (str(radioid), ssid))
        commands.append('wireless.@wifi-iface[%s].key=%s' % (str(radioid), passphrase))
        hidessid = int(hiddenssid == True) # Convert bool to int 1 or 0
        commands.append('wireless.@wifi-iface[%s].hidden=%s' % (str(radioid), str(hidessid)))

    
        self.commit_uci_commands(*commands)


    def _checkvalid_encryption(self, securitymode):
        try:
            encryption = self.config.ENCRYPTION[securitymode][0]
            return encryption
        except KeyError:
            modes = []
            for mode in self.config.ENCRYPTION:
                modes.append(mode)
            raise WiFiRouterError("Securitymode not in supported list: %s" % modes)




    def set_restart_wifi_after_commit(self, boolvalue):
        """ TODO
        """
        
        self.restart_wifi = boolvalue

    def read_uci_value(self, parameter):
        
        """ TODO
        """
        
        ret = self.send_router_command_and_return_output("uci show %s" % parameter)

        ret = ret.split("=")[1]

        return ret
    

    def commit_uci_commands(self, *commands):

    
        """  Sends a list of UCI commands to the router then commits them and restarts interfaces

        All output is concatenated and dumped to debug when the method completes

        Examples:
        | Commit UCI commands	| wireless.radio1.channel=${channel}	| wireless.radio1.txpower=${power}	|
        
        """
        output=""

        
        self._conn.set_default_configuration(timeout="2 minutes")
        self._conn.open_connection(self._ipaddress, prompt=self._prompt, newline=self._newline)
        self._conn.login(self._username, self._password)


        for command in commands:
            output = output + self._conn.execute_command("uci set " + command)
            
        output = output + self.execute_command("uci commit")
        
        if self.restart_wifi:
            logger.info("Restarting WiFi interfaces...")
            # New method
            output = output + self.execute_command("wifi")
            # Old method
            # output = output + self.execute_command("/etc/init.d/network restart && /etc/init.d/firewall restart")
        self._conn.close_all_connections()
        self._conn.set_default_configuration(timeout="3 seconds")
        logger.debug(output)
        return output



    def get_station_info(self, radio, target_mac, value="all"):
        """  Returns station dump info for a given mac address on a given interface device

        If the mac is not found on the wireless interface an error will be raised

        Possible values:-
        - all		- Returns full station dump for this mac
        - inactive time
        - rx bytes
	- rx packets
        - tx bytes
        - tx packets
        - tx retries
        - tx failed
        - signal:	- Just passing 'signal' will get the signal avg
        - signal avg
        - tx bitrate
        - rx bitrate
        - authorized
        - authenticated
        - preamble
        - wmm/wme
        - mfp
        - tdls peer

        Examples:-
        | ${txbr}=	| Get Station Info	| 1	| ce:21:23:23:fa:d5	| tx bitrate	|
        | ${all}=	| Get Station Info	| 0	| a1:2f:dc:61:09:11	| 		|

        """
 
        value=value.lower()
        
        output = self.execute_command("iw dev wlan%s station dump | grep -A17 %s" % ( str(radio),target_mac.lower()),return_rc=True)
        if output[1]!=0:
            raise WiFiRouterError("mac '%s' not found on interface 'wlan%s'" % (target_mac.lower(),str(radio)))
        if value == "all":
            return output[0]
        else:
            lines = output[0].split("\n")
            ret = ""
            for line in lines:
                if line.lower().find(value)!=-1:
                    ret = line.split(":")[1].rstrip().lstrip()
            if ret == "":
                raise WiFiRouterError("value '" + value + "' not found in station dump")
            else:
                return ret



class WiFiRouterError(RuntimeError):
    pass



        
