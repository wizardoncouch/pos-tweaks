from flask import Flask, render_template, request, make_response, redirect, session
from mysql import connector
from flask_session import Session
import requests
import click

db = connector.connect(
    host="localhost",
    user="root",
    password="mjm",
    database="lite",
    port=3309
)

cursor = db.cursor(dictionary=True, prepared=True)

app = Flask(__name__)
app.config['SECRET_KEY'] = "Oh_so_secret"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

@app.route("/")
def floors():
    args = request.args
    data = {
        "floor": None,
        "floors": [],
        "tables": []
    }

    cursor.execute("SELECT DISTINCT(flr) as floor FROM client WHERE isconsignee=1")
    for row in cursor.fetchall():
        data['floors'].append({
            "name": row['floor']
        })
    floor = args.get('floor')
    if floor is None and data['floors']:
        floor = data['floors'][0]['name']
    
    if floor:
        data['floor'] = floor
        cursor.execute("""SELECT `clientname`, `client`, `clientid`, `locx`, `locy`, (SELECT count(*) from salestran WHERE client=client.client) as `ordercount` FROM `client` WHERE flr=%s""", (floor,))
        for table in cursor.fetchall():
            data['tables'].append({
                "id": table['clientid'],
                "name": table['clientname'],
                "left": table['locx'],
                "top": table['locy'],
                "inuse": True if table['ordercount'] > 0 else False
            })

    return render_template('tables.html', data = data)

@app.route("/table/<id>")
def tables(id):
    args = request.args
    cursor.execute("SELECT id, class as name FROM tblmenulist where isinactive=0 and iscategory=1 order by class asc")
    categories = cursor.fetchall()

    products = []
    subProducts = []
    if args.get('category'):
        cursor.execute("SELECT DISTINCT(groupid) as itemname, class, '' as barcode FROM `item` WHERE `class`=%s AND `groupid` > ''", (args.get('category'),))
        groups = cursor.fetchall()
        if groups:
            products = groups
            if args.get('group'):
                cursor.execute("SELECT * FROM item WHERE `class`=%s AND `groupid`=%s ORDER by itemname ASC", (args.get('category'), args.get('group')))
                subProducts = cursor.fetchall()

            #for not grouped products
            cursor.execute("SELECT * FROM item WHERE `class`=%s and groupid='' ORDER by itemname ASC", (args.get('category'),))
            for p in cursor.fetchall():
                products.append(p)
        else:
            cursor.execute("SELECT * FROM item WHERE `class`=%s ORDER by itemname ASC", (args.get('category'),))
            products = cursor.fetchall()


    cursor.execute("SELECT * FROM client WHERE clientid=%s", (id,))
    table = cursor.fetchone()
    if table:
        cursor.execute("SELECT * FROM salestran where client=%s", (table['client'],))
        total = 0
        printable = False
        orders = []
        for order in cursor.fetchall():
            orders.append({
                "line": order['line'],
                "name": order['itemname'],
                "barcode": order['barcode'],
                "qty": float(order['isqty']),
                "amount": float(order['isamt']) * float(order['isqty']),
                "isprint": 1
            })
            total += float(order['isamt']) * float(order['isqty'])

        session_key = "transactions-" + table['client']
        if session.get(session_key):
            printable = True
            cursor.execute("SELECT * FROM `item` WHERE barcode in(%s)", (session.get(session_key).keys()))
            for item in cursor.fetchall():
                amount = float(item['amt']) * float(session.get(session_key)[item['barcode']])
                orders.append({
                    "line": 0,
                    "name": item['itemname'],
                    "barcode": item['barcode'],
                    "qty": float(session.get(session_key)[item['barcode']]),
                    "amount": amount, 
                    "isprint": 0
                })
                total += amount

        return render_template('order.html', data={
            "categories": categories,
            "products": products,
            "subProducts": subProducts,
            "table": table, 
            "orders": orders, 
            "total": total, 
            "printable": printable
        })
    else:
        return make_response("Table not found", 404)

