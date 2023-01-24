from flask import Flask, render_template, request, make_response, redirect, session, jsonify
from mysql import connector
import requests
import click
from datetime import timedelta
from flask_session import Session
import json


db = connector.connect(
    host="localhost",
    user="root",
    password="mjm",
    database="lite",
    port=3309
)


app = Flask(__name__)
app.config['SESSION_PERMANENT'] = True
app.config["SESSION_TYPE"] = "filesystem"
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

Session(app)


@app.route("/")
def floors():
    # session['transaction-01'] = {
    #     '10': 1,
    #     '101': 2
    # }
    # table = 10

    # t =  session['transaction-01']
    # return str(t['10'])

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
            # inuse = False
            # if table['ordercount'] > 0:
            #     inuse = True
            # if session.get("Transactions"+table['clientname']):
            #     inuse = True
            

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

        key = "Transactions" + table['clientname']
        if session.get(key):
            printable = True
            transactions = json.loads(str(session.get(key)))
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
        print(dict(session))
        key = 'Transactions' + table

        qty = request.form.get('qty')
        if request.form.get('barcode'):
            barcode = request.form.get('barcode')

            transactions = json.loads(str(session.get(key, {})))

            if barcode in transactions:
                if qty is None:
                    transactions[barcode] = transactions[barcode] + 1
                elif float(qty) > 0:
                    transactions[barcode] = float(qty)
                else:
                    del transactions[barcode]
            else:
                transactions[barcode] = 1

            print(transactions)
            session[key] = json.dumps(transactions)

    return redirect(request.referrer)
 

@app.route("/accept1", methods=['POST'])
def accept1():
    if request.form.get('id'):
        getTransaction = db.cursor(prepared=True, dictionary=True)
        getTransaction.execute("SELECT * FROM salestran WHERE line=%s", (request.form.get('id'),))
        transaction = getTransaction.fetchone()
        if transaction and request.form.get('qty'):
            updateTransaction = db.cursor(prepared=True)
            updateTransaction.execute("UPDATE salestran set isqty=%s WHERE line=%s", (request.form.get('qty'), transaction['line']))

    if request.form.get('barcode'):
        getItem = db.cursor(prepared=True, dictionary=True)
        getItem.execute("SELECT * FROM item WHERE barcode=%s", (request.form.get('barcode'),))
        item = getItem.fetchone()
        getTable = db.cursor(prepared=True, dictionary=True)
        getTable.execute("SELECT * FROM `client` WHERE `client`=%s", (request.form.get('table'),))
        table = getTable.fetchone()
        if table is None:
            return make_response("Table not specified", 404)
        
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
            updateTransaction.execute("UPDATE salestran SET isqty=isqty+1 WHERE line=%s", (existingTransation['line'],))
        else:
            insertTransaction = db.cursor(prepared=True)
            insertTransaction.execute("""INSERT INTO salestran(`client`, `clientname`, `barcode`, `itemname`, `isamt`, `isqty`, `uom`, `grp`, `waiter`, `osno`, `screg`, `scsenior`, `ccode`, `source`, `isprint`, dateid)
                                                        VALUES(%s,       %s,           %s,        %s,         %s,      1,       %s,    %s,    %s,       %s,     %s,      %s,         %s,      %s,       0,         CURRENT_DATE()       )""",
                                                            (table['client'], table['clientname'], item['barcode'], item['itemname'], item['amt'], item['uom'], grp, waiter, osno, screg, scsenior, ccode, source))
    return redirect(request.referrer)

@app.route("/transaction/delete", methods=['POST'])
def transaction_delete():
    if request.form.get('id'):
        getTransaction = db.cursor(prepared=True, dictionary=True)
        getTransaction.execute("SELECT * FROM salestran WHERE line=%s", (request.form.get('id'),))
        transaction = getTransaction.fetchone()
        deleteTransaction = db.cursor(prepared=True)
        deleteTransaction.execute("DELETE FROM salestran WHERE line=%s", (transaction['line'],))

        getTableTransactions = db.cursor(prepared=True)
        getTableTransactions.execute("SELECT count(*) FROM salestran WHERE client=%s", (transaction['client'],))
        transactions = getTableTransactions.fetchone()
        if transactions[0] == 0:
            deleteOSNumber = db.cursor(prepared=True)
            deleteOSNumber.execute("DELETE FROM osnumber WHERE tableno=%s", (transaction['client'],))

    return redirect(request.referrer)

@app.route("/accept", methods=['POST'])
def accept():

    import os
    import tempfile
    from fpdf import FPDF

    table = request.form.get('table')
    if table is None:
        return make_response(jsonify({'error': 'No table passed'}), 422)
    
    key = 'Transactions' + table
    printables = {}
    transactions = json.loads(str(session.get(key, {})))
    barcodes = ','.join(list(transactions.keys()))
    getItemFromSession = db.cursor(prepared=True, dictionary=True)
    getItemFromSession.execute("SELECT * FROM item where barcode in({b})".format(b=barcodes))
    for item in getItemFromSession.fetchall():
        printer = item['model'] if item['model'] else 'default'

        if not printer in printables:
            printables[printer] = []

        printables[printer].append({
            "name": item['itemname'],
            "qty": transactions[item['barcode']],
            "unit": item['uom']
        })

    for printer in printables:
        if os.name == 'nt':
            import win32print
            printer_name = printer
            # printer_name = win32print.GetDefaultPrinter()
            hPrinter = win32print.OpenPrinter(printer_name)

            header = "Order for table #{table}".format(table=table)
            try:
                # Set the print job properties
                job = win32print.StartDocPrinter(hPrinter, 1, (header, None, "RAW"))
                try:
                    win32print.StartPagePrinter(hPrinter)
                    for row in printables[printer]:
                        win32print.WritePrinter(hPrinter, str(row['qty']).rstrip('.0') + unit.lower() +" - "+row['name'])
                    win32print.EndPagePrinter(hPrinter)
                finally:
                    # End the print job
                    win32print.EndDocPrinter(hPrinter)
            finally:
                # Close the printer handle
                win32print.ClosePrinter(hPrinter)

    
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