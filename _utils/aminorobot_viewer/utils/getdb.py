"""
docstring
"""
# python imports
import os
import sqlite3

# local imports
from robot_view_utils import get_tests_tree
from stb_idents import get_stb_ident

DEBUG = False
DATABASE = '_utils/aminorobot_viewer/utils/local.db'



def _strip_def_file(file_line):
    """
    docstring
    """
    ret = file_line.split('(')[-1]
    ret = ret.replace('"', '')
    ret = ret.replace('\n', '')
    ret = ret.replace(')', '')
    ret = ret.replace(' ', '')

    return ret

def _set_stb_defaults(stb_ret):
    """
    docs
    """
    ret = stb_ret

    if 'iface_name' not in ret:
        ret['iface_name'] = 'Unavailable'
    if 'iface_addr' not in ret:
        ret['iface_addr'] = 'Unavailable'
    if 'iface_mac' not in ret:
        ret['iface_mac'] = 'Unavailable'
    if 'serialnumber' not in ret:
        ret['serialnumber'] = 'Unavailable'
    if 'hwfamily' not in ret:
        ret['hwfamily'] = 'Unavailable'
    if 'debugport' not in ret:
        ret['debugport'] = 'Unavailable'

    return ret

def get_stb_info(stb_ident):
    """
    docstring
    """
    if DEBUG:
        print "getting info for %s" % stb_ident

    ret = {}
    try:
        stb = open('%s' % stb_ident, 'r')

        for line in stb.readlines():
            spl = line.split(',')

            if ('create_interface' in line) and ('eth0' in line):
                ret['iface_name'] = _strip_def_file(spl[0])
                ret['iface_addr'] = _strip_def_file(spl[1])
                ret['iface_mac']  = _strip_def_file(spl[2])

            if ('set_property' in line) and (not 'shortname' in line):
                if 'serialnumber' in line:
                    ret['serialnumber'] = _strip_def_file(spl[1])
                if 'family' in line:
                    ret['hwfamily'] = _strip_def_file(spl[1])
                if ('debugport' in line) and (not '_debugport' in line):
                    ret['debugport'] = _strip_def_file(spl[1])

            if 'self._debugport' in line:
                ret['debugport'] = line.split('"')[1]

        stb.close()
    except IOError:
        print 'Failed to open def file'

    ret = _set_stb_defaults(ret)

    return ret


db = sqlite3.connect(DATABASE)
cur = db.cursor()

cur.execute('DROP TABLE IF EXISTS TestCases')

cur.execute('DROP TABLE IF EXISTS TestSuites')
cur.execute('DROP TABLE IF EXISTS stb_info')

cur.execute('''CREATE TABLE IF NOT EXISTS TestSuites(
                node_name TEXT,
                tags_force TEXT,
                tags_default TEXT,
                suite_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT
            );''')


cur.execute('''CREATE TABLE IF NOT EXISTS TestCases(
                test_suite_id SMALLINT NOT NULL,
                test_name TEXT,
                test_tags TEXT,
                FOREIGN KEY(test_suite_id) REFERENCES TestSuites(suite_id)
            );''')

cur.execute(''' CREATE TABLE IF NOT EXISTS stb_info(
                shortname VARCHAR(20),
                hwfamily VARCHAR(20),
                serialnumber VARCHAR(20),
                debugport VARCHAR(20),
                iface_name VARCHAR(30),
                iface_addr VARCHAR(16),
                iface_mac VARCHAR(20),
                hwident VARCHAR(30)
            );''')

db.commit();

test_info = get_tests_tree()

for suite in test_info.keys():

    list_inf = []

    list_inf.append(suite)
    list_inf.append(test_info[suite]['f_tags'])
    list_inf.append(test_info[suite]['d_tags'])

    str_inf = '","'.join(list_inf)

    str_query = 'INSERT INTO TestSuites(node_name, tags_force, tags_default) VALUES (\"%s\")' % (str_inf)
    cur.execute(str_query)


    for test in test_info[suite]['tests']:
        test_str_query = """INSERT INTO TestCases(test_suite_id, test_name, test_tags) VALUES
                     ((SELECT suite_id FROM TestSuites WHERE node_name="%s"), \"%s\", \"%s\")""" % (suite, test[0], test[1])
        cur.execute(test_str_query)

db.commit()


DEVICE_DIR = 'resources/devices'

for f in os.listdir(DEVICE_DIR):
    with open('%s/%s' % (DEVICE_DIR, f), 'r') as l:
        lines = l.readlines()
        if (any('(STB)' in s for s in lines) and (not 'getdb' in f)) or (any('(ESTB)' in s for s in lines) and (not 'getdb' in f)):
            inf = get_stb_info('%s/%s' % (DEVICE_DIR, f))
            inf['shortname'] = f.split('.')[0]
            inf['hwident'] = get_stb_ident(inf['serialnumber'])
            keys = inf.keys()
            vals = inf.values()

            str_keys = ','.join(keys)
            str_vals = '","'.join(vals)

            str_query = 'INSERT INTO stb_info (%s) VALUES (\"%s\");' % (str_keys, str_vals)

            if DEBUG:
                print str_query

            cur.execute(str_query)

db.commit()

db.close()
