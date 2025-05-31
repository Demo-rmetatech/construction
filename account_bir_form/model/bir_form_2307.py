# -*- coding: utf-8 -*-

from odoo import api, models
from odoo.exceptions import UserError,ValidationError
import re
import calendar
from datetime import datetime
from collections import defaultdict
import logging
_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = 'account.move'

    def get_quarter_info(self, date, company_id):
        """
        Determines the quarter and month key for a given date based on the selected fiscal year.

        :param date: Date object (datetime.date or datetime)
        :param fiscal_year: Fiscal year record (account.fiscal.year)
        :return: A tuple with the quarter (Q1, Q2, Q3, or Q4), the month key (1, 2, or 3) within the quarter, and the year.
        """

        if not date or not company_id:
            # Fallback for missing date or company
            return None, None, None, None, None
        quarter, fiscal_year, month_key = None, None, None
        quarter_start_date, quarter_end_date = None, None
        try:
            month = date.month
            year = date.year
            # Get the last month and last day of the fiscal year from the company's configuration
            # Fetch fiscal year details
            fiscal_year_obj = self.env['account.fiscal.year'].search([('company_id', '=', company_id.id)], limit=1)
            if not fiscal_year_obj:
                # Use default company fiscal year configuration if no fiscal year record is found
                fiscalyear_last_month = int(company_id.fiscalyear_last_month) or 12
                fiscalyear_start_month = (fiscalyear_last_month % 12) + 1
            else:
                fiscalyear_start_month = fiscal_year_obj.date_from.month

            # Determine the fiscal year
            fiscal_year = year if month >= fiscalyear_start_month else year - 1

            # Calculate offset and quarter
            month_offset = (month - fiscalyear_start_month) % 12
            quarter_number = (month_offset // 3) + 1

            # Quarter start and end dates
            quarter_start_month = fiscalyear_start_month + (quarter_number - 1) * 3
            if quarter_start_month > 12:
                quarter_start_month -= 12

            quarter_start_date = datetime(fiscal_year, quarter_start_month, 1).strftime('%m%d%Y')

            quarter_end_month = quarter_start_month + 2
            if quarter_end_month > 12:
                quarter_end_month -= 12
                quarter_end_year = fiscal_year + 1
            else:
                quarter_end_year = fiscal_year
            quarter_end_date = datetime(
                quarter_end_year, quarter_end_month, calendar.monthrange(quarter_end_year, quarter_end_month)[1]
            ).strftime('%m%d%Y')

            # Adjusted month and keys
            adjusted_month = (month - fiscalyear_start_month + 12) % 12 + 1
            if adjusted_month in [1, 2, 3]:
                quarter = 'Q1'
                month_key = f'{adjusted_month}'
            elif adjusted_month in [4, 5, 6]:
                quarter = 'Q2'
                month_key = f'{adjusted_month - 3}'
            elif adjusted_month in [7, 8, 9]:
                quarter = 'Q3'
                month_key = f'{adjusted_month - 6}'
            else:
                quarter = 'Q4'
                month_key = f'{adjusted_month - 9}'

        except Exception as e:
            # Log the error for debugging
            _logger.error("Error in get_quarter_info: %s", str(e))

        # Ensure a 5-value tuple is always returned
        return quarter, fiscal_year, month_key, quarter_start_date, quarter_end_date


    def generate_bir_form(self, records):
        vendor_ids = records.mapped('partner_id')
        if len(vendor_ids) > 1:
            raise UserError("Selected bills have different vendors. Please select bills from the same vendor.")
        
        company_ids = records.mapped('company_id')
        if len(company_ids) > 1:
            raise UserError("Selected bills have different Companies. Please select bills for the same company.")


        payee = records[0].partner_id
        payor = records[0].company_id
        selected_quarter = None
        selected_year = None
        bir_signatory = payor.bir_signatory.split('|') if payor.bir_signatory else ""
        bir_payor_signatory_name = bir_signatory[0].strip().upper() if len(bir_signatory) > 0 else '' 
        bir_payor_signatory_tin = bir_signatory[1].strip() if len(bir_signatory) > 1 else ''
        bir_payor_signatory_designation = bir_signatory[2].strip().upper() if len(bir_signatory) > 2 else ''
        payee_registered_address = f"{payee.street or ''} {payee.street2 or ''}, {payee.city or ''}, {payee.state_id.name or ''}, {payee.country_id.name or ''}"
        payor_registered_address = f"{payor.bir_street or ''} {payor.bir_street2 or ''}, {payor.bir_city or ''}, {payor.bir_state_id.name or ''}, {payor.bir_country_id.name or ''}"
        payee_tin_no = re.sub(r'\-', '', payee.vat).ljust(12) if payee.vat else ''
        payor_tin_no = re.sub(r'\-', '', payor.bir_tin_no).ljust(12) if payor.bir_tin_no else ''
        values={
                'payee_name': payee.name,
                'payee_tin_no': "-".join(payee_tin_no[i:i+3] for i in range(0, len(payee_tin_no), 3)) + "  " if payee_tin_no else '',
                'payee_zip_code': payee.zip,
                'payee_registered_address': ', '.join(filter(None, [part.strip() for part in payee_registered_address.split(',')])).strip(','),
                'payee_foreign_address': '',
                'payee_title_or_designation': '',
                'payee_tax_agent_accreditation_no': '',
                'payee_tax_agent_issue_date': '',
                'payee_tax_agent_expiry_date': '',


                'payor_name': payor.name,
                'payor_tin_no': "-".join(payor_tin_no[i:i+3] for i in range(0, len(payor_tin_no), 3)) + "  " if payor_tin_no else '',
                'payor_zip_code': payor.bir_zip_code,
                'payor_registered_address': ', '.join(filter(None, [part.strip() for part in payor_registered_address.split(',')])).strip(','),
                'bir_payor_signatory_name':bir_payor_signatory_name,
                'bir_payor_signatory_tin':bir_payor_signatory_tin,
                'bir_payor_signatory_designation':bir_payor_signatory_designation,
                'payor_tax_agent_accreditation_no': '',
                'payor_tax_agent_issue_date': '',
                'payor_tax_agent_expiry_date': '',

                 'income_subject_to_expanded_withholding_lines': defaultdict(lambda: {
                    'description': '',
                    'month_1': 0.0,
                    'month_2': 0.0,
                    'month_3': 0.0,
                    'quarter_subtotal': 0.0,
                    'tax_withhold_total': 0.0
                }),
                'month_1_expanded_withholding_income_total': 0.0,
                'month_2_expanded_withholding_income_total': 0.0, 
                'month_3_expanded_withholding_income_total': 0.0, 
                'quarter_expanded_withholding_income_total': 0.0,
                'quarterly_tax_withheld_total': 0.0,
            }
        
        if not values.get('payee_tin_no') or not values.get('payor_tin_no'):
            raise ValidationError("Please Provide TIN no in vendor detais and company info")
        
        for invoice_line in records.invoice_line_ids.filtered(lambda l: l.display_type not in ('line_note', 'line_section')):
            quarter, fiscal_year, month_key, quarter_start_date, quarter_end_date = self.get_quarter_info(invoice_line.move_id.invoice_date or invoice_line.move_id.date, payor)
            if selected_quarter is None and selected_year is None:
                selected_quarter = quarter
                selected_year = fiscal_year
                values['from_date'] = quarter_start_date
                values['to_date'] = quarter_end_date

            # Check if each record matches the initially selected quarter and year
            elif quarter != selected_quarter or fiscal_year != selected_year:
                raise UserError("Please select Bills that all belong to the same quarter and year.")
            
            for tax in invoice_line.tax_ids.filtered(lambda x: x.l10n_ph_atc):
                atc_code = tax.l10n_ph_atc
                price_subtotal = invoice_line.price_subtotal
                tax_amount = tax._compute_amount(price_subtotal, invoice_line.price_unit)

                
                # Update dictionary only for the validated quarter and year, formatted to 2 decimal places with trailing zeros
                values['income_subject_to_expanded_withholding_lines'][atc_code]['description'] = tax.wh_tax_description
                values['income_subject_to_expanded_withholding_lines'][atc_code][f'month_{month_key}'] = "{:,.2f}".format(
                    float(str(values['income_subject_to_expanded_withholding_lines'][atc_code].get(f'month_{month_key}', 0)).replace(',', '')) + price_subtotal)
                values['income_subject_to_expanded_withholding_lines'][atc_code]['quarter_subtotal'] = "{:,.2f}".format(
                    float(str(values['income_subject_to_expanded_withholding_lines'][atc_code].get('quarter_subtotal', 0)).replace(',', '')) + price_subtotal)
                values['income_subject_to_expanded_withholding_lines'][atc_code]['tax_withhold_total'] = "{:,.2f}".format(
                    float(str(values['income_subject_to_expanded_withholding_lines'][atc_code].get('tax_withhold_total', 0)).replace(',', '')) + abs(tax_amount))

                values[f'month_{month_key}_expanded_withholding_income_total'] = "{:,.2f}".format(
                    float(str(values.get(f'month_{month_key}_expanded_withholding_income_total', 0)).replace(',', '')) + price_subtotal)
                values['quarter_expanded_withholding_income_total'] = "{:,.2f}".format(
                    float(str(values.get('quarter_expanded_withholding_income_total', 0)).replace(',', '')) + price_subtotal)
                values['quarterly_tax_withheld_total'] = "{:,.2f}".format(
                    float(str(values.get('quarterly_tax_withheld_total', 0)).replace(',', '')) + abs(tax_amount))

                
        report_action = self.env.ref('account_bir_form.action_report_bir_form_2307')
        report = report_action.report_action(self, data=values)
        # paper format
        report['paperformat_id'] = self.env.ref('account_bir_form.paperformat_bir_2307_form').id
        return report
    