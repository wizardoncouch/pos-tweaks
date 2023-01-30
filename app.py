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

    # products = []
    # subProducts = []
    # if args.get('category'):
    #     getGroups = db.cursor(dictionary=True, prepared=True)
    #     getGroups.execute("SELECT DISTINCT(groupid) as itemname, class, '' as barcode FROM `item` WHERE `class`=%s AND `groupid` > ''", (args.get('category'),))
    #     groups = getGroups.fetchall()
    #     if groups:
    #         products = groups
    #         if args.get('group'):
    #             getProductsByGroup = db.cursor(dictionary=True, prepared=True)
    #             getProductsByGroup.execute("SELECT * FROM item WHERE `class`=%s AND `groupid`=%s ORDER by itemname ASC", (args.get('category'), args.get('group')))
    #             subProducts = getProductsByGroup.fetchall()

    #         #for not grouped products
    #         getProducts = db.cursor(dictionary=True, prepared=True)
    #         getProducts.execute("SELECT * FROM item WHERE `class`=%s and groupid='' ORDER by itemname ASC", (args.get('category'),))
    #         for p in getProducts.fetchall():
    #             products.append(p)
    #     else:
    #         getProducts = db.cursor(dictionary=True, prepared=True)
    #         getProducts.execute("SELECT * FROM item WHERE `class`=%s ORDER by itemname ASC", (args.get('category'),))
    #         products = getProducts.fetchall()
    
    # if args.get('search'):
    #     getSearchProducts = db.cursor(dictionary=True, prepared=True)
    #     stext = '%'+args.get('search')+'%'
    #     getSearchProducts.execute("SELECT * FROM item WHERE `itemname` LIKE %s",(stext,))
    #     products = getSearchProducts.fetchall()

    getTable = db.cursor(dictionary=True, prepared=True)
    getTable.execute("SELECT * FROM client WHERE clientid=%s", (id,))
    table = getTable.fetchone()

    if table:
        getOrders = db.cursor(dictionary=True, prepared=True)
        getOrders.execute("SELECT * FROM salestran where client=%s ORDER by encoded ASC", (table['client'],))
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
                "remarks": order['remarks'],
                "printed": order['isprint']
            })
            total += amount

        # key = table['clientname']
        # sessionOrders = {}
        # if os.path.isfile('orders.json'):
        #     p = open('orders.json')
        #     sessionOrders = dict(json.load(p))
        #     p.close()
        # if key in sessionOrders:
        #     printable = True
        #     transactions = sessionOrders[key] if key in sessionOrders else {}
        #     if transactions.keys():
        #         barcodes = ','.join(list(transactions.keys()))
        #         getItemFromSession = db.cursor(prepared=True, dictionary=True)
        #         getItemFromSession.execute("SELECT * FROM item where barcode in({b})".format(b=barcodes))
        #         for item in getItemFromSession.fetchall():
        #             amount = float(item['amt']) * float(transactions[item['barcode']])
        #             orders.append({
        #                 "id": 0,
        #                 "barcode": item['barcode'],
        #                 "name": item['itemname'],
        #                 "qty": transactions[item['barcode']],
        #                 "amount": amount,
        #                 "printed": 0
        #             })
        #             total += amount

        return render_template('order1.html', data={
            "categories": categories,
            # "products": products,
            # "subProducts": subProducts,
            "table":table, 
            "orders": orders, 
            "total": total, 
            "printable": printable
        })
    else:
        return make_response("Table not found", 404)

@app.route("/orders", methods=['GET'])
def orders():
    args = request.args

    orders = []
    total = 0

    print(args.get('client'))

    if args.get('client'):
        getOrders = db.cursor(dictionary=True, prepared=True)
        getOrders.execute("SELECT * FROM salestran where client=%s ORDER by encoded ASC", (args.get('client'),))

        for order in getOrders.fetchall():
            amount = float(order['isamt']) * float(order['isqty'])
            orders.append({
                "id": order['line'],
                "barcode": order['barcode'],
                "name": order['itemname'],
                "qty": order['isqty'],
                "amount": amount,
                "remarks": order['remarks'],
                "printed": order['isprint']
            })
            total += amount

    return make_response({
        "orders": orders,
        "total": total
    })


