from flask import Flask, render_template, request, make_response, redirect, session, jsonify
from mysql import connector
import requests
from datetime import datetime
import json
from os import environ, path


app = Flask(__name__)


app.config['DB_HOST'] = environ.get('DB_HOST', 'localhost')
app.config['DB_USER'] = environ.get('DB_USER', 'root')
app.config['DB_PASSWORD'] = environ.get('DB_PASSWORD', 'mjm')
app.config['DB_NAME'] = environ.get('DB_NAME', 'lite')
app.config['DB_PORT'] = environ.get('DB_PORT', 3309)

app.config['BRANCH_ID'] = environ.get('BRANCH_ID')


db = connector.connect(
    host=app.config.get('DB_HOST'),
    user=app.config.get('DB_USER'),
    password=app.config.get('DB_PASSWORD'),
    database=app.config.get('DB_NAME'),
    port=app.config.get('DB_PORT')
)

dash = "---------------------------------"
def ssql(scode, arrfields):
    scode = scode.lower().strip()
    scode = scode.replace('"', ' ').replace("'", ' ')
    where = ""
    
    if scode:
        arr = scode.split(' ')
        for e in arr:
            not_ = ""
            cond = " OR "
            cond1 = 0
            if e[0] == '-' and len(e) > 1:
                not_ = " NOT "
                e = e[1:]
                cond = " AND "
                cond1 = 1
            where += " AND ( {} ".format(cond1)
            for sfield in arrfields:
                where += "{} {} LIKE '%{}%'".format(cond, sfield, e)
            where += " ) "
    return where

@app.route('/config', methods=["POST", "GET"])
def config():

    if request.method == "POST":
        with open("printers.json", "w") as outfile:
            json.dump(request.form, outfile)

    printers = {}
    if path.isfile('printers.json'):
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
    getCategories.close()

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
        return render_template('order1.html', data={
            "categories": categories,
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
        where = ""
        for s in args.get('search').strip().lower().split(' '):
            where += " AND concat(' ',i.itemname) LIKE '% {s}%'".format(s=s)
        getSearchProducts = db.cursor(dictionary=True)
        # stext = '%'+args.get('search')+'%'
        # where = ssql(args.get('search'), ['i.itemname'])
        print(where)
        getSearchProducts.execute("""
            SELECT i.*, count(*) as orderCount 
            FROM item as i 
            LEFT JOIN `salestran` as st ON i.barcode = st.barcode 
            WHERE i.isinactive = 0 {where} 
            GROUP BY i.barcode 
            ORDER BY orderCount DESC""".format(where=where))
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
            if path.isfile('orders.json'):
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
    insertables = {}
    barcodes = ','.join(list(barcodes))
    getItemFromSession = db.cursor(prepared=True, dictionary=True)
    getItemFromSession.execute("SELECT * FROM item where barcode in({b})".format(b=barcodes))

    p = open('printers.json')
    printers = dict(json.load(p))
    p.close()

    for item in getItemFromSession.fetchall():
        prntr = item['model'] if item['model'] and item['model'] in printers else printers['default']
        if not prntr in printables:
            printables[prntr] = []

        filtered_order_items = list(filter(lambda x: x['barcode'] == item['barcode'], order_items))
        order_item_qty = filtered_order_items[0]['qty']
        order_item_remarks = filtered_order_items[0]['remarks']

        printables[prntr].append({
            "barcode": item['barcode'],
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

        insertables[item['barcode']] = {
            'client': table['client'],
            'clientname': table['clientname'],
            'barcode': item['barcode'],
            'itemname': item['itemname'],
            'amount': item['amt'],
            'qty': order_item_qty,
            'unit': item['uom'],
            'group': grp,
            'waiter': waiter,
            'osno': osno,
            'screg': screg,
            'scsenior': scsenior,
            'ccode': ccode,
            'source': source,
            'remarks': order_item_remarks,
        }

    try:
        from escpos import printer
        for prntr in printables:
            printerIP =  printers[prntr]

            p = printer.Network(printerIP)
            date = datetime.now()
            p.set(font='A')
            p.text(dash)
            p.text("\n\nOrder date: {d}".format(d=date.strftime("%b %d, %Y %H:%M:%S")))
            p.text("\n\nTable: {table}\n\n".format(table=table['clientname']))

            for row in printables[prntr]:
                print(row['name'])
                p.text("\n"+str(row['qty']).rstrip('.0') + " - " + row['name'] + "\n")
                i = insertables[row['barcode']]
                insertTransaction = db.cursor(prepared=True)
                insertTransaction.execute("""
                    INSERT INTO salestran   (`client`, `clientname`, `barcode`, `itemname`, `isamt`, `isqty`, `uom`, `grp`, `waiter`, `osno`, `screg`, `scsenior`, `ccode`, `source`, `remarks`, `isprint`, dateid)
                                VALUES      (%s,       %s,           %s,        %s,         %s,      %s,       %s,    %s,    %s,       %s,     %s,      %s,         %s,      %s,       %s,        1,         CURRENT_DATE()       )""",
                                (i['client'], i['clientname'], i['barcode'], i['itemname'], i['amount'], i['qty'], i['unit'], i['group'], i['waiter'], i['osno'], i['screg'], i['scsenior'], i['ccode'], i['source'], i['remarks']))
            p.text("\n{dash}\n\n\n".format(dash=dash))
            p.cut() 
        return make_response(jsonify({'success': 'Orders Printed'}))
    except:
        return make_response(jsonify({'error': 'Printer error'}))
    

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

    try:
        from escpos import printer
        printerIP =  printers[item['model']]

        p = printer.Network(printerIP)
        date = datetime.now()
        p.set(font='A')
        p.text(dash)
        p.text("\n\nVoid Slip")
        p.text("\n\nOrder date: {d}".format(d=date.strftime("%b %d, %Y %H:%M:%S")))
        p.text("\n\nTable: {table}\n\n".format(table=item['clientname']))

        p.text("\n"+str(item['qty']).rstrip('.0') + " - " + item['itemname'] + " !!! void void void !!! " + "\n")

        p.text("\n{dash}\n\n\n".format(dash=dash))
        p.cut()

        deleteItem = db.cursor(dictionary=True, prepared=True)
        deleteItem.execute("""
            DELETE FROM `salestran`
            WHERE `client` = %s and `line` = %s""", (client, line,))
        return make_response(jsonify({'success': 'Item Cancelled'}))
    except:
        return make_response(jsonify({'error': 'Printing error'}))


@app.cli.command()
# @click.option('--b')
def scheduled():
    b = app.config.get('BRANCH_ID')
    products = requests.get('https://pp.d3.net/api.php?action=products&branch=' + b)
    productInactive = db.cursor()
    productInactive.execute("UPDATE `item` set `isinactive`=1 WHERE `barcode` != ''")
    
    if len(products.json()):
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

    else:
        print('No products found, please check your config file for the branch id')
    
    #set the category to inactive if there are no active item found
    updateCategories = db.cursor()
    updateCategories.execute("UPDATE tblmenulist set isinactive=1 WHERE (SELECT count(*) FROM item WHERE iscategory=1 and `class`=tblmenulist.class and isinactive=0) = 0")


