import os
from flask import Flask, render_template, request, make_response, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, send, emit
from flask_httpauth import HTTPBasicAuth
from datetime import datetime, timedelta
import json
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from dotenv import load_dotenv
import time
import math
import logging


logging.basicConfig(filename=os.path.join(os.path.dirname(__file__), 'error.log'), level=logging.ERROR, format=f'%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s')

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

SYSTEM_NAME = "POS"
SECRET_KEY = "secret!"
SQLALCHEMY_DATABASE_URI = "mysql+pymysql://{user}:{password}@{host}:{port}/{database}".format(
    user = os.environ.get('DB_USER', 'root'),
    password = os.environ.get('DB_PASSWORD', 'mjm'),
    host = os.environ.get('DB_HOST', '127.0.0.1'),
    database = os.environ.get('DB_NAME', 'lite'),
    port = os.environ.get('DB_PORT', 3309)
)


SQLALCHEMY_TRACK_MODIFICATIONS = True
SQLALCHEMY_ECHO = False

app = Flask(__name__)
db = SQLAlchemy()
auth = HTTPBasicAuth()

app.config.from_object(__name__)
socketio = SocketIO(app)


db.init_app(app)

branch_id = os.environ.get('BRANCH_ID')

printersFile = os.path.join(os.path.dirname(__file__), 'printers.json')

users = {
    "admin": generate_password_hash("x1admin99"),
}


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


@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username

@app.before_request 
def before_request_callback(): 
    try:
        db.session.execute(text("CREATE DATABASE IF NOT EXISTS `pos-x`"))
    except:
        print('Cannot create database pos-x')
    
    try:
        db.session.execute(text("""CREATE TABLE IF NOT EXISTS `pos-x`.`printers` (
                `id` int unsigned NOT NULL AUTO_INCREMENT,
                `name` VARCHAR(255),
                `ip` VARCHAR(255),
                `floors` TEXT,
                PRIMARY KEY (`id`)
            ) ENGINE=InnoDB """))
    except Exception as e:
        print(f'Cannot create table printers: {e}')

    ordered = db.session.execute(text("SHOW COLUMNS FROM `salestran` LIKE 'ordered'"))
    if ordered.rowcount == 0:
        print('Add ordered column...')
        db.session.execute(text("ALTER TABLE `salestran` ADD `ordered` DATETIME NULL"))
    served = db.session.execute(text("SHOW COLUMNS FROM `salestran` LIKE 'served'"))
    if served.rowcount == 0:
        print('Add served column...')
        db.session.execute(text("ALTER TABLE `salestran` ADD `served` DATETIME NULL"))
    
    db.session.commit()

    
@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.close()

@app.route('/t')
def t():
    t = text("""Lorem Ipsum
                DOLOR {a}""".format(a='adf'))
    print(t)
    # db.session.execute(text("INSERT INTO osnumber(tableno) VALUES('{table}')".format(table='aa')))
    # [id] = db.session.execute(text("SELECT LAST_INSERT_ID()")).fetchone()
    # return str(id)



@app.route('/config', methods=["POST", "GET"])
@auth.login_required
def config():

    if request.method == "POST":
        for row in db.session.execute(text("SELECT * from `pos-x`.`printers` where 1")):
            ip = request.form.get(f'ip_{row.id}')
            floors = ','.join(request.form.getlist(f'floors_{row.id}'))
            db.session.execute(text(f"UPDATE `pos-x`.`printers` SET `ip`='{ip}', `floors`='{floors}' WHERE id='{row.id}'"))
            print(f"UPDATE `pos-x`.`printers` SET `ip`='{ip}', `floors`='{floors}' WHERE id='{row.id}'")
            db.session.commit()

    oldconfig = {}
    if os.path.isfile(printersFile):
        p = open(printersFile)
        oldconfig = dict(json.load(p))
        p.close()

    rows = db.session.execute(text("SELECT distinct(model) as name from `item` where model > ''")).fetchall()
    for row in rows:
        printer = db.session.execute(text(f"SELECT * FROM `pos-x`.`printers` WHERE `name`='{row.name}'")).fetchone()
        if printer is None:
            ip = oldconfig[row.name] if row.name in oldconfig else ''
            db.session.execute(text(f"INSERT INTO `pos-x`.`printers`(`name`,`ip`) VALUES('{row.name}', '{ip}')"))

    db.session.commit()
    printers = [{
            "id": row.id,
            "name": row.name, 
            "ip": row.ip, 
            "floors":row.floors.split(',') if row.floors else []
        } for row in db.session.execute(text("SELECT * from `pos-x`.`printers` where 1"))]
    floors = db.session.execute(text("SELECT DISTINCT(flr) as name FROM client where isconsignee=1")).fetchall()

    return render_template('config.html', data = {"printers":printers, "floors":floors})


