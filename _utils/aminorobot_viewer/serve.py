"""
docs
"""
# Flask imports
from flask import Flask
from flask import render_template
from flask import request
from flask import g
from flask import Response
from flask import abort
from flask import Markup

# Python imports
import sys
import json
import sqlite3
import pygal
import time
import subprocess
from datetime import datetime

# Local imports
from _utils.arb import ArbListener
import utils.robot_view_utils as view_utils

app = Flask(__name__)

ARB_IF = ArbListener()



DATABASE = '_utils/aminorobot_viewer/utils/local.db'

# Jenkins robots are not compatible with the viewer
EXCLUDES = ['10.172.3.99']

PYGAL_STYLE = pygal.style.Style(colors=('#36E336', '#F72D05'))

class LOG_TYPES(object):
    """     Docstring
    """

    LOG_ROBOTRUN = 0
    LOG_ROBOTDEBUG = 1
    LOG_STB_DEBUG = 2
    LOG_STB_CPU = 3
    LOG_STB_MEM = 4


@app.before_request
def before_request():
    """     Always open a DB connection before request
    """
    g.db = sqlite3.connect(DATABASE)
    g.cursor = g.db.cursor()

@app.after_request
def after_request(response):
    """     Close the DB connection after the request
    """
    # Close Database connection
    g.db.close()

    # Add Prevent caching header
    response.headers['Cache-Control'] = 'public, max-age=0'
    return response

def query_db(query, args=(), one=False):
    """     Execute a query on the database and return the result(s)

    Args:       - args
    Returns:    - returns
    """

    g.cursor.execute(query, args)
    rv = [dict((g.cursor.description[idx][0], value)
               for idx, value in enumerate(row)) for row in g.cursor.fetchall()]
    return (rv[0] if rv else None) if one else rv

@app.route('/')
def list_all_robots():
    """
    docs
    """

    return render_template('index.html')

@app.route('/robot_list_html')
def generate_robot_list():
    """
    docs
    """
    robot_list = ARB_IF.list_beacons()
    # sort by amount of tests running
    robot_list.sort(key=lambda x: int(x[1]), reverse=True)

    for robot in robot_list:
        robot.insert(1, view_utils.get_hostname_from_ip(robot[0]))

    robot_list = [x for x in robot_list if x[0] not in EXCLUDES]

    return render_template('robot_list_html.html', robots=robot_list)

@app.route('/show_robot')
def show_single_robot():
    """
    docs
    """
    robot_info = {}

    try:
        robot_info['robot_ip'] = request.args.get('robot_ip')
    except KeyError:
        robot_info['robot_ip'] = False
        pass

    jobs_info = {}

    if robot_info['robot_ip']:
        robot_info['hostname'] = view_utils.get_hostname_from_ip(robot_info['robot_ip']).strip(' ')

        procs = ARB_IF.send_command(robot_info['robot_ip'], "view_running_tasks()")

        try:
            jobs = json.loads(procs)
        except TypeError:
            # Failed to get a response, probably not a robot beacon. Return
            # an empty dict to prevent the front end falling over
            jobs = {}

        for job in jobs.keys():

            jobs_info[job] = {}

            if any('robotide' in s for s in jobs[job]):
                # RIDE sqarun list data is garbage, don't try to parse it
                jobs_info[job]['RIDE'] = True
                jobs_info[job]['JENKINS'] = False
            elif any('node_name' in s for s in jobs[job]):
                # Need to fix the arb get running commands function,
                # it doesn't cope well with jenkins jobs
                jobs_info[job]['JENKINS'] = True
                jobs_info[job]['RIDE'] = False
            else:
                jobs_info[job]['RIDE'] = False
                jobs_info[job]['JENKINS'] = False

                jobs_info[job]['test_args'] = jobs[job][0]
                jobs_info[job]['output_dir'] = jobs[job][1]
                jobs_info[job]['output_url'] = jobs[job][1][jobs[job][1].find('aminorobotresults'):]

                uut_shortname = jobs[job][0].split('uut:')[1].split(' ')[0]

                inf = query_db('SELECT * FROM stb_info WHERE shortname = "%s"' % (uut_shortname), one=True)
                jobs_info[job]['stb_info'] = inf

                jobs_info[job]['timings'] = view_utils.get_test_times(jobs_info[job])

    if robot_info['robot_ip']:
        json_audit = ARB_IF.send_command(robot_info['robot_ip'], "get_node_audit()")

        try:
            audit_info = json.loads(json_audit)

            # Handle potentially missing keywords due to version issues
            if not 'git' in audit_info:
                audit_info['git'] = {'branch':'Unknown', 'commit':'Please pull latest code to this robot and restart the Amimorobot beacon to obtain git information'}

            audit_info['git']['commit'] = Markup(audit_info['git']['commit'].replace('\n\n', '\n').replace("\n","<br>"))

        except (TypeError, ValueError):
            # Failed to get node audit, don't display the info
            audit_info = False



    return render_template('show_robot.html',
                            robot_info=robot_info,
                            procs=jobs_info,
                            node_audit=audit_info)

