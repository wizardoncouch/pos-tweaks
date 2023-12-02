import os,sys
import requests
import json
from dotenv import load_dotenv
from app import db, app
from sqlalchemy import text
import datetime

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))


branch_id = os.environ.get('BRANCH_ID')
domain    = os.environ.get('DOMAIN')
requests_headers = {'X-API-TOKEN': 'Hi8193YOls721e'}

remote_url = 'https://pp.d3.net'

 
# total arguments
if len(sys.argv) <= 1:
    exit('No action passed [options: files, items, sales, test]')

action = sys.argv[1]
if action not in ['files', 'items', 'sales','DynDNS', 'test']:
    exit('action options are: [files, items, sales, test]')

if sys.argv[2] is not None and sys.argv[2] == 'local': remote_url = 'http://pp.local'

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
    
    with app.app_context():
        itemids = []
        if len(products.json()):
            for product in products.json():
                if product['floor']: print(f"type is floor: {product['name']}")

                category = db.session.execute(text("SELECT count(*) as cnt FROM tblmenulist WHERE `class`='{cl}' and iscategory=1".format(cl=product['category']))).fetchone()
                if category.cnt == 0:
                    db.session.execute(text("""INSERT INTO tblmenulist   (`class`,   `iscategory`,      `skincolor`,    `fontcolor`,    `dlock`) 
                                                            VALUES      ('{cl}',      '{iscategory}',   '{skin}',       '{font}',        NOW())"""
                                        .format(cl=product['category'], iscategory=1, skin='-8355712', font='-16777216')))

                group = db.session.execute(text("SELECT count(*) as cnt FROM `tblmenugrp` WHERE `grp`='{group}'".format(group=product['group']))).fetchone()
                if group.cnt == 0:
                    db.session.execute(text("INSERT INTO `tblmenugrp`(`grp`, `dlock`) VALUES('{group}',NOW())".format(group=product['group'])))


                p = db.session.execute(text("SELECT *, `class` as category FROM `item` WHERE `barcode`='{uid}'".format(uid=product['uid']))).fetchone()
                t = 'floor' if product['floor'] else ''
                if p is None:
                    classPrinter = db.session.execute(text("SELECT model FROM item WHERE `class`='{cl}' and `model` > '' LIMIT 1".format(cl=product['category']))).fetchone()
                    model = classPrinter.model if classPrinter else ''
                    
                    inserted = db.session.execute(text("""INSERT INTO `item`(`barcode`,    `itemname`,     `shortname`,    `groupid`,      `part`, `class`,    `uom`,      `dlock`,    `amt`,      `taxable`, `model`, `type`  ) 
                                                        VALUES  ('{barcode}',   '{itemname}',   '{shortname}',  '{groupid}',    'MENU', '{cl}',     '{unit}',    NOW(),     '{amt}',    1,         '{model}' , '{type}')"""
                                                        .format(barcode=product['uid'], itemname=product['name'], shortname=product['name'], groupid=product['group'], cl=product['category'], unit=product['unit'], amt=product['price'], model=model, type=t)))
                    db.session.commit()
                    print("{name} is inserted... with id {id}".format(name=product['name'], id=inserted.lastrowid))
                    p = db.session.execute(text("SELECT *, `class` as category FROM `item` WHERE itemid='{itemid}'".format(itemid=inserted.lastrowid))).fetchone()
                    dlock = db.session.execute(text("SELECT * FROM `itemdlock` WHERE `itemid`='{itemid}'".format(itemid=p.itemid))).fetchone()
                    if dlock:
                        db.session.execute(text("UPDATE `itemdlock` SET `dlock`='{dlock}' WHERE `itemid`='{itemid}'".format(dlock=p.dlock, itemid=p.itemid)))
                    else:
                        db.session.execute(text("INSERT INTO `itemdlock`(`itemid`, `dlock`) VALUES('{itemid}', '{dlock}')".format(itemid=p.itemid, dlock=p.dlock)))
                
                if product['name'] != p.itemname or product['name'] != p.shortname:
                    db.session.execute(text("UPDATE `item` set `itemname`='{itemname}', `shortname`='{shortname}' WHERE `itemid`='{itemid}'".format(itemname=product['name'], shortname=product['name'], itemid=p.itemid)))
                    print("{name} name is updated...".format(name=product['name']))

                if float(product['price']) != float(p.amt):
                    db.session.execute(text("UPDATE `item` set `amt`='{amt}' WHERE `itemid`='{itemid}'".format(amt=product['price'], itemid=p.itemid)))
                    print("{name} price is updated...".format(name=product['name']))
                if p.type != t:
                    db.session.execute(text("UPDATE `item` set `type`='{type}' WHERE `itemid`='{itemid}'".format(type=t, itemid=p.itemid)))
                    print("{name} type is updated...".format(name=product['name']))

                #update if the category is changed
                if p.category != product['category']:
                    db.session.execute(text("UPDATE `item` set `class`='{cl}' WHERE `itemid`='{itemid}'".format(cl=product['category'], itemid=p.itemid)))
                    print("{name} category updated to {category}...".format(name=product['name'], category=product['category']))

                #update if the group is changed
                if p.groupid != product['group']:
                    db.session.execute(text("UPDATE `item` set `groupid`='{group}' WHERE `itemid`='{itemid}'".format(group=product['group'], itemid=p.itemid)))
                    print("{name} group updated to {group}...".format(name=product['name'], group=product['group']))
                
                itemids.append(p.itemid)

        else:
            print('No products found, please check your config file for the branch id')
        
        if itemids:
            print(len(itemids))
            format_ids = "({})".format(','.join([str(i) for i in itemids]))
            update = db.session.execute(text("UPDATE `item` set `isinactive`=1 WHERE `itemid` NOT IN %s" % format_ids))
            print("products set to inactive = {}".format(update.rowcount))

        #set the category to inactive if there are no active item found
        db.session.execute(text("UPDATE tblmenulist set isinactive=1 WHERE iscategory=1 AND (SELECT count(*) FROM item WHERE `class`=`tblmenulist`.`class` and `isinactive`=0) = 0"))
        db.session.execute(text("UPDATE tblmenulist set isinactive=0 WHERE iscategory=1 AND (SELECT count(*) FROM item WHERE `class`=`tblmenulist`.`class` and `isinactive`=0) > 0"))

