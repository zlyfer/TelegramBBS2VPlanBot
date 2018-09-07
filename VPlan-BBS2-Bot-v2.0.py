# modules
import os
import codecs
import MySQLdb
import logging
import hashlib
from datetime import date
from random import randint
from bs4 import BeautifulSoup
from selenium import webdriver
from time import gmtime, strftime, sleep
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from telegram.ext import MessageHandler, Filters, Updater, CommandHandler, InlineQueryHandler, CallbackQueryHandler, Job
from telegram import InlineQueryResultArticle, InputTextMessageContent, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, ReplyKeyboardMarkup

# misc
os.chdir("home/zlyfer/TelegramBots/VPlan_Bot2.0/")
logging.basicConfig(format="\n%(levelname)s: @'%(asctime)s' in '%(name)s':\n> %(message)s", level=logging.INFO)

# variables functions
vplanurl = "https://hepta.webuntis.com/WebUntis/monitor?school=BBS%202%20Emden&monitorType=subst&format=Vertretungsplan"
vplanfile = "Vertretungsplan_raw.txt"
vplanfile_a = "Vertretungsplan_TagA.txt"
vplanfile_b = "Vertretungsplan_TagB.txt"
vplanfile_ = "" # Nicht benutzen außer in DBFeeder()!
rssfile = "/var/www/html/vertretungsplan/rss/rss.xml"
cardsfile = "/var/www/html/vertretungsplan/cards/cards.html"
nameentrylist = ["Kurs", "Datum", "Stunde", "Fach", "Raum", "Lehrer", "Info", "Vertretungstext"]
updateonstart = True
holidays = False
outoforder = False
if holidays == True or outoforder == True:
    updateonstart = False
DBMYSQLHOST = "127.0.0.1"
DBMYSQLUSER = "root"
with codecs.open('sql_password.ini', 'r', 'utf-8') as sql_password_file:
    DBMYSQLPASSWD = sql_password_file.read()
DBMYSQLDB = "VPlan"

# functions
def logprefix():
    return strftime("%H:%M:%S - ")

def downloadplan(vplanurl = vplanurl, vplanfile = vplanfile):
    print (logprefix() + "Erhalte Plan")
    driver = webdriver.PhantomJS()
    driver.get(vplanurl)
    wait = WebDriverWait(driver, 7)
    try:
        wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "oddGroup")))
    except:
        print (logprefix() + "Plan nicht erhalten")
        return "FAILED"
    data = driver.page_source
    driver.quit()
    soup = BeautifulSoup(data, "html.parser")
    file = codecs.open(vplanfile, 'w', 'utf-8')
    #file.write(soup.get_text("\n"))
    file.write(data)
    file.close
    print (logprefix() + "Plan erhalten")
    return "SUCCESS"

def formatplan(vplanfile = vplanfile):
    print (logprefix() + "Formatiere Plan")
    # Daten extrahieren
    f = codecs.open(vplanfile, 'r', 'utf-8')
    fcontent = f.readlines()
    f.close
    dateA = ""
    dateB = ""
    dateAread = False
    extract = '        <div class="title" data-dojo-attach-point="titleNode">Vertretungen:<span data-dojo-attach-point="dateNode"> '
    for k in range(len(fcontent)):
        if extract in fcontent[k]:
            if dateAread == False:
                dateA = fcontent[k].replace(extract, '').replace('</span></div>', '')
                dateAread = True
            elif dateAread == True:
                dateB = fcontent[k].replace(extract, '').replace('</span></div>', '')

    # Tabelle extrahieren
    f = codecs.open(vplanfile, 'r', 'utf-8')
    fcontent = f.readlines()
    f.close
    dayA = "none"
    dayB = "none"
    dayAread = False
    for i in range(len(fcontent)):
        if "Keine Vertretungen" in fcontent[i]:
            if dayAread == False:
                dayA = "none"
                dayAread = True
        if "<table>" in fcontent[i]:
            if dayAread == False:
                dayA = fcontent[i]
                dayAread = True
            else:
                dayB = fcontent[i]
    dayAclean = ""
    dayBclean = ""

    # <td>s von Tabelle extrahieren (Tag 1)
    read = False
    detect = False
    for n in range(len(dayA)):
        if read == True:
            dayAclean += dayA[n]
            if dayA[n-4] == "<":
                if dayA[n-3] == "/":
                    if dayA[n-2] == "t":
                        if dayA[n-1] == "d":
                            if dayA[n] == ">":
                                read = False
                                dayAclean += "\n"
        if dayA[n] == "<":
            if dayA[n+1] == "t":
                if dayA[n+2] == "d":
                    detect = True
        if detect == True and dayA[n] == ">":
            read = True
            detect = False
    dayAclean = dayAclean.replace('</td>', '')
    # <td>s von Tabelle extrahieren (Tag 2)
    read = False
    detect = False
    for n in range(len(dayB)):
        if read == True:
            dayBclean += dayB[n]
            if dayB[n-4] == "<":
                if dayB[n-3] == "/":
                    if dayB[n-2] == "t":
                        if dayB[n-1] == "d":
                            if dayB[n] == ">":
                                read = False
                                dayBclean += "\n"
        if dayB[n] == "<":
            if dayB[n+1] == "t":
                if dayB[n+2] == "d":
                    detect = True
        if detect == True and dayB[n] == ">":
            read = True
            detect = False
    dayBclean = dayBclean.replace('</td>', '')

    # In Datei schreiben (Tag 1)
    f = codecs.open(vplanfile_a, 'w', 'utf-8')
    f.write(dayAclean.replace('<span class="substMonitorSubstElem">', '').replace('</span>', '').replace('<span class="cancelStyle">', ''))
    f.close
    # In Datei schreiben (Tag 2)
    f = codecs.open(vplanfile_b, 'w', 'utf-8')
    f.write(dayBclean.replace('<span class="substMonitorSubstElem">', '').replace('</span>', '').replace('<span class="cancelStyle">', ''))
    f.close

    # Sortieren und Beschriften (Tag 1)
    f = codecs.open(vplanfile_a, 'r', 'utf-8')
    fcontent = f.readlines()
    f.close
    fnewcontent = ""
    for j in range(0, len(fcontent), 8):
        fnewcontent += "Kurs: |" + fcontent[j].replace('\n', '') + "|" + "\n"
        fnewcontent += "Datum: " + dateA
        fnewcontent += "Stunde: |" + fcontent[j+2].replace('\n', '') + "|" + "\n"
        fnewcontent += "Fach: |" + fcontent[j+3].replace('\n', '') + "|" + "\n"
        fnewcontent += "Raum: |" + fcontent[j+4].replace('\n', '') + "|" + "\n"
        fnewcontent += "Lehrer: |" + fcontent[j+5].replace('\n', '') + "|" + "\n"
        fnewcontent += "Info: |" + fcontent[j+6].replace('\n', '') + "|" + "\n"
        fnewcontent += "Vertretungstext: |" + fcontent[j+7].replace('\n', '') + "|" + "\n"
    fnewcontent = fnewcontent.replace('||', 'N/A').replace('|', '')
    f = codecs.open(vplanfile_a, 'w', 'utf-8')
    f.write(fnewcontent)
    f.close
    # Sortieren und Beschriften (Tag 2)
    f = codecs.open(vplanfile_b, 'r', 'utf-8')
    fcontent = f.readlines()
    f.close
    fnewcontent = ""
    for j in range(0, len(fcontent), 8):
        fnewcontent += "Kurs: |" + fcontent[j].replace('\n', '') + "|" + "\n"
        fnewcontent += "Datum: " + dateB
        fnewcontent += "Stunde: |" + fcontent[j+2].replace('\n', '') + "|" + "\n"
        fnewcontent += "Fach: |" + fcontent[j+3].replace('\n', '') + "|" + "\n"
        fnewcontent += "Raum: |" + fcontent[j+4].replace('\n', '') + "|" + "\n"
        fnewcontent += "Lehrer: |" + fcontent[j+5].replace('\n', '') + "|" + "\n"
        fnewcontent += "Info: |" + fcontent[j+6].replace('\n', '') + "|" + "\n"
        fnewcontent += "Vertretungstext: |" + fcontent[j+7].replace('\n', '') + "|" + "\n"
    fnewcontent = fnewcontent.replace('||', 'N/A').replace('|', '')
    f = codecs.open(vplanfile_b, 'w', 'utf-8')
    f.write(fnewcontent)
    f.close
    print (logprefix() + "Plan formatiert")
    return "SUCCESS"

