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

import sys

class Sakinah_Move(models.Model):
    _inherit = "stock.move"

    move_type = fields.Selection([
        ('in', 'Income'),
        ('internal', 'Internal'),
        ('out', 'Outcome')
        ], string='Move Type', readonly=True, index=True, copy=False, compute='_compute_move_type', default='internal')

    @api.depends('location_id.usage', 'location_dest_id.usage')
    def _compute_move_type(self):
        for move in self:
            if move.location_id.usage == 'internal' and move.location_dest_id.usage != 'internal':
                move.move_type = 'out'
            elif move.location_id.usage != 'internal' and move.location_dest_id.usage == 'internal':
                move.move_type = 'in'
            else:
                move.move_type = 'internal'

    @api.multi
    def split_down(self, qty, restrict_lot_id=False, restrict_partner_id=False):
        self = self.with_prefetch() # This makes the ORM only look for one record and not 300 at a time, which improves performance
        if self.state in ('done', 'cancel'):
            raise UserError(_('You cannot split a move done'))
        elif self.state == 'draft':
            raise UserError(_('You cannot split a draft move. It needs to be confirmed first.'))
        if float_is_zero(qty, precision_rounding=self.product_id.uom_id.rounding) or self.product_qty <= qty:
            return self.id
        uom_qty = self.product_id.uom_id._compute_quantity(qty, self.product_uom, rounding_method='HALF-UP')
        defaults = {
            'product_uom_qty': uom_qty,
            'procure_method': 'make_to_stock',
            'restrict_lot_id': restrict_lot_id,
            'split_from': self.id,
            'procurement_id': self.procurement_id.id,
            'move_dest_id': self.move_dest_id.id,
            'origin_returned_move_id': self.origin_returned_move_id.id,
        }
        if restrict_partner_id:
            defaults['restrict_partner_id'] = restrict_partner_id
        if self.env.context.get('source_location_id'):
            defaults['location_id'] = self.env.context['source_location_id']
        new_move = self.with_context(rounding_method='HALF-UP').copy(defaults)
        self.with_context(do_not_propagate=True, rounding_method='HALF-UP').write({'product_uom_qty': self.product_uom_qty - uom_qty})
        
        if self.move_dest_id and self.propagate and self.move_dest_id.state not in ('done', 'cancel'):
            new_move_prop = self.move_dest_id.split_down(qty)
            new_move.write({'move_dest_id': new_move_prop})
        new_move.action_confirm()
        
        return new_move.id

    @api.multi
    def split(self, qty, restrict_lot_id=False, restrict_partner_id=False):
        """ Splits qty from move move into a new move

        :param qty: float. quantity to split (given in product UoM)
        :param restrict_lot_id: optional production lot that can be given in order to force the new move to restrict its choice of quants to this lot.
        :param restrict_partner_id: optional partner that can be given in order to force the new move to restrict its choice of quants to the ones belonging to this partner.
        :param context: dictionay. can contains the special key 'source_location_id' in order to force the source location when copying the move
        :returns: id of the backorder move created """
        self = self.with_prefetch() # This makes the ORM only look for one record and not 300 at a time, which improves performance
        if self.state in ('done', 'cancel'):
            raise UserError(_('You cannot split a move done'))
        elif self.state == 'draft':
            # we restrict the split of a draft move because if not confirmed yet, it may be replaced by several other moves in
            # case of phantom bom (with mrp module). And we don't want to deal with this complexity by copying the product that will explode.
            raise UserError(_('You cannot split a draft move. It needs to be confirmed first.'))
        if float_is_zero(qty, precision_rounding=self.product_id.uom_id.rounding) or self.product_qty <= qty:
            return self.id
        # HALF-UP rounding as only rounding errors will be because of propagation of error from default UoM
        uom_qty = self.product_id.uom_id._compute_quantity(qty, self.product_uom, rounding_method='HALF-UP')
        defaults = {
            'product_uom_qty': uom_qty,
            'procure_method': 'make_to_stock',
            'restrict_lot_id': restrict_lot_id,
            'split_from': self.id,
            'procurement_id': self.procurement_id.id,
            'move_dest_id': self.move_dest_id.id,
            'origin_returned_move_id': self.origin_returned_move_id.id,
        }
        
        if restrict_partner_id:
            defaults['restrict_partner_id'] = restrict_partner_id

        # TDE CLEANME: remove context key + add as parameter
        if self.env.context.get('source_location_id'):
            defaults['location_id'] = self.env.context['source_location_id']
        new_move = self.with_context(rounding_method='HALF-UP').copy(defaults)    
        # ctx = context.copy()
        # TDE CLEANME: used only in write in this file, to clean
        # ctx['do_not_propagate'] = True
        self.with_context(do_not_propagate=True, rounding_method='HALF-UP').write({'product_uom_qty': self.product_uom_qty - uom_qty})
        
        if self.move_dest_id and self.propagate and self.move_dest_id.state not in ('done', 'cancel'):
            new_move_prop = self.move_dest_id.split_down(qty)
            new_move.write({'move_dest_id': new_move_prop})
        # returning the first element of list returned by action_confirm is ok because we checked it wouldn't be exploded (and
        # thus the result of action_confirm should always be a list of 1 element length)
        if len(self.move_orig_ids.ids) == 1:
            new_move_prop = self.move_orig_ids[0].split_up(qty)
            new_move.write({'move_orig_ids': [(4, new_move_prop)]})
        # TDE FIXME: due to action confirm change
        new_move.action_confirm()
        return new_move.id

    @api.multi
    def split_up(self, qty, restrict_lot_id=False, restrict_partner_id=False):
        self = self.with_prefetch() # This makes the ORM only look for one record and not 300 at a time, which improves performance
        if self.state == 'draft':
            raise UserError(_('You cannot split a draft move. It needs to be confirmed first.'))
        if float_is_zero(qty, precision_rounding=self.product_id.uom_id.rounding) or self.product_qty <= qty:
            return self.id
        uom_qty = self.product_id.uom_id._compute_quantity(qty, self.product_uom, rounding_method='HALF-UP')
        defaults = {
            'product_uom_qty': uom_qty,
            'procure_method': 'make_to_stock',
            'restrict_lot_id': restrict_lot_id,
            'picking_id': '',
            'state': 'confirmed',
            'origin_returned_move_id': self.origin_returned_move_id.id,
        }
        if restrict_partner_id:
            defaults['restrict_partner_id'] = restrict_partner_id
        if self.env.context.get('source_location_id'):
            defaults['location_id'] = self.env.context['source_location_id']
        new_move = self.with_context(rounding_method='HALF-UP').copy(defaults)
        
        if len(self.move_orig_ids.ids) == 1:
            new_move_prop = self.move_orig_ids[0].split_up(qty)
            new_move.write({'move_orig_ids': [(4, new_move_prop)]})
        new_move.assign_picking()
        
        return new_move.id

    @api.multi
    def action_done(self):
        super(Sakinah_Move, self).action_done()
        
        for move in self:
            procurements = self.env['procurement.order'].search([('id', '=', move.procurement_id.id)])
            if procurements:
                for proc in procurements:
                    total = 0
                    
                    if move.state == 'done':
                        total += move.product_uom_qty
                    qty = proc.product_qty - total

                    proc.write({'remain_qty': qty})

    @api.one
    @api.constrains('product_uom_qty')
    def _check_amount(self):
        if self.product_uom_qty <= 0.0:
            raise ValidationError(_('Move product quantity amount must be strictly positive.'))
        

    def _get_new_picking_values(self):
        """ Prepares a new picking for this move as it could not be assigned to
        another picking. This method is designed to be inherited. """
        
        parent = self.env['stock.picking'].search([('state','=','confirmed'),('picking_type_id.warehouse_id.id','=',self.picking_type_id.warehouse_id.id)])

        return {
            'origin': self.origin,
            'company_id': self.company_id.id,
            'move_type': self.group_id and self.group_id.move_type or 'direct',
            'partner_id': self.partner_id.id,
            'picking_type_id': self.picking_type_id.id,
            'location_id': self.location_id.id,
            'location_dest_id': self.location_dest_id.id,
            'parent_batch': parent.parent_batch.id
        }

        _prepare_picking_assign = _get_new_picking_values

