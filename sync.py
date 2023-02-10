import os,sys
import mysql.connector
from mysql.connector import Error
import requests
from datetime import datetime
import json
from dotenv import load_dotenv
import time

load_dotenv()


branch_id = os.environ.get('BRANCH_ID')
requests_headers = {'X-API-TOKEN': 'Hi8193YOls721e'}

 
# total arguments
if len(sys.argv) <= 1:
    exit('No action passed [options: files, items, sales, test]')

action = sys.argv[1]
if action not in ['files', 'items', 'sales', 'test']:
    exit('action options are: [files, items, sales, test]')

db = None
if action in ['items', 'sales']:
    try:
        connection_config_dict = {
            'user': os.environ.get('DB_USER', 'root'),
            'password': os.environ.get('DB_PASSWORD', 'mjm'),
            'host': os.environ.get('DB_HOST', '127.0.0.1'),
            'database': os.environ.get('DB_NAME', 'lite'),
            'port': os.environ.get('DB_PORT', 3309),
            'raise_on_warnings': True,
            'use_pure': True,
            'autocommit': True,
            'pool_size': 5
        }

        db = mysql.connector.connect(**connection_config_dict)

        if db.is_connected():
            db_Info = db.get_server_info()
            print("Connected to MySQL Server version ", db_Info)
            cursor = db.cursor()
            # global connection timeout arguments
            global_connect_timeout = 'SET GLOBAL connect_timeout=180'
            global_wait_timeout = 'SET GLOBAL connect_timeout=180'
            global_interactive_timeout = 'SET GLOBAL connect_timeout=180'

            cursor.execute(global_connect_timeout)
            cursor.execute(global_wait_timeout)
            cursor.execute(global_interactive_timeout)

            db.commit()
            cursor.close()
    except Error as e:
        exit("Error while connecting to MySQL", e)

match action:
    case "files":
        print('Syncing files...')
        import tempfile
        import zipfile
        from io import BytesIO
        from urllib.request import urlopen
        import shutil

        tempDir = tempfile.mkdtemp()

        url = "https://github.com/wizardoncouch/pos-tweaks/archive/refs/heads/master.zip"
        toDir = os.path.dirname(__file__)
        with urlopen(url) as zipresp:
            with zipfile.ZipFile(BytesIO(zipresp.read())) as zfile:
                for fileName in zfile.namelist():
                    if fileName.endswith('.py') or fileName.endswith('html') or fileName.endswith('requirements.txt'):
                        zfile.extract(member=fileName, path=tempDir)
        
        for f in os.listdir(os.path.join(tempDir, 'pos-tweaks-master')):
            src = os.path.join(tempDir, 'pos-tweaks-master', f)
            dst = os.path.join(toDir, f)
            print(src + " :=> " + dst)
            if os.path.isfile(dst):
                os.remove(dst)
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            
            shutil.move(src=src, dst=dst)
    case "items":
        products = requests.get('https://pp.d3.net/api.php?action=products&branch=' + branch_id, headers=requests_headers)
        # productInactive = db.cursor()
        # productInactive.execute("UPDATE `item` set `isinactive`=1 WHERE `barcode` != ''")
        
        itemids = []
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
                            cursor.execute("SELECT * FROM `itemdlock` WHERE `itemid`=%s", (p['itemid'], ))
                            dlock = cursor.fetchone()
                            if dlock:
                                cursor.execute("UPDATE `itemdlock` SET `dlock`=%s WHERE `itemid`=%s", (p['dlock'], p['itemid']))
                            else:
                                cursor.execute("INSERT INTO `itemdlock`(`itemid`, `dlock`) VALUES(%s, %s)", (p['itemid'], p['dlock']))
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
                
                itemids.append(p['itemid'])

        else:
            print('No products found, please check your config file for the branch id')
        
        if itemids:
            print(len(itemids))
            format_ids = "({})".format(','.join([str(i) for i in itemids]))
            with db.cursor() as cursor:
                cursor.execute("UPDATE `item` set `isinactive`=1 WHERE `itemid` NOT IN %s" % format_ids)
                print("products set to inactive = {}".format(cursor.rowcount))
                cursor.close()

        #set the category to inactive if there are no active item found
        with db.cursor() as cursor:
            cursor.execute("UPDATE tblmenulist set isinactive=1 WHERE (SELECT count(*) FROM item WHERE iscategory=1 and `class`=tblmenulist.class and isinactive=0) = 0")
            cursor.close()

    case "sales":
        while True:
            print("Uploading sales...")
            response = requests.get('https://pp.d3.net/api.php?action=last-sync&branch=' + branch_id, headers=requests_headers)
            if response is None:
                exit('Cannot connect...')

            last = dict(response.json())
            if last['code'] != 200:
                exit('Error code: '+str(last['code']))
            
            last_number = last['number']

            with db.cursor(prepared=True, dictionary=True) as cursor:
                cursor.execute("SELECT * FROM `glhead` WHERE `docno` > %s ORDER BY `docno` ASC", (last_number,))
                sales = []
                for sale in cursor.fetchall():
                    cursor.execute("""SELECT g.*,i.barcode 
                                        FROM `glstock` as g 
                                        LEFT JOIN `item` as i ON i.itemid = g.itemid
                                        WHERE g.`trno`=%s""" % sale['trno'])
                    sales.append(dict({
                        'number': sale['docno'],
                        'created': sale['printtime'].strftime("%Y-%m-%d %H:%M:%S") if sale['printtime'] else '',
                        'total': float(sale['amt']),
                        'remarks': sale['rem'],
                        'items': [dict({
                            'uid': item['barcode'] if item['barcode'] else 0,
                            'name': item['itemname'],
                            'amount': float(item['ext']),
                            'qty': float(item['isqty']),
                            'created': item['createdate'].strftime("%Y-%m-%d %H:%M:%S") if item['createdate'] else ''
                        }) for item in cursor.fetchall()]
                    }))

                cursor.close()

                payload = {
                    "action": "sales",
                    "branch": branch_id,
                    "sales": json.dumps(sales)
                }

                response = requests.post("https://pp.d3.net/api.php", data=payload, headers=requests_headers)
                
                print(response.json())

            time.sleep(600)

    case "test":
        print('testing ...')
        response = requests.get('https://pp.d3.net/api.php?action=test', headers=requests_headers)
        print(response.json())
if db is not None:
    db.close()