@app.route('/show_test')
def show_test():
    ret = {}
    ret['robot_ip'] = str(request.args.get('robot_ip'))
    ret['test_pid'] = str(request.args.get('test_pid'))

    procs = ARB_IF.send_command(ret['robot_ip'], 'view_running_tasks()')

    try:
        # Load the JSON string into a dict
        procs_dict = json.loads(procs)
        this_proc = procs_dict[ret['test_pid']]
        ret['test_found'] = True
    except TypeError:
        # Failed to find the robot_ip in the arb tests response
        ret['test_found'] = False
    except KeyError:
        # The test PID does not exist in the list of running tasks
        ret['test_found'] = False

    if ret['test_found']:
        ret['test_parameter'] = ''
        ret['test_variables'] = []
        test_args = this_proc[0]

        for arg in test_args.split('--'):
            if ('test' in arg) or ('suite' in arg):
                ret['test_parameter'] = arg.split(' ')[1]

            elif 'variable' in arg:
                ret['test_variables'].append(arg.split(' ')[1])

        ret['output_dir'] = this_proc[1]
        ret['output_url'] = this_proc[1][this_proc[1].find('aminorobotresults'):]

        uut_info_set = False
        for arg in ret['test_variables']:
            splt = arg.split(':')

            if splt[0] == 'uut':
                ret['unit_under_test'] = query_db('SELECT * FROM stb_info WHERE shortname = "%s"' % (splt[1]), one=True)
                uut_info_set = True

        # Explicitly set this to None when the information is unavailable to
        # prevent wayward behaviour in the jinja2 template system
        if not uut_info_set:
            ret['unit_under_test'] = None

    return render_template('show_test.html', test_info=ret)

@app.route('/get_log_from_robot')
def get_log_from_robot():
    """     Get a sample fo the log from a remote robot using the arb interface
    """

    robot_ip = request.args.get('robot_ip')
    test_pid = request.args.get('test_pid')
    log_type = request.args.get('log_type')

    # If no length param is passed, then default to 50 lines
    length = request.args.get('length', 50)

    # If there is no offset, use default 0
    offset = request.args.get('offet', 0)

    ret_log = ARB_IF.send_command(robot_ip, "tail_log(%s, %s, length=%s, offset=%s)" % (
                                  test_pid, log_type, length, offset))

    ret_data = json.dumps({'status': 'success', 'data': ret_log.replace('\n', '<br>')})

    return Response(response=ret_data, status=200, mimetype='application/json')