def DBFeeder():
    print (logprefix() + "Fuettere Datenbank")
    while True:
        try:
            db=MySQLdb.connect(host=DBMYSQLHOST, user=DBMYSQLUSER, passwd=DBMYSQLPASSWD, db=DBMYSQLDB)
        except MySQLdb.Error:
            os.system("systemctl restart mysql")
            sleep(5)
        else:
            break
    cur = db.cursor()
    cur2 = db.cursor()
    cur3 = db.cursor()
    cur.execute("DELETE FROM `Vertretungsplan` WHERE 1")
    cur.execute("ALTER TABLE `Vertretungsplan` AUTO_INCREMENT = 1")
    # cur.execute("TRUNCATE TABLE `Vertretungsplan`")
    debugfile = codecs.open('debugzl.txt', 'w', 'utf-8')
    for vplnfle in ([vplanfile_a, vplanfile_b]):
        vplanfile_ = vplnfle
        file = codecs.open(vplanfile_, 'r', 'utf-8')
        content = file.readlines()
        file.close
        file = codecs.open(vplanfile_, 'r', 'utf-8')
        lines = file.read().count('\n')
        file.close
        lines += 1
        WTL = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
        Wochentag = "FEHLER"
        VList = []
        for i in range(0, lines-1):
            if "Kurs: " in content[i]:
                if "BG-13" in content[i]:
                    content[i] = "Kurs: BG-13"
                elif "BG-12" in content[i]:
                    content[i] = "Kurs: BG-12"
                elif "BG-11" in content[i]:
                    content[i] = "Kurs: BG-11"
                for n in range(len(WTL)):
                    if WTL[n] in content[i+1]:
                        Wochentag = WTL[n]
                debugvar = "%s ----- " % len(content)
                debugfile.write(debugvar + str(content) + "\n\n")
                row = {"Kurs": content[i].replace('\n', '').replace('Kurs: ', ''), "Datum": content[i+1].replace('\n', '').replace('Datum: ', ''), "Stunde": content[i+2].replace('\n', '').replace('Stunde: ', ''), "Fach": content[i+3].replace('\n', '').replace('Fach: ', ''), "Raum": content[i+4].replace('\n', '').replace('Raum: ', ''), "Lehrer": content[i+5].replace('\n', '').replace('Lehrer: ', ''), "Info": content[i+6].replace('\n', '').replace('Info: ', ''), "Vertretungstext": content[i+7].replace('\n', '').replace('Vertretungstext: ', ''), "Wochentag": Wochentag}
                for n in range(len(nameentrylist)):
                    # row[nameentrylist[n]] = row[nameentrylist[n]].replace('Ö', '&Ouml;').replace('ö', '&ouml;').replace('Ü', '&Uuml;').replace('ü', '&uuml;').replace('Ä', '&auml;').replace('ä', '&auml;').replace('ß', '&szlig;')
                    row[nameentrylist[n]] = row[nameentrylist[n]]
                if not row in VList:
                    VList.append(row)
                    cur.executemany("INSERT INTO Vertretungsplan (Kurs, Datum, Stunde, Fach, Raum, Lehrer, Info, Vertretungstext, Wochentag) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",[(row["Kurs"], row["Datum"], row["Stunde"], row["Fach"], row["Raum"], row["Lehrer"], row["Info"], row["Vertretungstext"], row["Wochentag"])])
                    cur2.execute("SELECT ID FROM VertretungsplanHistory WHERE Kurs='%s' AND Datum='%s' AND Stunde='%s' AND Fach='%s' AND Raum='%s' AND Lehrer='%s' AND Info='%s' AND Vertretungstext='%s' AND Wochentag='%s'" % (row["Kurs"], row["Datum"], row["Stunde"], row["Fach"], row["Raum"], row["Lehrer"], row["Info"], row["Vertretungstext"], row["Wochentag"]))
                    HistoryNewEntry = False
                    for z in cur2.fetchall():
                        HistoryNewEntry = True
                    if HistoryNewEntry == False:
                        cur3.executemany("INSERT INTO VertretungsplanHistory (Kurs, Datum, Stunde, Fach, Raum, Lehrer, Info, Vertretungstext, Wochentag) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",[(row["Kurs"], row["Datum"], row["Stunde"], row["Fach"], row["Raum"], row["Lehrer"], row["Info"], row["Vertretungstext"], row["Wochentag"])])
    db.commit()
    db.close
    debugfile.close
    print (logprefix() + "Datenbank gefuettert")
    return "SUCCESS"

def RSSGen():
    print (logprefix() + "Generiere RSS-Feed")
    while True:
        try:
            db=MySQLdb.connect(host=DBMYSQLHOST, user=DBMYSQLUSER, passwd=DBMYSQLPASSWD, db=DBMYSQLDB)
        except MySQLdb.Error:
            os.system("systemctl restart mysql")
            sleep(5)
        else:
            break
    cur = db.cursor()
    cur.execute("SELECT `Kurs`, `Datum`, `Stunde`, `Fach`, `Raum`, `Lehrer`, `Info`, `Vertretungstext` FROM `Vertretungsplan` WHERE 1")
    file = codecs.open(rssfile, 'w', 'UTF-8')
    file.write('<?xml version="1.0" encoding="UTF-8" ?>\n<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:atom="http://www.w3.org/2005/Atom">\n    <channel>\n        <title>BBS II - Vertretungsplan</title>\n        <link>http://zlyfer.de</link>\n        <description>Vertretungsplan der BBS II Emden</description>\n        <atom:link href="http://vplan.zlyfer.de/rss/rss.xml" rel="self" type="application/rss+xml"/>\n')
    for i in cur.fetchall():
        Stunden = "Stunden"
        if len(str(i[2])) == 1:
            Stunden = "Stunde"
        file.write("        <item>\n")
        file.write("            <title>%s, %s</title>\n" % (str(i[0]), str(i[1])))
        file.write("            <link>http://zlyfer.de/vertretungsplan/?kurs=%s</link>\n" % str(i[0]))
        file.write("            <description><![CDATA[<img src='http://zlyfer.de/vertretungsplan/images/mobile.png'>")
        file.write("%s %s: %s bei %s in %s: %s, %s" % (Stunden, str(i[2]), str(i[3]), str(i[5]), str(i[4]), str(i[6]), str(i[7])))
        file.write("]]></description>\n")
        file.write("        </item>\n")
    file.write("    </channel>\n</rss>")
    file.close
    print (logprefix() + "RSS-Feed generiert")
    return "SUCCESS"

def CardsGen():
    print (logprefix() + "Generiere Cards")
    while True:
        try:
            db=MySQLdb.connect(host=DBMYSQLHOST, user=DBMYSQLUSER, passwd=DBMYSQLPASSWD, db=DBMYSQLDB)
        except MySQLdb.Error:
            os.system("systemctl restart mysql")
            sleep(5)
        else:
            break
    cur = db.cursor()
    cur.execute("SELECT `Kurs`, `Datum`, `Stunde`, `Fach`, `Raum`, `Lehrer`, `Info`, `Vertretungstext` FROM `Vertretungsplan` WHERE 1")
    file = codecs.open(cardsfile, 'w', 'UTF-8')
    Class = ""
    Margin = "even"
    Date = ""
    file.write("		<div class='cardbox class left' id='mobile_class_left'>\n")
    for i in cur.fetchall():
        if not Class == str(i[0]):
            if Class != "":
                Margin = "odd"
            Class = str(i[0])

        if not Date == str(i[1]):
            if Date == "":
                file.write("				<section class='card class'>\n					<h1>%s</h1>\n				</section>\n" % str(i[1]))
            if Date != "":
                file.write("		</div>\n		<div class='cardbox class right' id='mobile_class_right'>\n")
                file.write("				<section class='card class'>\n					<h1>%s</h1>\n				</section>\n" % str(i[1]))
                Margin = "even"
            Date = str(i[1])
        file.write('			<a href="./index.php?class=%s">\n				<section class="card class %s class_%s">\n					<h1>%s, %s</h1>\n					<h2>(%s) (%s) (%s) (%s) (%s)</h2>\n				</section>\n			</a>\n' % (str(i[0]), Margin, str(i[0]), str(i[0]), str(i[2]), str(i[3]), str(i[5]), str(i[4]), str(i[6]), str(i[7])))

        Margin = "even"
    file.write("		</div>\n")
    file.close
    print (logprefix() + "Cards generiert")
    return "SUCCESS"

def updateplan(vplanurl = vplanurl, vplanfile = vplanfile, nameentrylist = nameentrylist):
    if downloadplan(vplanurl, vplanfile) == "SUCCESS" and formatplan(vplanfile) == "SUCCESS" and DBFeeder() == "SUCCESS":# and RSSGen() == "SUCCESS":# and CardsGen() == "SUCCESS":
       return "SUCCESS"
    else:
       return "FAILED"

#startroutine
uptpln = "SKIPPED"
if updateonstart == True:
    uptpln = updateplan()
print (logprefix() + "Plan update: " + uptpln)