@app.route('/repair')
@auth.login_required
def repair():
    os.system('mysqlcheck -h{dbhost} -u{dbuser} -p{dbpass} -P{dbport} lite -r'.format(
        dbhost = os.environ.get('DB_HOST', '127.0.0.1'),
        dbuser = os.environ.get('DB_USER', 'root'),
        dbpass = os.environ.get('DB_PASSWORD', 'mjm'),
        dbport = os.environ.get('DB_PORT', 3309)
        ))
    # mysqlcheck -h192.168.10.100 -uroot -p -P3309 lite -r
    print('done repair!')

@app.route('/fixdate')
@auth.login_required
def fixdate():
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    yesterday = now - timedelta(1)
    encoded = datetime.strftime(yesterday, '%Y-%m-%d 23:59:50')
    dateid = datetime.strftime(yesterday, '%Y-%m-%d')

    orderstoday = db.session.execute(db.text("SELECT * FROM salestran WHERE date(dateid)='{today}'".format(today=today))).fetchall()
    ordersyesterday = db.session.execute(db.text("SELECT * FROM salestran WHERE date(dateid)='{yesterday}'".format(yesterday=dateid))).fetchall()
    if orderstoday and ordersyesterday:
        db.session.execute(db.text("UPDATE salestran SET encoded='{encoded}', dateid='{dateid}' WHERE date(dateid)='{today}'".format(
            encoded=encoded,
            dateid=dateid,
            today=today
        )))
    print('done')

@app.route("/")
def floors():

    args = request.args
    data = {
        "floor": None,
        "floors": [],
        "tables": []
    }
    sql = text('SELECT DISTINCT(flr) as floor FROM client where isconsignee=1')
    data['floors'] = [{
        'name': row.floor
    } for row in db.session.execute(sql)]

    floor = args.get('floor')
    if floor is None and data['floors']:
        floor = data['floors'][0]['name']

    sql = text("""SELECT `clientname`, `client`, `clientid`, `locx`, `locy`, (SELECT count(*) from salestran WHERE client=client.client) as `ordercount` FROM `client` WHERE flr='{floor}'""".format(floor=floor))

    data['tables'] = [{
        "id": table.clientid,
        "name": table.clientname,
        "left": table.locx,
        "top": table.locy,
        "inuse": True if table.ordercount > 0 else False
    } for table in db.session.execute(sql)] 

    data['floor'] = floor

    return render_template('tables.html', data = data)

@app.route("/table/<id>")
def tables(id):
    table = text("SELECT * FROM client WHERE clientid='{id}'".format(id=id))
    tables = text("""SELECT t.* 
                            FROM client as t 
                            LEFT JOIN (SELECT DISTINCT(flr) as floor, client as fid FROM client where isconsignee=1) as f on f.floor = t.flr
                            WHERE f.fid>'' 
                            GROUP by t.client
                            ORDER by t.clientname""")
    categories = text("SELECT id, class as name FROM tblmenulist where isinactive=0 and iscategory=1 order by class asc")
    return render_template('order.html', data={
        "table":db.session.execute(table).fetchone(), 
        "tables": [{"id": t.client, "name": t.clientname} for t in db.session.execute(tables).fetchall()],
        "categories": db.session.execute(categories).fetchall()
    })

