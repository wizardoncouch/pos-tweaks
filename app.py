from flask import Flask, render_template, request, make_response, redirect, session, jsonify
from mysql import connector
import requests
import click
from datetime import timedelta, datetime
import json
import os


db = connector.connect(
    host="localhost",
    user="root",
    password="mjm",
    database="lite",
    port=3309
)


app = Flask(__name__)

@app.route('/config', methods=["POST", "GET"])
def config():

    if request.method == "POST":
        with open("printers.json", "w") as outfile:
            json.dump(request.form, outfile)

    printers = {}
    if os.path.isfile('printers.json'):
        p = open('printers.json')
        printers = dict(json.load(p))
        p.close()

    getPrinters = db.cursor(dictionary=True)
    getPrinters.execute("SELECT distinct(model) as printer from item where model > ''")

    default = printers['default'] if "default" in printers else None
    options = []
    for row in getPrinters.fetchall():
        if default is None:
            default = row['printer']
        options.append(row['printer'])

        if row['printer'] not in printers:
            printers[row['printer']] = ""
    
    if 'default' in printers:
        del printers['default']


    return render_template('config.html', data = {"printers":printers, "options": options, "default": default})

@app.route('/testing')
def testing():
    date = datetime.now()
    return date.strftime("%b %d, %Y")
    import socket
    printer_name = "EPSON L5190 Series" # replace with the name of your printer
    try:
        printer_ip = socket.gethostbyname(printer_name)
        return "Printer IP:", printer_ip
    except:
        return "Could not find IP address for printer:", printer_name
    

@app.route("/")
def floors():

    args = request.args
    data = {
        "floor": None,
        "floors": [],
        "tables": []
    }

    getFloors = db.cursor(dictionary=True)
    getFloors.execute("SELECT DISTINCT(flr) as floor FROM client WHERE isconsignee=1")
    for row in getFloors.fetchall():
        data['floors'].append({
            "name": row['floor']
        })
    floor = args.get('floor')
    if floor is None and data['floors']:
        floor = data['floors'][0]['name']
    
    if floor:
        data['floor'] = floor
        getTables = db.cursor(dictionary=True, prepared=True) 
        getTables.execute("""SELECT `clientname`, `client`, `clientid`, `locx`, `locy`, (SELECT count(*) from salestran WHERE client=client.client) as `ordercount` FROM `client` WHERE flr=%s""", (floor,))
        for table in getTables.fetchall():
            data['tables'].append({
                "id": table['clientid'],
                "name": table['clientname'],
                "left": table['locx'],
                "top": table['locy'],
                "inuse": True if table['ordercount'] > 0 or session.get("Transactions"+table['clientname']) else False
            })

    return render_template('tables.html', data = data)

@app.route("/table/<id>")
def tables(id):
    args = request.args
    getCategories = db.cursor(dictionary=True)
    getCategories.execute("SELECT id, class as name FROM tblmenulist where isinactive=0 and iscategory=1 order by class asc")
    categories = getCategories.fetchall()

    products = []
    subProducts = []
    if args.get('category'):
        getGroups = db.cursor(dictionary=True, prepared=True)
        getGroups.execute("SELECT DISTINCT(groupid) as itemname, class, '' as barcode FROM `item` WHERE `class`=%s AND `groupid` > ''", (args.get('category'),))
        groups = getGroups.fetchall()
        if groups:
            products = groups
            if args.get('group'):
                getProductsByGroup = db.cursor(dictionary=True, prepared=True)
                getProductsByGroup.execute("SELECT * FROM item WHERE `class`=%s AND `groupid`=%s ORDER by itemname ASC", (args.get('category'), args.get('group')))
                subProducts = getProductsByGroup.fetchall()

            #for not grouped products
            getProducts = db.cursor(dictionary=True, prepared=True)
            getProducts.execute("SELECT * FROM item WHERE `class`=%s and groupid='' ORDER by itemname ASC", (args.get('category'),))
            for p in getProducts.fetchall():
                products.append(p)
        else:
            getProducts = db.cursor(dictionary=True, prepared=True)
            getProducts.execute("SELECT * FROM item WHERE `class`=%s ORDER by itemname ASC", (args.get('category'),))
            products = getProducts.fetchall()

    getTable = db.cursor(dictionary=True, prepared=True)
    getTable.execute("SELECT * FROM client WHERE clientid=%s", (id,))
    table = getTable.fetchone()

    if table:
        getOrders = db.cursor(dictionary=True, prepared=True)
        getOrders.execute("SELECT * FROM salestran where client=%s", (table['client'],))
        orders = []
        total = 0
        printable = False
        for order in getOrders.fetchall():
            amount = float(order['isamt']) * float(order['isqty'])
            orders.append({
                "id": order['line'],
                "barcode": order['barcode'],
                "name": order['itemname'],
                "qty": order['isqty'],
                "amount": amount,
                "printed": order['isprint']
            })
            total += amount

        key = table['clientname']
        sessionOrders = {}
        if os.path.isfile('orders.json'):
            p = open('orders.json')
            sessionOrders = dict(json.load(p))
            p.close()
        if key in sessionOrders:
            printable = True
            transactions = sessionOrders[key] if key in sessionOrders else {}
            barcodes = ','.join(list(transactions.keys()))
            getItemFromSession = db.cursor(prepared=True, dictionary=True)
            getItemFromSession.execute("SELECT * FROM item where barcode in({b})".format(b=barcodes))
            for item in getItemFromSession.fetchall():
                amount = float(item['amt']) * float(transactions[item['barcode']])
                orders.append({
                    "id": 0,
                    "barcode": item['barcode'],
                    "name": item['itemname'],
                    "qty": transactions[item['barcode']],
                    "amount": amount,
                    "printed": 0
                })
                total += amount

        return render_template('order.html', data={
            "categories": categories,
            "products": products,
            "subProducts": subProducts,
            "table":table, 
            "orders": orders, 
            "total": total, 
            "printable": printable
        })
    else:
        return make_response("Table not found", 404)

