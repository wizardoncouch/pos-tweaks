import os
from flask import Flask, render_template, request, make_response, redirect, session, jsonify
from mysql import connector
import requests
from datetime import datetime
import json
from dotenv import load_dotenv


app = Flask(__name__)

load_dotenv()

dbhost = os.environ.get('DB_HOST', 'localhost')
dbuser = os.environ.get('DB_USER', 'root')
dbpassword = os.environ.get('DB_PASSWORD', 'mjm')
dbname = os.environ.get('DB_NAME', 'lite')
dbport = os.environ.get('DB_PORT', 3309)

branch_id = os.environ.get('BRANCH_ID')

printersFile = os.path.join(os.path.dirname(__file__), 'printers.json')

db = connector.connect(
    host=dbhost,
    user=dbuser,
    password=dbpassword,
    database=dbname,
    port=dbport
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
        with open(printersFile, "w") as outfile:
            json.dump(request.form, outfile)

    printers = {}
    if os.path.isfile(printersFile):
        p = open(printersFile)
        printers = dict(json.load(p))
        p.close()

    default = printers['default'] if "default" in printers else None
    options = []
    with db.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT distinct(model) as printer from item where model > ''")
        for row in cursor.fetchall():
            if default is None:
                default = row['printer']
            options.append(row['printer'])

            if row['printer'] not in printers:
                printers[row['printer']] = ""
        cursor.close()
    
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

    with db.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT DISTINCT(flr) as floor FROM client WHERE isconsignee=1")
        data['floors'] = [{
            'name': row['floor']
        } for row in cursor.fetchall()]
        cursor.close()

    floor = args.get('floor')
    if floor is None and data['floors']:
        floor = data['floors'][0]['name']
    
    if floor:
        data['floor'] = floor
        with db.cursor(dictionary=True, prepared=True) as cursor:
            cursor.execute("""SELECT `clientname`, `client`, `clientid`, `locx`, `locy`, (SELECT count(*) from salestran WHERE client=client.client) as `ordercount` FROM `client` WHERE flr=%s""", (floor,))
            data['tables'] = [{
                "id": table['clientid'],
                "name": table['clientname'],
                "left": table['locx'],
                "top": table['locy'],
                "inuse": True if table['ordercount'] > 0 else False
            } for table in cursor.fetchall()]
            cursor.close()

    return render_template('tables.html', data = data)

@app.route("/table/<id>")
def tables(id):
    categories = None
    table = None

    with db.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT id, class as name FROM tblmenulist where isinactive=0 and iscategory=1 order by class asc")
        categories = cursor.fetchall()
        cursor.close()

    with db.cursor(dictionary=True, prepared=True) as cursor:
        cursor.execute("SELECT * FROM client WHERE clientid=%s", (id,))
        table = cursor.fetchone()
        cursor.close()

    if table:
        with db.cursor(dictionary=True, prepared=True) as cursor:
            cursor.execute("SELECT * FROM salestran where client=%s ORDER by encoded ASC", (table['client'],))
            orders = []
            total = 0
            printable = False
            for order in cursor.fetchall():
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
            cursor.close()
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

    if args.get('client'):
        with db.cursor(dictionary=True, prepared=True) as cursor:
            cursor.execute("SELECT * FROM salestran where client=%s ORDER by encoded ASC", (args.get('client'),))
            for order in cursor.fetchall():
                amount = float(order['isamt']) * float(order['isqty'])
                orders.append({
                    "id": order['line'],
                    "barcode": order['barcode'],
                    "name": order['itemname'],
                    "qty": order['isqty'],
                    "amount": amount,
                    "remarks": order['remarks'],
                    "printed": order['isprint'],
                    "group": order['grp'],
                    "senior": order['scsenior']
                })
                total += amount
            cursor.close()

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
        with db.cursor(dictionary=True, prepared=True) as cursor:
            cursor.execute("SELECT DISTINCT(groupid) as itemname, class, '' as barcode FROM `item` WHERE `class`=%s AND `groupid` > '' AND `isinactive` = 0", (args.get('category'),))
            groups = cursor.fetchall()
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
            
            cursor.close()
    
    if args.get('search'):
        where = ""
        for s in args.get('search').strip().lower().split(' '):
            where += " AND concat(' ',i.itemname) LIKE '% {s}%'".format(s=s)
        with db.cursor(dictionary=True) as cursor:
            # stext = '%'+args.get('search')+'%'
            # where = ssql(args.get('search'), ['i.itemname'])
            cursor.execute("""
                SELECT i.*, count(*) as orderCount 
                FROM item as i 
                LEFT JOIN `salestran` as st ON i.barcode = st.barcode 
                WHERE i.isinactive = 0 {where} 
                GROUP BY i.barcode 
                ORDER BY orderCount DESC""".format(where=where))
            products = cursor.fetchall()

            cursor.close()

    return make_response({
        "products": products,
        "subProducts": subProducts
    })

@app.route("/remarks", methods=['POST'])
def getRemarks():

    remarks = None
    with db.cursor(prepared=True, dictionary=True) as cursor:
        cursor.execute("SELECT * FROM `item` WHERE `barcode`=%s", (request.form.get('barcode'),))
        item = cursor.fetchone()
        cursor.close()

        with db.cursor(prepared=True, dictionary=True) as cursor:
            cursor.execute("""SELECT st.remarks, count(*) as count
                FROM `item` as i
                LEFT JOIN `salestran` as st ON i.barcode = st.barcode
                WHERE `class`=%s AND st.remarks > ''
                GROUP BY st.remarks
                ORDER BY count desc""", (item['class'],))
            remarks = cursor.fetchall()
            cursor.close()

    return make_response(remarks)

@app.route("/accept", methods=['POST'])
def accept():
    form = request.get_json()

    table = None
    
    with db.cursor(prepared=True, dictionary=True) as cursor:
        cursor.execute("SELECT * FROM `client` WHERE `clientname`=%s", (form.get('table_name'),))
        table = cursor.fetchone()
        if table is None:
            return make_response(jsonify({'error': 'No table passed'}), 422)
        cursor.close()

    p = open(printersFile)
    printers = dict(json.load(p))
    p.close()

    printables = {}
    insertables = {}
    cntr = 1
    for order_item in form.get('order_items'):
        item = None
        with db.cursor(prepared=True, dictionary=True) as cursor:
            cursor.execute("SELECT * FROM item where barcode=%s",(order_item['barcode'],))
            item = cursor.fetchone()
            cursor.close()
        if item is None:
            continue

        prntr = item['model'] if item['model'] and item['model'] in printers else printers['default']


        if not prntr in printables:
            printables[prntr] = []
        
        if item['printer2'] and not item['printer2'] in printables:
            printables[item['printer2']] = []

        if item['printer3'] and not item['printer3'] in printables:
            printables[item['printer3']] = []

        if item['printer4'] and not item['printer4'] in printables:
            printables[item['printer4']] = []

        if item['printer5'] and not item['printer5'] in printables:
            printables[item['printer5']] = []

        order_item_qty = order_item['qty']
        order_item_remarks = order_item['remarks']

        printables[prntr].append({
            "cntr": cntr,
            "barcode": item['barcode'],
            "name": item['itemname'] + ("\n!!! "+order_item_remarks+" !!!" if order_item_remarks else ""),
            "qty": order_item_qty,
            "unit": item['uom']
        })
        extobj = {
            "barcode": item['barcode'],
            "name": item['itemname'] + ("\n!!! "+order_item_remarks+" !!!" if order_item_remarks else ""),
            "qty": order_item_qty,
            "unit": item['uom']
        }
        if item['printer2'] > '':
            printables[item['printer2']].append(extobj)
        if item['printer3'] > '':
            printables[item['printer3']].append(extobj)
        if item['printer4'] > '':
            printables[item['printer4']].append(extobj)
        if item['printer5'] > '':
            printables[item['printer5']].append(extobj)

        transaction = None
        with db.cursor(prepared=True, dictionary=True) as cursor:
            cursor.execute("SELECT * FROM salestran WHERE `client`=%s LIMIT 1", (table['client'],))
            transaction = cursor.fetchone()
            cursor.close()
        if transaction:
            osno = transaction['osno']
            ccode = transaction['ccode']
            screg = transaction['screg']
            scsenior = transaction['scsenior']
            grp = transaction['grp']
            waiter = transaction['waiter']
            source = transaction['source']
        else:
            osno = None
            with db.cursor(prepared=True) as cursor:
                cursor.execute("INSERT INTO osnumber(tableno) VALUES(%s)", (table['client'],))
                osno = cursor.lastrowid
                cursor.close()
            ccode = 'WALK-IN'
            screg = 10
            scsenior = 10
            grp = 'A'
            waiter = 'Administrator'
            source = 'WH00001'

        if osno > 0:
            insertables[cntr] = {
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

        cntr += 1

    try:
        from escpos import printer
        for prntr in printables:
            printerIP =  printers[prntr]
            if printerIP:
                p = printer.Network(printerIP)
                date = datetime.now()
                p.set(font='A')
                p.text(dash)
                p.text("\n\nOrder date: {d}".format(d=date.strftime("%b %d, %Y %H:%M:%S")))
                p.text("\n\nTable: {table}\n\n".format(table=table['clientname']))

                for row in printables[prntr]:
                    p.text("\n")
                    p.block_text(txt=str(row['qty']).rstrip('.0') + " - " + row['name'], columns=40)
                    p.text("\n")
                    if 'cntr' in row and row['cntr'] > 0:
                        i = insertables[row['cntr']]
                        if i:
                            with db.cursor(prepared=True) as cursor:
                                cursor.execute("""
                                    INSERT INTO salestran   (`client`, `clientname`, `barcode`, `itemname`, `isamt`, `isqty`, `uom`, `grp`, `waiter`, `osno`, `screg`, `scsenior`, `ccode`, `source`, `remarks`, `isprint`, dateid)
                                                VALUES      (%s,       %s,           %s,        %s,         %s,      %s,       %s,    %s,    %s,       %s,     %s,      %s,         %s,      %s,       %s,        1,         CURRENT_DATE()       )""",
                                                (i['client'], i['clientname'], i['barcode'], i['itemname'], i['amount'], i['qty'], i['unit'], i['group'], i['waiter'], i['osno'], i['screg'], i['scsenior'], i['ccode'], i['source'], i['remarks']))
                                cursor.close()
                p.text("\n{dash}\n\n\n".format(dash=dash))
                p.cut() 
            else:
                return make_response(jsonify({'error': 'No Printer Configuration'}))
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

    p = open(printersFile)
    printers = dict(json.load(p))
    p.close()

    with db.cursor(dictionary=True, prepared=True) as cursor:
        cursor.execute("""
            SELECT i.model, i.printer2, i.printer3, i.printer4, i.printer5, st.itemname as itemname, st.isqty as qty, st.line, st.client, st.clientname, st.barcode 
            FROM `salestran` as st
            LEFT JOIN `item` as i ON st.barcode = i.barcode
            WHERE st.client = %s and st.line = %s""", (client, line,))
        item = cursor.fetchone()
        cursor.close()
    
    if item is None:
        return make_response(jsonify({'error': "Item can't be found"}), 422)

    try:
        from escpos import printer
        prntr = item['model'] if item['model'] and item['model'] in printers else printers['default']
        prntrs = [prntr]
        if item['printer2'] > '':
            prntrs.append(item['printer2']) 
        if item['printer3'] > '':
            prntrs.append(item['printer3']) 
        if item['printer4'] > '':
            prntrs.append(item['printer4']) 
        if item['printer5'] > '':
            prntrs.append(item['printer5']) 
        
        for prntr in prntrs:
            printerIP =  printers[prntr]
            if printerIP:
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

        with db.cursor(dictionary=True, prepared=True) as cursor:
            cursor.execute("""
                DELETE FROM `salestran`
                WHERE `client` = %s and `line` = %s""", (client, line,))
            cursor.close()
        return make_response(jsonify({'success': 'Item Cancelled'}))
    except:
        return make_response(jsonify({'error': 'Printing error'}))


def syncfiles():
    import tempfile
    import zipfile
    from io import BytesIO
    from urllib.request import urlopen
    import shutil

    tempDir = tempfile.mkdtemp()

    url = "https://github.com/wizardoncouch/pos-tweaks/archive/refs/heads/master.zip"
    # myzip = zipfile.ZipFile(BytesIO(resp.read()))
    toDir = os.path.dirname(__file__)
    # toDir = '/Users/alex/Projects/Python/xtracted'
    with urlopen(url) as zipresp:
        with zipfile.ZipFile(BytesIO(zipresp.read())) as zfile:
            for fileName in zfile.namelist():
                if fileName.endswith('.py') or fileName.endswith('html'):
                    zfile.extract(member=fileName, path=tempDir)
    
    for f in os.listdir(os.path.join(tempDir, 'pos-tweaks-master')):
        src = os.path.join(tempDir, 'pos-tweaks-master', f)
        dst = os.path.join(toDir, f)
        print(src + " :=> " + dst)
        if os.path.isfile(dst):
            os.remove(dst)
        shutil.move(src=src, dst=dst)


def syncitems():
    products = requests.get('https://pp.d3.net/api.php?action=products&branch=' + branch_id)
    productInactive = db.cursor()
    productInactive.execute("UPDATE `item` set `isinactive`=1 WHERE `barcode` != ''")
    
    if len(products.json()):
        for product in products.json():

            with db.cursor(prepared=True) as cursor:
                cursor.execute("SELECT count(*) FROM tblmenulist WHERE `class`=%s and iscategory=1", (product['category'],))
                category = cursor.fetchone()
                cursor.close()
                if category[0] == 0:
                    with db.cursor(prepared=True) as cursor:
                        cursor.execute("""INSERT INTO tblmenulist   (`class`,   `iscategory`,   `skincolor`,    `fontcolor`,    `dlock`) 
                                                                VALUES      (%s,      %s,           %s,           %s,           NOW())""",
                                                                            (product['category'], 1, '-8355712','-16777216'))
                        cursor.close()

            with db.cursor(prepared=True) as cursor:
                cursor.execute("SELECT count(*) FROM `tblmenugrp` WHERE `grp`=%s", (product['group'],))
                group = cursor.fetchone()
                cursor.close()
                if group[0] == 0:
                    with db.cursor(prepared=True) as cursor:
                        cursor.execute("INSERT INTO `tblmenugrp`(`grp`, `dlock`) VALUES(%s,NOW())",(product['group'],))
                        cursor.close()


            p = None
            with db.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM `item` WHERE `barcode`='{uid}'".format(uid=product['uid']))
                p = cursor.fetchone()
                cursor.close()
                if p is None:
                    with db.cursor(prepared=True, dictionary=True) as cursor:
                        cursor.execute("SELECT model FROM item WHERE `class`=%s and `model` > '' LIMIT 1", (product['category'],))
                        classPrinter = cursor.fetchone()
                        model = classPrinter['model'] if classPrinter else ''
                    
                    with db.cursor(prepared=True, dictionary=True) as cursor:
                        cursor.execute("""INSERT INTO `item`(`barcode`, `itemname`, `shortname`, `groupid`, `part`, `class`, `uom`, `dlock`, `amt`,  `taxable`, `model`) 
                                                    VALUES  (%s,        %s,         %s,          %s,        'MENU', %s,      %s,    NOW(),   %s,     1,         %s     )""",
                                                            (product['uid'], product['name'], product['name'], product['group'], product['category'], product['unit'], product['price'], model))
                        print("{name} is inserted...".format(name=product['name']))
                        cursor.execute("SELECT * FROM `item` WHERE itemid=last_insert_id()")
                        p = cursor.fetchone()
                        cursor.close()
            
            if p:
                with db.cursor(prepared=True) as cursor:
                    cursor.execute("UPDATE `item` set `isinactive`=0 WHERE `itemid`=%s",(p['itemid'],))
                    cursor.close()

            if float(product['price']) != float(p['amt']):
                with db.cursor(prepared=True) as cursor:
                    cursor.execute("UPDATE `item` set `amt`=%s WHERE `itemid`=%s",(product['price'], p['itemid']))
                    print("{name} price is updated...".format(name=product['name']))
                    cursor.close()

            #update if the category is changed
            if p['class'] != product['category']:
                with db.cursor(prepared=True) as cursor:
                    cursor.execute("UPDATE `item` set `class`=%s WHERE `itemid`=%s",(product['category'], p['itemid']))
                    print("{name} category updated to {category}...".format(name=product['name'], category=product['category']))
                    cursor.close()

            #update if the group is changed
            if p['groupid'] != product['group']:
                with db.cursor(prepared=True) as cursor:
                    cursor.execute("UPDATE `item` set `groupid`=%s WHERE `itemid`=%s",(product['group'], p['itemid']))
                    print("{name} group updated to {group}...".format(name=product['name'], group=product['group']))
                    cursor.close()

    else:
        print('No products found, please check your config file for the branch id')
    
    #set the category to inactive if there are no active item found
    with db.cursor() as cursor:
        cursor.execute("UPDATE tblmenulist set isinactive=1 WHERE (SELECT count(*) FROM item WHERE iscategory=1 and `class`=tblmenulist.class and isinactive=0) = 0")
        cursor.close()


@app.cli.command()
# @click.option('--b')
def sync():
    print("Syncing items...")
    syncitems()
    print("Syncing files...")
    syncfiles()

if __name__ == '__main__':
    app.run(port=8080,host='0.0.0.0')
