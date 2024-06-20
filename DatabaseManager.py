import sqlite3

conn = sqlite3.connect('userHistroy.db')
cursor = conn.cursor()

# cursor.execute("CREATE TABLE IF NOT EXISTS chatSummaries(name TEXT, pincode TEXT, chats TEXT)")
# cursor.execute("INSERT INTO chatSummaries VALUES ('Arie', '1234', 'Shoulder hurts')")
# cursor.execute("DELETE FROM chatSummaries WHERE name = ''")
# cursor.execute("SELECT * FROM chatSummaries")

cursor.execute("SELECT pincode FROM chatSummaries WHERE name = 'rick'")
pincode = cursor.fetchall()
print(pincode[0][0])

# rows = cursor.fetchall()

# for row in rows:
#     print(row)

conn.commit()
conn.close()
