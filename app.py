from flask import Flask
from mysql import connector
import requests
import click
from datetime import datetime

db = connector.connect(
    host="localhost",
    user="root",
    password="x1root99",
    database="x-pp",
    port=3306
)


app = Flask(__name__)

@app.route("/")
def hello_world():
    print(db)
    return "<p>Hello, World!</p>"

@app.cli.command()
@click.option('--b')
def scheduled(b):
    # products = requests.get('https://pp.d3.net/api.php?action=products&branch=1154')
    products = requests.get('https://pp.d3.net/api.php?action=products&branch=' + b)
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
            if p:
                if p['amt'] != product['price']:
                    updateItem = db.cursor(prepared=True)
                    updateItem.execute("UPDATE `item` set `amt`=%s WHERE `itemid`=%s",(product['price'], p['itemid']))
                    print('Product price is updated...')

                if p['class'] != product['category']:
                    updateItem = db.cursor(prepared=True)
                    updateItem.execute("UPDATE `item` set `class`=%s WHERE `itemid`=%s",(product['category'], p['itemid']))
                    print('Product price is updated...')

                if p['groupid'] != product['group']:
                    updateItem = db.cursor(prepared=True)
                    updateItem.execute("UPDATE `item` set `groupid`=%s WHERE `itemid`=%s",(product['group'], p['itemid']))
                    print('Product price is updated...')

            else:
                insert = db.cursor(prepared=True)
                insert.execute("""INSERT INTO `item`(`barcode`,   `itemname`,   `shortname`,   `groupid`,    `part`,   `class`,      `amt`,        `uom`,    `dlock`) 
                                            VALUES  (%s,        %s,         %s,          %s,         'MENU',   %s,         %s,         %s,     NOW())""",
                                                    (product['uid'], product['name'], product['name'], product['group'], product['category'], product['price'], product['unit']))
                print('New product inserted...')

