import random
from flask import Flask, request, session, url_for, escape, redirect, jsonify, render_template, make_response
import sqlite3
from flask import g
from datetime import datetime
from dateutil import parser
import io, csv

app = Flask(__name__)
DATABASE = './database.db'
START_PORT = 1 # deprecated
ALTITUDE = [10, 15, 20, 25]

def dist_ports(a, b): # in meters
    dist = [
        [0, 0, 0, 0, 0, 0],
        [0, 0,     156.8,   216.1,  316.8,  0],
        [0, 156.8,   0,     138.3,  293.7,  0],
        [0, 216.1, 138.3, 0,      159.8,  0],
        [0, 316.8, 293.7, 159.8,  0,      0],
        [0, 0, 0, 0, 0, 0],
    ]
    return dist[a][b]

def cal_price(port_a, port_b, time_a, time_b):
    if isinstance(time_b, str):
        time_b = parser.parse(time_b)
    if isinstance(time_a, str):
        time_a = parser.parse(time_a)

    secs = (time_b - time_a).total_seconds()
    dist = dist_ports(port_a, port_b)
    speed = dist / secs

    f = 26 + 0.087 * dist - 0.458 * secs - 3.278 * speed
    return f

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


@app.route('/')
def index():
    team_id, drone_id = request.args.get('team_id'), request.args.get('drone_id')
    return render_template('index.html', team_id = team_id, drone_id = drone_id)

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/earning')
def team_earning():
    db = get_db()
    c = db.cursor()
    c.execute('SELECT * FROM team_state')
    ids = c.fetchall()
    d = {}

    for id in ids:
        team_id = id['team_id']
        if team_id not in d:
            d[team_id] = id['profit']
        else:
            d[team_id] += id['profit']

    return jsonify(d)

@app.route('/teams')
def teams_info():
    db = get_db()
    c = db.cursor()
    c.execute('SELECT * FROM team_state')
    ids = c.fetchall()
    d = []

    for id in ids:
        d.append({
            'team_id': id['team_id'],
            'drone_id': id['drone_id'],
            'state': id['state'],
            'curr_port': id['curr_port'],
            'next_port': id['next_port'],
            'altitude': id['altitude'],
            'profit': id['profit'],
        })

    return jsonify({"data": d})

@app.route('/trips')
def trips_info():
    db = get_db()
    c = db.cursor()


    team_id, drone_id = request.args.get('team_id'), request.args.get('drone_id')

    if team_id is None and drone_id is None:
        c.execute('SELECT * FROM team_trips')
    elif team_id is None and drone_id is not None:
        c.execute('SELECT * FROM team_trips WHERE drone_id = ?', (drone_id))
    elif team_id is not None and drone_id is None:
        c.execute('SELECT * FROM team_trips WHERE team_id = ?', (team_id, ))
    else:
        c.execute('SELECT * FROM team_trips WHERE team_id = ? AND drone_id = ?', (team_id, drone_id))

    ids = c.fetchall()
    d = []

    for id in ids:
        if id['to_time']:
            to_time = parser.parse(id['to_time']).strftime("%H:%M:%S")
        else:
            to_time = ''
        if id['from_time']:
            from_time = parser.parse(id['from_time']).strftime("%H:%M:%S")
        else:
            from_time = ''
        d.append({
            'team_id': id['team_id'],
            'drone_id': id['drone_id'],
            'trip_id': id['trip_id'],
            'from_port': id['from_port'],
            'to_port': id['to_port'],
            'from_time': from_time, 
            'to_time': to_time,  
            'state': id['state'],
            'distance': id['distance'],
            'altitude': id['altitude'],
            'price': id['price'],
        })

    return jsonify({"data": d})

@app.route('/next')
def next_port():
    db = get_db()
    c = db.cursor()

    try:
        team_id, drone_id = request.args.get('team_id'), int(request.args.get('drone_id'))
    except:
        return jsonify({
            'status': 'error',
            'msg': 'param error'
        })

    c.execute('SELECT * FROM team_state WHERE team_id = ? AND drone_id = ?', (team_id, drone_id))
    team_state = c.fetchone()
    if team_state is None:
        return jsonify({
            'status': 'error',
            'msg': 'drone not found'
        })
    if team_state['port_index'] is None:
        return jsonify({
            'status': 'error',
            'msg': 'no next'
        })
    else:
        return jsonify({
            'status': 'ok',
            'next': team_state['next_port'],
            'prev': team_state['curr_port'],
            'altitude': team_state['altitude'],
        })