#variables bot
WhatToDo = {}
Icons0 = [""]
Icons1 = ["🔵 ", "🔴 "]
Icons2 = ["🔔", "🔕"]
Icons3 = ["🕐", "🕑", "🕒", "🕓", "🕔", "🕕", "🕖", "🕗", "🕘", "🕙", "🕚", "🕛", "🕜", "🕝"," 🕟", "🕞", "🕠", "🕡", "🕢", "🕣", "🕤", "🕥", "🕦", "🕧"]
Icons4 = ["📙", "📗", "📘", "📕"]
Icons5 = ["❓", "❗️"]
UsrKeyboard = [[KeyboardButton("📋 Vertretungspläne"), KeyboardButton("⚙️ Einstellungen")]]#, [KeyboardButton("Website")]]
DevKeyboardA = [[KeyboardButton("📋 Vertretungspläne"), KeyboardButton("⚙️ Einstellungen")], [KeyboardButton("👾 Entwicklereinstellungen")]]
DevKeyboardB = [[KeyboardButton("👾 Telegram-Bot neustarten"), KeyboardButton("👾 MySQL neustarten")], [KeyboardButton("👾 Apache neustarten"), KeyboardButton("👾 Vertretungsplan updaten")]]
DevKeyboardB.append([KeyboardButton("🏠 Hauptmenü")])
PasswordForgotKeyboard = [[KeyboardButton("✔️ Ja"), KeyboardButton("❌ Nein")]]
DevList = [175576819, 304123618]

BackKeyboard = [[KeyboardButton("⬅️ Zurück")]]
RegisterKeyboard = [[KeyboardButton("📝 Registrieren"), KeyboardButton("🔐 Anmelden")]]
updater = Updater(token='349143763:AAH1kGXCp5OzOjoFc7GnxC6A4Wbj9ApVLEI')

#system functions bot
def console(bot, text = "ERROR", parsemode="HTML"): # WIRD NOCH NICHT ÜBERALL ANGEWANDT!
    bot.sendMessage(chat_id=-248828335, text=text, parse_mode=parsemode)
    return

def hash(input):
    hash = hashlib.sha1()
    hash.update(input.encode('utf-8'))
    return hash.hexdigest()

def keyboardgen(ChatID):
    while True:
        try:
            db=MySQLdb.connect(host=DBMYSQLHOST, user=DBMYSQLUSER, passwd=DBMYSQLPASSWD, db=DBMYSQLDB)
        except MySQLdb.Error:
            os.system("systemctl restart mysql")
            sleep(5)
        else:
            break
    tcur = db.cursor()
    vcur = db.cursor()
    global VPlanKeyboard
    global SettingsKeyboard
    global InfoKeyboard
    global TimesKeyboard
    global ClassKeyboard
    global PasswordForgotKeyboard
    tcur.execute("SELECT `MeinKurs` FROM `TelegramBot` WHERE `ChatID`=%s" % ChatID)
    vcur.execute("SELECT `Kurs` FROM `Vertretungsplan` WHERE 1")
    KursAnzahl = 0
    KursPAnzahl = 0
    KursVAnzahl = []
    for n in vcur.fetchall():
        KursAnzahl += 1
        if not n[0] in KursVAnzahl:
            KursVAnzahl += n
    KursPAnzahl = KursAnzahl // 5
    if KursAnzahl % 5 != 0:
        KursPAnzahl += 1
    KursVAnzahl = len(KursVAnzahl)
    for i in tcur.fetchall():
        VPlanKeyboard = [[KeyboardButton("📋 Vertretungsplan (%s)" % KursAnzahl)],
                    [KeyboardButton("📓 Mein Kurs (%s)" % i[0])],
                    [KeyboardButton("📚 Andere Kurse (%s)" % KursVAnzahl)],
                    [KeyboardButton("⬅️ Zurück")]]
    tcur.execute("SELECT `Username`, `MeinKurs`, `Zeitplan` FROM `TelegramBot` WHERE `ChatID`=%s" % (ChatID))#, `ZeitplanModus`
    for i in tcur.fetchall():
        SettingsKeyboardVars = [i[0], i[1], i[2]]#, i[3]
    TimesKeyboardVars = []
    ZeitenAnzahl = 0
    for n in ["00", "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23"]:
        tcur.execute("SELECT `%s` FROM `TelegramBot` WHERE `ChatID`=%s" % (n, ChatID))
        for i in tcur.fetchall():
            TimesKeyboardVars.append(i[0]) # für TimesKeyboard
            if i[0] == 1:
                ZeitenAnzahl += 1
    if ZeitenAnzahl < 10:
        ZeitenAnzahl = "0" + str(ZeitenAnzahl)
    if SettingsKeyboardVars[2] == 0:
        SettingsKeyboardVars[2] = "Ausgeschaltet"
        ZPIcon = Icons2[1]
    else:
        SettingsKeyboardVars[2] = "Eingeschaltet"
        ZPIcon = Icons2[0]
    if SettingsKeyboardVars[0] == "":
        SettingsKeyboardVars[0] = "Unbenannt"
    else:
        SettingsKeyboardVars[0] = SettingsKeyboardVars[0].replace(' ', '')
    ZZIcon = Icons3[randint(0, len(Icons3)-1)]
    SettingsKeyboard = [[KeyboardButton("%s Zeitplan: %s" % (ZPIcon, SettingsKeyboardVars[2]))],
                        [KeyboardButton("%s Zeitplan Zeiten (%s/24)" % (ZZIcon, ZeitenAnzahl))],
                        [KeyboardButton("ℹ️ Plan Informationen")],
                        [KeyboardButton("🔄 Kurs wechseln (%s)" % SettingsKeyboardVars[1])],
                        [KeyboardButton("🆔 TelegramID: %s" % ChatID)],
                        [KeyboardButton("⬅️ Zurück"), KeyboardButton("🙋🏼‍♂️ Hilfe")]]
    InfoKeyboardVars = []
    for n in ["Kurs", "Datum", "Stunde", "Fach", "Raum", "Lehrer", "Info", "Vertretungstext"]:
        tcur.execute("SELECT `%s` FROM `TelegramBot` WHERE `ChatID`=%s" % (n, ChatID))
        for i in tcur.fetchall():
            InfoKeyboardVars.append(i[0])
    for k in range(len(InfoKeyboardVars)):
        if InfoKeyboardVars[k] == 0:
            InfoKeyboardVars[k] = Icons1[1]
        else:
            InfoKeyboardVars[k] = Icons1[0]
    InfoKeyboard = [[KeyboardButton("%s Kurs" % InfoKeyboardVars[0])],
                    [KeyboardButton("%s Datum" % InfoKeyboardVars[1])],
                    [KeyboardButton("%s Stunde" % InfoKeyboardVars[2])],
                    [KeyboardButton("%s Fach" % InfoKeyboardVars[3])],
                    [KeyboardButton("%s Raum" % InfoKeyboardVars[4])],
                    [KeyboardButton("%s Lehrer" % InfoKeyboardVars[5])],
                    [KeyboardButton("%s Info" % InfoKeyboardVars[6])],
                    [KeyboardButton("%s Vertretungstext" % InfoKeyboardVars[7])],
                    [KeyboardButton("⬅️ Zurück")]]
    # Nach oben verschoben.
    for k in range(len(TimesKeyboardVars)):
        if TimesKeyboardVars[k] == 0:
            TimesKeyboardVars[k] = Icons1[1]
        else:
            TimesKeyboardVars[k] = Icons1[0]
    TimesKeyboard = [[KeyboardButton("%s 00" % TimesKeyboardVars[0]), KeyboardButton("%s 01" % TimesKeyboardVars[1]), KeyboardButton("%s 02" % TimesKeyboardVars[2]), KeyboardButton("%s 03" % TimesKeyboardVars[3])],
                    [KeyboardButton("%s 04" % TimesKeyboardVars[4]), KeyboardButton("%s 05" % TimesKeyboardVars[5]), KeyboardButton("%s 06" % TimesKeyboardVars[6]), KeyboardButton("%s 07" % TimesKeyboardVars[7])],
                    [KeyboardButton("%s 08" % TimesKeyboardVars[8]), KeyboardButton("%s 09" % TimesKeyboardVars[9]), KeyboardButton("%s 10" % TimesKeyboardVars[10]), KeyboardButton("%s 11" % TimesKeyboardVars[11])],
                    [KeyboardButton("%s 12" % TimesKeyboardVars[12]), KeyboardButton("%s 13" % TimesKeyboardVars[13]), KeyboardButton("%s 14" % TimesKeyboardVars[14]), KeyboardButton("%s 15" % TimesKeyboardVars[15])],
                    [KeyboardButton("%s 16" % TimesKeyboardVars[16]), KeyboardButton("%s 17" % TimesKeyboardVars[17]), KeyboardButton("%s 18" % TimesKeyboardVars[18]), KeyboardButton("%s 19" % TimesKeyboardVars[19])],
                    [KeyboardButton("%s 20" % TimesKeyboardVars[20]), KeyboardButton("%s 21" % TimesKeyboardVars[21]), KeyboardButton("%s 22" % TimesKeyboardVars[22]), KeyboardButton("%s 23" % TimesKeyboardVars[23])],
                    [KeyboardButton("⬅️ Zurück")]]
    ClassKeyboard = []
    ClassList = []
    vcur.execute("SELECT `Kurs` FROM `Vertretungsplan` WHERE 1")
    for i in vcur.fetchall():
        if not i[0] in ClassList:
            ClassList.append(i[0])
    ClassList.sort()
    Incr1 = 0
    for n in range(len(ClassList)):
        ClassKeyboard.append([KeyboardButton("%s %s" % (Icons4[Incr1], ClassList[n]))])
        Incr1 += 1
        if Incr1 == 4:
            Incr1 = 0
    ClassKeyboard.append([KeyboardButton("⬅️ Zurück")])
    db.close
    return