@app.route("/orders", methods=['GET'])
def orders():
    args = request.args
    if args.get('client') is None:
        return make_response({"message": "no client passed"})

    sql = text("SELECT * FROM salestran where client='{client}' ORDER by ordered ASC".format(client=args.get('client')))
    total = 0
    orders = []
    for order in db.session.execute(sql):
        amount = float(order.isamt) * float(order.isqty)
        orders.append({
            "id": order.line,
            "barcode": order.barcode,
            "name": order.itemname,
            "qty": order.isqty,
            "price": order.isamt,
            "remarks": order.remarks,
            "printed": order.isprint,
            "group": order.grp,
            "senior": order.scsenior,
            "table": order.client,
            "selected": 0
        })
        total += amount

    return make_response(orders)
    # return make_response({
    #     "orders": orders,
    #     "total": total
    # })


@app.route("/products", methods=['GET'])
def products():
    args = request.args

    products = []
    subProducts = []

    if args.get('category'):
        groups = [g._asdict() for g in db.session.execute(text("SELECT DISTINCT(groupid) as itemname, class, '' as barcode FROM `item` WHERE `class`='{cl}' AND `groupid` > '' AND `isinactive` = 0".format(cl=args.get('category'))))]
        if groups:
            products = groups
            if args.get('group'):
                subProducts = [p._asdict() for p in db.session.execute(text("""
                    SELECT i.*, count(*) as orderCount 
                    FROM item as i 
                    LEFT JOIN `salestran` as st ON i.barcode = st.barcode 
                    WHERE i.class='{cl}' AND i.groupid='{g}' AND i.isinactive = 0
                    GROUP BY i.barcode 
                    ORDER BY orderCount DESC""".format(cl=args.get('category'), g=args.get('group'))))]

            #for not grouped products
            sql = text("""
                SELECT i.*, count(*) as orderCount 
                FROM item as i 
                LEFT JOIN `salestran` as st ON i.barcode = st.barcode 
                WHERE i.class='{cl}' and i.groupid='' AND i.isinactive = 0 
                GROUP BY i.barcode 
                ORDER BY orderCount DESC""".format(cl=args.get('category')))
            for p in db.session.execute(sql):
                products.append(p._asdict())
        else:
            products = [p._asdict() for p in db.session.execute(text("""
                SELECT i.*, count(*) as orderCount 
                FROM item as i 
                LEFT JOIN `salestran` as st ON i.barcode = st.barcode 
                WHERE i.class='{cl}' AND i.isinactive = 0 
                GROUP BY i.barcode 
                ORDER BY orderCount DESC""".format(cl=args.get('category'))))]
    
    if args.get('search'):
        where = ""
        for s in args.get('search').strip().lower().split(' '):
            where += " AND concat(' ',i.itemname) LIKE '% {s}%'".format(s=s)
        products = [p._asdict() for p in db.session.execute(text("""
            SELECT i.*, count(*) as orderCount 
            FROM item as i 
            LEFT JOIN `salestran` as st ON i.barcode = st.barcode 
            WHERE i.isinactive = 0 {where} 
            GROUP BY i.barcode 
            ORDER BY orderCount DESC""".format(where=where)))]


    return make_response({
        "products": products,
        "subProducts": subProducts
    })

@app.route("/remarks", methods=['POST'])
def getRemarks():

    remarks = None
    
    item = db.session.execute(text("SELECT *, class as category FROM `item` WHERE `barcode`='{code}'".format(code=request.form.get('barcode')))).fetchone()

    remarks = [{"remarks": remark.remarks, "count": remark.count} for remark in db.session.execute(text("""SELECT st.remarks, count(*) as count
            FROM `item` as i
            LEFT JOIN `salestran` as st ON i.barcode = st.barcode
            WHERE `class`='{cl}' AND st.remarks > ''
            GROUP BY st.remarks
            ORDER BY count desc""".format(cl=item.category)))]

    return make_response(remarks)