class Sakinah_PackOperation(models.Model):
    _inherit = "stock.pack.operation"

    difference = fields.Integer(string='Difference', store=True, compute='_compute_diff')
    begining_qty = fields.Integer('Begining Qty')
    to_do = fields.Integer('To Do', compute='_compute_todo')
    child_batch = fields.Many2one('sakinah.stock.batch', string='Batch')
    is_admin = fields.Boolean(string='Is Admin', compute='_compute_user_id')
    location_dest_id = fields.Many2one(related='picking_id.location_dest_id', string='Location Destination Id')
    location_id = fields.Many2one(related='picking_id.location_id', string='Location Id')
    location_id_name = fields.Char(related='location_id.name', string='Id')
    hide_validate = fields.Boolean(compute='_compute_dest', string='Hide Validate')

    @api.multi
    def _compute_user_id(self):
        for pack in self:
            if pack.env.uid == 1:
                pack.is_admin = True
            else:
                pack.is_admin = False

    @api.depends('location_dest_id.warehouse_id.users')
    def _compute_dest(self):
        for pack in self:
            presence = 0
            for line in pack.location_dest_id.warehouse_id.users:
                if line.id == self.env.user.id:
                    presence += 1
    
            if presence != 0:
                pack.hide_validate = False
            else:
                pack.hide_validate = True

    @api.depends('qty_done','begining_qty','product_qty')
    def _compute_diff(self):
        for line in self:
            if line.begining_qty == 0:
                line.difference = line.qty_done - line.product_qty
            else:
                line.difference = line.qty_done - line.begining_qty

    @api.depends('begining_qty','product_qty')
    def _compute_todo(self):
        for line in self:
            if line.begining_qty == 0:
                line.to_do = line.product_qty
            else:
                line.to_do = line.begining_qty

    @api.one
    @api.constrains('product_qty', 'qty_done')
    def _check_amount(self):
        if self.product_qty <= 0.0 or self.qty_done < 0.0:
            raise ValidationError(_('Pack product quantity and Done quantity amount must be strictly positive.'))

