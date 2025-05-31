
from odoo import models, fields, api
from datetime import datetime
from odoo.exceptions import UserError, ValidationError
import io
import json
import xlsxwriter
from odoo import models
from odoo.tools import date_utils


class BillingStatement(models.Model):

    _name = 'billing.statement'
    _inherit = "mail.thread", "mail.activity.mixin"

    partner_id = fields.Many2one('res.partner', string='Customer')
    date = fields.Date(string='Date', default=fields.Date.today())
    name = fields.Char(string='Code')
    billing_statement_line = fields.One2many('billing.statement.line', 'billing_id')
    total_project_completion = fields.Float(string='Total Billed')
    billing_statement_percentage = fields.Float(string='Present Billing Percent')
    project_id = fields.Many2one('project.project', string='Project')
    boq_id = fields.Many2one('project.boq', string='BOQ')
    untaxed_total_amount = fields.Float(string='Untaxed Amount')
    taxes_amount = fields.Float(string='Taxes')
    taxed_total_amount = fields.Float(string='Total Amount')
    total_contract_price = fields.Float(string='Contract Price')
    downpayment_amount_adjusted = fields.Float(string='DownPayment Amount Adjusted')
    retention_amount_adjusted = fields.Float(string='Retention Amount Adjusted')
    total_billing_amount = fields.Float(string='Total Billing Amount(Before Adjustment)')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirmed'),
        ('cancel', 'Cancel')
    ])
    is_down_payment = fields.Boolean(default=False)
    invoice_count = fields.Integer(string='Invoice Count',
                                         help='Invoice Count',
                                         compute='_compute_invoice_count')
    contract_id = fields.Many2one('sale.order', string='Contract')
    is_retention_billing = fields.Boolean(string='Retention Billing', default=False, copy=False)

    @api.model
    def create(self, vals):
        res = super(BillingStatement, self).create(vals)
        if res:
            res.name = self.env['ir.sequence'].next_by_code(
                'billing.statement') or 'New'
        return res

    def create_invoice(self):
        for record in self:
            product_id = record.billing_statement_line.mapped('product_id')
            taxes = record.project_id.tax_id.amount
            untaxed_total_amount = round(record.taxed_total_amount / (1 + (taxes / 100)), 2)
            customer_invoice = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': record.partner_id.id,
                'invoice_date': record.date,
                'invoice_user_id': record.env.user.id,
                'billing_id': record.id,
                'invoice_line_ids': [(0, 0, {
                    'name': product_id.name,
                    'product_id': product_id.id,
                    'quantity': 1,
                    'price_unit': untaxed_total_amount,
                    'analytic_distribution': {str(record.project_id.analytic_account_id.id): 100},
                    'tax_ids': [(6, 0,
                                 record.project_id.tax_id.ids)]
                })]
            })
            if customer_invoice:
                customer_invoice.action_post()
                order = record.boq_id.contract_id
                order.invoice_ids += customer_invoice
                order.invoice_count = len(order.invoice_ids)
                vals = {
                    'order_id': record.boq_id.contract_id.id,
                    'product_id': product_id.id,
                    'billing_percent': record.contract_id.down_payment_percentage if record.is_down_payment else record.billing_statement_percentage,
                    'subtotal_amount': - record.taxed_total_amount,
                }
                order_line = self.env['sale.billing.line'].create(vals)

    def _compute_invoice_count(self):
        for record in self:
            record.invoice_count = len(self.env['account.move'].search([('billing_id', '=', record.id),
                                                                        ('state','=', 'posted')]))

    def action_invoice(self):
        boq = self.env['account.move'].search([('billing_id', '=', self.id),
                                               ('state','=', 'posted')])
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

    def confirm(self):
        for record in self:
            record.state = 'confirm'
            # if record.boq_id and not record.is_down_payment:
            #     for line in record.boq_id.boq_line_ids:
            #         if not line.display_type in ['line_section', 'line_note']:
            #             if line.previous_percent == 0 and line.present_percent == 0:
            #                 line.present_percent = line.completion_percent
            #             else:
            #                 line.previous_percent += line.present_percent
            #                 line.present_percent = line.completion_percent - line.previous_percent

    def cancel(self):
        for record in self:
            record.state = 'cancel'

    def billing_report_excel(self):
        data = {
            'model_id': self.id,
        }
        return {
            'type': 'ir.actions.report',
            'data': {'model': 'billing.statement',
                     'options': json.dumps(data,
                                           default=date_utils.json_default),
                     'output_format': 'xlsx',
                     'report_name': 'Billing Excel Report',
                     },
            'report_type': 'xlsx',
        }


    def get_xlsx_report(self, data, response):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Billing Progress')
        cell_format = workbook.add_format(
            {'font_size': '8px', 'align': 'center', 'bold': True})
        cell_format_total = workbook.add_format(
            {'font_size': '8px', 'align': 'center', 'bold': True, 'bg_color': '#4a646'})
        head = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': '10px'})
        txt = workbook.add_format({'font_size': '8px', 'align': 'center'})
        stage = workbook.add_format(
            {'align': 'center', 'font_size': '8px', 'bg_color': '#4a646'})
        task = workbook.add_format(
            {'align': 'center', 'font_size': '8px', 'bg_color': '#49a596'})
        if data['model_id']:
            project_boq = self.env['billing.statement'].search([('id', '=', data['model_id'])]).boq_id
            if project_boq:
                sheet.merge_range('B2:I3', 'Billing Statement Progress', head)
                sheet.merge_range('A4:B4', 'Project:', cell_format)
                sheet.merge_range('C4:F4', project_boq.project_id.name, cell_format)
                sheet.merge_range('A5:B5', 'Location:', cell_format)
                sheet.merge_range('C5:F5', str(project_boq.location), cell_format)
                sheet.merge_range('A6:B6', 'Owner:', cell_format)
                sheet.merge_range('C6:F6', project_boq.partner_id.name, cell_format)
                sheet.merge_range('A7:B7', 'Date:', cell_format)
                sheet.merge_range('C7:F7', str(project_boq.date), cell_format)
                sheet.merge_range('A8:B8', 'Subject:', cell_format)
                sheet.merge_range('C8:F8', str(project_boq.subject), cell_format)
                sheet.merge_range('A10:A11', 'Item No.', head)
                sheet.merge_range('B10:E11', 'Work Description', head)
                sheet.merge_range('F10:F11', 'Quantity', head)
                sheet.merge_range('G10:G11', 'UOM', head)
                sheet.merge_range('H10:I10', 'Material Cost', head)
                sheet.write('H11:H11', 'Unit', head)
                sheet.write('I11:I11', 'Total', head)
                sheet.merge_range('J10:J11', 'Labour Cost', head)
                sheet.merge_range('K10:K11', 'Total Amount', head)
                sheet.merge_range('L10:M10', 'Previous', head)
                sheet.write('L11:L11', 'Accomplishment', head)
                sheet.write('M11:M11', 'Amount', head)
                sheet.merge_range('N10:O10', 'Present', head)
                sheet.write('N11:N11', 'Accomplishment', head)
                sheet.write('O11:O11', 'Amount', head)
                sheet.merge_range('P10:Q10', 'To-Date', head)
                sheet.write('P11:P11', 'Accomplishment', head)
                sheet.write('Q11:Q11', 'Amount', head)
                row = 12
                previous_total_percent = 0
                previous_total_amount = 0
                present_total_percent = 0
                present_total_amount = 0
                to_date_total_percent = 0
                to_date_total_amount = 0
                for line in project_boq.boq_line_ids:
                    if line.display_type == 'line_section':
                        sheet.merge_range('B%s:E%s'%(row, row),  line.name, stage)
                        # sheet.write(row, 4, line.name, stage)
                    elif line.display_type == 'line_note':
                        parent_task = self.env['project.task'].search([('parent_id','=', False),
                                                                       ('name', '=', line.name)])
                        if parent_task:
                            sheet.merge_range('B%s:E%s' % (row, row), line.name, task)
                        else:
                            sheet.merge_range('B%s:E%s' % (row, row),  line.name, txt)
                    else:
                        if line.product_id:
                            sheet.merge_range('B%s:E%s' % (row, row), line.product_id.name, txt)
                    sheet.write(row-1, 5, line.quantity if line.quantity > 0 and line.display_type not in ['line_section', 'line_note'] else ' ', txt)
                    sheet.write(row-1, 6, line.uom_id.name or ' ', txt)
                    sheet.write(row-1, 7, line.unit_price if line.unit_price > 0 and line.display_type not in ['line_section',
                                                                                                 'line_note'] else ' ', txt)
                    sheet.write(row-1, 8, line.material_total if line.material_total > 0 and line.display_type not in ['line_section',
                                                                                                 'line_note'] else ' ', txt)
                    sheet.write(row-1, 9, line.labour_cost if line.labour_cost > 0 and line.display_type not in ['line_section',
                                                                                                 'line_note'] else ' ', txt)
                    sheet.write(row-1, 10, line.sub_total if line.sub_total > 0 and line.display_type not in ['line_section',
                                                                                                 'line_note'] else ' ', txt)
                    sheet.write(row - 1, 11,
                                round(line.previous_percent,2) if line.sub_total > 0 and line.display_type not in ['line_section',
                                                                                                   'line_note'] else ' ',
                                txt)
                    previous_subtotal = line.sub_total * (line.previous_percent / 100)
                    sheet.write(row - 1, 12,
                                round(previous_subtotal, 2) if line.sub_total > 0 and line.display_type not in ['line_section',
                                                                                                   'line_note'] else ' ',
                                txt)
                    sheet.write(row - 1, 13,
                                round(line.present_percent,2) if line.sub_total > 0 and line.display_type not in ['line_section',
                                                                                                   'line_note'] else ' ',
                                txt)
                    present_subtotal = line.sub_total * (line.present_percent / 100)
                    sheet.write(row - 1, 14,
                                round(present_subtotal,2) if line.sub_total > 0 and line.display_type not in ['line_section',
                                                                                                   'line_note'] else ' ',
                                txt)
                    to_date = round(line.previous_percent + line.present_percent, 2)
                    sheet.write(row - 1, 15,
                                to_date if line.sub_total > 0 and line.display_type not in ['line_section',
                                                                                                   'line_note'] else ' ',
                                txt)
                    to_date_amount = round(previous_subtotal + present_subtotal, 2)
                    sheet.write(row - 1, 16,
                                 to_date_amount if line.sub_total > 0 and line.display_type not in ['line_section',
                                                                                                   'line_note'] else ' ',
                                txt)
                    row += 1
                    # previous_total_percent += round(line.previous_percent, 2)
                    previous_total_amount += round(previous_subtotal, 2)
                    # present_total_percent += round(line.present_percent, 2)
                    present_total_amount += round(present_subtotal, 2)
                    # to_date_total_percent += round(line.previous_percent + line.present_percent, 2)
                    to_date_total_amount += round(previous_subtotal + present_subtotal, 2)
                sheet.write(row, 9, 'Grand Total', cell_format_total)
                previous_total_percent = (previous_total_amount / project_boq.final_total) * 100
                present_total_percent = (present_total_amount / project_boq.final_total) * 100
                to_date_total_percent = (to_date_total_amount / project_boq.final_total) * 100
                sheet.write(row, 10, project_boq.final_total, cell_format_total)
                sheet.write(row, 11, previous_total_percent, cell_format_total)
                sheet.write(row, 12, previous_total_amount, cell_format_total)
                sheet.write(row, 13, present_total_percent, cell_format_total)
                sheet.write(row, 14, present_total_amount, cell_format_total)
                sheet.write(row, 15, to_date_total_percent, cell_format_total)
                sheet.write(row, 16, to_date_total_amount, cell_format_total)
                workbook.close()
                output.seek(0)
                response.stream.write(output.read())
                output.close()

class BillingStatementLine(models.Model):
    _name = 'billing.statement.line'

    billing_id = fields.Many2one('billing.statement', string='Billing ID')
    date = fields.Date(string='Date', default=fields.Date.today())
    product_id = fields.Many2one('product.product', string='Type')
    description = fields.Char(string='Progress')
    reference = fields.Char(string='Reference')
    total_amount_due = fields.Float(string='Total Amount Due')
