# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    project_id = fields.Many2one('project.project', string='Project')
    boq_id = fields.Many2one('project.boq', string='BOQ')
    receipt_location_id = fields.Many2one('stock.location', string='Receipt Location', related='project_id.project_location_id')
    prepared_id = fields.Many2one('hr.employee', string='Prepared By')
    approved_id = fields.Many2one('res.users', string='Approved By')
    street = fields.Char(string="Delivery Address")
    street2 = fields.Char()
    city = fields.Char()
    state_id = fields.Many2one('res.country.state')
    zip = fields.Char()
    notes = fields.Html('Terms and Conditions', compute="_compute_note", readonly=False)

    @api.depends('state')
    def _compute_note(self):
        for rec in self:
            if rec.state in ['draft', 'sent', 'to approve']:
                rec.notes = 'This PO is not yet approved.'
            else:
                rec.notes = 'This Purchase Order is Digitally Approved and therefore it does not require Manual Signature.'

    def get_delivery_address(self):
        for record in self:
            address = '%s, \n %s, \n %s, %s , %s.' % (
                record.street if record.street else '', record.street2 if record.street2 else '', record.city if record.city else '',
                record.state_id.name if record.state_id else '',
                record.zip if record.zip else '')
            return address

    def button_confirm(self):
        res = super(PurchaseOrder, self).button_confirm()
        self.approved_id = self.env.user.id
        return res

    def _get_destination_location(self):
        self.ensure_one()
        if self.receipt_location_id:
            return self.receipt_location_id.id
        if self.dest_address_id:
            return self.dest_address_id.property_stock_customer.id
        return self.picking_type_id.default_location_dest_id.id

    # def _prepare_picking(self):
    #     res = super(PurchaseOrder, self)._prepare_picking()
    #     if self.receipt_location_id:
    #         res.update({
    #             'location_dest_id': self.receipt_location_id.id
    #         })
    #     return res

    def button_cancel(self):
        res = super(PurchaseOrder, self).button_cancel()
        if self.order_line:
            for line in self.order_line:
                line.boq_line_id.ordered_qty = line.boq_line_id.ordered_qty - line.product_qty
        return res


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    boq_line_id = fields.Many2one('boq.line', string='BOQ Line')