@app.route("/order/accept", methods=['POST'])
def order_accept():
    table = request.form.get('table')
    items = request.form.get('items')

    table = db.session.execute(text("SELECT * FROM `client` WHERE `client`='{table}'".format(table=table))).fetchone()
    if table is None:
        return make_response(jsonify({'error': 'No table passed'}), 422)

    allPrinters = {}
    for row in db.session.execute(text("SELECT * from `pos-x`.`printers`")).fetchall():
        allPrinters[row.name] = row.ip
    floorPrinters = {}
    for row in db.session.execute(text(f"SELECT * FROM `pos-x`.`printers` WHERE `floors` LIKE '%{table.flr}%'")).fetchall():
        floorPrinters[row.name] = row.ip

    dt = datetime.now()
    printables = {}
    for order_item in json.loads(items):
        item = db.session.execute(text("SELECT *, class as category FROM item where barcode='{code}'".format(code=order_item['barcode']))).fetchone()
        if item is None:
            continue

        printers = floorPrinters if item.type == 'floor' else allPrinters

        if item.model and not item.model in printables and item.model in printers:
            printables[item.model] = []
        
        if item.printer2 and not item.printer2 in printables and item.printer2 in printers:
            printables[item.printer2] = []

        if item.printer3 and not item.printer3 in printables and item.printer3 in printers:
            printables[item.printer3] = []

        if item.printer4 and not item.printer4 in printables and item.printer4 in printers:
            printables[item.printer4] = []

        if item.printer5 and not item.printer5 in printables and item.printer5 in printers:
            printables[item.printer5] = []

        order_item_qty = order_item['qty']
        order_item_remarks = order_item['remarks']

        order_name = "{itemname} {group} {remarks}".format(itemname=item.itemname, group=order_item['group'], remarks="\n!!! "+order_item_remarks+" !!!" if order_item_remarks else "")
        extobj = {
            "barcode": item.barcode,
            "name": order_name,
            "qty": order_item_qty,
            "unit": item.uom
        }
        if item.model > '' and item.model in printables:
            printables[item.model].append(extobj)
        if item.printer2 > '' and item.printer2 in printables:
            printables[item.printer2].append(extobj)
        if item.printer3 > '' and item.printer3 in printables:
            printables[item.printer3].append(extobj)
        if item.printer4 > '' and item.printer4 in printables:
            printables[item.printer4].append(extobj)
        if item.printer5 > '' and item.printer5 in printables:
            printables[item.printer5].append(extobj)

        transaction = db.session.execute(text("SELECT * FROM salestran WHERE `client`='{table}' LIMIT 1".format(table=table.client))).fetchone()
        if transaction is None:
            osno = None
            inserted = db.session.execute(text("INSERT INTO osnumber(tableno) VALUES('{table}')".format(table=table.client)))
            db.session.commit()
            osno = inserted.lastrowid
            ccode = 'WALK-IN'
            screg = 10
            scsenior = 10
            grp = order_item['group'] if order_item['group'] else 'A'
            waiter = 'Administrator'
            source = 'WH00001'
        else:
            osno = transaction.osno
            ccode = transaction.ccode
            screg = transaction.screg
            scsenior = transaction.scsenior
            grp = order_item['group'] if order_item['group'] else transaction.grp
            waiter = transaction.waiter
            source = transaction.source

        if osno > 0:
            i = {
                'client': table.client,
                'clientname': table.clientname,
                'barcode': item.barcode,
                'itemname': item.itemname,
                'amount': item.amt,
                'qty': order_item_qty,
                'unit': item.uom,
                'group': grp,
                'waiter': waiter,
                'osno': osno,
                'screg': screg,
                'scsenior': scsenior,
                'ccode': ccode,
                'source': source,
                'remarks': order_item_remarks,
            }
            sql = text("""INSERT INTO salestran (`client`,      `clientname`,   `barcode`,      `itemname`,     `isamt`,    `isqty`,    `uom`,      `grp`,      `waiter`,       `osno`,     `screg`,    `scsenior`,     `ccode`,    `source`,   `remarks`,      `isprint`, `dateid`, `ordered`)
                                    VALUES      ('{client}',    '{clientname}', '{barcode}',    '{itemname}',   '{amount}', '{qty}',    '{unit}',   '{group}',  '{waiter}',     '{osno}',   '{screg}',  '{scsenior}',   '{ccode}',  '{source}', '{remarks}',    1,         CURRENT_DATE(), '{ordered}')"""
                                    .format(client=i['client'],clientname=i['clientname'],barcode=i['barcode'],itemname=i['itemname'],amount=i['amount'],qty=i['qty'],unit=i['unit'],group=i['group'],waiter=i['waiter'],osno=i['osno'],screg=i['screg'],scsenior=i['scsenior'],ccode=i['ccode'],source=i['source'],remarks=i['remarks'],ordered=dt))
            db.session.execute(sql)
        # print(printables)

        # cntr += 1
    
    # return ''

    try:
        from escpos import printer
        for prntr in printables:
            printerIP =  printers[prntr]

            willPrint = True if printerIP != '0.0.0.0' else False
            if willPrint:
                p = printer.Network(printerIP)
                date = datetime.now()
                p.set(font='A')
                p.text(dash)
                p.text("\n\nOrder date: {d}".format(d=date.strftime("%b %d, %Y %H:%M:%S")))
                p.text("\n\nTable: {table}\n\n".format(table=table.clientname))

            for row in printables[prntr]:
                if willPrint:
                    p.text("\n")
                    p.block_text(txt=str(row['qty']).rstrip('.0') + " - " + row['name'], columns=40)
                    p.text("\n")

            if willPrint:
                p.text("\n{dash}\n\n\n".format(dash=dash))
                p.cut() 
        
        socketio.emit('updated', table.client, broadcast=True)
        return make_response(jsonify({'success': 'Orders Printed'}))
    except:
        return make_response(jsonify({'error': 'Printer error'}))
    
