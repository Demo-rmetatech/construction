# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Vishnu P(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
""" Purchase Requisition model"""
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class PurchaseRequisition(models.Model):
    """ Model for storing purchase requisition """
    _name = 'employee.purchase.requisition'
    _description = 'Purchase Requisition'
    _inherit = "mail.thread", "mail.activity.mixin"

    name = fields.Char(string="Reference No", readonly=True, copy=False)
    employee_id = fields.Many2one('hr.employee', string='Requester',
                                  help='Employee', copy=True)
    dept_id = fields.Many2one('hr.department', string='Department',
                              related='employee_id.department_id', store=True,
                              help='Department', copy=True)
    user_id = fields.Many2one('res.users', string='Requisition Responsible',
                              help='Requisition responsible user', copy=True, default=lambda l: l.env.user)
    requisition_date = fields.Date(string="Requisition Date",
                                   default=lambda self: fields.Date.today(),
                                   help='Date of Requisition', copy=True)
    receive_date = fields.Date(string="Received Date", readonly=True,
                               help='Receive Date', copy=True)
    requisition_deadline = fields.Date(string="Requisition Deadline",
                                       help="End date of Purchase requisition", copy=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company,
                                 help='Company')
    requisition_order_ids = fields.One2many('requisition.order',
                                            'requisition_product_id',
                                            required=True, copy=True)
    confirm_id = fields.Many2one('res.users', string='Confirmed By',
                                 default=lambda self: self.env.uid,
                                 readonly=True,
                                 help='User who Confirmed the requisition.', copy=True)
    manager_id = fields.Many2one('res.users', string='Department Manager',
                                 readonly=True, help='Department Manager', copy=True)
    requisition_head_id = fields.Many2one('res.users', string='Approved By',
                                          readonly=True,
                                          help='User who approved the requisition.', copy=True)
    rejected_user_id = fields.Many2one('res.users', string='Rejected By',
                                       readonly=True,
                                       help='user who rejected the requisition', copy=True)
    confirmed_date = fields.Date(string='Confirmed Date', readonly=True,
                                 help='Date of Requisition Confirmation', copy=True)
    department_approval_date = fields.Date(string='Department Approval Date',
                                           readonly=True,
                                           help='Department Approval Date', copy=True)
    approval_date = fields.Date(string='Approved Date', readonly=True,
                                help='Requisition Approval Date', copy=True)
    reject_date = fields.Date(string='Rejection Date', readonly=True,
                              help='Requisition Rejected Date', copy=True)
    source_location_id = fields.Many2one('stock.location',
                                         string='Source Location',
                                         help='Source location of requisition.', copy=True)
    destination_location_id = fields.Many2one('stock.location',
                                              string="Destination Location",
                                              help='Destination location of requisition.',
                                              related='project_id.project_location_id', copy=True)
    delivery_type_id = fields.Many2one('stock.picking.type',
                                       string='Delivery To',
                                       help='Type of Delivery.', copy=True)
    internal_picking_id = fields.Many2one('stock.picking.type',
                                          string="Internal Picking", copy=True)
    requisition_description = fields.Text(string="Reason For Requisition", copy=True)
    purchase_count = fields.Integer(string='Purchase Count',
                                    help='Purchase Count',
                                    compute='_compute_purchase_count')
    internal_transfer_count = fields.Integer(string='Internal Transfer count',
                                             help='Internal Transfer count',
                                             compute='_compute_internal_transfer_count')
    project_id = fields.Many2one('project.project', string='Project')
    boq_id = fields.Many2one('project.boq', string='BOQ')
    state = fields.Selection(
        [('new', 'New'),
         ('waiting_department_approval', 'Pending Purchase Order'),
         ('waiting_head_approval', 'Waiting Head Approval'),
         ('approved', 'Approved'),
         ('purchase_order_created', 'Purchase Order Created'),
         ('received', 'Received'),
         ('po_cancelled', 'PO Cancelled'),
         ('cancelled', 'Cancelled')],
        default='new', copy=False, tracking=True)

    @api.model
    def create(self, vals):
        """generate purchase requisition sequence"""
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'employee.purchase.requisition') or 'New'
        result = super(PurchaseRequisition, self).create(vals)
        return result

    def action_confirm_requisition(self):
        """confirm purchase requisition"""
        # self.source_location_id = self.employee_id.department_id.department_location_id.id
        # self.destination_location_id = self.employee_id.employee_location_id.id
        # self.delivery_type_id = self.source_location_id.warehouse_id.in_type_id.id
        # self.internal_picking_id = self.source_location_id.warehouse_id.int_type_id.id
        self.write({'state': 'waiting_department_approval'})
        self.confirm_id = self.env.uid
        self.confirmed_date = fields.Date.today()

    def action_department_approval(self):
        """approval from department"""
        self.write({'state': 'waiting_head_approval'})
        self.manager_id = self.env.uid
        self.department_approval_date = fields.Date.today()

    def action_department_cancel(self):
        """cancellation from department """
        if self.requisition_order_ids:
            for line in self.requisition_order_ids:
                line.boq_line_id.ordered_qty = line.boq_line_id.ordered_qty - line.quantity
        self.write({'state': 'cancelled'})
        self.rejected_user_id = self.env.uid
        self.reject_date = fields.Date.today()

    def action_head_approval(self):
        """approval from department head"""
        self.write({'state': 'approved'})
        self.requisition_head_id = self.env.uid
        self.approval_date = fields.Date.today()

    def action_head_cancel(self):
        """cancellation from department head"""
        if self.requisition_order_ids:
            for line in self.requisition_order_ids:
                line.boq_line_id.ordered_qty = line.boq_line_id.ordered_qty - line.quantity
        self.write({'state': 'cancelled'})
        self.rejected_user_id = self.env.uid
        self.reject_date = fields.Date.today()

    def action_create_purchase_order(self):
        """create purchase order and internal transfer"""
        if self.project_id:
            if not self.project_id.analytic_account_id:
                raise UserError("Please Select Analytic Account on Project")
        partner_ids = self.requisition_order_ids.mapped('partner_ids')
        for line in self.requisition_order_ids:
            if not line.partner_ids:
                raise UserError("Please select vendors")
        for partner_id in partner_ids:
            vendor_lines = (self.requisition_order_ids.filtered
                            (lambda l: partner_id.id in l.partner_ids.ids))
            vals = []
            if vendor_lines:
                # analytic_account_id = self.analytic_account_id.id
                # if self.project_id:
                #     analytic_account_id = self.project_id.analytic_account_id.id
                for line in vendor_lines:
                    vals.append((0, 0, {
                        'product_id': line.product_id.id,
                        'product_qty': line.quantity,
                        'name': line.description,
                        'boq_line_id': line.boq_line_id.id,
                        'analytic_distribution': {str(line.analytic_account_id.id): 100}
                    }))
            self.env['purchase.order'].create({
                'partner_id': partner_id.id,
                'requisition_order_id': self.id,
                'project_id': self.project_id.id,
                'boq_id': self.boq_id.id,
                "order_line": vals,
                'street': self.project_id.street,
                'street2': self.project_id.street2,
                'city': self.project_id.city,
                'state_id': self.project_id.state_id.id,
                'zip': self.project_id.zip,
            })
        self.write({'state': 'purchase_order_created'})

    def _compute_internal_transfer_count(self):
        # self.internal_active = 0
        self.internal_transfer_count = self.env['stock.picking'].search_count([
            ('requisition_order_id', '=', self.id)])

    def _compute_purchase_count(self):
        self.purchase_count = self.env['purchase.order'].search_count([
            ('requisition_order_id', '=', self.id),
            ('state', '!=', 'cancel')])

    def action_receive(self):
        """receive purchase requisition"""
        self.write({'state': 'received'})
        self.receive_date = fields.Date.today()

    def get_purchase_order(self):
        """purchase order smart button view"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Order',
            'view_mode': 'tree,form',
            'res_model': 'purchase.order',
            'domain': [('requisition_order_id', '=', self.id), ('state', '!=', 'cancel')],
        }

    def get_internal_transfer(self):
        """internal transfer smart tab view"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Internal Transfers',
            'view_mode': 'tree,form',
            'res_model': 'stock.picking',
            'domain': [('requisition_order_id', '=', self.id)],
        }

    def action_print_report(self):
        """print purchase requisition report"""
        data = {
            'employee': self.employee_id.name,
            'records': self.read(),
            'order_ids': self.requisition_order_ids.read(),
        }
        return self.env.ref(
            'employee_purchase_requisition.action_report_purchase_requisition').report_action(
            self, data=data)


