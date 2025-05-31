# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class Project(models.Model):
    """ Inherit project.project model"""

    _inherit = 'project.project'

    project_location_id = fields.Many2one('stock.location', string='Stock Location')
    labour_cost_percent = fields.Float(string='Labour Cost %')
    contingency_percent = fields.Float(string='Contingency %')
    over_head_profit = fields.Float(string='Over Head Profit %')
    tax_id = fields.Many2one('account.tax', string='VAT')
    project_type_id = fields.Many2one('project.type', string='Project Type')
    total_boq = fields.Integer(string='BOQ', compute='_compute_total_boq', copy=False)
    is_boq_created = fields.Boolean(copy=False)
    project_code = fields.Char(string='Code')
    street = fields.Char(string="Delivery Address")
    street2 = fields.Char()
    city = fields.Char()
    state_id = fields.Many2one('res.country.state')
    zip = fields.Char()

    def _compute_total_boq(self):
        for record in self:
            record.total_boq = len(self.env['project.boq'].search([('project_id', '=', record.id),
                                                                   ('state','!=', 'cancel')]))
            
    def action_create_project(self):
        if self and self.env.context.get('boq_id'):
            boq = self.env['project.boq'].browse(self.env.context.get('boq_id'))
            boq.project_id = self.id
            boq.state = 'project'
            qc_ids = self.env['qc.calculation'].search([('boq_id','=',boq.id)])
            if qc_ids:
                qc_ids.write({'project_id':self.id})
        

    def action_boq(self):
        boq = self.env['project.boq'].search([('project_id', '=', self.id),
                                              ('state','!=', 'cancel')])
        action = self.env["ir.actions.actions"]._for_xml_id("project_custom.action_project_boq")
        if len(boq) > 1:
            action['domain'] = [('id', 'in', boq.ids)]
        elif len(boq) == 1:
            form_view = [(self.env.ref('project_custom.boq_form_view').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = boq.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action



    def set_stages(self):
        struct = []
        arch = []
        task_vals = []
        arch_task_vals = []
        for record in self:
            vals = {
                'name': 'Set BOQ Stages',
                'project_type_id': record.project_type_id.id
            }
            wizard = self.env['project.stage.wizard'].create(vals)
            wizard.project_id = record.id
            if record.project_type_id:
                qc_master = self.env['quantity.computation'].search([])
                if not qc_master:
                    raise UserError("Please configure QC masters")
                # boq_products = self.env['product.template'].search([('detailed_type','=', 'product'), ('boq_item','=', 'yes'),
                #                                                     ('boq_cost','=', 0)])
                # if boq_products:
                #     raise UserError("Please configure BOQ Cost on BOQ Products.")
                project_stages = self.env['project.project.stage'].search([('type_of_project_ids','=', record.project_type_id.id),
                                                                           ('type_of_boq', '=', 'struct')])
                if project_stages:
                    stage_number = 1
                    for stage in project_stages:

                        val = (0, 0, {
                            'display_type': 'line_section',
                            'name': stage.name,
                            'common_code': str(stage_number),
                            'boq_id': wizard.id
                        })
                        struct.append(val)
                        stage_val = (0, 0, {
                            'display_type': 'line_section',
                            'name': stage.name,
                            'boq_id': wizard.id
                        })
                        task_vals.append(stage_val)
                        tasks = self.env['project.task'].search([('project_stage_id', '=', stage.id)])
                        if tasks:
                            task_number = 1
                            for task in tasks:
                                val = (0, 0, {
                                    'display_type': 'line_note',
                                    'name': task.name,
                                    'common_code': str(stage_number) + '.%s'%(str(task_number)),
                                    'boq_id': wizard.id
                                })
                                struct.append(val)
                                task_val = (0, 0, {
                                    'display_type': 'line_note',
                                    'name': task.name,
                                    'boq_id': wizard.id,
                                    'task_id': task.id
                                })
                                task_vals.append(task_val)
                                if task :
                                    if task.product_line_ids and task.type_of_job_work == 'job_work':
                                        line_number = 1
                                        for line in task.product_line_ids:
                                            val = (0, 0, {
                                                'product_id': line.product_id.id,
                                                'common_code': str(stage_number) + '.%s'%(str(task_number)) + '.%s'%(str(line_number)),
                                                'boq_id': wizard.id,
                                                'inventory_product_id': line.inventory_product_id.id
                                            })
                                            struct.append(val)
                                            line_number += 1
                                    if task.inventory_line_ids and task.type_of_job_work == 'inventory':
                                        line_number = 1
                                        for line in task.inventory_line_ids:
                                            val = (0, 0, {
                                                'product_id': line.product_id.id,
                                                'common_code': str(stage_number) + '.%s'%(str(task_number)) + '.%s'%(str(line_number)),
                                                'boq_id': wizard.id
                                            })
                                            struct.append(val)
                                            line_number += 1
                                    sub_tasks = self.env['project.task'].search([('parent_id', '=', task.id)])
                                    if sub_tasks:
                                        subtask_number = 1
                                        for sub_task in sub_tasks:
                                            val = (0, 0, {
                                                'display_type': 'line_note',
                                                'name': sub_task.name,
                                                'common_code': str(stage_number) + '.%s'%(str(task_number)) + '.%s'%(str(subtask_number)),
                                                'boq_id': wizard.id
                                            })
                                            struct.append(val)
                                            if sub_task and sub_task.product_line_ids and sub_task.type_of_job_work == 'job_work':
                                                line_number = 1
                                                for line in sub_task.product_line_ids:
                                                    computation = (self.env['quantity.computation'].search
                                                                   ([('task_id', '=', task.id),
                                                                     ('sub_task_id', '=', sub_task.id),
                                                                     ('job_id', '=', line.id)]))
                                                    val = (0, 0, {
                                                        'product_id': line.product_id.id,
                                                        'qc_id': computation.id,
                                                        'common_code': str(stage_number) + '.%s'%(str(task_number))
                                                                       + '.%s'%(str(subtask_number)) + '.%s'%(str(line_number)),
                                                        'boq_id': wizard.id,
                                                        'inventory_product_id': line.inventory_product_id.id
                                                    })
                                                    struct.append(val)
                                                    line_number += 1
                                            if sub_task and sub_task.inventory_line_ids and sub_task.type_of_job_work == 'inventory':
                                                line_number = 1
                                                for line in sub_task.inventory_line_ids:
                                                    val = (0, 0, {
                                                        'product_id': line.product_id.id,
                                                        'common_code': str(stage_number) + '.%s'%(str(task_number))
                                                                       + '.%s'%(str(subtask_number)) + '.%s'%(str(line_number)),
                                                        'boq_id': wizard.id
                                                    })
                                                    struct.append(val)
                                                    line_number += 1
                                            subtask_number += 1
                                task_number += 1
                        stage_number += 1
                project_stages = self.env['project.project.stage'].search(
                    [('type_of_project_ids', '=', record.project_type_id.id),
                     ('type_of_boq', '=', 'architectural')])
                if project_stages:
                    stage_number = 1
                    for stage in project_stages:
                        val = (0, 0, {
                            'display_type': 'line_section',
                            'name': stage.name,
                            'common_code': str(stage_number)

                        })
                        arch.append(val)
                        stage_val = (0, 0, {
                            'display_type': 'line_section',
                            'name': stage.name,
                            'boq_id': wizard.id
                        })
                        arch_task_vals.append(stage_val)
                        tasks = self.env['project.task'].search([('project_stage_id', '=', stage.id)])
                        if tasks:
                            task_number = 1
                            for task in tasks:
                                val = (0, 0, {
                                    'display_type': 'line_note',
                                    'name': task.name,
                                    'common_code':  str(stage_number) + '.%s'%(str(task_number))
                                })
                                arch.append(val)
                                tasks_val = (0, 0, {
                                    'display_type': 'line_note',
                                    'name': task.name,
                                    'boq_id': wizard.id,
                                    'task_id': task.id
                                })
                                arch_task_vals.append(tasks_val)
                                if task and task.product_line_ids or task.inventory_line_ids:
                                    if task.product_line_ids and task.type_of_job_work == 'job_work':
                                        line_number = 1
                                        for line in task.product_line_ids:
                                            if line.product_id:
                                                val = (0, 0, {
                                                    'product_id': line.product_id.id,
                                                    'common_code': str(stage_number) + '.%s'%(str(task_number)) + '.%s'%(str(line_number)),
                                                    'inventory_product_id': line.inventory_product_id.id
                                                })
                                            arch.append(val)
                                            line_number += 1
                                    if task.inventory_line_ids and task.type_of_job_work == 'inventory':
                                        line_number = 1
                                        for line in task.inventory_line_ids:
                                            if line.product_id:
                                                val = (0, 0, {
                                                    'product_id': line.product_id.id,
                                                    'common_code': str(stage_number) + '.%s'%(str(task_number)) + '.%s'%(str(line_number)),
                                                })
                                                arch.append(val)
                                                line_number += 1
                                    sub_tasks = self.env['project.task'].search([('parent_id', '=', task.id)])
                                    if sub_tasks:
                                        subtask_number = 1
                                        for sub_task in sub_tasks:
                                            val = (0, 0, {
                                                'display_type': 'line_note',
                                                'name': sub_task.name,
                                                'common_code': str(stage_number) + '.%s'%(str(task_number)) + '.%s'%(str(subtask_number))
                                            })
                                            arch.append(val)
                                            if sub_task and sub_task.product_line_ids and sub_task.type_of_job_work == 'job_work':
                                                line_number = 1
                                                for line in sub_task.product_line_ids:
                                                    if line.product_id:
                                                        computation = (self.env['quantity.computation'].search
                                                                       ([('task_id', '=', task.id),
                                                                         ('sub_task_id', '=', sub_task.id),
                                                                         ('job_id', '=', line.id)]))
                                                        val = (0, 0, {

                                                            'product_id': line.product_id.id,
                                                            'qc_id': computation.id,
                                                            'common_code': str(stage_number) + '.%s'%(str(task_number))
                                                                       + '.%s'%(str(subtask_number)) + '.%s'%(str(line_number)),
                                                            'inventory_product_id': line.inventory_product_id.id
                                                        })
                                                        arch.append(val)
                                                        line_number += 1
                                            if sub_task and sub_task.inventory_line_ids and sub_task.type_of_job_work == 'inventory':
                                                line_number = 1
                                                for line in sub_task.inventory_line_ids:
                                                    if line.product_id:
                                                        val = (0, 0, {
                                                            'product_id': line.product_id.id,
                                                            'common_code': str(stage_number) + '.%s'%(str(task_number))
                                                                       + '.%s'%(str(subtask_number)) + '.%s'%(str(line_number))
                                                        })
                                                        arch.append(val)
                                                        line_number += 1
                                            subtask_number += 1
                                task_number += 1
                        stage_number += 1
        wizard.update({
            'po_line_ids': struct,
            'arch_line_ids': arch,
            'task_line_ids': task_vals,
            'arch_task_line_ids': arch_task_vals,
        })
        return {
            'name': 'Set BOQ Structure',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'project.stage.wizard',
            'res_id': wizard.id,
            'view_id': self.env.ref('project_custom.set_project_form_view').id,
            'target': 'new',
        }



    @api.model
    def create(self, vals):
        res = super(Project,self).create(vals)
        if res:
            res.project_code = self.env['ir.sequence'].next_by_code(
                'project.project') or 'New'
            res.create_inventory_location()
            res.create_analytic_account()
        return res

    def create_analytic_account(self):
        for record in self:
            analytic_account_id = self.env['account.analytic.account'].search([
                                                                               ('name', '=', record.name)])
            if analytic_account_id:
                record.analytic_account_id = analytic_account_id.id
            else:
                vals = {
                    'plan_id': self.env['account.analytic.plan'].search([('name','ilike', 'Project')], limit=1).id,
                    'name': record.name,
                    'project_ids': record,
                    'partner_id': record.partner_id.id,
                }
                analytic_account_id = self.env['account.analytic.account'].create(vals)
                record.analytic_account_id = analytic_account_id.id

    def create_inventory_location(self):
        for record in self:
            vals = {
                'name': record.name,
                'usage': 'internal',
                'project_id': record.id
            }
            record.project_location_id = self.env['stock.location'].create(vals)


class ProjectTask(models.Model):
    _inherit = 'project.task'

    project_stage_id = fields.Many2one('project.project.stage', string='Stage')
    product_id = fields.Many2one('product.product', string='Product')
    uom_id = fields.Many2one('uom.uom', string='UOM', related='product_id.uom_id')
    product_line_ids = fields.One2many('task.product', 'task_id', string='Job Work')
    inventory_line_ids = fields.One2many('inv.task.product', 'task_id', string='Inventoried Items')
    type_of_job_work = fields.Selection([
        ('inventory', 'Inventory'),
        ('job_work', 'Job Work')
    ], string='Type of Work', default='job_work')
    task_sequence = fields.Integer(string="Task Sequence")

    # @api.model
    # def create(self, vals):
    #     res = super(ProjectTask, self).create(vals)
    #     if res.parent_id:
    #         vals = {
    #             'name': res.name,
    #             'detailed_type': 'service',
    #             'uom_id': res.uom_id.id,
    #             'uom_po_id': res.uom_id.id,
    #             'service_tracking': 'task_global_project'
    #         }
    #         print("======", vals)
    #         product = self.env['product.product'].sudo().create(vals)
    #         print("=======", product)
    #     return res


class JobWork(models.Model):
    _name = 'task.product'
    _rec_name = 'product_id'

    sequence = fields.Integer(string='Sequence')
    task_id = fields.Many2one('project.task', string='Task')
    product_id = fields.Many2one('product.product', string='Job Work')
    inventory_product_id = fields.Many2one('product.product', string='Product')
    uom_id = fields.Many2one('uom.uom', string='UOM', related='inventory_product_id.uom_id')

    # @api.onchange('inventory_product_id')
    # def set_name =


class ProductInventoriedJobWork(models.Model):
    _name = 'inv.task.product'
    _description = 'Inv Product'
    _rec_name = 'product_id'

    sequence = fields.Integer(string='Sequence')
    task_id = fields.Many2one('project.task', string='Task')
    product_id = fields.Many2one('product.product', string='Product')
    uom_id = fields.Many2one('uom.uom', string='UOM', related='product_id.uom_id')


class ProjectType(models.Model):
    _name = 'project.type'

    name = fields.Char(string='Name')


class ProjectStage(models.Model):
    _inherit = 'project.project.stage'
    _description = 'Project Stages'

    type_of_boq = fields.Selection([
        ('struct', 'Structural'),
        ('architectural', 'Architectural'),
    ], string='Type of BOQ')
    type_of_project_ids = fields.Many2many('project.type', string='Project Type')