class PickingType(models.Model):
    _inherit = "stock.picking.type"

    priority = fields.Integer('Priority', required=True)

class Sakinah_Picking(models.Model):
    _inherit = "stock.picking"
    _order = "picking_code asc, date desc"

    @api.model
    def _default_loc(self):
        user = self.env.user.id
        location = self.env['stock.location'].search([('warehouse_id.users.id','=',user)], limit=1).id
        return location

    user_id = fields.Integer("User Id", compute='_compute_user_id')
    location_id = fields.Many2one(
        'stock.location', "Source Location Zone",
        default=_default_loc,
        readonly=True, required=True,
        domain="[('warehouse_id.users.id','=',uid)]",
        states={'draft': [('readonly', False)]})
    parent_batch = fields.Many2one('sakinah.warehouse.batch', string='Batch', copy=False, domain=[('state','!=','done')])
    picking_code = fields.Integer(related="picking_type_id.priority", string="Picking Code", store=True)
    hide_validate = fields.Boolean('Hide Validate', compute='_compute_dest')

    @api.multi
    def _compute_user_id(self):
        for pick in self:
            pick.user_id = pick.env.uid

    @api.depends('location_dest_id.warehouse_id.users')
    def _compute_dest(self):
        for pick in self:
            presence = 0
            for line in pick.location_dest_id.warehouse_id.users:
                if line.id == self.env.user.id:
                    presence += 1
    
            if presence != 0:
                pick.hide_validate = False
            else:
                pick.hide_validate = True

    @api.model
    def create(self, vals):
        # TDE FIXME: clean that brol
        defaults = self.default_get(['name', 'picking_type_id'])
        if vals.get('name', '/') == '/' and defaults.get('name', '/') == '/' and vals.get('picking_type_id', defaults.get('picking_type_id')):
            vals['name'] = self.env['stock.picking.type'].browse(vals.get('picking_type_id', defaults.get('picking_type_id'))).sequence_id.next_by_id()

        # TDE FIXME: what ?
        # As the on_change in one2many list is WIP, we will overwrite the locations on the stock moves here
        # As it is a create the format will be a list of (0, 0, dict)
        if vals.get('move_lines') and vals.get('location_id') and vals.get('location_dest_id'):
            for move in vals['move_lines']:
                if len(move) == 3:
                    move[2]['location_id'] = vals['location_id']
                    move[2]['location_dest_id'] = vals['location_dest_id']
        
        return super(Sakinah_Picking, self).create(vals)

    @api.multi
    def write(self, vals):
        res = super(Sakinah_Picking, self).write(vals)
        # Change locations of moves if those of the picking change
        after_vals = {}
        if vals.get('location_id'):
            after_vals['location_id'] = vals['location_id']
        if vals.get('location_dest_id'):
            after_vals['location_dest_id'] = vals['location_dest_id']
        if after_vals:
            self.mapped('move_lines').filtered(lambda move: not move.scrapped).write(after_vals)

        if self.parent_batch:
            for line in self.pack_operation_ids:
                stock_batch =[]
                for product in self.env['sakinah.stock.batch'].search([('parent_batch.id','=',self.parent_batch.id)]):
                    stock_batch.append(product.product_id.id)
                if line.product_id.id in stock_batch:
                    line.child_batch = self.env['sakinah.stock.batch'].search([('product_id.id','=',line.product_id.id),('parent_batch.id','=',self.parent_batch.id)]).id
                else:
                    line.env['sakinah.stock.batch'].create({'product_id': line.product_id.id, 'parent_batch': self.parent_batch.id})
                    line.child_batch = self.env['sakinah.stock.batch'].search([('product_id.id','=',line.product_id.id),('parent_batch.id','=',self.parent_batch.id)]).id
        
        return res

    @api.multi
    def action_cancel(self):
        self.mapped('move_lines').action_cancel()
        if not self.move_lines:
            self.write({'state': 'cancel'})
        return True

    @api.onchange('parent_batch')
    def onchange_parent_batch(self):
        parent = self.env['stock.picking'].search([('state','=','waiting'),
            ('picking_type_id.warehouse_id.id','=',self.picking_type_id.warehouse_id.id)])
        if not parent.parent_batch:
            parent.write({'parent_batch': self.parent_batch.id})

    @api.onchange('location_dest_id')
    def onchange_location_dest_id(self):
        if self.location_dest_id:
            location_dest_id = self.location_dest_id.id
            picking_type_id = self.env['stock.picking.type'].\
            search(['&',('default_location_src_id','=',False),('default_location_dest_id.id','=',location_dest_id)]).id
            if location_dest_id == self.env.ref('stock.stock_location_stock').id:
                picking_type_id = self.env.ref('stock.picking_type_in').id
            if picking_type_id:
                self.picking_type_id = picking_type_id

    @api.onchange('partner_id')
    def onchange_picking_type(self):
        # TDE CLEANME move into onchange_partner_id
        if self.partner_id:
            if self.partner_id.picking_warn == 'no-message' and self.partner_id.parent_id:
                partner = self.partner_id.parent_id
            elif self.partner_id.picking_warn not in ('no-message', 'block') and self.partner_id.parent_id.picking_warn == 'block':
                partner = self.partner_id.parent_id
            else:
                partner = self.partner_id
            if partner.picking_warn != 'no-message':
                if partner.picking_warn == 'block':
                    self.partner_id = False
                return {'warning': {
                    'title': ("Warning for %s") % partner.name,
                    'message': partner.picking_warn_msg
                }}

    @api.multi
    def do_new_transfer(self):
        for pick in self:
            if pick.state == 'done':
                raise UserError(_('The pick is already validated'))
            pack_operations_delete = self.env['stock.pack.operation']
            if not pick.move_lines and not pick.pack_operation_ids:
                raise UserError(_('Please create some Initial Demand or Mark as Todo and create some Operations. '))

            print(pick.check_zero())

            if pick.check_zero():
                view = self.env.ref('stock.view_backorder_confirmation')
                wiz = self.env['stock.backorder.confirmation'].create({'pick_id': pick.id})
                    # TDE FIXME: same reamrk as above actually
                return {
                    'name': _('Create Backorder?'),
                    'type': 'ir.actions.act_window',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'stock.backorder.confirmation',
                    'views': [(view.id, 'form')],
                    'view_id': view.id,
                    'target': 'new',
                    'res_id': wiz.id,
                    'context': self.env.context,
                }

            # In draft or with no pack operations edited yet, ask if we can just do everything
            if pick.state == 'draft' or all([x.qty_done == 0.0 for x in pick.pack_operation_ids]):
                # If no lots when needed, raise error
                picking_type = pick.picking_type_id
                if (picking_type.use_create_lots or picking_type.use_existing_lots):
                    for pack in pick.pack_operation_ids:
                        if pack.product_id and pack.product_id.tracking != 'none':
                            raise UserError(_('Some products require lots/serial numbers, so you need to specify those first!'))
                view = self.env.ref('stock.view_immediate_transfer')
                wiz = self.env['stock.immediate.transfer'].create({'pick_id': pick.id})
                # TDE FIXME: a return in a loop, what a good idea. Really.
                return {
                    'name': _('Immediate Transfer?'),
                    'type': 'ir.actions.act_window',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'stock.immediate.transfer',
                    'views': [(view.id, 'form')],
                    'view_id': view.id,
                    'target': 'new',
                    'res_id': wiz.id,
                    'context': self.env.context,
                }
                # TDE FIXME: a return in a loop, what a good idea. Really.

            # Untuk stock picking yang pengirimannya bukan dari vendor tidak bisa validate jika penerimaan kurang dari yang seharusnya
            product = []
            count = 0
            for pack in pick.pack_operation_ids:
                if pack.child_batch.plus_sum < -pack.difference and not (pick.picking_code == 1 or pick.picking_type_id.name == "Internal Transfers"):
                    count += 1
                    product.append(pack.product_id.name)
            product_list = ', '.join(product)
            if count > 0:
                raise UserError(_('Tidak bisa memproses transaksi minus untuk barang berikut ini: %s jika belum ditemukan'\
                    ' transaksi plus pada cabang lain dengan jumlah yang memadai. Silahkan tunggu beberapa saat atau hubungi kantor pusat.' % (product_list)))

            # Check backorder should check for other barcodes
            if pick.check_backorder():
                view = self.env.ref('stock.view_backorder_confirmation')
                wiz = self.env['stock.backorder.confirmation'].create({'pick_id': pick.id})
                # TDE FIXME: same reamrk as above actually
                return {
                    'name': _('Create Backorder?'),
                    'type': 'ir.actions.act_window',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'stock.backorder.confirmation',
                    'views': [(view.id, 'form')],
                    'view_id': view.id,
                    'target': 'new',
                    'res_id': wiz.id,
                    'context': self.env.context,
                }

            for operation in pick.pack_operation_ids:
                product_qty = operation.product_qty
                if operation.qty_done < 0:
                    raise UserError(_('No negative quantities allowed'))
                if operation.qty_done > 0:
                    operation.write({'begining_qty': product_qty})
                    operation.write({'product_qty': operation.qty_done})
                else:
                    pack_operations_delete |= operation
            if pack_operations_delete:
                pack_operations_delete.unlink()

        self.do_transfer()

        return

    def check_backorder(self):
        need_rereserve, all_op_processed = self.picking_recompute_remaining_quantities(done_qtys=True)
        for move in self.move_lines:
            if float_compare(move.remaining_qty, 0, precision_rounding=move.product_id.uom_id.rounding) != 0:
                return True
        return False

    def check_zero(self):
        for pack in self.pack_operation_ids:
            quants = self.env['stock.quant'].search([('product_id', '=', pack.product_id.id), ('location_id', '=', self.location_id.id)])
            if not quants:
                return True
            for quant in quants:
                if pack.qty_done == 0 and quant.qty == 0:
                    return True
        return False

    @api.multi
    def do_transfer(self):
        """ If no pack operation, we do simple action_done of the picking.
        Otherwise, do the pack operations. """
        # TDE CLEAN ME: reclean me, please
        self._create_lots_for_picking()

        no_pack_op_pickings = self.filtered(lambda picking: not picking.pack_operation_ids)
        no_pack_op_pickings.action_done()
        other_pickings = self - no_pack_op_pickings
        for picking in other_pickings:
            need_rereserve, all_op_processed = picking.picking_recompute_remaining_quantities()
            todo_moves = self.env['stock.move']
            toassign_moves = self.env['stock.move']

            # create extra moves in the picking (unexpected product moves coming from pack operations)
            if not all_op_processed:
                todo_moves |= picking._create_extra_moves()

            if need_rereserve or not all_op_processed:
                moves_reassign = any(x.origin_returned_move_id or x.move_orig_ids for x in picking.move_lines if x.state not in ['done', 'cancel'])
                if moves_reassign and picking.location_id.usage not in ("supplier", "production", "inventory"):
                    # unnecessary to assign other quants than those involved with pack operations as they will be unreserved anyways.
                    picking.with_context(reserve_only_ops=True, no_state_change=True).rereserve_quants(move_ids=picking.move_lines.ids)
                picking.do_recompute_remaining_quantities()

            # split move lines if needed
            for move in picking.move_lines:
                rounding = move.product_id.uom_id.rounding
                remaining_qty = move.remaining_qty
                if move.state in ('done', 'cancel'):
                    # ignore stock moves cancelled or already done
                    continue
                elif move.state == 'waiting':
                    picking.force_assign()
                elif move.state == 'draft':
                    toassign_moves |= move
                if float_compare(remaining_qty, 0,  precision_rounding=rounding) == 0:
                    if move.state in ('draft', 'assigned', 'confirmed'):
                        todo_moves |= move
                elif float_compare(remaining_qty, 0, precision_rounding=rounding) > 0 and float_compare(remaining_qty, move.product_qty, precision_rounding=rounding) < 0:
                    # TDE FIXME: shoudl probably return a move - check for no track key, by the way
                    new_move_id = move.split(remaining_qty)
                    new_move = self.env['stock.move'].with_context(mail_notrack=True).browse(new_move_id)
                    todo_moves |= move
                    # Assign move as it was assigned before
                    toassign_moves |= new_move

            # TDE FIXME: do_only_split does not seem used anymore
            if todo_moves and not self.env.context.get('do_only_split'):
                todo_moves.action_done()
            elif self.env.context.get('do_only_split'):
                picking = picking.with_context(split=todo_moves.ids)

            picking._create_backorder()
        return True
