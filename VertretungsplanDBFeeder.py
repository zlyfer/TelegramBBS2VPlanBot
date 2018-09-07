import codecs
import MySQLdb
import os
os.chdir("home/zlyfer/TelegramBots/VPlan_Bot2.0/")
db=MySQLdb.connect(host="localhost", user="root", passwd="", db="VPlan")
cur = db.cursor()
vplanfile = "Vertretungsplan.txt"
file = codecs.open(vplanfile, 'r', 'utf-8')
content = file.readlines()
file.close
file = codecs.open(vplanfile, 'r', 'utf-8')
lines = file.read().count('\n')
file.close
lines += 1
row = {"Kurs": "1", "Datum": "2", "Stunde": "3", "Fach": "4", "Raum": "5", "Lehrer": "6", "Info": "7", "Vertretungstext": "8"}
for i in range(0, lines-1):
    if "Kurs: " in content[i]:
        row = {"Kurs": content[i].replace('\n', '').replace('Kurs: ', ''), "Datum": content[i+1].replace('\n', '').replace('Datum: ', ''), "Stunde": content[i+2].replace('\n', '').replace('Stunde: ', ''), "Fach": content[i+3].replace('\n', '').replace('Fach: ', ''), "Raum": content[i+4].replace('\n', '').replace('Raum: ', ''), "Lehrer": content[i+5].replace('\n', '').replace('Lehrer: ', ''), "Info": content[i+6].replace('\n', '').replace('Info: ', ''), "Vertretungstext": content[i+7].replace('\n', '').replace('Vertretungstext: ', '')}
        print (row)
        print (row["Kurs"], row["Datum"], row["Stunde"], row["Fach"], row["Raum"], row["Lehrer"], row["Info"], row["Vertretungstext"])
        cur.executemany(
              """INSERT INTO Vertretungsplan (Kurs, Datum, Stunde, Fach, Raum, Lehrer, Info, Vertretungstext)
              VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
              [
              (row["Kurs"], row["Datum"], row["Stunde"], row["Fach"], row["Raum"], row["Lehrer"], row["Info"], row["Vertretungstext"]),
              ] )
db.commit()
# cur.execute("SELECT * FROM `Vertretungsplan` WHERE 1")
# for i in cur.fetchall():
    # print(i)