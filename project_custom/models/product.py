# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime
from odoo.exceptions import UserError, ValidationError


class ProductProduct(models.Model):

    _inherit = 'product.product'

    boq_item = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], string='BOQ', default="no", related='product_tmpl_id.boq_item')
    boq_cost = fields.Monetary(string='BOQ Cost', related='product_tmpl_id.boq_cost')
    boq_cost_tolerance_percent = fields.Float(string='Tolerance %', related='product_tmpl_id.boq_cost_tolerance_percent')
    is_total_amount = fields.Boolean(string='Contract Amount Product',related='product_tmpl_id.is_total_amount')
    is_billing_product = fields.Boolean(string='Is Billing Product', related='product_tmpl_id.is_billing_product')
    is_job_work = fields.Boolean(string="Is Job Order", compute="_compute_job_work", store=True)

    @api.depends('product_tag_ids')
    def _compute_job_work(self):
        for rec in self:
            if rec.detailed_type == 'service':
                if rec.product_tag_ids:
                    if any(tag.name == 'Job Work' for tag in rec.product_tag_ids):
                        rec.is_job_work = True
                    else: 
                        rec.is_job_work = False
                else:
                    rec.is_job_work = False
            else:
                rec.is_job_work = True


class ProductTemplate(models.Model):

    _inherit = 'product.template'

    boq_item = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], string='BOQ', default="no")
    boq_cost = fields.Monetary(string='BOQ Cost')
    boq_cost_tolerance_percent = fields.Float(string='Tolerance %')
    is_total_amount = fields.Boolean(string='Contract Amount Product', default=False)
    is_billing_product = fields.Boolean(string='Is Billing Product', default=False)
