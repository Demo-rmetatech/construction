# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class PurchaseOrderWizard(models.TransientModel):
    _name = 'po.wizard'
    _description = 'PO Wizard'

    po_line_ids = fields.One2many('po.line.wizard', 'po_id')

    def create_requisition(self):
        # for partner_id in self.po_line_ids.mapped('vendor_ids'):
        qty_zero_lines = vendor_lines = (self.po_line_ids.filtered
                                         (lambda l: l.qty == 0))
        if qty_zero_lines:
            raise UserError("Quantity cannot be zero!!")
        vendor_lines = (self.po_line_ids.filtered
                        (lambda l: not l.vendor_ids))
        if vendor_lines:
            raise UserError("Vendor not set!!")
        vendor_lines = (self.po_line_ids.filtered
                        (lambda l: l.vendor_ids.ids))
        vals = []
        boq = self.env['project.boq'].search([('id', '=', self.env.context.get('active_id'))])
        if vendor_lines:
            for line in vendor_lines:
                vals.append((0, 0, {
                    'product_id': line.product_id.id,
                    'quantity': line.qty,
                    'uom': line.product_id.name,
                    'boq_line_id': line.boq_line_id.id,
                    'partner_ids': line.vendor_ids.ids,
                    'analytic_account_id': boq.project_id.analytic_account_id.id,
                }))
                line.boq_line_id.update({
                    'ordered_qty': line.boq_line_id.ordered_qty + line.qty
                })
        if vals:
            self.env['employee.purchase.requisition'].create({
                'employee_id': self.env.user.employee_id.id,
                'project_id': boq.project_id.id,
                'boq_id': boq.id,
                "requisition_order_ids": vals
            })
        # for partner_id in self.po_line_ids.mapped('vendor_ids'):
        #     vendor_lines = (self.po_line_ids.filtered
        #                     (lambda l: partner_id.id in l.vendor_ids.ids))
        #     vals = []
        #     if vendor_lines:
        #         for line in vendor_lines:
        #             vals.append((0, 0, {
        #                 'product_id': line.product_id.id,
        #                 'product_qty': line.qty,
        #                 'name': line.product_id.name,
        #                 'boq_line_id': line.boq_line_id.id
        #             }))
        #             line.boq_line_id.update({
        #                 'ordered_qty': line.qty
        #             })
        #     boq = self.env['project.boq'].search([('id','=', self.env.context.get('active_id'))])
        #     self.env['purchase.order'].create({
        #         'partner_id': partner_id.id,
        #         'project_id': boq.project_id.id,
        #         'boq_id': boq.id,
        #         "order_line": vals
        #     })


class PurchaseOrderLineWizard(models.TransientModel):
    _name = 'po.line.wizard'
    _description = 'PO Line Wizard'

    po_id = fields.Many2one('po.wizard')
    product_id = fields.Many2one('product.product', string='Product')
    uom_id = fields.Many2one('uom.uom', string='UOM', related='product_id.uom_id')
    total_qty = fields.Float(string='Total Qty', related='boq_line_id.quantity')
    ordered_qty = fields.Float(string='Ordered Qty', related='boq_line_id.ordered_qty')
    qty = fields.Float(string='Qty')
    vendor_ids = fields.Many2many('res.partner', string='Vendors')
    boq_line_id = fields.Many2one('boq.line', string='BOQ Line')
    # line_id = fields.Char()

    @api.onchange('qty')
    def check_qty(self):
        for record in self:
            actual_qty = record.qty + record.ordered_qty
            if actual_qty > record.total_qty:
                return {
                    'warning': {
                        'title': ('Warning'),
                        'message': ("Are you sure, you want to create a PR?"),
                    }
                }