def registercheck(ChatID, Username = "0"):
    while True:
        try:
            db=MySQLdb.connect(host=DBMYSQLHOST, user=DBMYSQLUSER, passwd=DBMYSQLPASSWD, db=DBMYSQLDB)
        except MySQLdb.Error:
            os.system("systemctl restart mysql")
            sleep(5)
        else:
            break
    cur = db.cursor()
    cur.execute("SELECT `ChatID` FROM `TelegramBot` WHERE `ChatID`=%s" % ChatID)
    db.close
    if cur.fetchone() != None:
        return True
    return False

def login(ChatID, Username, Password):
    while True:
        try:
            db=MySQLdb.connect(host=DBMYSQLHOST, user=DBMYSQLUSER, passwd=DBMYSQLPASSWD, db=DBMYSQLDB)
        except MySQLdb.Error:
            os.system("systemctl restart mysql")
            sleep(5)
        else:
            break
    cur2 = db.cursor()
    cur3 = db.cursor()
    cur2.execute("SELECT `password` FROM `TelegramBot` WHERE `Username`='%s'" % str(Username))
    PW = ""
    for n in cur2.fetchall():
        PW = n[0]
    if hash(str(Password)) == str(PW):
        cur3.execute("UPDATE `TelegramBot` SET `ChatID`='%s' WHERE `Username`='%s'" % (ChatID, Username))
        db.commit()
        db.close
        return "1Herzlichen Glückwunsch! Du hast dich erfolgreich angemeldet.\n\nBei Fragen kannst du dich <strong>jederzeit</strong> bei mir melden!\n~@zlyfer"
    elif hash(str(Password)) != str(PW):
        db.close
        return "0Anmeldung <strong>fehlgeschlagen</strong>!\n\n<i>Username und Passwort stimmen nicht überein! Eventuell musst du deinen Telegram-Usernamen ändern oder dich registrieren.</i>"
    else:
        db.close
        return "ERROR"

def updatename(ChatID, Username):
    while True:
        try:
            db=MySQLdb.connect(host=DBMYSQLHOST, user=DBMYSQLUSER, passwd=DBMYSQLPASSWD, db=DBMYSQLDB)
        except MySQLdb.Error:
            os.system("systemctl restart mysql")
            sleep(5)
        else:
            break
    cur1 = db.cursor()
    cur1.execute("SELECT `Username` FROM `TelegramBot` WHERE `ChatID`='%s'" % ChatID)
    User = cur1.fetchone()
    if str(User[0]) != str(Username) and str(Username) != "":
        cur2 = db.cursor()
        cur2.execute("UPDATE `TelegramBot` SET `Username`='%s' WHERE `ChatID`='%s'" % (Username, ChatID))
        db.commit()
        db.close
        return [True, "Wir haben erkannt, dass du deinen Usernamen von <strong>%s</strong> zu <strong>%s</strong> geändert hast, und haben die Änderungen übernommen." % (User[0], Username)]
    elif str(Username) == "" and str(User[0]) != str(ChatID):
        cur2 = db.cursor()
        cur2.execute("UPDATE `TelegramBot` SET `Username`='%s' WHERE `ChatID`='%s'" % (ChatID, ChatID))
        db.commit()
        db.close
        return [True, "Wir haben erkannt, dass du keinen Telegram Usernamen hast.\n\nDein Username wird nun deine TelegramID sein: <strong>%s</strong>.\nDu kannst dir jederzeit in Telegram einen Usernamen erstellen und wir werden die Daten automatisch übernehmen." % ChatID]
    else:
        db.close
        return [False]

def bot_sendplan(bot, ChatID, Caller, Additional = 0):
    while True:
        try:
            db=MySQLdb.connect(host=DBMYSQLHOST, user=DBMYSQLUSER, passwd=DBMYSQLPASSWD, db=DBMYSQLDB)
        except MySQLdb.Error:
            os.system("systemctl restart mysql")
            sleep(5)
        else:
            break
    tcur = db.cursor()
    vcur = db.cursor()
    tcur.execute("SELECT * FROM `TelegramBot` WHERE `ChatID`=%s" % ChatID)
    User = tcur.fetchone()
    PlanDic = {}
    HasPlan = 0
    if Caller == "EVERYTHING":
        vcur.execute("SELECT * FROM `Vertretungsplan` WHERE 1")
        Kind = "NONE"
    elif Caller == "MYPLAN":
        vcur.execute("SELECT * FROM `Vertretungsplan` WHERE `Kurs`='%s'" % str(User[3]))
        Kind = str(User[3])
    elif Caller == "SELECTED":
        vcur.execute("SELECT * FROM `Vertretungsplan` WHERE `Kurs`='%s'" % Additional)
        Kind = Additional
    elif Caller == "ZEITPLAN":
        UmRe = {'\u00c4': 'Ä', '\u00e4': 'ä', '\u00d6': 'Ö', '\u00f6': 'ö', '\u00dc': 'Ü', '\u00fc': 'ü', '\u00df': 'ß'}
        PlanList = ["Mo1_2", "Mo3_4", "Mo5_6", "Mo7_8", "Mo9_10", "Mo11_12", "Di1_2", "Di3_4", "Di5_6", "Di7_8", "Di9_10", "Di11_12", "Mi1_2", "Mi3_4", "Mi5_6", "Mi7_8", "Mi9_10", "Mi11_12", "Do1_2", "Do3_4", "Do5_6", "Do7_8", "Do9_10", "Do11_12", "Fr1_2", "Fr3_4", "Fr5_6", "Fr7_8", "Fr9_10", "Fr11_12"]
        pcur = db.cursor()
        pcur.execute("SELECT `Mo1_2`, `Mo3_4`, `Mo5_6`, `Mo7_8`, `Mo9_10`, `Mo11_12`, `Di1_2`, `Di3_4`, `Di5_6`, `Di7_8`, `Di9_10`, `Di11_12`, `Mi1_2`, `Mi3_4`, `Mi5_6`, `Mi7_8`, `Mi9_10`, `Mi11_12`, `Do1_2`, `Do3_4`, `Do5_6`, `Do7_8`, `Do9_10`, `Do11_12`, `Fr1_2`, `Fr3_4`, `Fr5_6`, `Fr7_8`, `Fr9_10`, `Fr11_12`, `user` FROM `plaene` WHERE `user`='%s'" % User[2])
        Plan = pcur.fetchone()
        pncur = db.cursor()
        pncur.execute("SELECT `user` FROM `plaene` WHERE `user`='%s'" % User[2])
        if pncur.fetchone():
            HasPlan = 1
            for i in range(len(PlanList)):
                PlanDic[PlanList[i]] = Plan[i]
        WeekDayList = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
        VPlanEntries = []
        vcur.execute("SELECT `Datum`, `ID` FROM `Vertretungsplan` WHERE `Kurs`='%s'" % str(User[3]))
        for l in vcur.fetchall():
            VPlanDate = l[0]
            for k in range(len(WeekDayList)):
                VPlanDate = VPlanDate.replace("%s, " % WeekDayList[k], "")
            VDay = VPlanDate[0] + VPlanDate[1]
            VMonth = VPlanDate[3] + VPlanDate[4]
            VYear = VPlanDate[6] + VPlanDate[7] + VPlanDate[8] + VPlanDate[9]
            VDate = date(int(VYear), int(VMonth), int(VDay))
            RDay = strftime("%d")
            RMonth = strftime("%m")
            RYear = strftime("%Y")
            RDate = date(int(RYear), int(RMonth), int(RDay))
            DD = VDate - RDate
            DD = int(DD.total_seconds())
            if DD > -1: # Wenn nicht in der Vergangenheit
                if DD == 0: # Wenn am gleichen Tag
                    if int(strftime("%H")) < 18: # Wenn vor 18 Uhr
                    # if int(strftime("%H")) != -1: # Für Testzwecke
                        VPlanEntries.append(l[1])
                else: # Wenn an einem Tag in der Zukunft - logischer Weise
                    VPlanEntries.append(l[1])
        VPlanEntries = tuple(VPlanEntries)
        NothingHere = False
        if len(VPlanEntries) == 1:
            vcur.execute("SELECT * FROM `Vertretungsplan` WHERE `ID` = %s" % VPlanEntries[0])
        elif len(VPlanEntries) > 1:
            vcur.execute("SELECT * FROM `Vertretungsplan` WHERE `ID` IN %s" % (VPlanEntries,))
        elif len(VPlanEntries) == 0:
            NothingHere = True
        else:
            # Fehlernachricht hier.
            db.close
            return
        VPlanEntries = []
        currenttime = int(strftime("%H"))
        greeting = "!"
        if currenttime in range(5) or currenttime in range(22,24):
            greeting = "Gute Nacht"
        if currenttime in range(5,10):
            greeting = "Guten Morgen"
        if currenttime in range(10,12):
            greeting = "Guten Vormittag"
        if currenttime in range(12,14):
            greeting = "Guten Mittag"
        if currenttime in range(14,18):
            greeting = "Guten Nachmittag"
        if currenttime in range(18,22):
            greeting = "Guten Abend"
        UName = "!"
        if User[2] != "":
            UName = ", %s!" % User[2]
        if NothingHere == True:
            db.close
            return
        bot.send_chat_action(chat_id=ChatID, action="TYPING")
        bot.sendMessage(chat_id=-248828335, text="<strong>%s</strong> to <strong>%s/%s</strong>." % (str(User[3]), str(User[2]), str(User[1])), parse_mode="HTML")
        bot.sendMessage(chat_id=ChatID, text="%s%s\n<i>Es ist %s Uhr. Hier ist dein Vertretungsplan.</i>" % (greeting, UName, currenttime), parse_mode="HTML")
        Kind = str(User[3])
    VPlan = ""
    Entry = 0
    Page = 0
    for i in vcur.fetchall():
        # Wochentag: i[8]
        # Stunde: i[2]
        # Lehrer: i[5]
        WochentagStunde = i[9] + " " + i[2]
        if not Caller == "ZEITPLAN" or HasPlan == 0:
            PlanDic[WochentagStunde] = i[5]
        if Entry == 6:
            Entry = 0
            Page += 1
            sleep(0.2)
            bot.sendMessage(chat_id=ChatID, text="<strong>Vertretungsplan Seite %s</strong>\n\n%s" % (Page, VPlan), parse_mode="HTML")
            VPlan = ""
        if PlanDic[WochentagStunde] == i[5]:
            Entry += 1
            if User[5] == 1:
                VPlan += "<strong>Kurs</strong>: <a href='https://zlyfer.de/vertretungsplan/?kurs=%s'>%s</a>\n" % (i[0], i[0])
            if User[6] == 1:
                VPlan += "<strong>Datum</strong>: <i>" + i[1] + "</i>\n"
            if User[7] == 1:
                VPlan += "<strong>Stunde</strong>: <i>" + i[2] + "</i>\n"
            if User[8] == 1:
                VPlan += "<strong>Fach</strong>: <i>" + i[3] + "</i>\n"
            if User[9] == 1:
                VPlan += "<strong>Raum</strong>: <i>" + i[4] + "</i>\n"
            if User[10] == 1:
                VPlan += "<strong>Lehrer</strong>: <i>" + i[5] + "</i>\n"
            if User[11] == 1:
                VPlan += "<strong>Info</strong>: <i>" + i[6] + "</i>\n"
            if User[12] == 1:
                VPlan += "<strong>Vertretungstext</strong>: <i>" + i[7] + "</i>\n"
            VPlan += "\n"
        # VPlan = VPlan.replace('&Ouml;', 'Ö').replace('&ouml;', 'ö').replace('&Uuml;', 'Ü').replace('&uuml;', 'ü').replace('&Auml;', 'Ä').replace('&auml;', 'ä').replace('&szlig;', 'ß')
    if VPlan != "":
        Page += 1
        sleep(0.2)
        if Page == 1:
            bot.sendMessage(chat_id=ChatID, text="<strong>Vertretungsplan</strong>\n\n%s" % VPlan, parse_mode="HTML")
        else:
            bot.sendMessage(chat_id=ChatID, text="<strong>Vertretungsplan Seite %s</strong>\n\n%s" % (Page, VPlan), parse_mode="HTML")
    else:
        if Page == 0:
            if Kind == "NONE":
                bot.sendMessage(chat_id=ChatID, text="Der Vertretungsplan ist leer.", parse_mode="HTML")
            else:
                bot.sendMessage(chat_id=ChatID, text="Der Kurs '<strong>%s</strong>' ist nicht auf dem Vertretungsplan vermerkt." % Kind, parse_mode="HTML")
    #if Caller == "ZEITPLAN" and HasPlan == 0:
        #bot.sendMessage(chat_id=ChatID, text="<strong>Info:</strong>\n\nDu willst nur die Vertretungen, die <strong>für dich</strong> relevant sind?\nDann <strong>verbinde dich jetzt</strong> mit deinem Telegram-Account auf unserer <a href='https://zlyfer.de/vertretungsplan/?site=account'>Website</a> und trage <strong>deinen Stundenplan</strong> ein!\n\nMithilfe deines Stundenplans können wir dir die nur für dich <strong>relevanten Daten</strong> senden.", parse_mode="HTML")
    return

