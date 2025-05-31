# -*- coding: utf-8 -*-

from odoo import models, fields


class Company(models.Model):
    _inherit = "res.company"

    bir_tin_no = fields.Char(string="TIN(BIR)")
    bir_street = fields.Char(string="Street Line 1 (BIR)")
    bir_street2 = fields.Char(string="Street Line 2 (BIR)")
    bir_zip_code = fields.Char(string="Zip (BIR)")
    bir_city = fields.Char(string="City (BIR)")
    bir_state_id = fields.Many2one("res.country.state", string='State (BIR)')
    bir_country_id = fields.Many2one('res.country', string='Country (BIR)')
    bir_signatory = fields.Text(string="BIR  Signatory", help="Fill in this 'Name | TIN | Designation' format")