class RequisitionProducts(models.Model):
    _name = 'requisition.order'
    _description = 'Requisition order'

    requisition_product_id = fields.Many2one(
        'employee.purchase.requisition', help='Requisition product.')
    state = fields.Selection(string='State',
                             related='requisition_product_id.state')
    requisition_type = fields.Selection(
        string='Requisition Type',
        selection=[
            ('purchase_order', 'Purchase Order'),
            ('internal_transfer', 'Internal Transfer'),
        ], help='type of requisition')
    product_id = fields.Many2one('product.product', required=True,
                                 help='Product', copy=True)
    description = fields.Text(
        string="Description",
        compute='_compute_name',
        store=True, readonly=False,
        precompute=True, help='Product Description', copy=True)
    quantity = fields.Float(string='Quantity', help='Quantity', copy=True)
    uom = fields.Char(related='product_id.uom_id.name',
                      string='Unit of Measure', help='Product Uom', copy=True)
    partner_ids = fields.Many2many('res.partner', string='Vendor',
                                 help='Vendor for the requisition', copy=True)
    boq_line_id = fields.Many2one('boq.line', string='BOQ Line')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account', copy=True)

    @api.depends('product_id')
    def _compute_name(self):
        """compute product description"""
        for option in self:
            option.partner_ids = False
            if not option.product_id:
                continue
            product_lang = option.product_id.with_context(
                lang=self.requisition_product_id.employee_id.lang)
            option.description = product_lang.get_product_multiline_description_sale()
            option.partner_ids += option.product_id.seller_ids.mapped('partner_id')

    @api.onchange('requisition_type')
    def _onchange_product(self):
        """fetching product vendors"""
        vendors_list = []
        for data in self.product_id.seller_ids:
            vendors_list.append(data.partner_id.id)
        return {'domain': {'partner_id': [('id', 'in', vendors_list)]}}