@app.route("/transaction", methods=['POST'])
def transaction():
    if request.form.get('table'):
        session_key = "transactions-" + request.form.get('table')
    
    if request.form.get('barcode'):
        barcode = int(request.form.get('barcode'))

        if session.get(session_key)[barcode]:
            session[session_key][barcode] += 1
        else:
            session[session_key][barcode] + 1

    return redirect(request.referrer)

@app.route("/print", methods=['POST'])
def print():
    # import os, sys import win32print
    import tempfile
    import win32api
    import win32print

    printerName = 'Bar Printer'
    filename = tempfile.mktemp (".txt")
    open (filename, "w").write ("This is a test")

    win32api.ShellExecute (0,"print", filename, '/d:"%s"' % printerName, ".", 0 )


    # cursor.execute("SELECT * FROM item WHERE barcode IN(381,382,383)")
    # for item in cursor.fetchall():

    # if request.form.get('id'):
    #     cursor.execute("SELECT * FROM salestran WHERE line=%s", (request.form.get('id'),))
    #     transaction = cursor.fetchone()
    #     if transaction and request.form.get('qty'):
    #         cursor.execute("UPDATE salestran set isqty=%s WHERE line=%s", (request.form.get('qty'), transaction['line']))

    # if request.form.get('barcode'):
    #     cursor.execute("SELECT * FROM item WHERE barcode=%s", (request.form.get('barcode'),))
    #     item = cursor.fetchone()
    #     cursor.execute("SELECT * FROM `client` WHERE `client`=%s", (request.form.get('table'),))
    #     table = cursor.fetchone()
    #     if table is None:
    #         return make_response("Table not specified", 404)
        
    #     cursor.execute("SELECT * FROM salestran WHERE `client`=%s LIMIT 1", (table['client'],))
    #     transaction = cursor.fetchone()
    #     if transaction:
    #         osno = transaction['osno']
    #         ccode = transaction['ccode']
    #         screg = transaction['screg']
    #         scsenior = transaction['scsenior']
    #         grp = transaction['grp']
    #         waiter = transaction['waiter']
    #         source = transaction['source']
    #     else:
    #         cursor.execute("INSERT INTO osnumber(tableno) VALUES(%s)", (table['client'],))
    #         osno = cursor.lastrowid
    #         ccode = 'WALK-IN'
    #         screg = 10
    #         scsenior = 10
    #         grp = 'A'
    #         waiter = 'Administrator'
    #         source = 'WH00001'
    #     cursor.execute("SELECT * FROM salestran WHERE client=%s and barcode=%s", (table['client'], item['barcode']))
    #     existingTransation = cursor.fetchone()
    #     if existingTransation:
    #         cursor.execute("UPDATE salestran SET isqty=isqty+1 WHERE line=%s", (existingTransation['line'],))
    #     else:
    #         cursor.execute("""INSERT INTO salestran(`client`, `clientname`, `barcode`, `itemname`, `isamt`, `isqty`, `uom`, `grp`, `waiter`, `osno`, `screg`, `scsenior`, `ccode`, `source`, `isprint`, dateid)
    #                                                     VALUES(%s,       %s,           %s,        %s,         %s,      1,       %s,    %s,    %s,       %s,     %s,      %s,         %s,      %s,       0,         CURRENT_DATE()       )""",
    #                                                         (table['client'], table['clientname'], item['barcode'], item['itemname'], item['amt'], item['uom'], grp, waiter, osno, screg, scsenior, ccode, source))
    return redirect(request.referrer)

@app.route("/transaction/delete", methods=['POST'])
def transaction_delete():
    if request.form.get('id'):
        cursor.execute("SELECT * FROM salestran WHERE line=%s", (request.form.get('id'),))
        transaction = cursor.fetchone()
        cursor.execute("DELETE FROM salestran WHERE line=%s", (transaction['line'],))

        cursor.execute("SELECT count(*) as cnt FROM salestran WHERE client=%s", (transaction['client'],))
        if cursor['cnt'] == 0:
            cursor.execute("DELETE FROM osnumber WHERE tableno=%s", (transaction['client'],))

    return redirect(request.referrer)