@app.route("/order/update", methods=['POST'])
def order_update():
    id = request.form.get('id')
    table = request.form.get('table')
    group = request.form.get('group')
    item = db.session.execute(text("SELECT * FROM salestran WHERE `line`='{line}'".format(line=id))).fetchone()
    if item is None:
        return make_response(jsonify({'error': 'Item not found'}))
    
    osno = item.osno
    client = item.client
    clientname = item.clientname
    if table != item.client:
        t = db.session.execute(text("SELECT * FROM `client` where `client`='{table}'".format(table=table))).fetchone()
        client = t.client
        clientname = t.clientname
        transaction = db.session.execute(text("SELECT * FROM salestran WHERE `client`='{table}' LIMIT 1".format(table=t.client))).fetchone()
        if transaction is None:
            inserted = db.session.execute(text("INSERT INTO osnumber(tableno) VALUES('{table}')".format(table=t.client)))
            db.session.commit()
            osno = inserted.lastrowid
        else:
            osno = transaction.osno
    db.session.execute(text("UPDATE salestran SET `osno`='{osno}', `grp`='{group}', `client`='{client}', `clientname`='{clientname}' WHERE `line`='{line}'".format(osno=osno, group=group, client=client, clientname=clientname, line=item.line)))
    db.session.commit()

    socketio.emit('updated', item.client, broadcast=True)

    return make_response(jsonify({'success': 'Item updated'}))

