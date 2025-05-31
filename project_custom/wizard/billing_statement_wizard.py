# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class BillingStmntWizard(models.TransientModel):
    _name = 'billing.statement.wizard'
    _description = 'Billing Statement Wizard'

    total_project_completion = fields.Float(string='Total Project Completion %')
    billing_percentage = fields.Float(string='Present Billing Percentage')
    product_id = fields.Many2one('product.product', string='Type of Billing')
    total_billed_percentage = fields.Float(string='Total Billed Percentage')
    is_down_payment = fields.Boolean(default=False)
    is_retention_amount = fields.Boolean(string='Is Retention Amount', default=False)

    @api.onchange('is_retention_amount')
    def set_retention_amount(self):
        for record in self:
            if record.is_retention_amount:
                boq = self.env['project.boq'].search([('id', '=', self.env.context.get('active_id'))])
                if boq.state == 'contract':
                    record.billing_percentage = boq.contract_id.retention_percentage

    @api.onchange('billing_percentage')
    def check_billing_percent(self):
        for record in self:
            if record.billing_percentage > 0:
                if record.billing_percentage + record.total_billed_percentage > 100 and not record.is_retention_amount:
                    raise UserError("Billing cannot exceed 100%!!")

    def create_billing_statement(self):
        for record in self:
            if record.billing_percentage > 0:
                if record.billing_percentage + record.total_billed_percentage > 100 and not record.is_retention_amount:
                    raise UserError("Billing cannot exceed 100%!!")
            boq = self.env['project.boq'].search([('id', '=', self.env.context.get('active_id'))])
            boq.is_set_percent = False
            if boq:
                if boq.state == 'contract':
                    line_vals = []
                    product_id = record.product_id
                    downpayment_amount_adjusted = 0
                    retention_amount_adjusted = 0
                    if not record.is_retention_amount:
                        downpayment_amount_adjusted = boq.contract_id.down_payment_amount * (record.billing_percentage / 100)
                        retention_amount_adjusted = boq.contract_id.retention_amount * (record.billing_percentage / 100)
                    total_amount_due = ((record.billing_percentage / 100) * boq.final_total) - (downpayment_amount_adjusted + retention_amount_adjusted)
                    if product_id:
                        val = (0, 0, {
                            'product_id': product_id.id,
                            'description': 0 if record.is_down_payment else record.billing_percentage,
                            'reference': record.product_id.name,
                            'total_amount_due': total_amount_due,
                        })
                        line_vals.append(val)
                    vals = {
                        'partner_id': boq.partner_id.id,
                        'project_id': boq.project_id.id,
                        'boq_id': boq.id,
                        'contract_id': boq.contract_id.id,
                        'billing_statement_line': line_vals,
                        'taxed_total_amount': total_amount_due,
                        # 'name': record.product_id.name,
                        'total_project_completion': record.billing_percentage + record.total_billed_percentage if not record.is_retention_amount else record.total_billed_percentage,
                        'billing_statement_percentage': record.billing_percentage,
                        'total_contract_price': boq.final_total,
                        'state': 'draft',
                        'downpayment_amount_adjusted':  downpayment_amount_adjusted,
                        'retention_amount_adjusted': retention_amount_adjusted,
                        'total_billing_amount': total_amount_due + retention_amount_adjusted + downpayment_amount_adjusted
                    }
                    if record.is_retention_amount:
                        vals.update({
                            'is_retention_billing': True,
                            'billing_statement_percentage': 0,
                            'downpayment_amount_adjusted': 0,
                            'retention_amount_adjusted': 0
                        })
                    if record.is_down_payment:
                        boq.contract_id.down_payment_amount = boq.final_total * (record.billing_percentage / 100)
                        boq.contract_id.retention_amount = (
                                boq.final_total * (boq.contract_id.retention_percentage / 100))
                        vals.update({
                            'is_down_payment': True,
                            'total_project_completion': 0,
                            'billing_statement_percentage': 0
                        })
                    print("=======", vals)
                    billing_statement = self.env['billing.statement'].create(vals)