@app.cli.command()
@click.option('--b')
def scheduled(b):
    products = requests.get('https://pp.d3.net/api.php?action=products&branch=' + b)
    productInactive = db.cursor()
    productInactive.execute("UPDATE `item` set `isinactive`=1 AND `barcode` > 0")
    if products:
        for product in products.json():

            checkCategory = db.cursor(prepared=True)
            checkCategory.execute("SELECT count(*) FROM tblmenulist WHERE `class`=%s and iscategory=1", (product['category'],))
            category = checkCategory.fetchone()
            if category[0] == 0:
                insertCategory = db.cursor(prepared=True)
                insertCategory.execute("""INSERT INTO tblmenulist   (`class`,   `iscategory`,   `skincolor`,    `fontcolor`,    `dlock`) 
                                                        VALUES      (%s,      %s,           %s,           %s,           NOW())""",
                                                                    (product['category'], 1, '-8355712','-16777216'))

            checkGroup = db.cursor(prepared=True)
            checkGroup.execute("SELECT count(*) FROM `tblmenugrp` WHERE `grp`=%s", (product['group'],))
            group = checkGroup.fetchone()
            if group[0] == 0:
                inserGroup = db.cursor(prepared=True)
                inserGroup.execute("INSERT INTO `tblmenugrp`(`grp`, `dlock`) VALUES(%s,NOW())",(product['group'],))


            fetchItem = db.cursor(dictionary=True)
            fetchItem.execute("SELECT * FROM `item` WHERE `barcode`='{uid}'".format(uid=product['uid']))
            p = fetchItem.fetchone()
            if p is None:
                getClassPrinter = db.cursor(prepared=True, dictionary=True)
                getClassPrinter.execute("SELECT model FROM item WHERE `class`=%s and `model` > '' LIMIT 1", (product['category'],))
                classPrinter = getClassPrinter.fetchone()
                model = classPrinter['model'] if classPrinter else ''
                
                insert = db.cursor(prepared=True)
                insert.execute("""INSERT INTO `item`(`barcode`, `itemname`, `shortname`, `groupid`, `part`, `class`, `uom`, `dlock`, `amt`,  `taxable`, `model`) 
                                            VALUES  (%s,        %s,         %s,          %s,        'MENU', %s,      %s,    NOW(),   %s,     1,         %s     )""",
                                                    (product['uid'], product['name'], product['name'], product['group'], product['category'], product['unit'], product['price'], model))
                print("{name} is inserted...".format(name=product['name']))
                fetchItem = db.cursor(dictionary=True)
                fetchItem.execute("SELECT * FROM `item` WHERE itemid=last_insert_id()")
                p = fetchItem.fetchone()
            
            updateItem = db.cursor(prepared=True)
            updateItem.execute("UPDATE `item` set `isinactive`=0 WHERE `itemid`=%s",(p['itemid'],))

            if float(product['price']) != float(p['amt']):
                updateItem = db.cursor(prepared=True)
                updateItem.execute("UPDATE `item` set `amt`=%s WHERE `itemid`=%s",(product['price'], p['itemid']))
                print("{name} price is updated...".format(name=product['name']))

            #update if the category is changed
            if p['class'] != product['category']:
                updateItem = db.cursor(prepared=True)
                updateItem.execute("UPDATE `item` set `class`=%s WHERE `itemid`=%s",(product['category'], p['itemid']))
                print("{name} category updated to {category}...".format(name=product['name'], category=product['category']))

            #update if the group is changed
            if p['groupid'] != product['group']:
                updateItem = db.cursor(prepared=True)
                updateItem.execute("UPDATE `item` set `groupid`=%s WHERE `itemid`=%s",(product['group'], p['itemid']))
                print("{name} group updated to {group}...".format(name=product['name'], category=product['group']))
    
    #set the category to inactive if there are no active item found
    updateCategories = db.cursor()
    updateCategories.execute("UPDATE tblmenulist set isinactive=1 WHERE (SELECT count(*) FROM item WHERE iscategory=1 and `class`=tblmenulist.class and isinactive=0) = 0")