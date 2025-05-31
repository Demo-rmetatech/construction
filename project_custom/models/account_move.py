
from odoo import models, fields, api,_
from odoo.exceptions import UserError, ValidationError
from collections import defaultdict


class AccountMove(models.Model):

    _inherit = 'account.move'

    billing_id = fields.Many2one('billing.statement', string='Billing')
    state = fields.Selection(selection_add=[
        ('waiting_approval', 'Waiting Payment Approval')
    ], ondelete={'waiting_approval': 'set default'}
    )
    payment_state = fields.Selection(selection_add=[
        ('waiting_approval', 'Waiting Payment Approval')],
        )
    is_approved = fields.Boolean(default=False, copy=False)
    is_rejected = fields.Boolean(string='Payment Rejected', default=False, copy=False)

    @api.depends('amount_residual', 'move_type', 'state', 'company_id')
    def _compute_payment_state(self):
        stored_ids = tuple(self.ids)
        if stored_ids:
            self.env['account.partial.reconcile'].flush_model()
            self.env['account.payment'].flush_model(['is_matched'])

            queries = []
            for source_field, counterpart_field in (('debit', 'credit'), ('credit', 'debit')):
                queries.append(f'''
                            SELECT
                                source_line.id AS source_line_id,
                                source_line.move_id AS source_move_id,
                                account.account_type AS source_line_account_type,
                                ARRAY_AGG(counterpart_move.move_type) AS counterpart_move_types,
                                COALESCE(BOOL_AND(COALESCE(pay.is_matched, FALSE))
                                    FILTER (WHERE counterpart_move.payment_id IS NOT NULL), TRUE) AS all_payments_matched,
                                BOOL_OR(COALESCE(BOOL(pay.id), FALSE)) as has_payment,
                                BOOL_OR(COALESCE(BOOL(counterpart_move.statement_line_id), FALSE)) as has_st_line
                            FROM account_partial_reconcile part
                            JOIN account_move_line source_line ON source_line.id = part.{source_field}_move_id
                            JOIN account_account account ON account.id = source_line.account_id
                            JOIN account_move_line counterpart_line ON counterpart_line.id = part.{counterpart_field}_move_id
                            JOIN account_move counterpart_move ON counterpart_move.id = counterpart_line.move_id
                            LEFT JOIN account_payment pay ON pay.id = counterpart_move.payment_id
                            WHERE source_line.move_id IN %s AND counterpart_line.move_id != source_line.move_id
                            GROUP BY source_line_id, source_move_id, source_line_account_type
                        ''')

            self._cr.execute(' UNION ALL '.join(queries), [stored_ids, stored_ids])

            payment_data = defaultdict(lambda: [])
            for row in self._cr.dictfetchall():
                payment_data[row['source_move_id']].append(row)
        else:
            payment_data = {}

        for invoice in self:
            if invoice.payment_state == 'invoicing_legacy':
                # invoicing_legacy state is set via SQL when setting setting field
                # invoicing_switch_threshold (defined in account_accountant).
                # The only way of going out of this state is through this setting,
                # so we don't recompute it here.
                continue

            currencies = invoice._get_lines_onchange_currency().currency_id
            currency = currencies if len(currencies) == 1 else invoice.company_id.currency_id
            reconciliation_vals = payment_data.get(invoice.id, [])
            payment_state_matters = invoice.is_invoice(True)

            # Restrict on 'receivable'/'payable' lines for invoices/expense entries.
            if payment_state_matters:
                reconciliation_vals = [x for x in reconciliation_vals if
                                       x['source_line_account_type'] in ('asset_receivable', 'liability_payable')]

            new_pmt_state = 'not_paid'
            if invoice.state == 'posted':

                # Posted invoice/expense entry.
                if payment_state_matters:

                    if currency.is_zero(invoice.amount_residual):
                        if any(x['has_payment'] or x['has_st_line'] for x in reconciliation_vals):

                            # Check if the invoice/expense entry is fully paid or 'in_payment'.
                            if all(x['all_payments_matched'] for x in reconciliation_vals):
                                new_pmt_state = 'paid'
                            else:
                                new_pmt_state = invoice._get_invoice_in_payment_state()

                        else:
                            new_pmt_state = 'paid'

                            reverse_move_types = set()
                            for x in reconciliation_vals:
                                for move_type in x['counterpart_move_types']:
                                    reverse_move_types.add(move_type)

                            in_reverse = (invoice.move_type in ('in_invoice', 'in_receipt')
                                          and (reverse_move_types == {'in_refund'} or reverse_move_types == {
                                        'in_refund', 'entry'}))
                            out_reverse = (invoice.move_type in ('out_invoice', 'out_receipt')
                                           and (reverse_move_types == {'out_refund'} or reverse_move_types == {
                                        'out_refund', 'entry'}))
                            misc_reverse = (invoice.move_type in ('entry', 'out_refund', 'in_refund')
                                            and reverse_move_types == {'entry'})
                            if in_reverse or out_reverse or misc_reverse:
                                new_pmt_state = 'reversed'

                    elif reconciliation_vals:
                        new_pmt_state = 'partial'

            invoice.payment_state = new_pmt_state
            if invoice.payment_state == 'partial' and invoice.move_type == 'in_invoice':
                invoice.is_approved = True

    def set_approval(self):
        for record in self:
            record.is_approved = True

    def action_post(self):
        res = super(AccountMove, self).action_post()
        if self.move_type == 'in_invoice':
            self.is_approved = True
        return res

    def request_approval(self):
        for record in self:
            record.payment_state = 'waiting_approval'

    def approval(self):
        for record in self:
            record.is_approved = False
            record.is_rejected = False
            if record.amount_residual != record.amount_total:
                record.payment_state = 'partial'
            else:
                record.payment_state = 'not_paid'


    def reject(self):
        for record in self:
            record.state = 'posted'
            record.is_rejected = True
            record.is_approved = True
            record.payment_state = 'not_paid'