elif action == "sales":
    with app.app_context():

        syncFile = os.path.join(os.path.dirname(__file__), 'sync.json')

        sync = {}
        if os.path.isfile(syncFile):
            p = open(syncFile)
            sync = dict(json.load(p))
            p.close()

        print("Uploading sales...")
        # response = requests.get('https://pp.d3.net/api.php?action=last-sync&branch=' + branch_id, headers=requests_headers)
        # print(response.json())
        # if response is None:
        #     exit('Cannot connect...')

        # last = dict(response.json())
        # if last['code'] != 200:
        #     exit('Error code: '+str(last['code']))
        
        # last_created = datetime.datetime.strptime(last['created'], '%Y-%m-%d %H:%M:%S') if 'created' in last and last['created'] > '' else ''

        sql = text("SELECT * FROM `glhead` WHERE `trno`>'{last}' ORDER BY `trno` ASC".format(last=sync["last"]))
        sales = []
        lastuid = None
        for sale in db.session.execute(sql):
            tsql = text("""SELECT g.*,i.barcode 
                                FROM `glstock` as g 
                                LEFT JOIN `item` as i ON i.itemid = g.itemid
                                WHERE g.`trno`=%s""" % sale.trno)
            sales.append(dict({
                'number': sale.docno,
                'created': sale.printtime.strftime("%Y-%m-%d %H:%M:%S") if sale.printtime else '',
                'timein': sale.timein.strftime("%Y-%m-%d %H:%M:%S") if sale.timein else '',
                'date': sale.dateid.strftime("%Y-%m-%d") if sale.dateid else datetime.today().strftime('%Y-%m-%d'),
                'total': float(sale.amt),
                'remarks': sale.rem.replace('"', '').replace("'", ''),
                'currency': 'PHP',
                'paytype': sale.yourref.lower(),
                'batch': sale.batch.lower(),
                'approval': sale.approval,
                'items': [dict({
                    'uid': item.barcode if item.barcode else 0,
                    'name': item.itemname,
                    'amount': float(item.ext),
                    'qty': float(item.isqty),
                    'created': item.createdate.strftime("%Y-%m-%d %H:%M:%S") if item.createdate else ''
                }) for item in db.session.execute(tsql)]
            }))
            lastuid = sale.trno


        payload = {
            "action": "sales",
            "branch": branch_id,
            "sales": json.dumps(sales)
        }

        try:
            response = requests.post(f"{remote_url}/api.php", data=payload, headers=requests_headers)
            print(response.json())

            if lastuid != None:
                with open(syncFile, "w") as outfile:
                    sync["last"] = lastuid
                    json.dump(sync, outfile)
        except Exception as e:
            print("Exception occurred"+ repr(e))

            print('Cannot sync...')

elif action == 'DynDNS':

    response = requests.get('https://d3net.d3.net/api.php?action=DynDNS&domain='+domain, headers=requests_headers)

elif action == "test":
    print('testing ...')
    response = requests.get('https://pp.d3.net/api.php?action=test', headers=requests_headers)
    print(response.json())