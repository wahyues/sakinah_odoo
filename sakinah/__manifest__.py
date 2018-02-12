# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Sakinah Configuration',
    'version': '1',
    'category': 'Sakinah',
    'sequence': 1,
    'summary': 'Konfigurasi untuk aplikasi Sakinah sebelum diinstall',
    'author' : 'Muhammad Miqdad',
    'description': """
Konfigurasi Awal Database
==================================================

Untuk membuat database baru dengan pengaturan yang digunakan oleh Sakinah Kerudung perlu beberapa pengaturan agar sesuai standard.

Dengan menginstal aplikasi ini maka tidak perlu lagi mengubah pengaturan bawaan odoo yang belum sesuai secara satu per satu. Semua pengaturan
Sakinah Kerudung sudah terpasang di dalam aplikasi ini. 

Berikut ini adalah aplikasi yang terinstall otomatis:
---------------------------------------------------------
* Purchase
* Inventory Management
* Accounting
* Sales
    """,
    'website': 'https://www.sakinahkerudung.com',
    'depends': ['purchase', 'sale_contract', 'account_accountant', 'contacts', 'hr_expense'],
    'data': [
            'data/sakinah_config.xml',
    	    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
