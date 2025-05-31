# -*- coding: utf-8 -*-

from odoo import models, fields, api


class QuantityComputation(models.Model):
    _name = 'quantity.computation'
    _rec_name = 'job_id'

    task_id = fields.Many2one('project.task', string='Task')
    sub_task_id = fields.Many2one('project.task', string='Sub Task')
    job_id = fields.Many2one('task.product', string='Job Work')
    qc_line_ids = fields.One2many('qc.product', 'qc_id')
    total_volume = fields.Float(string='Total Volume', compute='_compute_total_volume')
    labour_cost_percent = fields.Float(string='Labour Cost %')

    @api.depends('qc_line_ids.volume')
    def _compute_total_volume(self):
        for record in self:
            record.total_volume = 0
            for line in record.qc_line_ids:
                record.total_volume += line.volume


class QuantityComputationCalculation(models.Model):
    _name = 'qc.calculation'
    _rec_name = 'job_id'

    task_id = fields.Char( string='Task')
    sub_task_id = fields.Char( string='Sub Task')
    job_id = fields.Char( string='Job Work')
    qc_line_ids = fields.One2many('qc.product.line', 'qc_id')
    total_volume = fields.Float(string='Total Volume', compute='_compute_total_volume')
    labour_cost_percent = fields.Float(string='Labour Cost %')
    project_id = fields.Many2one('project.project', string='Project')
    boq_id = fields.Many2one('project.boq', string='BOQ')
    product_ids = fields.Many2many('product.product', string='Products')

    @api.depends('qc_line_ids.volume')
    def _compute_total_volume(self):
        for record in self:
            record.total_volume = 0
            for line in record.qc_line_ids:
                record.total_volume += line.volume


class QCProductLine(models.Model):
    _name = 'qc.product.line'

    qc_id = fields.Many2one('qc.calculation')
    particular = fields.Char(string='Particular')
    # uom_id = fields.Many2one('uom.uom', string='UOM')
    length = fields.Float(string='L')
    width = fields.Float(string='W')
    height = fields.Float(string='H')
    quantity = fields.Float(string='Qty')
    volume = fields.Float(string='Volume', readonly=True)

    @api.onchange('length', 'width', 'height', 'quantity')
    def calculate_volume(self):
        for record in self:
            if record.length and record.width and record.height and record.quantity:
                record.volume = record.length * record.width * record.height * record.quantity


class QCProduct(models.Model):
    _name = 'qc.product'

    qc_id = fields.Many2one('quantity.computation')
    product_id = fields.Many2one('product.product', string='Particular')
    uom_id = fields.Many2one('uom.uom', string='UOM', related='product_id.uom_id')
    length = fields.Float(string='L')
    width = fields.Float(string='W')
    height = fields.Float(string='H')
    quantity = fields.Float(string='Qty')
    volume = fields.Float(string='Volume', readonly=True)

    @api.onchange('length', 'width', 'height', 'quantity')
    def calculate_volume(self):
        for record in self:
            if record.length and record.width and record.height and record.quantity:
                record.volume = record.length * record.width * record.height * record.quantity
