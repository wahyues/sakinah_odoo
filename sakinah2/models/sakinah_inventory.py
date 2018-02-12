# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, AccessError
import time

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare, float_round, float_is_zero
import odoo.addons.decimal_precision as dp

class Sakinah_Users(models.Model):
    _inherit = "res.users"

    warehouses = fields.Many2many('stock.warehouse', 'res_users_stock_warehouse_rel', 'res_users_id', 'stock_warehouse_id', string='Warehouses')

class Sakinah_Warehouse(models.Model):
    _inherit = "stock.warehouse"

    users = fields.Many2many('res.users', 'res_users_stock_warehouse_rel', 'stock_warehouse_id', 'res_users_id', string='Users')

class Sakinah_Location(models.Model):
    _inherit = "stock.location"

    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')

class ProcurementOrder(models.Model):
    _inherit = "procurement.order"

    user_id = fields.Integer('User Id', default=lambda self: self.env.user.id)
    warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse', help="Warehouse to consider for the route selection",
        default=lambda self: self.env['stock.warehouse'].search(['&',('users.id', '=', self.env.user.id),('name','!=','Gudang Pusat')], limit=1).id,
        domain="['&',('users.id','=',user_id),('name','!=','Gudang Pusat')]")
    route_ids = fields.Many2many(
        'stock.location.route', 'stock_location_route_procurement', 'procurement_id', 'route_id', 'Preferred Routes',
        help="Preferred route to be followed by the procurement order. Usually copied from the generating document"\
        " (SO) but could be set up manually.")
    name = fields.Text('Description', default='Isi keterangan warna di sini', required=True)
    remain_qty = fields.Float('Remain Qty', compute="_compute_remaining", store=True)
    product_uom = fields.Many2one(
        'product.uom', 'Product Unit of Measure',
        readonly=True, required=True, domain=[('category_id.id', '=', 1)], 
        states={'confirmed': [('readonly', False)]})

    @api.onchange('warehouse_id')
    def onchange_warehouse_id(self):
        if self.warehouse_id:
            self.location_id = self.warehouse_id.lot_stock_id.id
            self.route_ids = self.warehouse_id.route_ids.search(['&',('name','like','Procurement'),
                ('name','ilike',self.warehouse_id.name)]).ids

    @api.one
    @api.depends('product_qty','move_ids.product_uom_qty')
    def _compute_remaining(self):
        for proc in self:
            total = 0
            for move in proc.move_ids:
                if move.state == 'done':
                    total += move.product_uom_qty
            proc.remain_qty = proc.product_qty - total

class Sakinah_Warehouse_Batch(models.Model):
    _name = "sakinah.warehouse.batch"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = "Sakinah Warehouse Batch"
    _order = "create_date desc"

    name = fields.Char('Batch ID', required=True, index=True, copy=False, default='New')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('wait', 'Waiting for validation'),
        ('done', 'Done')
        ], string='Status', readonly=True, index=True, copy=False, default='draft')
    stock_picking = fields.One2many('stock.picking', 'parent_batch', string='Stock Picking',
        domain=[('picking_type_id.name','in',['Receipts','Finished'])])
    stock_move = fields.One2many('sakinah.stock.batch', 'parent_batch', string='Stock Picking')
    validation_count = fields.Integer('Remaining Transfer', compute='_compute_validation', store=True)
    product_plus = fields.Integer('Transfer', compute='_compute_validation', store=True)

    @api.depends('stock_picking.state', 'stock_move.plus_sum')
    def _compute_validation(self):
        for line in self:
            all_pick = 0
            done_pick = 0
            plus = 0
            for subline in line.stock_picking:
                all_pick += 1
                if subline.state == 'done':
                    done_pick += 1
            line.validation_count = all_pick - done_pick
            for subline in line.stock_move:
                plus += subline.plus_sum
            line.product_plus = plus

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('sakinah.wh.batch') or '/'
        return super(Sakinah_Warehouse_Batch, self).create(vals)

    @api.multi
    def button_done(self):
        for line in self:
            count = 0
            finished = 0
            for subline in line.stock_picking:
                count += 1
                if subline.state == 'done':
                    finished += 1
            if count == finished:
                self.write({'state': 'done'})
            else:
                raise UserError(_('Tidak dapat menyelesaikan transaksi'\
                    ' jika masih ada transfer yang belum berstatus (done)'))

    @api.multi
    def action_view_picking(self):
        action = self.env.ref('stock.action_picking_tree_all')
        result = action.read()[0]
        result['domain'] = "[('id', 'in', " + str(self.stock_picking.ids) + ")]"
        return result

    @api.multi
    def action_view_pack(self):
        action = self.env.ref('sakinah2.sakinah_st_batch')
        result = action.read()[0]
        result['domain'] = "[('id', 'in', " + str(self.stock_move.ids) + "),('count','!=',0)]"
        return result