def userconfg(Task, ChatID, Text = "USERCONFGERROR"):
    while True:
        try:
            db=MySQLdb.connect(host=DBMYSQLHOST, user=DBMYSQLUSER, passwd=DBMYSQLPASSWD, db=DBMYSQLDB)
        except MySQLdb.Error:
            os.system("systemctl restart mysql")
            sleep(5)
        else:
            break
    cur = db.cursor()
    cur.execute("SELECT `Username` FROM `TelegramBot` WHERE `ChatID`=%s" % ChatID)
    UUser = cur.fetchone()
    Text = str(Text)
    if Task == "register":
        cur.execute("SELECT `ChatID` FROM `TelegramBot` WHERE 1")
        if registercheck(ChatID) == True:
            return "Okay %s, du bist bereits registriert." % Text
        cur.execute("INSERT IGNORE INTO `TelegramBot`(`ChatID`, `Username`, `MeinKurs`, `Zeitplan`, `Kurs`, `Datum`, `Stunde`, `Fach`, `Raum`, `Lehrer`, `Info`, `Vertretungstext`, `00`, `01`, `02`, `03`, `04`, `05`, `06`, `07`, `08`, `09`, `10`, `11`, `12`, `13`, `14`, `15`, `16`, `17`, `18`, `19`, `20`, `21`, `22`, `23`, `password`, `permission`) VALUES (%s,'%s','BG-12',0,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,'%s',10)" % (ChatID, Text, hash(Text)))
        db.commit()
        db.close
        RegNoUsAdd = "\n"
        if Text == str(ChatID):
            RegNoUsAdd = "\nDa du keinen Telegram Usernamen hast, ist dein Username nun deine TelegramID <strong>%s</strong>.\n" % ChatID
        return "Herzlichen Glückwunsch %s! Du wurdest registriert.\n\nWenn du dich auf unserer <a href='https://zlyfer.de/vertretungsplan/?site=account'>Website</a> mit deinem Telegram-Account <strong>verbindest</strong> und deinen <strong>Stundenplan einträgst</strong>, können wir dir die nur für dich <strong>relevanten</strong> Vertretungen schicken.\nProbiere es doch gleich aus!\n%sDein Passwort ist dein Username.\nEs wird <strong>empfohlen</strong>, dein Passwort so schnell wie möglich zu ändern!\n\nBei Fragen kannst du dich <strong>jederzeit</strong> bei mir melden!\n~@zlyfer" % (Text, RegNoUsAdd)
    elif Task == "toggletimeplan":
        cur.execute("SELECT `Zeitplan` FROM `TelegramBot` WHERE `ChatID`='%s'" % ChatID)
        for i in cur.fetchall():
            if i[0] == 0:
                cur.execute("UPDATE `TelegramBot` SET `Zeitplan`=1 WHERE `ChatID`='%s'" % ChatID)
                db.commit()
                db.close
                keyboardgen(ChatID)
                return "Okay %s, dein Zeitplan wurde <strong>eingeschaltet</strong>." % UUser[0]
            else:
                cur.execute("UPDATE `TelegramBot` SET `Zeitplan`=0 WHERE `ChatID`='%s'" % ChatID)
                db.commit()
                db.close
                keyboardgen(ChatID)
                return "Okay %s, dein Zeitplan wurde <strong>ausgeschaltet</strong>." % UUser[0]
        return "USERCONFGERROR"
    elif Task == "setclass":
        cur.execute("UPDATE `TelegramBot` SET `MeinKurs`='%s' WHERE `ChatID`=%s" % (Text, ChatID))
        db.commit()
        db.close
        keyboardgen(ChatID)
        return "Okay %s, du bist im Kurs <strong>%s</strong>." % (UUser[0], Text)
    elif Task == "setinfo":
        cur.execute("SELECT `%s` FROM `TelegramBot` WHERE `ChatID`='%s'" % (Text, ChatID))
        for i in cur.fetchall():
            if i[0] == 0:
                cur.execute("UPDATE `TelegramBot` SET `%s`=1 WHERE `ChatID`='%s'" % (Text, ChatID))
                db.commit()
                db.close
                keyboardgen(ChatID)
                return "Okay %s, du wirst die Information '<strong>%s</strong>' erhalten." % (UUser[0], Text)
            else:
                cur.execute("UPDATE `TelegramBot` SET `%s`=0 WHERE `ChatID`='%s'" % (Text, ChatID))
                db.commit()
                db.close
                keyboardgen(ChatID)
                return "Okay %s, du wirst die Information '<strong>%s</strong>' nicht mehr erhalten." % (UUser[0], Text)
        return "USERCONFGERROR"
    elif Task == "settimes":
        cur.execute("SELECT `%s` FROM `TelegramBot` WHERE `ChatID`='%s'" % (Text, ChatID))
        for i in cur.fetchall():
            if i[0] == 0:
                cur.execute("UPDATE `TelegramBot` SET `%s`=1 WHERE `ChatID`='%s'" % (Text, ChatID))
                db.commit()
                db.close
                keyboardgen(ChatID)
                return "Okay %s, du wirst um <strong>%s Uhr</strong> den Vertretungsplan erhalten." % (UUser[0], Text)
            else:
                cur.execute("UPDATE `TelegramBot` SET `%s`=0 WHERE `ChatID`='%s'" % (Text, ChatID))
                db.commit()
                db.close
                keyboardgen(ChatID)
                return "Okay %s, du wirst nicht mehr um <strong>%s Uhr</strong> den Vertretungsplan erhalten." % (UUser[0], Text)
        return "USERCONFGERROR"
    return "USERCONFGERROR"

