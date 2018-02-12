# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Sakinah Kerudung',
    'version': '1',
    'category': 'Sakinah',
    'sequence': 2,
    'summary': 'Modul pelengkap untuk internal Sakinah Kerudung',
    'author' : 'Muhammad Miqdad',
    'description': """
Manage goods requirement by Purchase Orders easily
==================================================

Purchase management enables you to track your vendors' price quotations and convert them into purchase orders if necessary.
Odoo has several methods of monitoring invoices and tracking the receipt of ordered goods. You can handle partial deliveries in Odoo, so you can keep track of items that are still to be delivered in your orders, and you can issue reminders automatically.

Odoo's replenishment management rules enable the system to generate draft purchase orders automatically, or you can configure it to run a lean process driven entirely by current production needs.

Dashboard / Reports for Purchase Management will include:
---------------------------------------------------------
* Request for Quotations
* Purchase Orders Waiting Approval
* Monthly Purchases by Category
* Receipt Analysis
* Purchase Analysis
    """,
    'website': 'https://www.sakinahkerudung.com',
    'depends': ['purchase', 'stock', 'procurement', 'point_of_sale'],
    'data': [
            'security/sakinah_security.xml',
            'security/ir.model.access.csv',
            'views/s_account_views.xml',
            'views/s_purchase_views.xml',
            'views/s_inventory_views.xml',
            'views/s_user_contact.xml',
            'data/sakinah_company.xml',
            'data/sakinah_accounts.xml',
            'data/sakinah_users.xml',
            'data/sakinah_warehouses.xml',
            'data/sakinah_sequences.xml',
            'data/sakinah_uom.xml',
            'data/sakinah_journals.xml',
            'data/sakinah_pos_conf.xml',
            'data/sakinah_employees.xml'
    	    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