@app.route("/order/void", methods=['POST'])
def order_void():
    line = request.form.get('id')

    p = open(printersFile)
    printers = dict(json.load(p))
    p.close()

    sql = text("""
            SELECT i.type, i.model, i.printer2, i.printer3, i.printer4, i.printer5, st.itemname as itemname, st.isqty as qty, st.line, st.client, st.clientname, st.barcode 
            FROM `salestran` as st
            LEFT JOIN `item` as i ON st.barcode = i.barcode
            WHERE st.line = '{line}'""".format(line=line))
    item = db.session.execute(sql).fetchone()
    
    if item is None:
        return make_response(jsonify({'error': "Item can't be found"}), 422)
    
    table = db.session.execute(text("SELECT * FROM `client` WHERE `client`='{client}'".format(client=item.client))).fetchone()
    if table is None:
        return make_response(jsonify({'error': 'No table found'}), 422)

    allPrinters = {}
    for row in db.session.execute(text("SELECT * from `pos-x`.`printers`")).fetchall():
        allPrinters[row.name] = row.ip
    floorPrinters = {}
    for row in db.session.execute(text(f"SELECT * FROM `pos-x`.`printers` WHERE `floors` LIKE '%{table.flr}%'")).fetchall():
        floorPrinters[row.name] = row.ip
    
    printerOptions = floorPrinters if item.type == 'floor' else allPrinters

    try:
        from escpos import printer
        # prntr = item.model if item.model and item.model in printers else printers['default']
        prntrs = []
        if item.model > '' and not item.model in prntrs and item.model in printerOptions:
            prntrs.append(item.model) 
        if item.printer2 > '' and not item.printer2 in prntrs and item.printer2 in printerOptions:
            prntrs.append(item.printer2) 
        if item.printer3 > '' and not item.printer3 in prntrs and item.printer3 in printerOptions:
            prntrs.append(item.printer3) 
        if item.printer4 > '' and not item.printer4 in prntrs and item.printer4 in printerOptions:
            prntrs.append(item.printer4) 
        if item.printer5 > '' and not item.printer5 in prntrs and item.printer5 in printerOptions:
            prntrs.append(item.printer5) 
        
        try:
            for prntr in prntrs:
                printerIP =  printers[prntr]

                if printerIP and printerIP != '0.0.0.0':
                    p = printer.Network(printerIP)
                    date = datetime.now()
                    p.set(font='A')
                    p.text(dash)
                    p.text("\n\nVoid Slip")
                    p.text("\n\nOrder date: {d}".format(d=date.strftime("%b %d, %Y %H:%M:%S")))
                    p.text("\n\nTable: {table}\n\n".format(table=item.clientname))

                    p.text("\n"+str(item.qty).rstrip('.0') + " - " + item.itemname + " !!! void void void !!! " + "\n")

                    p.text("\n{dash}\n\n\n".format(dash=dash))
                    p.cut()
        except Exception as e:
            print(str(e))
        finally:
            db.session.execute(text("DELETE FROM `salestran` WHERE `line`='{line}'".format(line=line)))
            db.session.commit()

        socketio.emit('updated', item.client, broadcast=True)

        return make_response(jsonify({'success': 'Item Cancelled'}))
    except:
        return make_response(jsonify({'error': 'Printing error'}))

@app.route("/order/serve/<string:direction>", methods=['POST'])
def order_serve(direction = 'out'):
    id = request.form.get('id')
    item = db.session.execute(text("SELECT * FROM salestran WHERE `line`='{line}'".format(line=id))).fetchone()
    if item is None:
        return make_response(jsonify({'error': 'Item not found'}))
    
    if direction == 'out':
        db.session.execute(text("UPDATE salestran SET `served`='{d}' WHERE `line`='{line}'".format(d=datetime.now(), line=item.line)))
    else:
        db.session.execute(text("UPDATE salestran SET `served`=NULL WHERE `line`='{line}'".format(line=item.line)))

    db.session.commit()
    socketio.emit('updated', item.client, broadcast=True)
    return make_response(jsonify({'success': 'Item served'}))

@app.route("/observe", methods=['GET'])
def observe():
    if request.method == 'GET':
        return render_template('observe.html')
    pass

@app.route("/kitchens", methods=['GET'])
def kitchens():
    rows = db.session.execute(text("SELECT DISTINCT(model) as printer FROM item WHERE model > ''")).fetchall()

    return make_response(jsonify([{"printer": row.printer} for row in rows]))

