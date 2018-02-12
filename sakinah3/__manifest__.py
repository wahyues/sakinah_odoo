# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Sakinah Kerudung2',
    'version': '1',
    'category': 'Sakinah',
    'sequence': 3,
    'summary': 'Mudul pelengkap untuk internal Sakinah Kerudung',
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
    'depends': ['sakinah', 'sakinah2', 'point_of_sale'],
    'data': [
            'data/sakinah_externalid.xml',
            'data/sakinah_picking.xml',
            'data/sakinah_route.xml',
            'data/sakinah_rule1.xml',
            'data/sakinah_rule2.xml',
            'data/sakinah_rule3.xml',
            'data/sakinah_location.xml',
            'data/sakinah_journals.xml',
            'data/sakinah_pos_conf.xml',
            'views/s_pos_session.xml',
            'views/s_expenses_views.xml'
    	    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