@app.route('/refresh_uut_db')
def refresh_uut_db():
    """
    docs
    """

    sync = subprocess.Popen(['python', 'getdb.py'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            cwd='./utils/')

    out, err = sync.communicate()

    if sync.returncode == 0:
        status = 'PASS'
    else:
        status = 'FAIL'

    print "******* Status of getdb execution = '%s' ********" % status


    return json.dumps({'status': status, 'debug': '%s%s' % (out, err)})

@app.route('/test_list')
def test_list():
    """
    docs
    """
    return render_template('test_list.html')

@app.route('/start_test')
def start_test():
    """
    docs
    """
    return render_template('start_test.html')

@app.route('/stream_monitor')
def stream_monitor():
    """     docs
    """

    streams = query_db('''SELECT p.id, p.stream_name, p.stream_url, p.stream_enabled, p.stream_type, p.time_down_since,
                                 c.stream_test_id, c.stream_test_time, c.stream_status
                            FROM stream_test p
                            LEFT JOIN (SELECT c1.stream_test_id, c1.stream_test_time, c1.stream_status
                                    FROM test_log c1
                                        join (SELECT p1.id, Max(c2.stream_test_time) maxTestTime
                                            FROM stream_test p1
                                                LEFT JOIN test_log c2 ON p1.id = c2.stream_test_id
                                                GROUP BY p1.id) cf ON c1.stream_test_id = cf.id
                                                AND c1.stream_test_time = cf.maxTestTime) c
                            ON p.id = c.stream_test_id''')

    for result in streams:
        last_timestr = time.strftime('%d/%m %H:%M:%S', time.gmtime(int(result['stream_test_time'])))
        result['stream_test_time'] = last_timestr

        if result['time_down_since'] != None:
            down_since = time.strftime('%d/%m %H:%M:%S', time.gmtime(int(result['time_down_since'])))
            result['time_down_since'] = down_since

    return render_template('stream_monitor.html', stream_list=streams)

@app.route('/graph/<int:graph_id>')
def graph(graph_id):
    """     render svg graph
    """
    custom_style = pygal.style.Style(colors=('#36E336', '#F72D05'))

    line_graph = pygal.Bar(style=custom_style)

    line_graph.add('Fibonacci', [1, 2, 3, 5, 8, 13, 21, 34, 55, 89])

    return Response(response=line_graph.render(), content_type='image/svg+xml')

@app.route('/graph/memory_graph')
def get_memory_graph():
    """     Get a graph memory usage, using a sample of the data
    only if the data is available
    """

    # Get request args, default to None if not passed.
    robot_ip = request.args.get('robot_ip', None)
    test_pid = request.args.get('test_pid', None)

    # Optional request arg, default to 50 if it is not passed
    data_rows = request.args.get('data_rows', 50)

    if not robot_ip or not test_pid:
        # If either of the required args are not passed, send bad request
        abort(400)

    graph_data = ARB_IF.send_command(robot_ip, "get_log_data_sample('%s', %d, data_rows=%s)" % (
                                            str(test_pid), LOG_TYPES.LOG_STB_MEM, int(data_rows)))

    json_data = json.loads(graph_data)

    if json_data['status'] == 'FAIL':
        # TODO: send a default graph not available image
        abort(404)

    data_times = []

    for log_time in json_data['data']:
        d_mem_val = int(log_time[log_time.keys()[0]])
        d_time = datetime.strptime(log_time.keys()[0], '%Y%m%d%H%M%S')

        data_times.append((d_time, d_mem_val))

    # Use 95% of minimum and 105% of maximum for the values scale range
    min_val = min([x[1] for x in data_times]) * 0.95
    max_val = max([x[1] for x in data_times]) * 1.05

    line_graph = pygal.DateTimeLine(style=PYGAL_STYLE, range=(min_val, max_val),
                                    width=600, height=400, x_label_rotation=35,
                                    show_legend=False,
                                    x_value_formatter=lambda dt: dt.strftime('%m-%d %H:%M:%S'))

    line_graph.add('Free Memory', data_times)

    return Response(response=line_graph.render(), content_type='image/svg+xml')


@app.route('/graph/cpu_graph')
def get_cpu_graph():
    """     Get a sampled graph of the CPU usage
    """

    # Get request args, default to None if not passed.
    robot_ip = request.args.get('robot_ip', None)
    test_pid = request.args.get('test_pid', None)

    # Optional request arg, default to 50 if it is not passed
    data_rows = request.args.get('data_rows', 50)

    if not robot_ip or not test_pid:
        # If either of the required args are not passed, send bad request
        abort(400)

    graph_data = ARB_IF.send_command(robot_ip, "get_log_data_sample('%s', %d, data_rows=%s)" % (
                                            str(test_pid), LOG_TYPES.LOG_STB_CPU, int(data_rows)))

    json_data = json.loads(graph_data)

    if json_data['status'] == 'FAIL':
        # TODO: send a default graph not available image
        abort(404)

    data_times = []

    for log_time in json_data['data']:
        d_mem_val = int(log_time[log_time.keys()[0]])
        d_time = datetime.strptime(log_time.keys()[0], '%Y%m%d%H%M%S')

        data_times.append((d_time, d_mem_val))

    # Use 95% of minimum and 105% of maximum for the values scale range
    min_val = min([x[1] for x in data_times]) * 0.95
    max_val = max([x[1] for x in data_times]) * 1.05

    line_graph = pygal.DateTimeLine(style=PYGAL_STYLE, range=(min_val, max_val),
                                    width=600, height=400, x_label_rotation=35,
                                    show_legend=False,
                                    x_value_formatter=lambda dt: dt.strftime('%m-%d %H:%M:%S'))

    line_graph.add('Free CPU', data_times)

    return Response(response=line_graph.render(), content_type='image/svg+xml')


@app.route('/graph/start_time_graph/<int:stream_id>')
def start_time_graph(stream_id):
    """     render svg graph
    """

    times = query_db('''SELECT stream_start_time, stream_test_time
                FROM test_log WHERE stream_test_id=%s
                ORDER BY stream_test_time DESC LIMIT 50;''' % (stream_id))

    start_time_list = []

    for i in times:
        start_time_list.append(i['stream_start_time'])

    custom_style = pygal.style.Style(colors=('#36E336', '#F72D05'))

    line_graph = pygal.Line(style=custom_style,
                            range=(0, 5))

    line_graph.add('stream_start_time', start_time_list)

    return Response(response=line_graph.render(), content_type='image/svg+xml')

@app.route('/graph/uptime_graph/<int:stream_id>')
def uptime_graph(stream_id):
    """     render svg graph
    """

    times = query_db('''SELECT stream_test_status, stream_test_time
                FROM test_log WHERE stream_test_id=%s
                ORDER BY stream_test_time DESC LIMIT 200;''' % (stream_id))


    start_time_list = []

    for i in times:
        start_time_list.append(i['stream_test_status'])

    custom_style = pygal.style.Style(
        colors=('#36E336', '#F72D05'))

    bar_graph = pygal.StackedLine(style=custom_style,
                                  range=(0, 1),
                                  fill=True)

    bar_graph.add('stream_test_status', start_time_list)

    return Response(response=bar_graph.render(), content_type='image/svg+xml')

if __name__ == '__main__':

    try:
        app.debug = True
        app.run(host='0.0.0.0', port=7357)

    except KeyboardInterrupt:
        sys.exit(0)