@socketio.on('refresh')
def refresh(table, printers):
    format_printers = "('{}')".format("','".join([str(i) for i in printers]))

    response = {
        "todos": None,
        "tables": None
    }
    sql = text("""SELECT o.*, i.model, i.class as cl 
                    FROM salestran o 
                    LEFT JOIN item i on i.barcode = o.barcode 
                    WHERE i.barcode > 0 AND i.model IN %s AND o.served IS NULL ORDER BY o.`ordered` ASC""" % format_printers)

    todos = dict()
    for row in db.session.execute(sql):
        if row.cl not in todos:
            todos[row.cl] = dict()
        if row.barcode not in todos[row.cl]:
            todos[row.cl][row.barcode] = {
                'name': row.itemname,
                'printer': row.model,
                'count': 0
            }
        todos[row.cl][row.barcode]['count'] += float(row.isqty)
    response["todos"] = todos
    
    t = db.session.execute(text("SELECT * FROM `client` where `client`='{table}'".format(table=table))).fetchone()
    if t:
        format_printers = "('{}')".format("','".join([str(i) for i in printers]))
        sql = text("""SELECT o.*, i.model 
                    FROM salestran o 
                    LEFT JOIN item i on i.barcode = o.barcode 
                    WHERE i.barcode > 0 AND i.model IN {printers} AND `client`='{client}' ORDER BY o.`ordered` ASC""".format(printers=format_printers, client=t.client))
        current = datetime.now()
        items = [{
                    "id": row.line,
                    "barcode": row.barcode,
                    "name": row.itemname, 
                    "qty": float(row.isqty),
                    "amount": float(row.isamt),
                    "remarks": row.remarks,
                    "group": row.grp,
                    "table": row.clientname,
                    "client": row.client,
                    "printer": row.model,
                    "duration": math.floor((current - (row.ordered if row.ordered else 0)).total_seconds()/60),
                    "served": math.floor((current - row.served).total_seconds()/60) if row.served else None
                } for row in db.session.execute(sql)]
        db.session.close()
        response["table"] = {"client":t.client, "name": t.clientname, "items": items}

    emit('refreshed', response)

@socketio.on('orders')
def orders(printers):
    while True:
        format_printers = "('{}')".format("','".join([str(i) for i in printers]))
        db.session.execute(text("UPDATE `salestran` SET `ordered` = `encoded` WHERE `ordered` IS NULL"))
        db.session.commit()
        sql = text("""SELECT o.*, i.model, i.class as cl 
                        FROM salestran o 
                        LEFT JOIN item i on i.barcode = o.barcode 
                        WHERE i.barcode > 0 AND i.model IN %s ORDER BY o.`ordered` ASC""" % format_printers)

        tables = dict()
        todos = dict()
        current = datetime.now()
        for row in db.session.execute(sql):
            if 'k'+str(row.client) not in tables:
                tables['k'+str(row.client)] = {
                    "client": row.client,
                    'name': row.clientname,
                    'items': []
                }
            obj = {
                "id": row.line,
                "barcode": row.barcode,
                "name": row.itemname, 
                "qty": float(row.isqty),
                "amount": float(row.isamt),
                "remarks": row.remarks,
                "group": row.grp,
                "table": row.clientname,
                "client": row.client,
                "printer": row.model,
                "duration": math.floor((current - (row.ordered if row.ordered else 0)).total_seconds()/60),
                "served": math.floor((current - row.served).total_seconds()/60) if row.served else None
            }
            tables['k'+str(row.client)]['items'].append(obj)
            if row.served is None:
                if row.cl not in todos:
                    todos[row.cl] = dict()
                if row.barcode not in todos[row.cl]:
                    todos[row.cl][row.barcode] = {
                        'name': row.itemname,
                        'printer': row.model,
                        'count': 0
                    }
                todos[row.cl][row.barcode]['count'] += float(row.isqty)
        db.session.close()
        emit('observe', {"todos": todos, "tables": tables})
        time.sleep(60)
if __name__ == '__main__':
    # app.run(port=8000, debug=True)
    socketio.run(app=app,host='0.0.0.0',port=8008,debug=True)
