from flask import Flask, request, session, url_for, escape, redirect, jsonify, render_template
import sqlite3
from flask import g
from datetime import datetime

app = Flask(__name__)
DATABASE = './database.db'
START_PORT = 5

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
    return render_template('index.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

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
            'profit': id['profit'],
        })

    return jsonify({"data": d})

@app.route('/trips')
def trips_info():
    db = get_db()
    c = db.cursor()

    try:
        team_id, drone_id = request.args.get('team_id'), int(request.args.get('drone_id'))
    except:
        return jsonify({
            'status': 'error',
            'msg': 'param error'
        })

    c.execute('SELECT * FROM team_trips WHERE team_id = ? AND drone_id = ?', (team_id, drone_id))
    ids = c.fetchall()
    d = []

    for id in ids:
        d.append({
            'trip_id': id['trip_id'],
            'drone_id': id['drone_id'],
            'from_port': id['from_port'],
            'to_port': id['to_port'],
            'state': id['state'],
            'distance': id['distance'],
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
            'next': team_state['next_port']
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

    team_id, drone_id = request.args.get('team_id'), int(request.args.get('drone_id'))
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

    team_id, drone_id = request.args.get('team_id'), int(request.args.get('drone_id'))
    c.execute('SELECT * FROM team_state WHERE team_id = ? AND drone_id = ?', (team_id, drone_id))
    team_state = c.fetchone()
    if team_state is not None:
        state, port_index, trip_id, curr_port = \
            team_state['state'], team_state['port_index'], team_state['trip_id'], team_state['next_port']

        if state == 'land':
            return jsonify({
                'status': 'error',
                'msg': 'the drone has already landed'
            })

        c.execute('UPDATE team_trips SET to_time = ?, state = ?'
                  ' WHERE team_id = ? AND drone_id = ? AND trip_id = ?',
                  (datetime.now(), 'success', team_id, drone_id, trip_id))
        # TODO: Calculate profit

        c.execute('SELECT * FROM team_ports WHERE team_id = ? AND drone_id = ? AND port_index = ?',
                  (team_id, drone_id, port_index + 1))
        port_data = c.fetchone()

        if port_data is not None:
            next_port, port_index, trip_id = port_data['port_id'], port_index + 1, trip_id + 1
            c.execute('INSERT INTO team_trips(team_id, drone_id, trip_id, from_port, to_port, state, distance) '
                      'VALUES (?, ?, ?, ?, ?, ?, ?)',
                      (team_id, drone_id, trip_id, curr_port, next_port, 'created', 1))
        else:
            next_port, port_index, trip_id = None, None, None

        c.execute('UPDATE team_state SET state = ?, port_index = ?, trip_id = ?, curr_port = ?, next_port = ? '
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

    team_id, drone_id = request.args.get('team_id'), int(request.args.get('drone_id'))
    curr_port = request.args.get('port')
    c.execute('SELECT * FROM team_state WHERE team_id = ? AND drone_id = ?', (team_id, drone_id))
    team_state = c.fetchone()

    if team_state is not None:
        state, port_index, trip_id = \
            team_state['state'], team_state['port_index'], team_state['trip_id']

        if not curr_port:
            curr_port = team_state['curr_port']

        c.execute('UPDATE team_trips SET to_time = ?, state = ?'
                  ' WHERE team_id = ? AND drone_id = ? AND trip_id = ?',
                  (datetime.now(), 'fail', team_id, drone_id, trip_id))
        # TODO: Calculate profit

        c.execute('SELECT * FROM team_ports WHERE team_id = ? AND drone_id = ? AND port_index = ?',
                  (team_id, drone_id, port_index + 1))
        port_data = c.fetchone()

        if port_data is not None:
            next_port, port_index, trip_id = port_data['port_id'], port_index + 1, trip_id + 1
            c.execute('INSERT INTO team_trips(team_id, drone_id, trip_id, from_port, to_port, state, distance) '
                      'VALUES (?, ?, ?, ?, ?, ?, ?)',
                      (team_id, drone_id, trip_id, curr_port, next_port, 'created', 1))
        else:
            next_port, port_index, trip_id = None, None, None

        c.execute('UPDATE team_state SET state = ?, port_index = ?, trip_id = ?, curr_port = ?, next_port = ? '
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
        c.execute('SELECT port_index, port_id FROM team_ports WHERE team_id = ? AND drone_id = ? '
                  'ORDER BY port_index ASC LIMIT 1', (team_id, drone_id))
        port_info = c.fetchone()
        port_index, port_id = port_info['port_index'], port_info['port_id']
        c.execute('INSERT INTO team_trips(team_id, drone_id, trip_id, from_port, to_port, state, distance) '
                  'VALUES (?, ?, ?, ?, ?, ?, ?)',
                  (team_id, drone_id, 0, START_PORT, port_id, 'created', 1))
        c.execute('UPDATE team_state SET state = ?, port_index = ?, trip_id = ?, curr_port = ?, next_port = ? '
                  'WHERE team_id = ? AND drone_id = ?',
                  ('land', port_index, 0, START_PORT, port_id, team_id, drone_id))
        db.commit()

    return jsonify({
        'status': 'ok'
    })

if __name__ == '__main__':
    app.run()
