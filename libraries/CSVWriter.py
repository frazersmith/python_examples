from robot.api import logger
from robot.version import get_version
from robot import utils
from robot.libraries.BuiltIn import BuiltIn
import os

__version__ = "0.1 beta"


class CSVWriter(object):
    """ Amino CSVWriter Library by Frazer Smith.

    This library is designed for use with Robot Framework.

    A list of columns must be defined using `Set Columns` before any data will be accepted.

    Once the columns are in place, data for each column can be appended to the 'row' with `Item Append`.
    These row items can be added at any point in the suite as the scope of the CSV object is TESTSUITE.

    Once you are happy calling `Writeline` will output the data (and the headings, if it's a new file)
    and clear the row data (can be overridden).

    By default the file written to is [SUITE].[TEST]_data.csv in the output directory, but 'data' can be overridden
    using `Set Suffix`

    The separator is, by default, a comma, but this can be changed with `Set Separator` (which must be called before the first `Writeline`)

    NOTE:  If a value is text it will be encapsulated in quotes when written to the csv.  You don't need to handle text or numbers differently
    when using `Set Columns` or `Item Append`.

    
    """
    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self):
        self._suffix='data'
        self._columns=None
        self._sep=','
        self._rowdict={}
        self._row=[]

    def set_suffix(self, value):
        """ Change the suffix used in the filename.

        By default the filename will use 'data.csv'.  When you change the suffix you are only changing
        the 'data' part. '.csv' will always be added.

        Example:-
        | Set Suffix	| thruput	|

        """
        self._suffix = value
    
    def set_columns(self, *columns):
        """ Set the columns for the csv file
 
        This gives values for the heading and the dictionary key values used to set the row items.

        It accepts a tuple or a list

        Example:-
        | Set Columns	| Timestamp	| Channel	| Power Level	| Throughput	|
        """

        self._columns=None
        self._rowdict={}
        columns = self._tuple(columns)
        self._columns=columns 
        for c in columns:
            self._rowdict[c] = ''

    def item_append(self, column, value):
        """ Set a single item in the row by giving it's column name

        Examples:-
        | Item Append	| Timestamp	| ${timestamp}	|
        | Item Append	| Channel	| 76		|
        """

        if not column in self._rowdict:
            logger.warn("Unable to add item '%s' to column '%s' as that column is not defined!" % (value, column))
        elif self._rowdict[column] != '':
            logger.warn("Column '%s' already has a value of '%s'.  Overwriting with '%s'" % (column, self._rowdict[column], value))
            self._rowdict[column] = value
        else:
            self._rowdict[column] = value

    def clear_row(self):
        """  Allows the user to clear any values currently in the row but not yet written

        Example:-
        | Clear Row	|
        """

        for c in self._columns:
            self._rowdict[c] = ''
        self._row=[]        

    def _isnumber(self, s):
        try:
            float(s)
            return True
        except ValueError:
            return False

    def set_separator(self, separator):
        """  Allows the user to define a custom separator (instead of the default comma)

        Example:-
        | Set Separator	| ;	|
        """

        self._sep=separator

    #def row_append(self, *values):
    #    values = self._tuple(values)
    #    for v in values:
    #        if self._columns!=None:
    #            if len(self._columns) < (len(self._row)+1):
    #                logger.warn("Adding more row items than there are columns!")
    #        self._row.append(v)
            
            

    def writeline(self, clearrow=True):
        """  Output the current row values to the csv file

        If this is the first time the file has been written to it will also output the column headers

        Default behaviour is for the row data to be cleared, but this can be overridden using clearrow

        Example:-
        | Writeline	|			|
	| Writeline	| clearrow=${False}	|
        """
 
        try:
            outdir = BuiltIn().replace_variables('${OUTPUTDIR}')
        except:
            outdir = "/tmp"

        try:
            suitename = BuiltIn().replace_variables('${SUITENAME}')
        except:
            suitename = "CSVDEBUG"

        outputpath = os.path.join(outdir, suitename).replace(' ','_')

        outputpath = outputpath + ("_%s.csv" % self._suffix)
        headings=None       

        if not os.path.isfile(outputpath):
            # Write headings
            headings = self._sep.join(self._formatted_list(self._columns))
        

        # Make list of value in the right order as the rows
        row=[]
        for c in self._columns:
            row.append(self._rowdict[c] if self._rowdict[c] is not None else "(None)")

        try:
            with open(outputpath,'a') as f:
                if headings!=None:
                    f.write('%s\r\n' % headings)
                f.write('%s\r\n' % self._sep.join(self._formatted_list(row)))
            if clearrow:
                self.clear_row()
        except:
            raise CSVError("Unable to write to CSV file '%s" % outputpath)

    def _formatted_list(self, inlist):
        o=[]
        for i in inlist:
            if self._isnumber(i):
                o.append(str(i))
            else:
                o.append('"%s"' % str(i))
        return o

    def _tuple(self, tup):
        if isinstance(tup[0],list):
            return tuple(tup[0])
        else:
            return tup

class CSVError(RuntimeError):
    pass