@app.route('/takeoff')
def take_off():
    db = get_db()
    c = db.cursor()

    try:
        team_id, drone_id = request.args.get('team_id'), int(request.args.get('drone_id'))
    except:
        return jsonify({
            'status': 'error',
            'msg': 'param error'
        })

    c.execute('SELECT * FROM team_state WHERE team_id = ? AND drone_id = ?', (team_id, drone_id))
    team_state = c.fetchone()
    # update current drone state, add trip information (time)
    if team_state is not None:
        next_port, state = team_state['next_port'], team_state['state']
        if state == 'takeoff':
            return jsonify({
                'status': 'error',
                'msg': 'the drone has already taken off'
            })
        if next_port is not None:
            c.execute('UPDATE team_state SET state = ? WHERE team_id = ? AND drone_id = ?', ('takeoff', team_id, drone_id))
            trip_id = team_state['trip_id']
            c.execute('UPDATE team_trips SET from_time = ?, state = ?'
                      ' WHERE team_id = ? AND drone_id = ? AND trip_id = ?',
                      (datetime.now(), 'takeoff', team_id, drone_id, trip_id))
            db.commit()
            return jsonify({
                'status': 'ok'
            })
        else:
            return jsonify({
                'status': 'error',
                'msg': 'no next_port'
            })
    else:
        return jsonify({
            'status': 'error',
            'msg': 'drone not found'
        })