@app.route("/products", methods=['GET'])
def products():
    args = request.args

    products = []
    subProducts = []

    print(args.get('category'))

    if args.get('category'):
        getGroups = db.cursor(dictionary=True, prepared=True)
        getGroups.execute("SELECT DISTINCT(groupid) as itemname, class, '' as barcode FROM `item` WHERE `class`=%s AND `groupid` > '' AND `isinactive` = 0", (args.get('category'),))
        groups = getGroups.fetchall()
        if groups:
            products = groups
            if args.get('group'):
                getProductsByGroup = db.cursor(dictionary=True, prepared=True)
                getProductsByGroup.execute("""
                    SELECT i.*, count(*) as orderCount 
                    FROM item as i 
                    LEFT JOIN `salestran` as st ON i.barcode = st.barcode 
                    WHERE i.class=%s AND i.groupid=%s AND i.isinactive = 0
                    GROUP BY i.barcode 
                    ORDER BY orderCount DESC""", (args.get('category'), args.get('group')))
                subProducts = getProductsByGroup.fetchall()

            #for not grouped products
            getProducts = db.cursor(dictionary=True, prepared=True)
            getProducts.execute("""
                SELECT i.*, count(*) as orderCount 
                FROM item as i 
                LEFT JOIN `salestran` as st ON i.barcode = st.barcode 
                WHERE i.class=%s and i.groupid='' AND i.isinactive = 0 
                GROUP BY i.barcode 
                ORDER BY orderCount DESC""", (args.get('category'),))
            for p in getProducts.fetchall():
                products.append(p)
        else:
            getProducts = db.cursor(dictionary=True, prepared=True)
            getProducts.execute("""
                SELECT i.*, count(*) as orderCount 
                FROM item as i 
                LEFT JOIN `salestran` as st ON i.barcode = st.barcode 
                WHERE i.class=%s AND i.isinactive = 0 
                GROUP BY i.barcode 
                ORDER BY orderCount DESC""", (args.get('category'),))
            products = getProducts.fetchall()
    
    if args.get('search'):
        getSearchProducts = db.cursor(dictionary=True, prepared=True)
        stext = '%'+args.get('search')+'%'
        getSearchProducts.execute("""
            SELECT i.*, count(*) as orderCount 
            FROM item as i 
            LEFT JOIN `salestran` as st ON i.barcode = st.barcode 
            WHERE i.itemname LIKE %s AND i.isinactive = 0 
            GROUP BY i.barcode 
            ORDER BY orderCount DESC""",(stext,))
        products = getSearchProducts.fetchall()

    return make_response({
        "products": products,
        "subProducts": subProducts
    })

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

@app.route("/remarks", methods=['POST'])
def getRemarks():
    getTable = db.cursor(prepared=True, dictionary=True)
    getTable.execute("SELECT * FROM `item` WHERE `barcode`=%s", (request.form.get('barcode'),))
    item = getTable.fetchone()
    
    getRemarksTable = db.cursor(prepared=True, dictionary=True)
    getRemarksTable.execute("""SELECT st.remarks, count(*) as count
        FROM `item` as i
        LEFT JOIN `salestran` as st ON i.barcode = st.barcode
        WHERE `class`=%s AND st.remarks > ''
        GROUP BY st.remarks
        ORDER BY count desc""", (item['class'],))
    remarks = getRemarksTable.fetchall()

    return make_response(remarks)