class Sakinah_Stock_Batch(models.Model):
    _name = "sakinah.stock.batch"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = "Sakinah Stock Batch"

    name = fields.Char('Product', index=True, related='product_id.name')
    product_id = fields.Many2one('product.product', 'Product', ondelete="cascade")
    parent_batch = fields.Many2one('sakinah.warehouse.batch', string='Batch')
    stock_pack = fields.One2many('stock.pack.operation', 'child_batch', string='Stock Move', domain=[('picking_id.picking_type_id.name','in',['Receipts','Finished'])])
    count = fields.Integer('Count', compute='_compute', store=True)
    plus_sum = fields.Integer('Total Plus', compute='_compute', store=True)
    begining = fields.Integer('Begining', compute='_compute_data', store=True)
    shipped = fields.Integer('+ Shipped', compute='_compute_data', store=True)
    ending = fields.Integer('Ending =', compute='_compute_ending', store=True)
    real = fields.Integer('Real', compute='_compute_data', store=True)
    remaining = fields.Integer('In Transit', compute='_compute_ending')

    @api.depends('stock_pack.difference', 'stock_pack.state')
    def _compute(self):
        for line in self:
            count = 0
            result = 0
            for subline in line.stock_pack:
                count += 1
                if subline.state == 'done' and subline.picking_id.picking_type_id.priority not in (0, 1, 100):
                    result += subline.difference
                elif subline.difference > 0 and subline.state != 'done' and subline.picking_id.picking_type_id.priority not in (0, 1, 100):
                    result += subline.difference
            line.plus_sum = result
            line.count = count

    @api.depends('stock_pack')
    def _compute_data(self):
        for line in self:
            real = 0
            begining = 0
            shipped = 0
            for subline in line.stock_pack:
                if subline.picking_id.picking_type_id.priority == 1:
                    begining += subline.qty_done
                elif subline.picking_id.picking_type_id.priority == 100:
                    real += subline.qty_done
                elif subline.picking_id.picking_type_id.priority != 0:
                    shipped += subline.qty_done
            line.begining = begining
            line.shipped = shipped
            line.real = real

    @api.depends('stock_pack')
    def _compute_ending(self):
        for line in self:
            line.ending = line.begining - line.shipped
            line.remaining = line. ending - line.real

class Sakinah_StockBackorderConfirmation(models.TransientModel):
    _inherit = 'stock.backorder.confirmation'

    location_id = fields.Integer(related='pick_id.location_id.id')

    @api.one
    def _process(self, cancel_backorder=False):
        operations_to_delete = self.pick_id.pack_operation_ids.filtered(lambda o: o.qty_done <= 0)
        for pack in self.pick_id.pack_operation_ids - operations_to_delete:
            pack.begining_qty = pack.product_qty
            print("not zero")
            print(pack.begining_qty)
            pack.product_qty = pack.qty_done
            print(pack.product_qty)

        operations_to_delete.unlink()
        self.pick_id.do_transfer()
        if cancel_backorder:
            backorder_pick = self.env['stock.picking'].search([('backorder_id', '=', self.pick_id.id)])
            backorder_pick.action_cancel()
            self.pick_id.message_post(body=_("Back order <em>%s</em> <b>cancelled</b>.") % (backorder_pick.name))

class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.onchange('barcode')
    def _onchange_barcode(self):
        if self.barcode:
            self.default_code = self.barcode
            