def DevSysAction(bot, update, action = ""):
    if not action == "":
        bot.sendMessage(chat_id=update.message.chat_id, text="Wird ausgeführt: <i>%s</i>" % action, parse_mode="HTML")
        os.system(action)
        bot.sendMessage(chat_id=update.message.chat_id, text="Befehl ausgeführt.")
        return
    else:
        bot.sendMessage(chat_id=update.message.chat_id, text="Unbekannter Befehl!")
        return

def unknown(bot, update):
    sleep(0.3)
    bot.sendMessage(chat_id=update.message.chat_id, text="Es tut mir leid, das habe ich nicht verstanden.\nBitte benutze die <strong>Telegram-Tastatur</strong> um mich zu steuern.\nFalls du diese nicht siehst, benutze den <strong>Befehl</strong> /start um mich erneut zu starten.\n\nDanke!", parse_mode="HTML")
    return

#bot functions bot
def bot_mainhandler(bot, update):
    bot.send_chat_action(chat_id=update.message.chat_id, action="TYPING")
    #print (logprefix() + "%s/%s/%s: '%s'" % (update.message.chat.username, update.message.chat.first_name, update.message.chat_id, update.message.text))
    console(bot, "<strong>%s/%s/%s:</strong>  <i>%s</i>" % (update.message.chat.username, update.message.chat.first_name, update.message.chat_id, update.message.text))
    if not update.message.chat.username:
        bot.sendMessage(chat_id=update.message.chat_id, text="Du hast noch keinen <strong>Telegram-Usernamen!</strong>\n\nUm den Bot und die Website im <strong>vollem Umfang</strong> nutzen zu können, benötigst du einen Telegram-Usernamen.", parse_mode="HTML")
    Request = update.message.text

    if update.message.chat_id in DevList:
        Keyboard = DevKeyboardA
    else:
        Keyboard = UsrKeyboard

    if "👾" in Request or "🏠" in Request:
        if update.message.chat_id in DevList:
            if Request == "👾 Entwicklereinstellungen":
                bot.sendMessage(chat_id=update.message.chat_id, text="Wilkommen, was möchtest du tun?", parse_mode="HTML", reply_markup=ReplyKeyboardMarkup(DevKeyboardB))
                return
            if Request == "👾 Telegram-Bot neustarten":
                DevSysAction(bot, update, "systemctl restart vplanbot")
                return
            elif Request == "👾 MySQL neustarten":
                DevSysAction(bot, update, "systemctl restart mysql")
                return
            elif Request == "👾 Apache neustarten":
                DevSysAction(bot, update, "systemctl restart apache2")
                return
            elif Request == "👾 Vertretungsplan updaten":
                bot.sendMessage(chat_id=update.message.chat_id, text="Planupdate wird ausgeführt.")
                if updateplan() == "SUCCESS":
                    bot.sendMessage(chat_id=update.message.chat_id, text="Planupdate erfolgreich.")
                else:
                    bot.sendMessage(chat_id=update.message.chat_id, text="Planupdate fehlgeschlagen.")
                return
            elif Request == "🏠 Hauptmenü":
                bot.sendMessage(chat_id=update.message.chat_id, text="Okay.", reply_markup=ReplyKeyboardMarkup(Keyboard))
                return
            else:
                bot.sendMessage(chat_id=update.message.chat_id, text="Fehlerhafte Eingabe!")
                return
        else:
            console(bot, "%s/%s/%s hat versucht unerlaubterweise in die Entwicklereinstellungen zu kommen - verweigert!" % (update.message.chat.username, update.message.chat.first_name, update.message.chat_id))
            bot.sendMessage(chat_id=update.message.chat_id, text="Du bist kein Entwickler!\nDie Symbole '🏠' und '👾' sind ausschliesßlich für Entwickler des alternativen Vertretungsplans oder des Vertretungsplan-Bots reserviert.")
            return

    while True:
        try:
            db=MySQLdb.connect(host=DBMYSQLHOST, user=DBMYSQLUSER, passwd=DBMYSQLPASSWD, db=DBMYSQLDB)
        except MySQLdb.Error:
            os.system("systemctl restart mysql")
            sleep(5)
        else:
            break

    if update.message.chat_id < 0:
        bot.sendMessage(chat_id=update.message.chat_id, text="Gruppen sind leider nicht erlaubt.")
        return

    if Request == "📝 Registrieren":
        cur2 = db.cursor()
        if update.message.chat.username:
            Username = update.message.chat.username
        else:
            Username = update.message.chat_id
        cur2.execute("SELECT `Username` FROM `TelegramBot` WHERE `Username`='%s'" % Username)
        if cur2.fetchone():
            bot.sendMessage(chat_id=update.message.chat_id, text="Registrierung <strong>fehlgeschlagen</strong>!\n\nEs gibt bereits einen Account mit diesem Nutzernamen ('%s'). Bitte melde dich an oder ändere deinen Telegram Usernamen.\n\nBei Fragen kannst du dich <strong>jederzeit</strong> bei mir melden!\n~@zlyfer" % Username, parse_mode="HTML", reply_markup=ReplyKeyboardMarkup(RegisterKeyboard))
        else:
            bot.sendMessage(chat_id=update.message.chat_id, text=userconfg("register", update.message.chat_id, Username), parse_mode="HTML", reply_markup=ReplyKeyboardMarkup(Keyboard))
        return
    elif Request == "🔐 Anmelden":
        WhatToDo[update.message.chat_id] = "LOGIN"
        bot.sendMessage(chat_id=update.message.chat_id, text="Bitte sende mir dein Passwort.", reply_markup=ReplyKeyboardMarkup(BackKeyboard))
        return
    if update.message.chat_id in WhatToDo:
        if WhatToDo[update.message.chat_id] == "LOGIN" and Request == "⬅️ Zurück":
            bot.sendMessage(chat_id=update.message.chat_id, text="Okay.", reply_markup=ReplyKeyboardMarkup(RegisterKeyboard))
            return
    if registercheck(update.message.chat_id) == False:
        NotRegText = "Du bist noch nicht angemeldet.\nBitte registriere dich oder melde dich an indem du auf den Button <strong>📝 Registrieren</strong> oder <strong>🔐 Anmelden</strong> in deiner Telegram-Tastatur drückst.\nFalls du diese nicht siehst, benutze den <strong>Befehl</strong> /start um mich erneut zu starten.\n\nDanke!"
        if not update.message.chat_id in WhatToDo:
            bot.sendMessage(chat_id=update.message.chat_id, text=NotRegText, parse_mode="HTML", reply_markup=ReplyKeyboardMarkup(RegisterKeyboard))
            return
        elif WhatToDo[update.message.chat_id] != "LOGIN":
            bot.sendMessage(chat_id=update.message.chat_id, text=NotRegText, parse_mode="HTML", reply_markup=ReplyKeyboardMarkup(RegisterKeyboard))
            return
    else:
        CheckUN = updatename(update.message.chat_id, update.message.chat.username)
        if CheckUN[0] == True:
            bot.sendMessage(chat_id=update.message.chat_id, text=CheckUN[1], parse_mode="HTML")

    cur = db.cursor()
    cur.execute("SELECT `Username` FROM `TelegramBot` WHERE `ChatID`=%s" % update.message.chat_id)
    MUser = cur.fetchone()
    db.close

    if not update.message.chat_id in WhatToDo:
        keyboardgen(update.message.chat_id)
    elif WhatToDo[update.message.chat_id] != "LOGIN":
        keyboardgen(update.message.chat_id)

    if Request == "📋 Vertretungspläne":
        WhatToDo[update.message.chat_id] = "MAIN"
        bot.sendMessage(chat_id=update.message.chat_id, text="Okay %s,\nwähle <strong>Vertretungsplan</strong> um den gesamten Vertretungsplan zu erhalten,\nwähle <strong>Mein Kurs</strong> um den Vertretungsplan für deinen Kurs zu erhalten,\nwähle <strong>Andere Kurse</strong> um den Vertretungsplan für einen ausgewählten Kurs zu erhalten." % MUser[0], reply_markup=ReplyKeyboardMarkup(VPlanKeyboard), parse_mode="HTML")
        return

    elif "📋 Vertretungsplan (" in Request and ")" in Request:
        bot_sendplan(bot, update.message.chat_id, "EVERYTHING")
        return

    elif "🆔 TelegramID: %s" % update.message.chat_id in Request: # Vielleicht ist das besser als es bei "unknown" zu isolieren.
        bot.sendMessage(chat_id=update.message.chat_id, parse_mode="HTML", text="Du kannst deine TelegramID benutzen, um dich auf unserer <a href='vplan.zlyfer.de'>Website</a> mit deinem Telegram Account zu verbinden.\nWenn du keinen Nutzernamen in Telegram hast, benutze beim Anmelden deine TelegramID als Nutzername.")
        return

    elif "📓 Mein Kurs (" in Request and ")" in Request:
        bot_sendplan(bot, update.message.chat_id, "MYPLAN")
        return

    elif "📚 Andere Kurse (" in Request and ")" in Request:
        WhatToDo[update.message.chat_id] = "OTHERCLASSES"
        bot.sendMessage(chat_id=update.message.chat_id, text="Okay %s, wähle einen Kurs aus und ich sende dir den Vertretungsplan." % MUser[0], reply_markup=ReplyKeyboardMarkup(ClassKeyboard))
        return

    elif Request == "⚙️ Einstellungen":
        WhatToDo[update.message.chat_id] = "MAIN"
        bot.sendMessage(chat_id=update.message.chat_id, text="Okay %s." % MUser[0], reply_markup=ReplyKeyboardMarkup(SettingsKeyboard))
        return

    elif Request == "ℹ️ Plan Informationen":
        WhatToDo[update.message.chat_id] = "SETINFO"
        bot.sendMessage(chat_id=update.message.chat_id, text="Okay %s, wähle aus, welche Informationen du von dem Vertretungsplan erhalten willst." % MUser[0], reply_markup=ReplyKeyboardMarkup(InfoKeyboard))
        return

    elif "Zeitplan Zeiten (" in Request and "/24)" in Request:
        WhatToDo[update.message.chat_id] = "SETTIMES"
        bot.sendMessage(chat_id=update.message.chat_id, text="Okay %s, wähle aus, zu welchen Uhrzeiten du automatisch den Vertretungsplan erhalten willst." % MUser[0], reply_markup=ReplyKeyboardMarkup(TimesKeyboard))
        return

    elif "🔄 Kurs wechseln (" in Request and ")" in Request:
        WhatToDo[update.message.chat_id] = "SETCLASS"
        bot.sendMessage(chat_id=update.message.chat_id, text="Okay %s, schreibe mir in welchem Kurs du bist." % MUser[0], reply_markup=ReplyKeyboardMarkup(BackKeyboard, resize_keyboard=True))
        return

    elif "Zeitplan" in Request:
        if ": Eingeschaltet" in Request or ": Ausgeschaltet" in Request:
            bot.sendMessage(chat_id=update.message.chat_id, text=userconfg("toggletimeplan", update.message.chat_id), parse_mode="HTML", reply_markup=ReplyKeyboardMarkup(SettingsKeyboard))
            return
        else:
            return

    elif Request == "🙋🏼‍♂️ Hilfe":
        bot.sendMessage(chat_id=update.message.chat_id, text="Du hast <strong>Fragen</strong>, <strong>Probleme</strong>, brauchst <strong>Hilfestellung</strong> oder willst einen <strong>Fehler melden</strong>?\n\nDann schreib uns <strong>jederzeit</strong> an!\n\n<code>Telegram: </code>@zlyfer\n<code>Website:  </code>@TariqqMC", parse_mode="HTML")
        return

    elif Request == "⬅️ Zurück":
        if not update.message.chat_id in WhatToDo or WhatToDo[update.message.chat_id] == "" or WhatToDo[update.message.chat_id] == "MAIN":
            bot.sendMessage(chat_id=update.message.chat_id, text="Okay %s." % MUser[0], reply_markup=ReplyKeyboardMarkup(Keyboard))
            WhatToDo[update.message.chat_id] = ""
        elif WhatToDo[update.message.chat_id] == "SETTIMES" or WhatToDo[update.message.chat_id] == "SETINFO" or WhatToDo[update.message.chat_id] == "RENAME" or WhatToDo[update.message.chat_id] == "SETCLASS":
            WhatToDo[update.message.chat_id] = "MAIN"
            bot.sendMessage(chat_id=update.message.chat_id, text="Okay %s." % MUser[0], reply_markup=ReplyKeyboardMarkup(SettingsKeyboard))
        elif WhatToDo[update.message.chat_id] == "OTHERCLASSES":
            bot.sendMessage(chat_id=update.message.chat_id, text="Okay %s." % MUser[0], reply_markup=ReplyKeyboardMarkup(VPlanKeyboard))
            WhatToDo[update.message.chat_id] = "MAIN"
        return

    else:
        if not update.message.chat_id in WhatToDo:
            unknown(bot, update)
            return

        elif WhatToDo[update.message.chat_id] == "":
            unknown(bot, update)
            return

        elif WhatToDo[update.message.chat_id] == "LOGIN":
            if update.message.chat.username:
                LogUN= update.message.chat.username
            else:
                LogUN = update.message.chat_id
            LoginText = login(update.message.chat_id, LogUN, Request)
            if LoginText[0] == "0":
                TempKeyboard = RegisterKeyboard
            else:
                TempKeyboard = Keyboard
            bot.sendMessage(chat_id=update.message.chat_id, text=LoginText[1:], parse_mode="HTML", reply_markup=ReplyKeyboardMarkup(TempKeyboard))
            WhatToDo[update.message.chat_id] = "MAIN"
            return

        elif WhatToDo[update.message.chat_id] == "SETCLASS":
            bot.sendMessage(chat_id=update.message.chat_id, text=userconfg("setclass", update.message.chat_id, Request), parse_mode="HTML", reply_markup=ReplyKeyboardMarkup(SettingsKeyboard))
            WhatToDo[update.message.chat_id] = "MAIN"
            return

        elif WhatToDo[update.message.chat_id] == "SETINFO":
            Request = Request.replace('%s ' % Icons1[0], '').replace('%s ' % Icons1[1], '')
            if Request in nameentrylist:
                bot.sendMessage(chat_id=update.message.chat_id, text=userconfg("setinfo", update.message.chat_id, Request), parse_mode="HTML",reply_markup=ReplyKeyboardMarkup(InfoKeyboard))
                return
            else:
                unknown(bot, update)
                return

        elif WhatToDo[update.message.chat_id] == "SETTIMES":
            Request = Request.replace('%s ' % Icons1[0], '').replace('%s ' % Icons1[1], '')
            if Request in ["00", "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23"]:
                bot.sendMessage(chat_id=update.message.chat_id, text=userconfg("settimes", update.message.chat_id, Request), parse_mode="HTML",reply_markup=ReplyKeyboardMarkup(TimesKeyboard))
                return
            else:
                unknown(bot, update)
                return

        elif WhatToDo[update.message.chat_id] == "OTHERCLASSES":
            Request = Request.replace('📕 ', '').replace('📗 ', '').replace('📘 ', '').replace('📙 ', '')
            bot_sendplan(bot, update.message.chat_id, "SELECTED", Request)
            return

        elif WhatToDo[update.message.chat_id] == "PASSWORD_FORGOT":
            while True:
                try:
                    db=MySQLdb.connect(host=DBMYSQLHOST, user=DBMYSQLUSER, passwd=DBMYSQLPASSWD, db=DBMYSQLDB)
                except MySQLdb.Error:
                    os.system("systemctl restart mysql")
                    sleep(5)
                else:
                    break
            curPF = db.cursor()
            if "Ja" in Request:
                curPF.execute("SELECT `Password` FROM `PasswordForgot` WHERE `TelegramID`='%s'" % update.message.chat_id)
                NewPW = curPF.fetchone()
                curPF.execute("UPDATE `TelegramBot` SET `password`='%s' WHERE `ChatID`='%s'" % (NewPW[0], update.message.chat_id))
                curPF.execute("DELETE FROM `PasswordForgot` WHERE `TelegramID`='%s'" % update.message.chat_id)
                WhatToDo[update.message.chat_id] = "MAIN"
                bot.sendMessage(chat_id=update.message.chat_id, text="Okay, dein Passwort wurde geändert.", reply_markup=ReplyKeyboardMarkup(Keyboard))
                db.commit()
                db.close
                return
            else:
                curPF.execute("DELETE FROM `PasswordForgot` WHERE `TelegramID`='%s'" % update.message.chat_id)
                WhatToDo[update.message.chat_id] = "MAIN"
                bot.sendMessage(chat_id=update.message.chat_id, text="Okay, die Aktion wurde abgebrochen.", reply_markup=ReplyKeyboardMarkup(Keyboard))
                db.commit()
                db.close
                return
            return

        else:
            unknown(bot, update)
            return

    return

