# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, AccessError, ValidationError
import time

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare, float_round, float_is_zero
import odoo.addons.decimal_precision as dp

# class SupplierInfo ini untuk mengoveride modul agar pada saat purchase otomatis bisa 
# menambah pricelist pada produk sesuai dengan UoM nya
class Sakinah_SupplierInfo(models.Model):
    _inherit = "product.supplierinfo"

    product_uom = fields.Many2one('product.uom', 'Vendor Unit of Measure', readonly="1", related='',
        help="This comes from the product form.")

class Sakinah_PurchaseOrder(models.Model):
    _inherit = "purchase.order"
    
    @api.depends('picking_ids', 'picking_ids.state')
    def _compute_is_shipped(self):
        for order in self:
            for pick in order.picking_ids:
                if pick.location_id.id == 8 and pick.state == 'done':
                    order.is_shipped = True
            if order.picking_ids and all([x.state == 'done' for x in order.picking_ids]):
                order.is_shipped = True

    invoice_document = fields.Many2many('ir.attachment', string='Invoice', attachment=True, help='Masukkan foto atau dokumen faktur pembelian', required=True)
    date_planned = fields.Datetime(string='Scheduled Date', compute='_compute_date_planned', store=True, index=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'RFQ Sent'),
        ('to approve', 'To Approve'),
        ('purchase', 'Purchase Order'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
        ], string='Status', readonly=True, index=True, copy=False, default='draft', track_visibility='onchange')
    is_shipped = fields.Boolean(compute="_compute_is_shipped", store=True, index=True)

    @api.depends('order_line.date_planned')
    def _compute_date_planned(self):
        for order in self:
            min_date = False
            for line in order.order_line:
                if not min_date or line.date_planned < min_date:
                    min_date = line.date_planned
            if min_date:
                order.date_planned = min_date
            else:
            	order.date_planned = datetime.strptime(order.date_order, "%Y-%m-%d %H:%M:%S") + timedelta(days=10)

    @api.multi
    def button_confirm(self):
        for order in self:
            total = 0
            for line in order.order_line:
                total = total + line.product_qty

            if order.state not in ['draft', 'sent'] or total == 0:
                raise UserError(_('Pembelian tidak dapat dikonfirmasi jika tidak ada barang yang diinput')) 
                continue
            order._add_supplier_to_product()
            # Deal with double validation process
            if order.company_id.po_double_validation == 'one_step'\
                    or (order.company_id.po_double_validation == 'two_step'\
                        and order.amount_total < self.env.user.company_id.currency_id.compute(order.company_id.po_double_validation_amount, order.currency_id))\
                    or order.user_has_groups('purchase.group_purchase_manager'):
                order.button_approve()
            else:
                order.write({'state': 'to approve'})
        return True

    @api.multi
    def button_done(self):
        for order in self:
            clear = 0
            qty_received = 0
            for line in order.order_line:
                qty_received += line.qty_received
                if (line.qty_received - line.qty_invoiced) != 0:
                    clear = clear + 1
            if clear == 0 and qty_received > 0:
                order.write({'state': 'done'})
            elif qty_received == 0:
                raise UserError(_('Tidak dapat menyelesaikan transaksi'\
                    ' jika belum ada penerimaan barang oleh bagian gudang'))
            else:
                raise UserError(_('Tidak dapat menyelesaikan transaksi'\
                    ' jika masih ada selisih antara jumlah yang diterima dengan jumlah yang telah dibayar'))

    @api.one
    def _add_supplier_to_product(self):
        # Add the partner in the supplier list of the product if the supplier is not registered for
        # this product. We limit to 10 the number of suppliers for a product to avoid the mess that
        # could be caused for some generic products ("Miscellaneous").
        for line in self.order_line:
            # Do not add a contact as a supplier
            partner = self.partner_id if not self.partner_id.parent_id else self.partner_id.parent_id
            if partner not in line.product_id.seller_ids.mapped('name') and len(line.product_id.seller_ids) <= 10:
                currency = partner.property_purchase_currency_id or self.env.user.company_id.currency_id
                supplierinfo = {
                    'name': partner.id,
                    'sequence': max(line.product_id.seller_ids.mapped('sequence')) + 1 if line.product_id.seller_ids else 1,
                    'product_uom': line.product_uom.id,
                    'min_qty': 0.0,
                    'price': self.currency_id.compute(line.price_unit, currency),
                    'currency_id': currency.id,
                    'delay': 0,
                }
                vals = {
                    'seller_ids': [(0, 0, supplierinfo)],
                }
                try:
                    line.product_id.write(vals)
                except AccessError:  # no write access rights -> just ignore
                    break

            for sup in line.product_id.seller_ids:
                
                if partner in sup.mapped('name') and line.price_unit != sup.price:
                    
                    currency = partner.property_purchase_currency_id or self.env.user.company_id.currency_id
                    supplierinfo = {
                            'name': partner.id,
                            'product_uom': line.product_uom.id,
                            'min_qty': 0.0,
                            'price': self.currency_id.compute(line.price_unit, currency),
                            'currency_id': currency.id,
                            'delay': 0,
                    }
                    try:
                        sup.write(supplierinfo)
                    except AccessError:
                        break

