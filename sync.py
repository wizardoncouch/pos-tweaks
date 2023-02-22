import os,sys
import requests
import json
from dotenv import load_dotenv
from app import db, app
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
    
    with app.app_context():
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
                    db.session.execute(text("INSERT INTO `tblmenugrp`(`grp`, `dlock`) VALUES('{group}',NOW())".format(group=product['group'])))


                p = db.session.execute(text("SELECT *, `class` as category FROM `item` WHERE `barcode`='{uid}'".format(uid=product['uid']))).fetchone()
                if p is None:
                    classPrinter = db.session.execute(text("SELECT model FROM item WHERE `class`='{cl}' and `model` > '' LIMIT 1".format(cl=product['category']))).fetchone()
                    model = classPrinter.model if classPrinter else ''
                    
                    inserted = db.session.execute(text("""INSERT INTO `item`(`barcode`,    `itemname`,     `shortname`,    `groupid`,      `part`, `class`,    `uom`,      `dlock`,    `amt`,      `taxable`, `model`  ) 
                                                        VALUES  ('{barcode}',   '{itemname}',   '{shortname}',  '{groupid}',    'MENU', '{cl}',     '{unit}',    NOW(),     '{amt}',    1,         '{model}')"""
                                                        .format(barcode=product['uid'], itemname=product['name'], shortname=product['name'], groupid=product['group'], cl=product['category'], unit=product['unit'], amt=product['price'], model=model)))
                    db.session.commit()
                    print("{name} is inserted... with id {id}".format(name=product['name'], id=inserted.lastrowid))
                    p = db.session.execute(text("SELECT *, `class` as category FROM `item` WHERE itemid='{itemid}'".format(itemid=inserted.lastrowid))).fetchone()
                    dlock = db.session.execute(text("SELECT * FROM `itemdlock` WHERE `itemid`='{itemid}'".format(itemid=p.itemid))).fetchone()
                    if dlock:
                        db.session.execute(text("UPDATE `itemdlock` SET `dlock`='{dlock}' WHERE `itemid`='{itemid}'".format(dlock=p.dlock, itemid=p.itemid)))
                    else:
                        db.session.execute(text("INSERT INTO `itemdlock`(`itemid`, `dlock`) VALUES('{itemid}', '{dlock}')".format(itemid=p.itemid, dlock=p.dlock)))
                
                if float(product['price']) != float(p.amt):
                    db.session.execute(text("UPDATE `item` set `amt`='{amt}' WHERE `itemid`='{itemid}'".format(amt=product['price'], itemid=p.itemid)))
                    print("{name} price is updated...".format(name=product['name']))

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
        db.session.execute(text("UPDATE tblmenulist set isinactive=1 WHERE (SELECT count(*) FROM item WHERE iscategory=1 and `class`=tblmenulist.class and isinactive=0) = 0"))

elif action == "sales":
    with app.app_context():

        print("Uploading sales...")
        response = requests.get('https://pp.d3.net/api.php?action=last-sync&branch=' + branch_id, headers=requests_headers)
        print(response.json())
        if response is None:
            exit('Cannot connect...')

        last = dict(response.json())
        if last['code'] != 200:
            exit('Error code: '+str(last['code']))
        
        last_number = ''#last['number']

        sql = text("SELECT * FROM `glhead` WHERE `billnumber`>'' AND `docno` > '{docno}' ORDER BY `docno` ASC".format(docno=last_number))
        sales = []
        for sale in db.session.execute(sql):
            tsql = text("""SELECT g.*,i.barcode 
                                FROM `glstock` as g 
                                LEFT JOIN `item` as i ON i.itemid = g.itemid
                                WHERE g.`trno`=%s""" % sale.trno)
            sales.append(dict({
                'number': sale.docno,
                'created': sale.printtime.strftime("%Y-%m-%d %H:%M:%S") if sale.printtime else '',
                'total': float(sale.amt),
                'remarks': sale.rem,
                'items': [dict({
                    'uid': item.barcode if item.barcode else 0,
                    'name': item.itemname,
                    'amount': float(item.ext),
                    'qty': float(item.isqty),
                    'created': item.createdate.strftime("%Y-%m-%d %H:%M:%S") if item.createdate else ''
                }) for item in db.session.execute(tsql)]
            }))

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