def bot_start(bot, update):
    bot.send_chat_action(chat_id=update.message.chat_id, action="TYPING")
    print (logprefix() + "%s/%s/%s: '%s'" % (update.message.chat.username, update.message.chat.first_name, update.message.chat_id, update.message.text))
    bot.sendMessage(chat_id=-248828335, text="<strong>%s/%s/%s:</strong>  <i>%s</i>" % (update.message.chat.username, update.message.chat.first_name, update.message.chat_id, update.message.text), parse_mode="HTML")
    if update.message.chat_id < 0:
        bot.sendMessage(chat_id=update.message.chat_id, text="Gruppen sind leider nicht erlaubt.")
        return
    if registercheck(update.message.chat_id) == False:
        bot.sendMessage(chat_id=update.message.chat_id, text="Hallo, benutze die <strong>Tastatur</strong> um den Bot zu bedienen.\n\n<strong>Hilfe:</strong>\nFalls du zum ersten Mal den Bot benutzt und dich auch noch nicht auf unserer Website registriert hast, benutze den Button <strong>📝 Registrieren</strong>.\nWenn du dich bereits hier beim Bot registriert hast, benutze den Button <strong>🔐 Anmelden</strong> und nutze als Passwort deinen Usernamen.\nWenn du keinen Telegram-Usernamen hast, dann spreche ich dich mit deiner Telegram-ID an. Benutze diese Telegram-ID als Passwort.\nAuf unserer Website kannst du dich mit einem eigenen Passwort registrieren oder dein aktuelles Passwort ändern.\n\nBesuche auch unseren alternativen und <strong>schnelleren</strong> Vertretungsplan: http://vplan.zlyfer.de/vplan.php\n\n<i>Du siehst keine Telegram-Tastatur oder du hast andere Fragen? Dann schreibe mir doch einfach eine Nachricht - Ich helfe gerne!</i>\n~@zlyfer", parse_mode="HTML", reply_markup=ReplyKeyboardMarkup(RegisterKeyboard))
    else:
        bot.sendMessage(chat_id=update.message.chat_id, text="Hallo, benutze die <strong>Tastatur</strong> um den Bot zu bedienen.\n\nBesuche auch unseren alternativen und <strong>schnelleren</strong> Vertretungsplan: http://vplan.zlyfer.de\n\n<i>Du siehst keine Telegram-Tastatur oder du hast andere Fragen? Dann schreibe mir doch einfach eine Nachricht - Ich helfe gerne!</i>\n~@zlyfer", parse_mode="HTML", reply_markup=ReplyKeyboardMarkup(UsrKeyboard))
    return

