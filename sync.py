import os,sys
import requests
from datetime import datetime
import json
from dotenv import load_dotenv
from app import db
from sqlalchemy import text

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))


branch_id = os.environ.get('BRANCH_ID')
domain    = os.environ.get('DOMAIN')
requests_headers = {'X-API-TOKEN': 'Hi8193YOls721e'}

 
# total arguments
if len(sys.argv) <= 1:
    exit('No action passed [options: files, items, sales, test]')

action = sys.argv[1]
if action not in ['files', 'items', 'sales','DynDNS', 'test']:
    exit('action options are: [files, items, sales, test]')


if action == "files":
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
                if fileName.endswith('.py') or fileName.endswith('.html') or fileName.endswith('requirements.txt'):
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
elif action == "items":
    products = requests.get('https://pp.d3.net/api.php?action=products&branch=' + branch_id, headers=requests_headers)
    # productInactive = db.cursor()
    # productInactive.execute("UPDATE `item` set `isinactive`=1 WHERE `barcode` != ''")
    
    itemids = []
    if len(products.json()):
        for product in products.json():

            category = db.session.execute(text("SELECT count(*) as cnt FROM tblmenulist WHERE `class`='{cl}' and iscategory=1".format(cl=product['category']))).fetchone()
            if category.cnt == 0:
                db.session.execute(text("""INSERT INTO tblmenulist   (`class`,   `iscategory`,      `skincolor`,    `fontcolor`,    `dlock`) 
                                                        VALUES      ('{cl}',      '{iscategory}',   '{skin}',       '{font}',        NOW())"""
                                    .format(cl=product['category'], iscategory=1, skin='-8355712', font='-16777216')))

            group = db.session.execute(text("SELECT count(*) as cnt FROM `tblmenugrp` WHERE `grp`='{group}'".format(group=product['group']))).fetchone()
            if group.cnt == 0:
                db.session.execute(text("INSERT INTO `tblmenugrp`(`grp`, `dlock`) VALUES('{group}',NOW())".format(product['group'])))


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

elif action == "sales":
    print("Uploading sales...")
    response = requests.get('https://pp.d3.net/api.php?action=last-sync&branch=' + branch_id, headers=requests_headers)
    if response is None:
        exit('Cannot connect...')

    last = dict(response.json())
    if last['code'] != 200:
        exit('Error code: '+str(last['code']))
    
    last_number = last['number']

    with db.cursor(prepared=True, dictionary=True) as cursor:
        cursor.execute("SELECT * FROM `glhead` WHERE `billnumber`>'' AND `docno` > %s ORDER BY `docno` ASC", (last_number,))
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

elif action == 'DynDNS':

    response = requests.get('https://d3net.d3.net/api.php?action=DynDNS&domain='+domain, headers=requests_headers)

elif action == "test":
    print('testing ...')
    response = requests.get('https://pp.d3.net/api.php?action=test', headers=requests_headers)
    print(response.json())
if db is not None:
    db.close()