@app.route('/land')
def land():
    # update current drone state, add trip information (time)
    db = get_db()
    c = db.cursor()

    try:
        team_id, drone_id = request.args.get('team_id'), int(request.args.get('drone_id'))
    except:
        return jsonify({
            'status': 'error',
            'msg': 'param error'
        })

    c.execute('SELECT * FROM team_state WHERE team_id = ? AND drone_id = ?', (team_id, drone_id))
    team_state = c.fetchone()
    if team_state is not None:
        state, port_index, trip_id, curr_port, profit = \
            team_state['state'], team_state['port_index'], team_state['trip_id'], team_state['next_port'], team_state['profit']

        if state == 'land':
            return jsonify({
                'status': 'error',
                'msg': 'the drone has already landed'
            })

        # ---------------------------------- update prv trip ------------------------------------------

        c.execute('SELECT from_port, to_port, from_time FROM team_trips WHERE team_id = ? AND drone_id = ? AND trip_id = ?',
                  (team_id, drone_id, trip_id))
        prev_trip = c.fetchone()
        from_port, to_port, from_time = prev_trip['from_port'], prev_trip['to_port'], parser.parse(prev_trip['from_time'])
        to_time = datetime.now()
        price = cal_price(from_port, to_port, from_time, to_time)

        c.execute('UPDATE team_trips SET to_time = ?, state = ?, price = ?'
                  ' WHERE team_id = ? AND drone_id = ? AND trip_id = ?',
                  (to_time, 'success', price, team_id, drone_id, trip_id))

        # ---------------------------------- setup new trip ------------------------------------------

        c.execute('SELECT * FROM team_ports WHERE team_id = ? AND drone_id = ? AND port_index = ?',
                  (team_id, drone_id, port_index + 1))
        port_data = c.fetchone()

        if port_data is not None:
            next_port, port_index, trip_id = port_data['port_id'], port_index + 1, trip_id + 1
            altitude = random.choice(ALTITUDE)

            c.execute('INSERT INTO team_trips(team_id, drone_id, trip_id, from_port, to_port, state, distance, altitude) '
                      'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                      (team_id, drone_id, trip_id, curr_port, next_port, 'created', dist_ports(curr_port, next_port), altitude))
        else:
            next_port, port_index, trip_id, altitude = None, None, None, None

        c.execute('UPDATE team_state SET state = ?, port_index = ?, trip_id = ?, curr_port = ?, next_port = ?, profit = ?, altitude = ?'
                  'WHERE team_id = ? AND drone_id = ?',
                  ('land', port_index, trip_id, curr_port, next_port, profit + price, altitude, team_id, drone_id))
        db.commit()

        return jsonify({
            'status': 'ok'
        })
    else:
        return jsonify({
            'status': 'error',
            'msg': 'drone not found'
        })

@app.route('/fail')
def fail():
    # update current drone state, add trip information (time, fail / succeed?)
    db = get_db()
    c = db.cursor()

    try:
        team_id, drone_id = request.args.get('team_id'), int(request.args.get('drone_id'))
    except:
        return jsonify({
            'status': 'error',
            'msg': 'param error'
        })

    c.execute('SELECT * FROM team_state WHERE team_id = ? AND drone_id = ?', (team_id, drone_id))
    team_state = c.fetchone()

    if team_state is not None:
        curr_port, next_port, state, port_index, trip_id, altitude = \
            team_state['curr_port'], team_state['next_port'], team_state['state'], \
            team_state['port_index'], team_state['trip_id'], team_state['ALTITUDE']

        if next_port == None:
            return jsonify({
                'status': 'error',
                'msg': 'You have finished all the trips.'
            })

        c.execute('UPDATE team_trips SET to_time = ?, state = ?, price = 0'
                  ' WHERE team_id = ? AND drone_id = ? AND trip_id = ?',
                  (datetime.now(), 'fail', team_id, drone_id, trip_id))

        trip_id = trip_id + 1
        c.execute('INSERT INTO team_trips(team_id, drone_id, trip_id, from_port, to_port, state, distance, altitude) '
                  'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                  (team_id, drone_id, trip_id, curr_port, next_port, 'created', dist_ports(curr_port, next_port), altitude))

        c.execute('UPDATE team_state SET state = ?, port_index = ?, trip_id = ?, curr_port = ?, next_port = ?'
                  'WHERE team_id = ? AND drone_id = ?',
                  ('land', port_index, trip_id, curr_port, next_port, team_id, drone_id))
        db.commit()

        return jsonify({
            'status': 'ok'
        })
    else:
        return jsonify({
            'status': 'error',
            'msg': 'drone not found'
        })

@app.route('/reset')
def reset():
    db = get_db()
    c = db.cursor()
    c.execute('SELECT DISTINCT team_id, drone_id FROM team_ports')
    ids = c.fetchall()

    for id in ids:
        team_id, drone_id = id[0], id[1]
        c.execute('DELETE FROM team_trips WHERE team_id = ? AND drone_id = ?', (team_id, drone_id))
        c.execute('DELETE FROM team_state WHERE team_id = ? AND drone_id = ?', (team_id, drone_id))
        c.execute('SELECT port_index, port_id FROM team_ports WHERE team_id = ? AND drone_id = ? '
                  'ORDER BY port_index ASC LIMIT 1', (team_id, drone_id))
        port_info = c.fetchone()
        port_index, port_id = port_info['port_index'], port_info['port_id']

        c.execute('SELECT port_index, port_id FROM team_ports WHERE team_id = ? AND drone_id = ? AND port_index > ?'
                  'ORDER BY port_index ASC LIMIT 1', (team_id, drone_id, port_index))
        port_info = c.fetchone()
        port_index_next, port_id_next = port_info['port_index'], port_info['port_id']

        altitude = random.choice(ALTITUDE)
        c.execute('INSERT INTO team_trips(team_id, drone_id, trip_id, from_port, to_port, state, distance, altitude) '
                  'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                  (team_id, drone_id, 0, port_id, port_id_next, 'created', dist_ports(port_id, port_id_next), altitude))
        c.execute('INSERT INTO team_state (state, port_index, trip_id, curr_port, next_port, team_id, drone_id, altitude, profit) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                  ('land', port_index_next, 0, port_id, port_id_next, team_id, drone_id, altitude, 0))
        db.commit()

    return jsonify({
        'status': 'ok'
    })

@app.route('/dump_trips')
def dump():
    db = get_db()
    c = db.cursor()
    c.execute('SELECT * FROM team_trips')
    d = []
    ids = c.fetchall()

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_NONNUMERIC)
    writer.writerow(["team_id", "drone_id", "trip_id", "from_port", "to_port",
                     "from_time", "to_time", "state", "distance", "altitude", "price"])

    for id in ids:
        if id['to_time']:
            to_time = parser.parse(id['to_time']).strftime("%H:%M:%S")
        else:
            to_time = ''
        if id['from_time']:
            from_time = parser.parse(id['from_time']).strftime("%H:%M:%S")
        else:
            from_time = ''
        writer.writerow([
            id['team_id'],
            id['drone_id'],
            id['trip_id'],
            id['from_port'],
            id['to_port'],
            from_time,
            to_time,
            id['state'],
            id['distance'],
            id['altitude'],
            id['price'],
        ])
    res = make_response()
    res.data = output.getvalue()
    res.headers['Content-Type'] = 'text/csv'
    res.headers['Content-Disposition'] = 'attachment; filename=trips.csv'
    return res

@app.route('/dump_teams')
def dump_teams():
    db = get_db()
    c = db.cursor()
    c.execute('SELECT * FROM team_state')
    d = []
    ids = c.fetchall()

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_NONNUMERIC)
    writer.writerow(["team_id", "drone_id", "trip_id", "curr_port", "next_port",
                     "state", "altitude", "profit"])

    for id in ids:
        writer.writerow([
            id['team_id'],
            id['drone_id'],
            id['trip_id'],
            id['curr_port'],
            id['next_port'],
            id['state'],
            id['altitude'],
            id['profit'],
        ])
    res = make_response()
    res.data = output.getvalue()
    res.headers['Content-Type'] = 'text/csv'
    res.headers['Content-Disposition'] = 'attachment; filename=teams.csv'
    return res


if __name__ == '__main__':
    app.run(host='0.0.0.0')
