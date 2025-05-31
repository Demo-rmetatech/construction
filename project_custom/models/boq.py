# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime
from odoo.exceptions import UserError, ValidationError
import io
import json
import xlsxwriter
from odoo import models
from odoo.tools import date_utils
import base64


class ProjectBOQ(models.Model):

    _name = 'project.boq'
    _rec_name = 'name'
    _inherit = "mail.thread", "mail.activity.mixin"


    name = fields.Char(string="BOQ", copy=False, readonly=True, default='New')
    project_id = fields.Many2one('project.project', string='Project')
    location = fields.Char(string='Location')
    project_description = fields.Char(string='Project Description')
    partner_id = fields.Many2one('res.partner', string='Owner',)
    date = fields.Date(string='Date', default=datetime.today())
    subject = fields.Char(string='Memo')
    boq_line_ids = fields.One2many('boq.line', 'boq_id')
    arch_line_ids = fields.One2many('arch.line', 'boq_id')

    total_cost = fields.Float(string='Total Cost', compute='calculate_amount')
    arch_total_cost = fields.Float(string='Total Cost', compute='calculate_amount')
    contingency = fields.Float(string='Contingency', compute='calculate_amount')
    arch_contingency = fields.Float(string='Contingency', compute='calculate_amount')
    over_head_profit = fields.Float(string='Over Head Profit', compute='calculate_amount')
    arch_over_head_profit = fields.Float(string='Over Head Profit', compute='calculate_amount')
    vat = fields.Float(string='VAT', compute='calculate_amount')
    arch_vat = fields.Float(string='VAT', compute='calculate_amount')
    final_total = fields.Float(string='Grand Total', compute='calculate_amount')
    arch_final_total = fields.Float(string='Grand Total', compute='calculate_amount')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'BOQ Approved'),
        ('project', 'Project Created'),
        # ('pending', 'Pending Approval'),
        ('contract', 'Contract Created'),
        ('completed', 'Completed'),
        ('revise', 'Revise'),
        ('revised', 'Revised')
    ], default='draft', tracking=True)
    requisition_count = fields.Integer(string='Requisition Count',
                                    help='Purchase Count',
                                    compute='_compute_purchase_count')
    project_completion_percent = fields.Float(string='Purchase Completion %', compute='compute_total_po_amount')
    billing_completion_percent = fields.Float(string='Billing Collection %', compute='compute_total_billing_amount')
    total_billed_amount = fields.Float(string='Total Billed Amount', compute='compute_billing_amount')
    total_po_amount = fields.Float(string='Total PO Amount', compute='compute_po_amount')
    actual_po_amount = fields.Float(string='Comparative BOQ Amount', compute='compute_boq_po_amount')
    contract_id = fields.Many2one('sale.order', string='Contract')
    total_contract = fields.Integer(string='Contract', compute='_compute_total_contract', copy=False)
    is_contract_created = fields.Boolean(default=False)
    billing_stmnt_count = fields.Integer(string='Billing Statement Count',
                                       help='Billing Count',
                                       compute='_compute_billing_statement_count')
    type_of_boq = fields.Selection([
        ('struct', 'Structural'),
        ('archi', 'Architectural')
        ], string='Type of BOQ')
    is_set_percent = fields.Boolean(default=False)
    actual_boq_completion = fields.Float(string='BOQ Actual Completion %', compute='compute_actual_boq_percent')
    n_labour_cost_percent = fields.Float(string='Labour Cost %')
    n_contingency_percent = fields.Float(string='Contingency %')
    n_over_head_profit = fields.Float(string='Over Head Profit %')
    n_tax_id = fields.Many2one('account.tax', string='VAT')
    n_count_total_qc = fields.Integer(compute="compute_n_count_total_qc")

    @api.constrains('boq_line_ids')
    def _check_required(self):
        for record in self:
            if not record.boq_line_ids:
                raise ValidationError("There must be at least one line to proceed.")


    @api.model_create_multi
    def create(self, vals_list):
        records = super(ProjectBOQ, self).create(vals_list)
        for rec in records:
            if rec.name == 'New':
                rec.name = self.env['ir.sequence'].next_by_code('project.boq') or 'New'
        return records
    
    @api.onchange('n_labour_cost_percent')
    def onchange_n_labour_cost_percent(self):
        for rec in self:
            rec.boq_line_ids.compute_cost()

    @api.depends()
    def compute_n_count_total_qc(self):
        for rec in self:
            rec.n_count_total_qc = self.env['qc.calculation'].search_count([('boq_id', '=', rec.id)])

    def get_qty_computation(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Quantity Computation',
            'view_mode': 'tree,form',
            'res_model': 'qc.calculation',
            'domain': [('boq_id', '=', self.id)],
        }

    def open_create_project(self):
        self.ensure_one()
        return {
            **self.env["ir.actions.actions"]._for_xml_id("project_custom.open_create_project_custom"),
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_user_ids': [self.env.uid],
                'default_allow_billable': 1,
                'hide_allow_billable': True,
                'default_company_id': self.env.company.id,
                'default_labour_cost_percent': self.n_labour_cost_percent,
                'default_contingency_percent': self.n_contingency_percent,
                'default_over_head_profit': self.n_over_head_profit,
                'default_tax_id': self.n_tax_id.id,
                'default_is_boq_created':True,
                'boq_id':self.id,
            },
        }


    def set_unit_price(self):
        for record in self:
            for line  in record.boq_line_ids:
                if line.unit_price == 0:
                    if line.product_id:
                        line.unit_price = line.product_id.boq_cost
                    if line.inventory_product_id:
                        line.unit_price = line.inventory_product_id.boq_cost

    @api.depends('boq_line_ids.actual_completion_percent', 'boq_line_ids.to_date_amount')
    def compute_actual_boq_percent(self):
        for record in self:
            record.actual_boq_completion = 0
            total = 0
            to_date_total = 0
            for line in record.boq_line_ids:
                total += line.sub_total
                to_date_total += line.to_date_amount
            if to_date_total and total > 0:
                record.actual_boq_completion = (to_date_total / total) * 100

    def set_completion_percent(self):
        for record in self:
            for line in record.boq_line_ids:
                if line.completion_percent > 0  and not line.display_type in ['line_section', 'line_note']:
                    line.actual_completion_percent = line.completion_percent
                    if line.previous_percent == 0 and line.present_percent == 0:
                        line.present_percent = line.actual_completion_percent
                        line.present_amount = line.sub_total * (line.present_percent / 100)
                    else:
                        line.previous_percent += line.present_percent
                        line.previous_amount = line.sub_total * (line.previous_percent / 100)
                        line.present_percent = line.actual_completion_percent - line.previous_percent
                        line.present_amount = line.sub_total * (line.present_percent / 100)
                    line.to_date_percent = line.previous_percent + line.present_percent
                    line.to_date_amount = line.previous_amount + line.present_amount
            record.is_set_percent = True

    def revised(self):
        for record in self:
            record.state = 'revised'

    def boq_completed(self):
        for record in self:
            record.state = 'completed'

    def cancel(self):
        for record in self:
            record.state = 'revise'
            project_computation = self.env['qc.calculation'].search([('project_id', '=', record.project_id.id)])
            if project_computation:
                project_computation.unlink()

    def compute_boq_po_amount(self):
        for record in self:
            record.actual_po_amount = 0
            po_orders = self.env['purchase.order'].search([('boq_id', '=', record.id),
                                                           ('state', 'in', ['purchase', 'done'])])
            if po_orders:
                for line in po_orders.mapped('order_line'):
                    labour_cost_percent = 0
                    if line.boq_line_id.qc_calculation_id.labour_cost_percent:
                        labour_cost_percent = line.boq_line_id.qc_calculation_id.labour_cost_percent
                    else:
                        labour_cost_percent = record.project_id.labour_cost_percent
                    record.actual_po_amount += (line.boq_line_id.unit_price * line.product_qty) + (
                            (line.boq_line_id.unit_price * line.product_qty) * (labour_cost_percent / 100)
                    )

    def compute_po_amount(self):
        for record in self:
            po_orders = self.env['purchase.order'].search([('boq_id','=', record.id),
                                                           ('state', 'in', ['purchase', 'done'])])
            if po_orders:
                record.total_po_amount = sum(po_orders.mapped('amount_total'))
            else:
                record.total_po_amount = 0

    @api.depends('billing_stmnt_count')
    def compute_billing_amount(self):
        for record in self:
            if record.billing_stmnt_count > 0:
                billing_stmnts = self.env['billing.statement'].search([('boq_id', '=', record.id),
                                                                                       ('is_down_payment','=', False),
                                                                                       ('state','=', 'confirm')])
                record.total_billed_amount = sum(billing_stmnts.mapped('taxed_total_amount')) + sum(billing_stmnts.mapped('downpayment_amount_adjusted'))

            else:
                record.total_billed_amount = 0

    def compute_total_po_amount(self):
        self.project_completion_percent = 0
        if self.actual_po_amount:
            self.project_completion_percent = round((self.actual_po_amount / self.total_cost) * 100,2)
            # if self.project_completion_percent == 100:
            #     self.state = 'completed'

    # def compute_total_billing_amount(self):
    #     self.billing_completion_percent = 0
    #     self.billing_completion_percent = (self.total_billed_amount / self.final_total) * 100

    def _compute_billing_statement_count(self):
        for record in self:
            record.billing_stmnt_count = len(self.env['billing.statement'].search([('boq_id', '=', record.id)]))

    def _compute_total_contract(self):
        for record in self:
            record.total_contract = len(self.env['sale.order'].search([('boq_id', '=', record.id),
                                                                       ('state', '=', 'sale')]))
            if record.total_contract == 0:
                record.is_contract_created = False

    def billing_stmnt_wizard(self):
        for record in self:
            total_project_completion = record.project_completion_percent
            total_billing_percentage = 0
            down_payment = self.env['billing.statement'].search([('boq_id','=', record.id),
                                                                  ('state','=', 'confirm'),
                                                                  ('is_down_payment', '=', True)])
            billed_stmnts = self.env['billing.statement'].search([('boq_id','=', record.id),
                                                                  ('state','=', 'confirm'),
                                                                  ('is_down_payment', '=', False)])
            total_billing_percentage = sum(billed_stmnts.mapped('billing_statement_percentage'))
            if total_billing_percentage == 0 and not down_payment:
                billing_percent = record.contract_id.down_payment_percentage
                is_down_payment = True
            else:
                is_down_payment = False
                total = 0
                previous_billing = 0
                for line in record.boq_line_ids:
                    total += line.sub_total
                    previous_billing += line.previous_amount
                previous_billing = (previous_billing / total) * 100
                billing_percent = record.actual_boq_completion - previous_billing

            return {
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'billing.statement.wizard',
                'view_id': self.env.ref('project_custom.billing_wizard_form_view').id,
                'target': 'new',
                'context': {
                    'default_total_billed_percentage': total_billing_percentage,
                    'default_billing_percentage': billing_percent,
                    'default_is_down_payment': is_down_payment,
                    'default_total_project_completion': total_project_completion
                },
            }

    def action_contract(self):
        boq = self.env['sale.order'].search([('boq_id', '=', self.id),
                                             ('state','=', 'sale')])
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_orders")
        if len(boq) > 1:
            action['domain'] = [('id', 'in', boq.ids)]
        elif len(boq) == 1:
            form_view = [(self.env.ref('sale.view_order_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = boq.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def action_billing_statement(self):
        boq = self.env['billing.statement'].search([('boq_id', '=', self.id)])
        action = self.env["ir.actions.actions"]._for_xml_id("project_custom.action_billing_statement")
        if len(boq) > 1:
            action['domain'] = [('id', 'in', boq.ids)]
        elif len(boq) == 1:
            form_view = [(self.env.ref('project_custom.billing_statement_form_view').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = boq.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.depends('total_billed_amount', 'final_total')
    def compute_total_billing_amount(self):
        for record in self:
            if record.final_total and record.total_billed_amount > 0:
                record.billing_completion_percent = (record.total_billed_amount / record.final_total) * 100
                # if record.billing_completion_percent == 100:
                #     record.state = 'completed'
            else:
                record.billing_completion_percent = 0

    def _compute_purchase_count(self):
        self.requisition_count = self.env['employee.purchase.requisition'].search_count([
            ('boq_id', '=', self.id)])

    # def submit_for_approval(self):
    #     for record in self:
    #         record.state = 'pending'
    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id and self.state == 'approved':
            self.state = 'project'
        elif self.state == 'project' and not self.project_id:
            self.state = 'approved'

    def approve(self):
        for record in self:
            if not record.boq_line_ids:
                raise ValidationError("There must be at least one line to proceed.")
            if record.project_id:
                record.state = 'project'
            else:
                record.state = 'approved'

    def create_contract_so(self):
        for record in self:
            if record.state == 'project':
                record.state = 'contract'
                line_vals = []
                billing_vals = []
                product_id = self.env['product.product'].search([('is_total_amount','=', True)], limit=1)
                if product_id:
                    val = (0, 0, {
                        'product_id': product_id.id,
                        'name': product_id.name,
                        'price_unit': record.total_cost if record.n_tax_id else record.final_total,
                        'tax_id': record.n_tax_id.ids,
                        'price_subtotal': record.total_cost if record.n_tax_id else record.final_total,
                        'analytic_distribution': {str(record.project_id.analytic_account_id.id): 100}
                    })
                    line_vals.append(val)
                    billing_val = (0, 0,{
                        'product_id': product_id.id,
                        'subtotal_amount': record.final_total
                    })
                    billing_vals.append(billing_val)
                vals = {
                    'partner_id': record.partner_id.id,
                    'project_id': record.project_id.id,
                    'boq_id': record.id,
                    'order_line': line_vals,
                    'billing_line': billing_vals,
                    'total_amount_due': record.final_total
                }
                contract_id = self.env['sale.order'].create(vals)
                contract_id.action_confirm()
                record.is_contract_created = True
                record.contract_id = contract_id.id

    def compute_boq(self):
        for record in self:
            for line in record.boq_line_ids:
                line.with_context(is_compute=True).compute_cost()
            for line in record.arch_line_ids:
                line.with_context(is_compute=True).compute_cost()
            record.calculate_amount()
            # if record.boq_line_ids:
            #     record.boq_line_ids.unlink()
            # if record.project_id:
            #     stages = self.env['project.project.stage'].search([])
            #     if stages:
            #         order_lines = []
            #         for stage in stages:
            #             val = (0, 0, {
            #                 'display_type': 'line_section',
            #                 'name': stage.name,
            #             })
            #             order_lines.append(val)
            #             tasks = self.env['project.task'].search([('project_stage_id','=', stage.id)])
            #             if tasks:
            #                 for task in tasks:
            #                     val = (0, 0, {
            #                         'display_type': 'line_note',
            #                         'name': task.name,
            #                     })
            #                     order_lines.append(val)
            #                     if task and task.product_line_ids:
            #                         for line in task.product_line_ids:
            #                             val = (0, 0, {
            #                                 'product_id': line.product_id.id,
            #                                 'uom_id': line.uom_id.id,
            #                             })
            #                             order_lines.append(val)
            #                     else:
            #                         sub_tasks = self.env['project.task'].search([('parent_id','=', task.id)])
            #                         if sub_tasks:
            #                             for sub_task in sub_tasks:
            #                                 val = (0, 0, {
            #                                      'display_type': 'line_note',
            #                                     'name': sub_task.name,
            #                                     'is_sub_task': True
            #                                 })
            #                                 order_lines.append(val)
            #                                 if sub_task and sub_task.product_line_ids:
            #                                     for line in sub_task.product_line_ids:
            #                                         print(":=", sub_task.product_line_ids)
            #                                         computation = (self.env['quantity.computation'].search
            #                                                        ([('task_id', '=', task.id),
            #                                                          ('sub_task_id','=', sub_task.id),
            #                                                          ('job_id','=', line.id)]))
            #                                         volume = computation.total_volume
            #                                         val = (0, 0, {
            #                                             'product_id': line.product_id.id,
            #                                             'uom_id': line.uom_id.id,
            #                                             'quantity': volume,
            #                                             'qc_id': computation.id,
            #                                         })
            #                                         print("=====", val, volume, line)
            #                                         order_lines.append(val)
            #         record.update({'boq_line_ids': order_lines})
            #         for line in record.boq_line_ids:
            #             line.compute_cost()
            #         record.calculate_amount()

    @api.depends('boq_line_ids.sub_total', 'arch_line_ids.sub_total')
    def calculate_amount(self):
        for record in self:
            for line in record.boq_line_ids:
                record.total_cost += line.sub_total
            for line in record.arch_line_ids:
                record.arch_total_cost += line.sub_total
            if record.total_cost > 0 or record.arch_total_cost > 0:
                record.contingency = (record.n_contingency_percent * record.total_cost   ) / 100
                record.over_head_profit = (record.n_over_head_profit * record.total_cost) / 100
                record.vat = (record.n_tax_id.amount * record.total_cost) / 100
                record.final_total = record.total_cost + record.vat + record.contingency + record.over_head_profit
                record.arch_contingency = (record.n_contingency_percent * record.arch_total_cost) / 100
                record.arch_over_head_profit = (record.n_over_head_profit * record.arch_total_cost) / 100
                record.arch_vat = (record.n_tax_id.amount * record.arch_total_cost) / 100
                record.arch_final_total = record.arch_total_cost + record.arch_vat + record.arch_contingency + record.arch_over_head_profit
            else:
                record.total_cost = 0
                record.contingency = 0
                record.over_head_profit = 0
                record.vat = 0
                record.final_total = 0
                record.arch_total_cost = 0
                record.arch_contingency = 0
                record.arch_over_head_profit = 0
                record.arch_vat = 0
                record.arch_final_total = 0

    def create_po(self):
        for record in self:
            po_lines = record.boq_line_ids.filtered(lambda l:l.create_po)
            if po_lines:
                products = []
                for line in po_lines:
                    product_id = line.product_id
                    if product_id:
                        val = (0, 0, {
                            'product_id': product_id.id,
                            'vendor_ids': product_id.seller_ids.mapped('partner_id').ids,
                            'boq_line_id': line.id,
                            'total_qty': line.quantity,
                            'ordered_qty': line.ordered_qty
                        })
                        products.append(val)
                    else:
                        if line.inventory_product_id:
                            product_id = line.inventory_product_id
                        else:
                            product_id = line.product_id
                        if product_id:
                            val = (0, 0, {
                                'product_id': product_id.id,
                                'vendor_ids': product_id.seller_ids.mapped('partner_id').ids,
                                'boq_line_id': line.id,
                                'total_qty': line.quantity,
                                'ordered_qty': line.ordered_qty
                            })
                            products.append(val)
                po_lines.create_po = False
                if products:
                    return{
                        'type': 'ir.actions.act_window',
                        'view_type': 'form',
                        'view_mode': 'form',
                        'res_model': 'po.wizard',
                        'view_id': self.env.ref('project_custom.po_wizard_form_view').id,
                        'target': 'new',
                        'context': {
                            'default_po_line_ids': products,
                        },
                    }
            else:
                raise ValidationError("Please select a BOQ Line")

    def get_purchase_requisition(self):
        """purchase order smart button view"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Requisition',
            'view_mode': 'tree,form',
            'res_model': 'employee.purchase.requisition',
            'domain': [('boq_id', '=', self.id)],
        }

    def boq_report_excel(self):
        data = {
            'model_id': self.id,
            'type': 'boq'
        }
        return {
            'type': 'ir.actions.report',
            'data': {'model': 'project.boq',
                     'options': json.dumps(data,
                                           default=date_utils.json_default),
                     'output_format': 'xlsx',
                     'report_name': 'BOQ Excel Report',
                     },
            'report_type': 'xlsx',
        }

    def billing_report_excel(self):
        data = {
            'model_id': self.id,
            'type': 'billing'
        }
        return {
            'type': 'ir.actions.report',
            'data': {'model': 'project.boq',
                     'options': json.dumps(data,
                                           default=date_utils.json_default),
                     'output_format': 'xlsx',
                     'report_name': 'Billing Progress Excel Report',
                     },
            'report_type': 'xlsx',
        }

    def get_xlsx_report(self, data, response):
        if data['type'] == 'boq':
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            sheet = workbook.add_worksheet('BOQ')
            project = workbook.add_format(
                {'font_size': '12', 'align': 'center', 'bold': True})
            cell_format = workbook.add_format(
                {'font_size': '11', 'align': 'center'})
            cell_format_total = workbook.add_format(
                {'font_size': '10', 'align': 'right', 'bold': True, 'bg_color': '#00B0F0', 'border': 1})
            head = workbook.add_format(
                {'align': 'center', 'bold': True, 'font_size': '12', 'border': 2})
            txt = workbook.add_format({'font_size': '8', 'align': 'left', 'border': 1, 'border_color':'black'})
            txt_sub_total = workbook.add_format({'font_size': '8', 'align': 'left', 'border': 1, 'border_color':'black'})
            txt_total = workbook.add_format({'font_size': '8', 'align': 'right', 'border': 1, 'border_color':'black'})
            content = workbook.add_format({'font_size': '8', 'align': 'center', 'border': 1, 'border_color':'black'})
            content_code = workbook.add_format({'font_size': '8', 'align': 'left', 'border': 1, 'border_color':'black'})
            content_subtotal = workbook.add_format({'font_size': '8', 'align': 'right', 'border': 1, 'border_color':'black'})
            stage_color = workbook.add_format({'bg_color': '#D3D3D3'})
            stage_total_format = workbook.add_format({'align': 'right', 'font_size': '10', 'bg_color': '#F9CB9C', 'bold': True, 'border': 1})
            stage = workbook.add_format(
                {'align': 'left', 'font_size': '10', 'bg_color': '#D3D3D3', 'bold': True, 'border': 1})
            task = workbook.add_format(
                {'align': 'left', 'font_size': '10', 'bg_color': '#CFE2F3', 'bold': True, 'border': 1})
            sub_task = workbook.add_format({'align': 'left', 'font_size': '8', 'bold': True, 'border': 1})
            sub_total = workbook.add_format({'align': 'left', 'font_size': '8', 'bold': True, 'border': 1})
            right_border = workbook.add_format({'border': 5})
            if data['model_id']:
                project_boq = self.env['project.boq'].search([('id', '=', data['model_id'])])
                if project_boq:
                    if self.env.company.logo:
                        product_image = io.BytesIO(base64.b64decode(self.env.company.logo))
                        sheet.insert_image(0, 3, 'image.png',
                                           {'image_data': product_image, 'x_scale': 0.10, 'y_scale': 0.08})
                    sheet.write('A1', 'Project:', project)
                    sheet.write('B1', project_boq.project_id.name or '', project)
                    sheet.write('A3', 'Location:', cell_format)
                    sheet.write('B3', str(project_boq.location or ''), cell_format)
                    sheet.write('A4', 'Owner:', cell_format)
                    sheet.write('B4', project_boq.partner_id.name or '', cell_format)
                    sheet.write('A6', 'Date:', cell_format)
                    sheet.write('B6', str((project_boq.date.strftime("%B %Y") if project_boq.date else project_boq.date) or ''), cell_format)
                    sheet.write('A8', 'Subject:', cell_format)
                    sheet.write('B8', str(project_boq.subject or ''), cell_format)
                    all_lines = project_boq.boq_line_ids
                    if all_lines:
                        # Head
                        head = [
                            {'name': 'Item No.',
                             'larg': 15,
                             'col': {'header_format': head}},
                            {'name': 'Description',
                             'larg': 60,
                             'col': {'header_format': head}},
                            {'name': 'Quantity',
                             'larg': 15,
                             'col': {'header_format': head}},
                            {'name': 'Unit',
                             'larg': 15,
                             'col': {'header_format': head}},
                            # {'name': 'Unit Cost',
                            #  'larg': 15,
                            #  'col': {'header_format': head}},
                            {'name': 'Material/Unit',
                             'larg': 15,
                             'col': {'header_format': head}},
                            {'name': 'Labour/Unit',
                             'larg': 15,
                             'col': {'header_format': head}},
                            {'name': 'Total',
                             'larg': 20,
                             'col': {'header_format': head}},
                            {'name': 'Total Amount',
                             'larg': 15,
                             'col': {'header_format': head}},
                        ]
                        row = 12
                        row += 1
                        start_row = row
                        stage_color_total = 0
                        line_section_name = ''
                        section_id = 0
                        i = row
                        for line in all_lines:
                            if line.display_type == 'line_section' and line.id != section_id and section_id != 0:
                                sheet.write(i, 1, 'Total - %s' % line_section_name, stage_total_format)
                                sheet.write(i, 7, stage_color_total, stage_total_format)
                                sheet.conditional_format(i, 0, i, 7, {'type': 'blanks',
                                                                      'format': stage_total_format})
                                stage_color_total = 0
                                section_id = 0
                                line_section_name = ''
                                i += 1
                            if line.display_type == 'line_section' and line.common_code:
                                # print("=======111111111111111111")
                                sheet.write(i, 0, line.common_code or '', stage)
                                line_section_name = line.name or ''
                                sheet.write(i, 1, line.name or '', stage)
                                sheet.conditional_format(i, 0, i, 7, {'type': 'blanks',
                                                                      'format': stage})
                                # sheet.write(row, 4, line.name, stage)
                            if line.display_type == 'line_note':
                                # print("====2222222222222222222222")
                                parent_task = self.env['project.task'].search([('parent_id', '=', False),
                                                                               ('name', '=', line.name)])
                                if parent_task:
                                    sheet.write(i, 0, line.common_code or '', task)
                                    sheet.write(i, 1, line.name or '', task)
                                    sheet.conditional_format(i, 0, i, 7, {'type': 'blanks',
                                                                          'format': task})
                                else:
                                    sheet.write(i, 0, line.common_code or '', sub_task)
                                    sheet.write(i, 1, line.name or '', sub_task)
                            if line.product_id and line.display_type not in ['line_section', 'line_note']:
                                sheet.write(i, 0, line.common_code or '', content_code)
                                sheet.write(i, 1, line.product_id.name, content_code)
                                stage_color_total += line.sub_total
                            sheet.write(i, 2, line.quantity if line.quantity > 0 and line.display_type not in ['line_section', 'line_note'] else ' ', content)
                            sheet.write(i, 3, line.uom_id.name or ' ', content)
                            sheet.write(i, 4, line.unit_price if line.unit_price > 0 and line.display_type not in ['line_section',
                                                                                                         'line_note'] else ' ', content)
                            # sheet.write(row-1, 8, line.material_total if line.material_total > 0 and line.display_type not in ['line_section',
                            #                                                                              'line_note'] else ' ', txt)
                            sheet.write(i, 5, line.labour_unit_cost if line.labour_unit_cost > 0 and line.display_type not in ['line_section',
                                                                                                         'line_note'] else ' ', content)

                            sheet.write(i, 6, line.material_total + line.labour_cost if line.material_total > 0 and line.labour_cost > 0 and line.display_type not in ['line_section',
                                                                                                         'line_note'] else ' ', content)
                            sheet.write(i, 7, line.sub_total if line.sub_total > 0 and line.display_type not in ['line_section',
                                                                                                         'line_note'] else ' ', content_subtotal)
                            section_id = line.id
                            i += 1
                        i += 1
                        sheet.write(i, 1, 'Total - %s' % line_section_name, stage_total_format)
                        sheet.write(i, 7, stage_color_total, stage_total_format)
                        sheet.conditional_format(i, 0, i, 7, {'type': 'blanks',
                                                              'format': stage_total_format})
                        row = i
                        for j, h in enumerate(head):
                            sheet.set_column(j, j, h['larg'])

                        table = []
                        for h in head:
                            col = {}
                            col['header'] = h['name']
                            col.update(h['col'])
                            table.append(col)
                        sheet.add_table(start_row - 1, 0, row + 1, len(head) - 1,
                                        {'total_row': 1,
                                         'columns': table,
                                         'style': 'Table Style Light 9',
                                         'autofilter': False,
                                         })

                        row += 1
                        sheet.write(row + 1, 6, 'Total Cost', sub_total)
                        sheet.write(row + 1, 7, project_boq.total_cost, txt_total)
                        sheet.write(row + 2, 6, 'Contingency & Mark Up', txt_sub_total)
                        sheet.write(row + 2, 7, project_boq.contingency + project_boq.over_head_profit, txt_total)
                        sheet.write(row + 3, 6, 'VAT %s' % (project_boq.n_tax_id.amount), txt_sub_total)
                        sheet.write(row + 3, 7, project_boq.vat, txt_total)
                        sheet.write(row + 4, 6, 'Grand Total', sub_total)
                        sheet.write(row + 4, 7, project_boq.final_total, cell_format_total)
                    workbook.close()
                    output.seek(0)
                    response.stream.write(output.read())
                    output.close()
        if data['type'] == 'billing':
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            sheet = workbook.add_worksheet('Billing Progress')
            project = workbook.add_format(
                {'font_size': '12', 'align': 'center', 'bold': True})
            cell_format = workbook.add_format(
                {'font_size': '11', 'align': 'center'})
            cell_format_total = workbook.add_format(
                {'font_size': '10', 'align': 'right', 'bold': True, 'bg_color': '#00B0F0', 'border': 1})
            head = workbook.add_format(
                {'align': 'center', 'bold': True, 'font_size': '12', 'border': 2})
            txt = workbook.add_format({'font_size': '8', 'align': 'left', 'border': 1, 'border_color': 'black'})
            txt_sub_total = workbook.add_format(
                {'font_size': '8', 'align': 'left', 'border': 1, 'border_color': 'black'})
            txt_total = workbook.add_format(
                {'font_size': '10', 'align': 'right', 'border': 1, 'border_color': 'black'})
            content = workbook.add_format({'font_size': '8', 'align': 'center', 'border': 1, 'border_color': 'black'})
            content_code = workbook.add_format({'font_size': '8', 'align': 'left', 'border': 1, 'border_color':'black'})
            content_subtotal = workbook.add_format(
                {'font_size': '8', 'align': 'right', 'border': 1, 'border_color': 'black'})
            stage_color = workbook.add_format({'bg_color': '#D3D3D3'})
            stage_total_format = workbook.add_format(
                {'align': 'right', 'font_size': '8', 'bg_color': '#F9CB9C', 'bold': True, 'border': 1})
            stage = workbook.add_format(
                {'align': 'left', 'font_size': '10', 'bg_color': '#D3D3D3', 'bold': True, 'border': 1})
            task = workbook.add_format(
                {'align': 'left', 'font_size': '9', 'bg_color': '#CFE2F3', 'bold': True, 'border': 1})
            sub_task = workbook.add_format({'align': 'left', 'font_size': '8', 'bold': True, 'border': 1})
            sub_total = workbook.add_format({'align': 'left', 'font_size': '10', 'bold': True, 'border': 1})
            right_border = workbook.add_format({'border': 5})
            if data['model_id']:
                project_boq = self.env['project.boq'].search([('id', '=', data['model_id'])])
                if project_boq:
                    if self.env.company.logo:
                        product_image = io.BytesIO(base64.b64decode(self.env.company.logo))
                        sheet.insert_image(0, 3, 'image.png',
                                           {'image_data': product_image, 'x_scale': 0.10, 'y_scale': 0.08})
                    sheet.write('A1', 'Project:', project)
                    sheet.write('B1', project_boq.project_id.name or '', project)
                    sheet.write('A3', 'Location:', cell_format)
                    sheet.write('B3', str(project_boq.location or ''), cell_format)
                    sheet.write('A4', 'Owner:', cell_format)
                    sheet.write('B4', project_boq.partner_id.name or '', cell_format)
                    sheet.write('A6', 'Date:', cell_format)
                    sheet.write('B6', str((project_boq.date.strftime("%B %Y") if project_boq.date else project_boq.date) or ''), cell_format)
                    sheet.write('A8', 'Subject:', cell_format)
                    sheet.write('B8', str(project_boq.subject or ''), cell_format)
                    all_lines = project_boq.boq_line_ids
                    if all_lines:
                        # Head
                        head = [
                            {'name': 'Item No.',
                             'larg': 15,
                             'col': {'header_format': head}},
                            {'name': 'Description',
                             'larg': 60,
                             'col': {'header_format': head}},
                            {'name': 'Quantity',
                             'larg': 15,
                             'col': {'header_format': head}},
                            {'name': 'Unit',
                             'larg': 15,
                             'col': {'header_format': head}},
                            # {'name': 'Unit Cost',
                            #  'larg': 15,
                            #  'col': {'header_format': head}},
                            {'name': 'Material/Unit',
                             'larg': 15,
                             'col': {'header_format': head}},
                            {'name': 'Labour/Unit',
                             'larg': 15,
                             'col': {'header_format': head}},
                            {'name': 'Total',
                             'larg': 20,
                             'col': {'header_format': head}},
                            {'name': 'Total Amount',
                             'larg': 15,
                             'col': {'header_format': head}},
                            {'name': 'Previous Accomplishment',
                             'larg': 30,
                             'col': {'header_format': head}},
                            {'name': 'Previous Amount',
                             'larg': 25,
                             'col': {'header_format': head}},
                            {'name': 'Present Accomplishment',
                             'larg': 30,
                             'col': {'header_format': head}},
                            {'name': 'Present Amount',
                             'larg': 25,
                             'col': {'header_format': head}},
                            {'name': 'To-date Accomplishment',
                             'larg': 30,
                             'col': {'header_format': head}},
                            {'name': 'To-date Amount',
                             'larg': 25,
                             'col': {'header_format': head}},
                        ]
                        row = 12
                        previous_total_percent = 0
                        previous_total_amount = 0
                        present_total_percent = 0
                        present_total_amount = 0
                        to_date_total_percent = 0
                        to_date_total_amount = 0
                        row += 1
                        start_row = row
                        stage_color_total = 0
                        line_section_name = ''
                        for i, line in enumerate(all_lines):

                            i += row
                            if line.display_type == 'line_section' and stage_color_total > 0:
                                sheet.write(i, 1, 'Total - %s' % line_section_name, stage_total_format)
                                sheet.write(i, 7, stage_color_total, stage_total_format)
                                sheet.conditional_format(i, 0, i, 13, {'type': 'blanks',
                                                                      'format': stage_total_format})
                                i += 1
                                stage_color_total = 0
                            if line.display_type == 'line_section':
                                sheet.write(i, 0, line.common_code or '', stage)
                                line_section_name = line.name or ''
                                sheet.write(i, 1, line.name or '', stage)
                                sheet.conditional_format(i, 0, i, 13, {'type': 'blanks',
                                                                      'format': stage})
                                # sheet.write(row, 4, line.name, stage)
                            elif line.display_type == 'line_note':
                                parent_task = self.env['project.task'].search([('parent_id', '=', False),
                                                                               ('name', '=', line.name)])
                                if parent_task:
                                    sheet.write(i, 0, line.common_code or '', task)
                                    sheet.write(i, 1, line.name or '', task)
                                    sheet.conditional_format(i, 0, i, 13, {'type': 'blanks',
                                                                          'format': task})
                                else:
                                    sheet.write(i, 0, line.common_code or '', sub_task)
                                    sheet.write(i, 1, line.name or '', sub_task)

                            else:
                                if line.product_id:
                                    sheet.write(i, 0, line.common_code or '', content_code)
                                    sheet.write(i, 1, line.product_id.name or '', content_code)
                                    stage_color_total += line.sub_total
                            sheet.write(i, 2,
                                        line.quantity if line.quantity > 0 and line.display_type not in ['line_section',
                                                                                                         'line_note'] else ' ',
                                        content)
                            sheet.write(i, 3, line.uom_id.name or ' ', content)
                            sheet.write(i, 4, line.unit_price if line.unit_price > 0 and line.display_type not in [
                                'line_section',
                                'line_note'] else ' ', content)
                            # sheet.write(row-1, 8, line.material_total if line.material_total > 0 and line.display_type not in ['line_section',
                            #                                                                              'line_note'] else ' ', txt)
                            sheet.write(i, 5,
                                        line.labour_unit_cost if line.labour_unit_cost > 0 and line.display_type not in [
                                            'line_section',
                                            'line_note'] else ' ', content)

                            sheet.write(i, 6,
                                        line.material_total + line.labour_cost if line.material_total > 0 and line.labour_cost > 0 and line.display_type not in [
                                            'line_section',
                                            'line_note'] else ' ', content)
                            sheet.write(i, 7, line.sub_total if line.sub_total > 0 and line.display_type not in [
                                'line_section',
                                'line_note'] else ' ', content_subtotal)

                            sheet.write(i, 8,
                                        round(line.previous_percent,
                                              2) if line.sub_total > 0 and line.display_type not in ['line_section',
                                                                                                     'line_note'] else ' ',
                                        content_subtotal)
                            previous_subtotal = line.sub_total * (line.previous_percent / 100)
                            sheet.write(i, 9,
                                        round(previous_subtotal, 2) if line.sub_total > 0 and line.display_type not in [
                                            'line_section',
                                            'line_note'] else ' ',
                                        content_subtotal)
                            sheet.write(i, 10,
                                        round(line.present_percent,
                                              2) if line.sub_total > 0 and line.display_type not in ['line_section',
                                                                                                     'line_note'] else ' ',
                                        content_subtotal)
                            present_subtotal = line.sub_total * (line.present_percent / 100)
                            sheet.write(i, 11,
                                        round(present_subtotal, 2) if line.sub_total > 0 and line.display_type not in [
                                            'line_section',
                                            'line_note'] else ' ',
                                        content_subtotal)
                            to_date = round(line.previous_percent + line.present_percent, 2)
                            sheet.write(i, 12,
                                        to_date if line.sub_total > 0 and line.display_type not in ['line_section',
                                                                                                    'line_note'] else ' ',
                                        content_subtotal)
                            to_date_amount = round(previous_subtotal + present_subtotal, 2)
                            sheet.write(i, 13,
                                        to_date_amount if line.sub_total > 0 and line.display_type not in [
                                            'line_section',
                                            'line_note'] else ' ',
                                        content_subtotal)
                            previous_total_amount += round(previous_subtotal, 2)
                            present_total_amount += round(present_subtotal, 2)
                            to_date_total_amount += round(previous_subtotal + present_subtotal, 2)

                        row = i
                        for j, h in enumerate(head):
                            sheet.set_column(j, j, h['larg'])

                        table = []
                        for h in head:
                            col = {}
                            col['header'] = h['name']
                            col.update(h['col'])
                            table.append(col)
                        sheet.add_table(start_row - 1, 0, row + 1, len(head) - 1,
                                        {'total_row': 1,
                                         'columns': table,
                                         'style': 'Table Style Light 9',
                                         'autofilter': False,
                                         })

                        row += 1

                        sheet.write(row, 6, 'Grand Total', cell_format_total)
                        previous_total_percent = (previous_total_amount / project_boq.final_total) * 100
                        present_total_percent = (present_total_amount / project_boq.final_total) * 100
                        to_date_total_percent = (to_date_total_amount / project_boq.final_total) * 100
                        sheet.write(row, 7, project_boq.final_total, cell_format_total)
                        sheet.write(row, 8, previous_total_percent, cell_format_total)
                        sheet.write(row, 9, previous_total_amount, cell_format_total)
                        sheet.write(row, 10, present_total_percent, cell_format_total)
                        sheet.write(row, 11, present_total_amount, cell_format_total)
                        sheet.write(row, 12, to_date_total_percent, cell_format_total)
                        sheet.write(row, 13, to_date_total_amount, cell_format_total)
                    workbook.close()
                    output.seek(0)
                    response.stream.write(output.read())
                    output.close()


class BoqLine(models.Model):
    _name = 'boq.line'
    _rec_name = 'product_id'
    _order="boq_id desc,sequence asc, id"


    is_lower_cost = fields.Boolean(default="False")
    boq_id = fields.Many2one('project.boq')
    name = fields.Char(string='Name')
    product_id = fields.Many2one('product.product')
    display_type = fields.Selection(
        selection=[
            ('line_section', "Section"),
            ('line_note', "Note"),
        ],
        default=False)
    is_sub_task = fields.Boolean(default=False)
    quantity = fields.Float(string='Qty', default=1)
    ordered_qty = fields.Float(string='Ordered Qty')
    completion_percent = fields.Float(string='Completed %', compute='compute_progress')
    uom_id = fields.Many2one('uom.uom', string='UOM')
    unit_price = fields.Float(string='Unit Price')
    material_total = fields.Float(string='Sub Total', compute='compute_cost')
    labour_cost = fields.Float(string='Labour Cost', compute='compute_cost')
    sub_total = fields.Float(string='Total', compute='compute_cost')
    create_po = fields.Boolean(default=False)
    qc_id = fields.Many2one('quantity.computation')
    qc_calculation_id = fields.Many2one('qc.calculation')
    difference_po_cost = fields.Float(string='Difference')
    last_po_price = fields.Float(string='Last PO Price')
    common_code = fields.Char()
    previous_percent = fields.Float(string='Previous Percent')
    present_percent = fields.Float(string='Present Percent')
    labour_unit_cost = fields.Float(string='Labour/Unit', compute='compute_labour_cost')
    labour_unit_cost_extra = fields.Float(string='Labour/Unit')
    actual_completion_percent = fields.Float(string='Actual Completion%')
    to_date_percent = fields.Float(string='To Date Percent')
    previous_amount = fields.Float(string='Previous Amount')
    present_amount = fields.Float(string='Present Amount')
    to_date_amount = fields.Float(string='To Date Amount')
    inventory_product_id = fields.Many2one('product.product', string='Inventory')
    sequence = fields.Integer(string="Sequence")

    @api.onchange('actual_completion_percent')
    def set_actual_billing(self):
        for line in self:
            if line.completion_percent > 0 and not line.display_type in ['line_section', 'line_note']:
                if line.previous_percent == 0:
                    line.present_percent = line.actual_completion_percent
                    line.present_amount = line.sub_total * (line.present_percent / 100)
                else:
                    line.previous_percent += line.present_percent
                    line.previous_amount = line.sub_total * (line.previous_percent / 100)
                    line.present_percent = line.to_date_percent - line.previous_percent
                    line.present_amount = line.sub_total * (line.present_percent / 100)
                line.to_date_percent = line.previous_percent + line.present_percent
                line.to_date_amount = line.previous_amount + line.present_amount

    @api.depends('quantity', 'labour_cost', 'labour_unit_cost_extra','boq_id.n_labour_cost_percent')
    def compute_labour_cost(self):
        for record in self:
            if record.labour_unit_cost_extra != record.labour_unit_cost and not record.labour_unit_cost_extra == 0:
                record.labour_unit_cost = record.labour_unit_cost_extra
            else:
                if record.qc_calculation_id:
                    labour_percent = record.qc_calculation_id.labour_cost_percent
                else:
                    labour_percent = record.boq_id.n_labour_cost_percent
                labour_cost = (record.material_total * labour_percent) / 100
                if record.quantity and labour_cost:
                    record.labour_unit_cost = labour_cost / record.quantity
                    record.labour_unit_cost_extra = record.labour_unit_cost
                else:
                    record.labour_unit_cost = 0



    def action_purchase_history(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("purchase.action_purchase_history")
        product = self.product_id
        action['domain'] = [('state', 'in', ['purchase', 'done']), ('product_id', '=', product.id)]
        action['display_name'] = ("Purchase History for %s" % product.display_name)
        # action['context'] = {
        #     'search_default_partner_id': self.partner_id.id
        # }
        return action

    @api.depends('quantity', 'ordered_qty')
    def compute_progress(self):
        for record in self:
            if record.quantity and record.ordered_qty > 0:
                record.completion_percent = (record.ordered_qty / record.quantity) * 100
            else:
                record.completion_percent = 0

    @api.onchange('quantity', 'unit_price','qc_calculation_id.labour_cost_percent','boq_id.n_labour_cost_percent','qc_calculation_id.total_volume')
    def compute_cost(self):
        for record in self:
            record.is_lower_cost = False
            if record.qc_calculation_id:
                record.quantity = record.qc_calculation_id.total_volume
                if record.unit_price == 0 or record._context.get('is_compute'):
                    record.quantity = record.qc_calculation_id.total_volume
                    record.unit_price = record.product_id.boq_cost
                product = record.product_id
                if product.boq_cost and record.unit_price and product.boq_cost_tolerance_percent:
                    tolerance_amount = (product.boq_cost_tolerance_percent / 100) * product.boq_cost
                    tolerance_amount_higher = product.boq_cost + tolerance_amount
                    tolerance_amount_lower = product.boq_cost - tolerance_amount

                    if record.unit_price > tolerance_amount_higher or record.unit_price < tolerance_amount_lower:
                        record.is_lower_cost = True

            else:
                if record.unit_price == 0 or record._context.get('is_compute'):
                    record.unit_price = record.product_id.boq_cost
                    record.unit_price = record.inventory_product_id.boq_cost
                product = record.product_id
                if record.inventory_product_id:
                    product = record.inventory_product_id
                if product.boq_cost and record.unit_price and product.boq_cost_tolerance_percent:
                    tolerance_amount = (product.boq_cost_tolerance_percent / 100) * product.boq_cost
                    tolerance_amount_higher = product.boq_cost + tolerance_amount
                    tolerance_amount_lower = product.boq_cost - tolerance_amount
                    if record.unit_price > tolerance_amount_higher or record.unit_price < tolerance_amount_lower:
                        record.is_lower_cost = True
            if record.quantity and record.unit_price:
                record.compute_labour_cost()
                labour_percent = 0
                if record.qc_calculation_id:
                    labour_percent = record.qc_calculation_id.labour_cost_percent
                else:
                    labour_percent = record.boq_id.n_labour_cost_percent
                if record.qc_calculation_id:
                    record.material_total = round(record.quantity,2) * record.unit_price
                else:
                    record.material_total = round(record.quantity,2) * record.unit_price
                record.labour_cost = (record.material_total * labour_percent) / 100
                if record.labour_unit_cost_extra:
                    record.labour_cost = record.labour_unit_cost_extra * record.quantity
                record.sub_total = record.material_total + record.labour_cost
            else:
                record.material_total = 0
                record.labour_cost = 0
                record.sub_total = 0
            if record.unit_price and record.qc_calculation_id:
                last_po_line = self.env['purchase.order.line'].search([('state', 'in', ['purchase', 'done']),
                                                                       ('product_id','=', record.product_id.id)],
                                                                      order='create_date desc',limit=1)
                if last_po_line:
                    record.last_po_price = last_po_line.price_unit
                    record.difference_po_cost = record.unit_price - record.last_po_price
            else:
                if record.inventory_product_id:
                    last_po_line = self.env['purchase.order.line'].search([('state', 'in', ['purchase', 'done']),
                                                                           ('product_id', '=',
                                                                            record.inventory_product_id.id)],
                                                                          order='create_date desc', limit=1)
                else:

                    last_po_line = self.env['purchase.order.line'].search([('state', 'in', ['purchase', 'done']),
                                                                       ('product_id', '=',
                                                                        record.product_id.id)],
                                                                      order='create_date desc', limit=1)
                if last_po_line:
                    record.last_po_price = last_po_line.price_unit
                    record.difference_po_cost = record.unit_price - record.last_po_price


class ArchLine(models.Model):
    _name = 'arch.line'
    _rec_name = 'product_id'

    is_lower_cost = fields.Boolean(default="False")
    boq_id = fields.Many2one('project.boq')
    name = fields.Char(string='Name')
    product_id = fields.Many2one('product.product')
    display_type = fields.Selection(
        selection=[
            ('line_section', "Section"),
            ('line_note', "Note"),
        ],
        default=False)
    is_sub_task = fields.Boolean(default=False)
    quantity = fields.Float(string='Qty')
    ordered_qty = fields.Float(string='Ordered Qty')
    completion_percent = fields.Float(string='Completed %', compute='compute_progress')
    uom_id = fields.Many2one('uom.uom', string='UOM')
    unit_price = fields.Float(string='Unit Price', related='product_id.standard_price')
    material_total = fields.Float(string='Total', compute='compute_cost')
    labour_cost = fields.Float(string='Labour Cost', compute='compute_cost')
    sub_total = fields.Float(string='Sub Total', compute='compute_cost')
    create_po = fields.Boolean(default=False)
    qc_id = fields.Many2one('quantity.computation')
    qc_calculation_id = fields.Many2one('qc.calculation')
    difference_po_cost = fields.Float(string='Difference')
    last_po_price = fields.Float(string='Last PO Price')
    labour_unit_cost = fields.Float(string='Labour/Unit', compute='compute_labour_cost')

    @api.depends('quantity', 'labour_cost')
    def compute_labour_cost(self):
        for record in self:
            if record.quantity and record.labour_cost:
                record.labour_unit_cost = record.labour_cost / record.quantity
            else:
                record.labour_unit_cost = 0

    @api.depends('quantity', 'ordered_qty')
    def compute_progress(self):
        for record in self:
            if record.quantity and record.ordered_qty > 0:
                record.completion_percent = (record.ordered_qty / record.quantity) * 100
            else:
                record.completion_percent = 0

    def action_purchase_history(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("purchase.action_purchase_history")
        # if self.qc_calculation_id:
        #     product = self.qc_calculation_id.product_id
        # else:
        product = self.product_id
        action['domain'] = [('state', 'in', ['purchase', 'done']), ('product_id', '=', product.id)]
        action['display_name'] = ("Purchase History for %s" % product.display_name)
        # action['context'] = {
        #     'search_default_partner_id': self.partner_id.id
        # }
        return action

    @api.onchange('quantity', 'unit_price', 'material_total', 'labour_cost')
    def compute_cost(self):
        for record in self:
            record.is_lower_cost = False
            if record.qc_calculation_id:
                record.quantity = record.qc_calculation_id.total_volume
                if record.unit_price == 0 or record._context.get('is_compute'):
                    record.quantity = record.qc_calculation_id.total_volume
                    record.unit_price = record.product_id.boq_cost
                product = record.product_id
                if product.boq_cost and record.unit_price and product.boq_cost_tolerance_percent:
                    tolerance_amount = (product.boq_cost_tolerance_percent / 100) * product.boq_cost
                    tolerance_amount_higher = product.boq_cost + tolerance_amount
                    tolerance_amount_lower = product.boq_cost - tolerance_amount

                    if record.unit_price > tolerance_amount_higher or record.unit_price < tolerance_amount_lower:
                        record.is_lower_cost = True

            else:
                if record.unit_price == 0 or record._context.get('is_compute'):
                    record.unit_price = record.product_id.boq_cost
                product = record.product_id
                if product.boq_cost and record.unit_price and product.boq_cost_tolerance_percent:
                    tolerance_amount = (product.boq_cost_tolerance_percent / 100) * product.boq_cost
                    tolerance_amount_higher = product.boq_cost + tolerance_amount
                    tolerance_amount_lower = product.boq_cost - tolerance_amount
                    if record.unit_price > tolerance_amount_higher or record.unit_price < tolerance_amount_lower:
                        record.is_lower_cost = True
            if record.quantity and record.unit_price:
                labour_percent = 0
                if record.qc_calculation_id.labour_cost_percent > 0:
                    labour_percent = record.qc_calculation_id.labour_cost_percent
                else:
                    labour_percent = record.boq_id.project_id.labour_cost_percent
                if record.qc_calculation_id:
                    record.material_total = round(record.quantity, 2) * record.unit_price
                else:
                    record.material_total = round(record.quantity, 2) * record.unit_price
                record.labour_cost = (record.material_total * labour_percent) / 100
                record.sub_total = record.material_total + record.labour_cost
            else:
                record.material_total = 0
                record.labour_cost = 0
                record.sub_total = 0
            if record.unit_price and record.qc_calculation_id:
                last_po_line = self.env['purchase.order.line'].search([('state', 'in', ['purchase', 'done']),
                                                                       ('product_id', '=',
                                                                        record.product_id.id)],
                                                                      order='create_date desc', limit=1)
                if last_po_line:
                    record.last_po_price = last_po_line.price_unit
                    record.difference_po_cost = record.unit_price - record.last_po_price
            else:
                last_po_line = self.env['purchase.order.line'].search([('state', 'in', ['purchase', 'done']),
                                                                       ('product_id', '=',
                                                                        record.product_id.id)],
                                                                      order='create_date desc', limit=1)
                if last_po_line:
                    record.last_po_price = last_po_line.price_unit
                    record.difference_po_cost = record.unit_price - record.last_po_price
    # @api.depends('')
    # def _compute_name