def bot_zeitplan_job(bot, job):
    if strftime("%M") == "00": # NICHT-TESTZWECKE
    # if 1 == 1: # TESTZWECKE
        while True:
            try:
                db=MySQLdb.connect(host=DBMYSQLHOST, user=DBMYSQLUSER, passwd=DBMYSQLPASSWD, db=DBMYSQLDB)
            except MySQLdb.Error:
                os.system("systemctl restart mysql")
                sleep(5)
            else:
                break
        cur1 = db.cursor()
        cur1.execute("SELECT `Zeitplan`, `%s`, `ChatID`, `MeinKurs`, `Username` FROM `TelegramBot` WHERE 1" % strftime("%H")) # , `ZeitplanModus`
        db.close
        for i in cur1.fetchall():
            # if i[2] == 304123618: # TESTZWECKE
            # if i[2] == 175576819: # TESTZWECKE
            if 1 == 1: # NICHT-TESTZWECKE
                if i[0] == 1: # Wenn Zeitplan aktiviert ist.
                    if i[1] == 1: # Wenn aktuelle Stunde eingetragen ist.
                        bot_sendplan(bot, i[2], "ZEITPLAN")
    return

def bot_nocommands(bot, update):
    bot.send_chat_action(chat_id=update.message.chat_id, action="TYPING")
    print (logprefix() + "%s/%s/%s: '%s'" % (update.message.chat.username, update.message.chat.first_name, update.message.chat_id, update.message.text))
    bot.sendMessage(chat_id=-248828335, text="<strong>%s/%s/%s:</strong>  <i>%s</i>" % (update.message.chat.username, update.message.chat.first_name, update.message.chat_id, update.message.text), parse_mode="HTML")
    bot.sendMessage(chat_id=update.message.chat_id, text="Ich werde <strong>nicht mehr</strong> mit Befehlen gesteuert.\nBitte benutze die <strong>Telegram-Tastatur</strong> um mich zu steuern.\nFalls du diese nicht siehst, benutze den <strong>einzigen Befehl</strong> /start um mich erneut zu starten.\n\nDanke!", parse_mode="HTML")
    return

def bot_updateplan_job(bot, job):
    m = strftime("%M")
    if m in ["15","30","45"]:
        #bot.sendMessage(chat_id=-248828335, text="Routine Plan-Update")
        print (logprefix() + "Routine Plan-Update")
        if updateplan() == "FAILED":
            bot.sendMessage(chat_id=-248828335, text="Routine Plan-Update fehlgeschlagen")
            print (logprefix() + "Routine Plan-Update fehlgeschlagen")
    return

def bot_forgot_password(bot, job):
    while True:
        try:
            db=MySQLdb.connect(host=DBMYSQLHOST, user=DBMYSQLUSER, passwd=DBMYSQLPASSWD, db=DBMYSQLDB)
        except MySQLdb.Error:
            os.system("systemctl restart mysql")
            sleep(5)
        else:
            break
    cur = db.cursor()
    cur.execute("SELECT `TelegramID` FROM `PasswordForgot` WHERE 1")
    for i in cur.fetchall():
        bot.sendMessage(chat_id=-248828335, text="<strong>Password Reset Request: </strong><i>%s</i>" % (i[0]), parse_mode="HTML")
        WhatToDo[i[0]] = "PASSWORD_FORGOT"
        bot.sendMessage(chat_id=i[0], parse_mod="HTML", text="Hast du angefordert, dein Passwort zu ändern?", reply_markup=ReplyKeyboardMarkup(PasswordForgotKeyboard))
    return

def bot_holidays(bot, update):
    bot.sendMessage(chat_id=-248828335, text="<strong>%s/%s/%s:</strong>  <i>%s</i>" % (update.message.chat.username, update.message.chat.first_name, update.message.chat_id, update.message.text), parse_mode="HTML")
    bot.sendMessage(chat_id=update.message.chat_id, text="Es sind <strong>Ferien</strong>, geh raus an die frische Luft!\nBei wichtigen Fragen: @zlyfer", parse_mode="HTML")
    return

def bot_outoforder(bot, update):
    bot.sendMessage(chat_id=-248828335, text="<strong>%s/%s/%s:</strong>  <i>%s</i>" % (update.message.chat.username, update.message.chat.first_name, update.message.chat_id, update.message.text), parse_mode="HTML")
    bot.sendMessage(chat_id=update.message.chat_id, text="<strong>Der Bot ist momentan gestoppt.</strong>\n\nEs liegen <strong>Fehler</strong> vor, die behoben werden müssen und ich kümmere mich so <strong>schnell wie möglich</strong> darum.\nIch bitte um Verständnis, danke!\n\nBei wichtigen Fragen: @zlyfer", parse_mode="HTML")
    return

#bot init
if holidays == True:
    updater.dispatcher.add_handler(MessageHandler(Filters.text, bot_holidays))
    updater.dispatcher.add_handler(MessageHandler(Filters.command, bot_holidays))
elif outoforder == True:
    updater.dispatcher.add_handler(MessageHandler(Filters.text, bot_outoforder))
    updater.dispatcher.add_handler(MessageHandler(Filters.command, bot_outoforder))
else:
    updater.dispatcher.add_handler(MessageHandler(Filters.text, bot_mainhandler))
    updater.dispatcher.add_handler(CommandHandler('start', bot_start))
    updater.dispatcher.add_handler(MessageHandler(Filters.command, bot_nocommands))
    updater.job_queue.put(Job(bot_zeitplan_job, 60.0), next_t=0.0)
    updater.job_queue.put(Job(bot_updateplan_job, 60.0), next_t=0.0)
    updater.job_queue.put(Job(bot_forgot_password, 60.0), next_t=0.0)

#bot start
print (logprefix() + "Bot gestartet")
updater.start_polling()
updater.idle()
