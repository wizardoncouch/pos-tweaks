from flask import Flask
from mysql import connector
import requests
import json
from datetime import datetime

db = connector.connect(
    host="localhost",
    user="root",
    password="mjm",
    database="lite",
    port=3309
)


app = Flask(__name__)

@app.route("/")
def hello_world():
    print(db)
    return "<p>Hello, World!</p>"

@app.cli.command()
def scheduled():

    print('Importing products...')

    # products = requests.get('https://pp.d3.net/api.php?action=products&branch=1154')
    products = requests.get('https://pp.d3.net/api.php?action=products&branch=1361')
    if products:
        for product in products.json():

            checkCategory = db.cursor()
            checkCategory.execute("SELECT count(*) FROM tblmenulist WHERE `class`='{category}' and iscategory=1".format(category=product['category']))
            category = checkCategory.fetchone()
            if category[0] == 0:
                insertCategory = db.cursor()
                insertCategory.execute("""INSERT INTO tblmenulist   (`class`, `iscategory`, `skincolor`, `fontcolor`, `dlock`) 
                                                        VALUES      ('{name}','{iscategory}','{skincolor}','{fontcolor}',NOW())""".format(
                    name=product['category'], 
                    iscategory=1, 
                    skincolor='-8355712',
                    fontcolor='-16777216',
                    )
                )

            checkGroup = db.cursor()
            checkGroup.execute("SELECT count(*) FROM `tblmenugrp` WHERE `grp`='{group}'".format(group=product['group']))
            group = checkGroup.fetchone()
            if group[0] == 0:
                inserGroup = db.cursor()
                inserGroup.execute("INSERT INTO `tblmenugrp`(`grp`, `dlock`) VALUES('{name}',NOW())".format(name=product['group']))


            fetchItem = db.cursor(dictionary=True)
            fetchItem.execute("SELECT * FROM `item` WHERE `barcode`='{uid}'".format(uid=product['uid']))
            p = fetchItem.fetchone()
            if p and p['amt'] != product['price']:
                    updateItem = db.cursor()
                    updateItem.execute("UPDATE `item` set `amt`='{price}' WHERE `uid`='{uid}'".format(price=product['price'], uid=p['uid']))
                    print('Product updated...')
            if p is None:
                insert = db.cursor()
                insert.execute("""INSERT INTO `item`(`barcode`,   `itemname`,   `shortname`,   `groupid`,    `part`,   `class`,      `amt`,        `uom`,    `dlock`) 
                                            VALUES('{barcode}',   '{name}',     {name},        '{group}',    '{part}', '{category}', '{price}',    '{unit}', NOW())""".format(
                                                barcode=product['uid'], 
                                                name=product['name'], 
                                                category=product['category'], 
                                                group=product['group'], 
                                                price=product['price'],
                                                unit=product['unit']
                                            )
                                        )
                print('New product inserted...')