class ResCompany(models.Model):
    _inherit = 'res.company'

    is_company_details_empty = fields.Boolean(default=False)


class AccountPayment(models.Model):
    _inherit = 'account.payment'
    # _inherit = ['portal.mixin', 'product.catalog.mixin', 'mail.thread', 'mail.activity.mixin', 'utm.mixin']


    prepared_by = fields.Many2one('hr.employee', string='Prepared By', default=lambda self: self.env.user.employee_id)
    approved_by = fields.Many2one('hr.employee', string='Approved By')
    checked_by = fields.Many2one('hr.employee', string='Checked By')
    project_id = fields.Many2one('project.project', string='Project')
    approval_status = fields.Selection([
        ('draft', 'Draft'),
        ('waiting_approval', 'Waiting Payment Approval'),
        ('approved', 'Approved'),
    ], string='Approval Status', tracking=True)
    is_waiting_approval = fields.Boolean(default=False)
    is_rejected = fields.Boolean(default=False, string='Payment Rejected')
    new_payment_id = fields.Many2one('account.payment', string="New Payment")

    def change_payment(self):
        no_found = []
        active_ids = self.env.context.get('active_ids')
        if not active_ids:
            raise UserError('No active payment found.')
        else:
            for active_id in active_ids:
                payment = self.env['account.payment'].browse(active_id)
                if not payment:
                    raise UserError('Payment not found.')
                if payment.state == 'posted':
                    if payment.reconciled_bill_ids:
                        for bill in payment.reconciled_bill_ids:
                            # Ensure the bill is in a state that allows for canceling and reposting
                            if bill.state == 'posted':
                                # Cancel the payment to reverse its effects
                                payment.action_draft()  # Ensure the payment is cancellable

                                payment.action_cancel()  # Ensure the payment is cancellable

                                # Move the bill back to draft
                                bill.button_draft()

                                # Post the bill again
                                bill.action_post()

                                # If bill approval is required, request approval
                                if hasattr(bill, 'request_approval'):
                                    bill.request_approval()

                                # If approval action is available, perform approval
                                if hasattr(bill, 'approval'):
                                    bill.approval()
                            
                        # Create a new payment for the same partner and bill
                        vals = {
                            'journal_id': 14,  # Replace with your desired journal ID
                            'amount': payment.amount,   # Replace with the amount you need
                            'communication':payment.ref,
                            'partner_id': payment.partner_id.id,
                            'payment_date': payment.date,
                            
                            'partner_bank_id':payment.partner_bank_id.id,

                            'payment_type': 'outbound',  # Assuming outbound payment
                            'partner_type': 'supplier',  # Assuming this is for a supplier
                            'company_id': payment.company_id.id,  # Same company as original payment
                        }


                        # Create the new payment
                        payment_register = self.env['account.payment.register'].with_context(
                            active_model='account.move', active_ids=[bill.id]).create(vals)
                        
                        # Confirm the payment to process it
                        new_payment = payment_register._create_payments()
                        if new_payment:
                            payment.write({'new_payment_id':new_payment.id})
                            new_payment.write({
                                            'project_id':payment.project_id.id,
                                            'prepared_by':payment.prepared_by.id,
                                            'checked_by':payment.checked_by.id,
                                            'approved_by':payment.approved_by.id,})
                            new_payment.request_approval()
                            new_payment.approval()
                    else:
                        no_found.append(payment.name)
        if len(no_found) > 0:
            raise UserError(f'No reconciled bills found for this payment. {no_found}')



    # @api.model
    # def create(self, vals):
    #     res = super(AccountPayment, self).create(vals)
    #     if res.payment_type == 'outbound':
    #         res.approval_status = 'draft'
    #     return res

    def set_approval(self):
        for record in self:
            record.approval_status = 'draft'

    def request_approval(self):
        group_admin = self.env.ref('base.group_user')
        group_account = self.env.ref('account.group_account_manager')
        if group_admin and group_account:
            users = self.env['res.users'].search([
                ('groups_id', 'in', [group_admin.id, group_account.id])
            ])
            if users:
                for user in users:
                    self.activity_schedule(
                        'mail.mail_activity_data_todo', 
                        user_id= user.id,
                        note =_("Internal Transfers - Vendor"),
                        summary='Pending for approval',
                    )
            for record in self:
                record.approval_status = 'waiting_approval'
                record.is_waiting_approval = True
        else:
            raise UserError("No Approver Found , Please Contact Your Administrator.")

    def approval(self):
        for record in self:
            record.approval_status = 'approved'
            record.is_waiting_approval = False
            record.is_rejected = False
            if self.create_uid.id:
                self.activity_schedule(
                    'mail.mail_activity_data_todo', 
                    user_id=self.create_uid.id,
                    note=_("Approved Payments"),
                    summary='Approved'
                )


    def reject(self):
        for record in self:
            record.approval_status = 'draft'
            record.is_waiting_approval = False
            record.is_rejected = True

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def get_account_name(self):
        if self.account_id:
            return '%s %s' %(self.account_id.code, self.account_id.name)


