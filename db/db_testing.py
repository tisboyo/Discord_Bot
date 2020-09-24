# -*- coding: utf-8 -*-
"""
Created on Wed Nov 13 16:49:05 2019

@author: Boyo
"""
# Test file for doing manual database queries
import sqlite3

filename = "./378302095633154050.db3"

db = sqlite3.connect(filename)
cursor = db.cursor()

print("Use: cursor.execute(query, values)")
print("result = cursor.fetchall() or cursor.fetchone()")

query = "SELECT * FROM table"
# values = ('*', )

cursor.execute(query)
result = cursor.fetchall()
