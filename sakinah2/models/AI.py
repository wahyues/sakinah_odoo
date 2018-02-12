# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, AccessError

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

class Stock_Distribution_AI(models.Model):
    _name = "stock.distribution.ai"
    _description = "Artificial Inteligence for Distirbution"

    name = fields.Char('Product', index=True, related='product_id.name')
    location_id = fields.Many2one('stock.location', 'Location', index=True, required=True)
    product_id = fields.Many2one('product.product', 'Product', ondelete="cascade")
    stock_available = fields.Integer()
    stock_remaining = fields.Integer()
    stock_procured = fields.Integer()
    last_month_sale = fields.Integer()
    calculation = fields.Float()

    @api.multi
    def _compute_available(self):
        for line in self:
            quants = self.env['stock.quant'].search([('location_id', '=', self.location_id.id), ('product_id', '=', self.product_id.id)])
            theoretical_qty = sum([x.qty for x in quants])
            line.stock_remaining = theoretical_qty

    
    
    