class Sakinah_PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.depends('product_qty', 'price_unit', 'taxes_id')
    def _compute_amount(self):
        for line in self:
            taxes = line.taxes_id.compute_all(line.price_unit, line.order_id.currency_id, line.product_qty, product=line.product_id, partner=line.order_id.partner_id)
            line.update({
                'price_tax': taxes['total_included'] - taxes['total_excluded'],
                'price_total': taxes['total_included'],
            })    

    product_uom = fields.Many2one('product.uom', string='Product Unit of Measure', domain=[('category_id.id', '=', 1)], required=True)
    price_subtotal = fields.Monetary(compute='', string='Subtotal', store=True)
    price_unit = fields.Float(compute='_compute_unit_price', string='Unit Price', 
        required=True, digits=dp.get_precision('Product Price'))
    product_qty = fields.Float(string='Quantity', digits=dp.get_precision('Product Unit of Measure'), required=True)

    @api.onchange('product_qty')
    def _onchange_quantity2(self):
        for line in self:
            if line.product_qty != 0 and line.price_unit != 0:
                line.price_subtotal = line.price_unit * line.product_qty

    @api.onchange('price_subtotal')
    def _compute_unit_price(self):
        for line in self:
            if line.price_subtotal != 0:
                if line.product_qty == 0:
                    line.product_qty = 1
                line.price_unit = line.price_subtotal/line.product_qty

    @api.onchange('product_uom')
    def _onchange_quantity(self):
        if not self.product_id:
            return

        seller = self.product_id._select_seller(
            partner_id=self.partner_id,
            quantity=self.product_qty,
            date=self.order_id.date_order and self.order_id.date_order[:10],
            uom_id=self.product_uom)

        if seller or not self.date_planned:
            self.date_planned = self._get_date_planned(seller).strftime(DEFAULT_SERVER_DATETIME_FORMAT)

        if not seller:
            return

        price_unit = self.env['account.tax']._fix_tax_included_price_company(seller.price, self.product_id.supplier_taxes_id, self.taxes_id, self.company_id) if seller else 0.0
        if price_unit and seller and self.order_id.currency_id and seller.currency_id != self.order_id.currency_id:
            price_unit = seller.currency_id.compute(price_unit, self.order_id.currency_id)

        if seller and self.product_uom and seller.product_uom != self.product_uom:
            price_unit = seller.product_uom._compute_price(price_unit, self.product_uom)

        self.price_unit = price_unit
        self.price_subtotal = price_unit * self.product_qty

    @api.one
    @api.constrains('product_qty', 'price_subtotal')
    def _check_amount(self):
        if self.product_qty <= 0.0 or self.price_subtotal <= 0.0:
            raise ValidationError(_('Product quantity and Subtotal amount must be strictly positive.'))
