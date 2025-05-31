# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    boq_id = fields.Many2one('project.boq', string='BOQ')
    project_id = fields.Many2one(string='Project')
    down_payment_percentage = fields.Float(string='Down Payment %', tracking=True)
    retention_percentage = fields.Float(string='Retention %', tracking=True)
    total_amount_due = fields.Monetary(string='Billing Amount Due', compute='compute_amount_due')
    actual_amount_due = fields.Monetary(string='Actual Amount Due', compute='compute_actual_amount_due')
    down_payment_amount = fields.Monetary()
    retention_amount = fields.Monetary()
    invoice_boq_count = fields.Integer(string='Count', compute='compute_boq_inv_count')
    billing_line = fields.One2many('sale.billing.line', 'order_id')

    # def action_confirm(self):
    #     res = super(SaleOrder, self).action_confirm()
    #     vals = {
    #         'name': self.project_id.name or self.name,
    #         'date_from': self.project_id.date_start,
    #         'date_to': self.project_id.date,
    #     }
    #     budget = self.env['crossovered.budget'].create(vals)
    #     if budget:
    #         budget.update({
    #             'crossovered_budget_line': [(0, 0, {
    #                 'analytic_account_id': self.project_id.analytic_account_id.id,
    #                 'date_from': self.project_id.date_start,
    #                 'date_to': self.project_id.date,
    #                 'planned_amount': self.boq_id.total_cost
    #             })]
    #         })
    #     budget.action_budget_confirm()
    #     budget.action_budget_validate()
    #     budget.action_budget_done()
    #     return res

    def compute_boq_inv_count(self):
        for record in self:
            record.invoice_boq_count = 0
            record.invoice_boq_count = len(self.env['account.move'].search([
                ('billing_id.boq_id','=', record.boq_id.id),('partner_id','=', record.partner_id.id)
                                                                           ]))

    def action_boq_invoice(self):
        boq = self.env['account.move'].search([('billing_id.boq_id', '=', self.boq_id.id)])
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        if len(boq) > 1:
            action['domain'] = [('id', 'in', boq.ids)]
        elif len(boq) == 1:
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = boq.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def compute_amount_due(self):
        for record in self:
            invoices = self.env['account.move'].search([('billing_id.boq_id','=', record.boq_id.id),
                                                        ('billing_id.is_down_payment', '=', False)
                                                        ])
            if invoices:
                billed_amount = 0
                for inv in invoices:
                    billed_amount += inv.billing_id.taxed_total_amount + inv.billing_id.downpayment_amount_adjusted
                    record.total_amount_due = record.amount_total - billed_amount
            else:
                record.total_amount_due = record.amount_total

    @api.depends('billing_line.subtotal_amount')
    def compute_actual_amount_due(self):
        for record in self:
            record.actual_amount_due = 0
            for line in record.billing_line:
                record.actual_amount_due += line.subtotal_amount


class SaleBillingLine(models.Model):
    _name = 'sale.billing.line'
    _description = 'Sale Billing Line'

    order_id = fields.Many2one('sale.order')
    product_id = fields.Many2one('product.product', string='Product')
    subtotal_amount = fields.Float(string='Total')
    billing_percent = fields.Float(string='Billing Percent')