@app.route("/accept", methods=['POST'])
def accept():
    form = request.get_json()

    table = form.get('table_name')
    order_items = form.get('order_items')

    barcodes = []
    for item in order_items:
        barcodes.append(item['barcode'])

    getTable = db.cursor(prepared=True, dictionary=True)
    getTable.execute("SELECT * FROM `client` WHERE `clientname`=%s", (table,))
    table = getTable.fetchone()
    if table is None:
        return make_response(jsonify({'error': 'No table passed'}), 422)
    
    key = table['clientname']
    printables = {}
    # sessionOrders = {}
    # if os.path.isfile('orders.json'):
    #     p = open('orders.json')
    #     sessionOrders = dict(json.load(p))
    #     p.close()

    # transactions = sessionOrders[key] if key in sessionOrders else {}

    # barcodes = ','.join(list(transactions.keys()))
    barcodes = ','.join(list(barcodes))
    getItemFromSession = db.cursor(prepared=True, dictionary=True)
    getItemFromSession.execute("SELECT * FROM item where barcode in({b})".format(b=barcodes))

    p = open('printers.json')
    printers = dict(json.load(p))
    p.close()

    for item in getItemFromSession.fetchall():
        prntr = item['model'] if item['model'] and printers[item['model']] else printers['default']
        if not prntr in printables:
            printables[prntr] = []

        filtered_order_items = list(filter(lambda x: x['barcode'] == item['barcode'], order_items))
        order_item_qty = filtered_order_items[0]['qty'];
        order_item_remarks = filtered_order_items[0]['remarks'];

        printables[prntr].append({
            "name": item['itemname'] + ("\n!!! "+order_item_remarks+" !!!" if order_item_remarks else ""),
            "qty": order_item_qty,
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

        # checkTransaction = db.cursor(prepared=True, dictionary=True)
        # # checkTransaction.execute("SELECT * FROM salestran WHERE client=%s and barcode=%s", (table['client'], item['barcode']))
        # checkTransaction.execute("SELECT * FROM salestran WHERE client=%s and barcode=%s and remarks=%s", (table['client'], item['barcode'], order_item_remarks))
        # existingTransation = checkTransaction.fetchone()
        # if existingTransation:
        #     updateTransaction = db.cursor(prepared=True)
        #     salesQty = existingTransation['isqty'] + order_item_qty
        #     updateTransaction.execute("UPDATE salestran SET isqty=%s, remarks=%s WHERE line=%s", (salesQty, order_item_remarks, existingTransation['line']))
        # else:
        insertTransaction = db.cursor(prepared=True)
        insertTransaction.execute("""
            INSERT INTO salestran(`client`, `clientname`, `barcode`, `itemname`, `isamt`, `isqty`, `uom`, `grp`, `waiter`, `osno`, `screg`, `scsenior`, `ccode`, `source`, `remarks`, `isprint`, dateid)
            VALUES(%s,       %s,           %s,        %s,         %s,      %s,       %s,    %s,    %s,       %s,     %s,      %s,         %s,      %s,       %s,        1,         CURRENT_DATE()       )""",
            (table['client'], table['clientname'], item['barcode'], item['itemname'], item['amt'], order_item_qty, item['uom'], grp, waiter, osno, screg, scsenior, ccode, source, order_item_remarks))

    from escpos import printer
    for prntr in printables:
        printerIP =  printers[prntr]

        p = printer.Network(printerIP)
        date = datetime.now()
        p.set(font='A')
        p.text("----------------------------------------")
        p.text("\n\nOrder date: {d}".format(d=date.strftime("%b %d, %Y %H:%M:%S")))
        p.text("\n\nTable: {table}\n\n".format(table=table['clientname']))

        for row in printables[prntr]:
            print(row['name'])
            p.text("\n"+str(row['qty']).rstrip('.0') + " - " + row['name'] + "\n")
        p.text("\n----------------------------------------\n\n\n")
        p.cut() 

    # del sessionOrders[key]

    # with open("orders.json", "w") as outfile:
    #     json.dump(sessionOrders, outfile) 
    
    return make_response(jsonify({'success': 'Orders Printed'}))

@app.route("/voidItem", methods=['POST'])
def voidItem():
    form = request.get_json()

    client = form.get('client')
    line = form.get('line')

    if client is None:
        return make_response(jsonify({'error': 'No client passed'}), 422)
    if line is None:
        return make_response(jsonify({'error': 'No line passed'}), 422)

    p = open('printers.json')
    printers = dict(json.load(p))
    p.close()

    getItem = db.cursor(dictionary=True, prepared=True)
    getItem.execute("""
        SELECT i.model, st.itemname as itemname, st.isqty as qty, st.line, st.client, st.clientname, st.barcode FROM `salestran` as st
        LEFT JOIN `item` as i ON st.barcode = i.barcode
        WHERE st.client = %s and st.line = %s""", (client, line,))
    item = getItem.fetchone()
    
    if item is None:
        return make_response(jsonify({'error': "Item can't be found"}), 422)

    from escpos import printer
    printerIP =  printers[item['model']]

    p = printer.Network(printerIP)
    date = datetime.now()
    p.set(font='A')
    p.text("----------------------------------------")
    p.text("\n\nVoid Slip")
    p.text("\n\nOrder date: {d}".format(d=date.strftime("%b %d, %Y %H:%M:%S")))
    p.text("\n\nTable: {table}\n\n".format(table=item['clientname']))

    p.text("\n"+str(item['qty']).rstrip('.0') + " - " + item['itemname'] + " !!! void void void !!! " + "\n")

    p.text("\n----------------------------------------\n\n\n")
    p.cut()

    deleteItem = db.cursor(dictionary=True, prepared=True)
    deleteItem.execute("""
        DELETE FROM `salestran`
        WHERE `client` = %s and `line` = %s""", (client, line,))

    return make_response(jsonify({'success': 'Item Cancelled'}))

@app.cli.command()
@click.option('--b')
def scheduled(b):
    products = requests.get('https://pp.d3.net/api.php?action=products&branch=' + b)
    productInactive = db.cursor()
    productInactive.execute("UPDATE `item` set `isinactive`=1 WHERE `barcode` != ''")
    
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