@app.route("/transaction", methods=['POST'])
def transaction():
    if request.form.get('table'):
        table = request.form.get('table')
        qty = request.form.get('qty')
        if request.form.get('barcode'):
            barcode = request.form.get('barcode')
            
            key = table
            sessionOrders = {}
            if os.path.isfile('orders.json'):
                p = open('orders.json')
                sessionOrders = dict(json.load(p))
                p.close()
                
            transactions = sessionOrders[key] if key in sessionOrders else {}

            if barcode in transactions:
                if qty is None:
                    transactions[barcode] = transactions[barcode] + 1
                elif float(qty) > 0:
                    transactions[barcode] = float(qty)
                else:
                    del transactions[barcode]
            else:
                transactions[barcode] = 1

            sessionOrders[key] = transactions

            with open("orders.json", "w") as outfile:
                json.dump(sessionOrders, outfile) 

    return redirect(request.referrer)


@app.route("/accept", methods=['POST'])
def accept():

    getTable = db.cursor(prepared=True, dictionary=True)
    getTable.execute("SELECT * FROM `client` WHERE `clientname`=%s", (request.form.get('table', ''),))
    table = getTable.fetchone()
    if table is None:
        return make_response(jsonify({'error': 'No table passed'}), 422)
    
    key = table['clientname']
    printables = {}
    sessionOrders = {}
    if os.path.isfile('orders.json'):
        p = open('orders.json')
        sessionOrders = dict(json.load(p))
        p.close()

    transactions = sessionOrders[key] if key in sessionOrders else {}

    barcodes = ','.join(list(transactions.keys()))
    getItemFromSession = db.cursor(prepared=True, dictionary=True)
    getItemFromSession.execute("SELECT * FROM item where barcode in({b})".format(b=barcodes))

    p = open('printers.json')
    printers = dict(json.load(p))
    p.close()

    for item in getItemFromSession.fetchall():
        prntr = item['model'] if item['model'] and printers[item['model']] else printers['default']
        if not prntr in printables:
            printables[prntr] = []

        printables[prntr].append({
            "name": item['itemname'],
            "qty": transactions[item['barcode']],
            "unit": item['uom']
        })

        getTransaction = db.cursor(prepared=True, dictionary=True)
        getTransaction.execute("SELECT * FROM salestran WHERE `client`=%s LIMIT 1", (table['client'],))
        transaction = getTransaction.fetchone()
        if transaction:
            osno = transaction['osno']
            ccode = transaction['ccode']
            screg = transaction['screg']
            scsenior = transaction['scsenior']
            grp = transaction['grp']
            waiter = transaction['waiter']
            source = transaction['source']
        else:
            getOS = db.cursor(prepared=True)
            getOS.execute("INSERT INTO osnumber(tableno) VALUES(%s)", (table['client'],))
            osno = getOS.lastrowid
            ccode = 'WALK-IN'
            screg = 10
            scsenior = 10
            grp = 'A'
            waiter = 'Administrator'
            source = 'WH00001'

        checkTransaction = db.cursor(prepared=True, dictionary=True)
        checkTransaction.execute("SELECT * FROM salestran WHERE client=%s and barcode=%s", (table['client'], item['barcode']))
        existingTransation = checkTransaction.fetchone()
        if existingTransation:
            updateTransaction = db.cursor(prepared=True)
            salesQty = existingTransation['isqty'] + transactions[item['barcode']] 
            updateTransaction.execute("UPDATE salestran SET isqty=%s WHERE line=%s", (salesQty, existingTransation['line']))
        else:
            insertTransaction = db.cursor(prepared=True)
            insertTransaction.execute("""INSERT INTO salestran(`client`, `clientname`, `barcode`, `itemname`, `isamt`, `isqty`, `uom`, `grp`, `waiter`, `osno`, `screg`, `scsenior`, `ccode`, `source`, `isprint`, dateid)
                                                        VALUES(%s,       %s,           %s,        %s,         %s,      1,       %s,    %s,    %s,       %s,     %s,      %s,         %s,      %s,       1,         CURRENT_DATE()       )""",
                                                            (table['client'], table['clientname'], item['barcode'], item['itemname'], item['amt'], item['uom'], grp, waiter, osno, screg, scsenior, ccode, source))

    from escpos import printer
    for prntr in printables:
        printerIP =  printers[prntr]
        p = printer.Network(printerIP)
        date = datetime.now()
        p.set(text_type='B')
        p.text("\n\nOrder date: {d}".format(d=date.strftime("%b %d, %Y")))
        p.text("\n\nOrder for table: {table}\n\n".format(table=table['clientname']))

        for row in printables[prntr]:
            print(row['name'])
            p.text("\n"+str(row['qty']).rstrip('.0') + " - " + row['name'] + "\n")

        p.text("\n\n------\n\n")
        p.cut() 

    del sessionOrders[key]

    with open("orders.json", "w") as outfile:
        json.dump(sessionOrders, outfile) 
    
    return make_response(jsonify({'success': 'Orders Printed'}))


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
                print("{name} group updated to {group}...".format(name=product['name'], group=product['group']))
    
    #set the category to inactive if there are no active item found
    updateCategories = db.cursor()
    updateCategories.execute("UPDATE tblmenulist set isinactive=1 WHERE (SELECT count(*) FROM item WHERE iscategory=1 and `class`=tblmenulist.class and isinactive=0) = 0")