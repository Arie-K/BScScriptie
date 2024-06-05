import sqlite3

conn = sqlite3.connect('userHistroy.db')
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS chatSummaries(name TEXT, password TEXT, chats TEXT)")
cursor.execute("INSERT INTO chatSummaries VALUES ('Arie', 'test123', 'Shoulder hurts')")
#cursor.execute("DELETE FROM chatSummaries WHERE name = 'Arie'")
cursor.execute("SELECT * FROM chatSummaries")

rows = cursor.fetchall()

for row in rows:
    print(row)

conn.commit()
conn.close()