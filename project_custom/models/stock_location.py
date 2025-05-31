# -*- coding: utf-8 -*-

from odoo import models, fields, api


class StockLocation(models.Model):
    """ Inherit stock.location model"""

    _inherit = 'stock.location'

    project_id = fields.Many2one('project.project', string='Project')
