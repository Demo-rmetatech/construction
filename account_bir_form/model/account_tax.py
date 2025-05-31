# -*- coding: utf-8 -*-

from odoo import api, models, fields


class AccountMoveLine(models.Model):
    _inherit = "account.tax"

    wh_tax_description = fields.Text(string='WH Tax Description', help='Description according to Philiphians ATC code')