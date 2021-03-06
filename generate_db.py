import sqlite3

port_list = {
    (1, 0): [2,3,1,4,3,2,1,3,2,1,2,4,3,4,2,4,2,3,4,2,3,1,2,3,1,2,4,2,4,2,1,4,2,1,3,2,1,3,1,3,2,3,4,3,4,3,2,1,4,1,2,3,2,3,2,1,3,4,2,1,4,1,2,3,1,3,1],
    (2, 0): [2,4,3,2,1,3,4,1,2,3,2,1,3,1,3,1,4,2,1,2,4,3,1,4,3,2,1,3,1,3,2,1,3,4,2,1,3,2,4,2,4,1,2,3,1,2,3,1,2,4,3,1,2,3,2,1,2,1,4,3,4,2,4,2,1,4,1],
    (3, 0): [2,3,2,1,4,1,4,3,4,3,2,1,2,4,2,1,3,4,3,1,2,4,3,1,2,1,2,1,2,3,4,3,2,1,3,2,4,3,1,3,4,1,3,2,1,4,3,4,3,4,3,1,4,1,4,1,2,3,2,1,3,4,1,4,2,3,4],
    (4, 0): [2,1,3,2,4,2,4,3,1,4,2,3,1,3,4,1,3,4,2,4,2,3,1,3,4,3,4,1,4,1,4,1,4,2,1,2,3,2,4,2,1,4,2,3,2,4,2,3,4,2,4,3,1,3,2,1,3,1,4,1,2,3,4,3,4,1,2],
}


DATABASE = './database.db'
db = sqlite3.connect(DATABASE)
db.row_factory = sqlite3.Row

c = db.cursor()
c.execute('DELETE FROM team_trips')
c.execute('DELETE FROM team_ports')

for team_id in (1, 2, 3, 4):
    for drone_id in (0, ):
        pl = port_list[(team_id, drone_id)]
        for port_index in range(len(pl)):
            c.execute('INSERT INTO team_ports(team_id, drone_id, port_index, port_id) VALUES (?, ?, ?, ?)',
                      (team_id, drone_id, port_index, pl[port_index]))
db.commit()




