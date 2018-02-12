# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from dateutil.relativedelta import relativedelta

from lxml import etree
from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_is_zero, float_compare
from odoo.exceptions import UserError, AccessError
from odoo.tools.misc import formatLang
from odoo.addons.base.res.res_partner import WARNING_MESSAGE, WARNING_HELP
from odoo.addons.account.wizard.pos_box import CashBox          

class Sakinah_Users(models.Model):
    _inherit = "res.users"

    journal_id = fields.Many2one('account.journal', string='Journal')

class Sakinah_Accounts(models.Model):
    _inherit = "account.journal"

    users = fields.One2many('res.users', 'journal_id', string='User')

class Sakinah_POS(models.Model):
    _inherit = "pos.session"

    @api.multi
    def action_view_payment(self):
        uid = self.env.uid
        context = self._context

        receive = self.env['account.payment'].search([('payment_type', '=', 'transfer'), ('state', '=', 'saved'), ('destination_journal_id.users', '=', uid)], order='create_date desc', limit=1)
        sent = self.env['account.payment'].search([('payment_type', '=', 'transfer'), ('state', '=', 'saved'), ('journal_id.users', '=', uid)], order='create_date desc', limit=1)
        
        action = {
            'name': _('Payments'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.payment',
            'view_id': self.env.ref('account.view_account_payment_form').id,
            'type': 'ir.actions.act_window',
            'context': context,
            'target': 'new'
            }

        if receive:
            action['res_id'] = receive.id

        elif sent:
            action['res_id'] = sent.id

        return action

class Sakinah_Payment(models.Model):
    _inherit = "account.payment"

    state = fields.Selection([('draft', 'Draft'), ('saved', 'Saved'), ('posted', 'Posted'), ('sent', 'Sent'), ('reconciled', 'Reconciled')], readonly=True, copy=False, string="Status")
    hide_validate = fields.Boolean('Hide Validate', compute='_compute_validation')

    @api.onchange('payment_type')
    def _onchange_payment_type(self):
        if not self.invoice_ids:
            # Set default partner type for the payment type
            if self.payment_type == 'inbound':
                self.partner_type = 'customer'
            elif self.payment_type == 'outbound':
                self.partner_type = 'supplier'
        # Set payment method domain
        res = self._onchange_journal()
        if not res.get('domain', {}):
            res['domain'] = {}
        res['domain']['journal_id'] = self.payment_type == 'inbound' and [('at_least_one_inbound', '=', True)] or [('at_least_one_outbound', '=', True)]
        res['domain']['journal_id'].append(('type', 'in', ('bank', 'cash')))

        if self.payment_type == 'transfer':
            res['domain']['journal_id'].append(('users.id', '=', self.env.uid))
        else:
            res['domain']['journal_id'].append(('name', 'in', ('Bank', 'Cash')))

        return res

    @api.multi
    def save(self):
        desjourname = self.destination_journal_id.name
        journame = self.journal_id.name
        writename = journame + " to " + desjourname
        self.write({'state': 'saved', 'name': writename})

    @api.multi
    def post(self):
        self.write({'state': 'draft'})
        return super(Sakinah_Payment, self).post()

    @api.depends('destination_journal_id')
    def _compute_validation(self):
        for pay in self:
            presence = 0
            for dest in pay.destination_journal_id.users:
                if dest.id == self.env.uid:
                    presence += 1
        
            if presence != 0:
                pay.hide_validate = False
            else:
                pay.hide_validate = True

class Sakinah_Expense(models.Model):
    _inherit = "hr.expense"

    @api.multi
    def _new_mode(self):
        return [("company_account", "Company")]

    payment_mode = fields.Selection(_new_mode, default='company_account', states={'done': [('readonly', True)], 'post': [('readonly', True)]}, string="Payment By")

class Sakinah_Expense_Sheet(models.Model):
    _inherit = "hr.expense.sheet"

    @api.multi
    def _new_mode(self):
        return [("company_account", "Company")]

    payment_mode = fields.Selection(_new_mode, related='expense_line_ids.payment_mode', default='company_account', readonly=True, string="Payment By")
    hide_resubmit = fields.Boolean('Hide Resubmit', compute='_compute_resubmit')

    @api.depends('employee_id')
    def _compute_resubmit(self):
        for sh in self:
            presence = 0
            for em in sh.employee_id.user_id:
                if em.id == self.env.uid:
                    presence += 1
        
            if presence != 0:
                sh.hide_resubmit = False
            else:
                sh.hide_resubmit = True

class SPosBox(CashBox):
    _register = False

class SPosBoxOut(SPosBox):
    _inherit = 'cash.box.out'

    @api.multi
    def _calculate_values_for_statement_line(self, record):
        if not record.journal_id.company_id.transfer_account_id:
            raise UserError(_("You should have defined an 'Internal Transfer Account' in your cash register's journal!"))
        amount = self.amount or 0.0
        return {
            'date': record.date,
            'statement_id': record.id,
            'journal_id': record.journal_id.id,
            'amount': -amount if amount > 0.0 else amount,
            'account_id': 19,
            'name': self.name,
        }

 

