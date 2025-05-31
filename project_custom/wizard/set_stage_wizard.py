# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class ProjectStageWizard(models.TransientModel):
    _name = 'project.stage.wizard'
    _description = 'Project Stage Wizard'

    name = fields.Char()
    type = fields.Selection([
          ('struct', 'Structural'),
        ('archi', 'Architectural')
    ], string='Type of BOQ')
    po_line_ids = fields.One2many('boq.line.wizard', 'boq_id')
    arch_line_ids = fields.One2many('arch.line.wizard', 'boq_id')
    task_line_ids = fields.One2many('task.sequence', 'boq_id')
    arch_task_line_ids = fields.One2many('arch.task.seq', 'boq_id')
    project_type_id = fields.Many2one('project.type', string='Project Type')
    project_id = fields.Many2one('project.project', string='Project')

    def update_boq(self):
        for record in self:
            if record.type == 'struct':
                sequence = 1
                for line in record.task_line_ids:
                    line.task_seq =  line.sequence
                    if line.task_id:
                        line.task_id.task_sequence = line.task_seq
                    sequence += 1
                record.po_line_ids.unlink()
                struct = []
                if record.project_type_id:
                    qc_master = self.env['quantity.computation'].search([])
                    if not qc_master:
                        raise UserError("Please configure QC masters")
                    boq_products = self.env['product.template'].search([('boq_item', '=', 'yes'),
                                                                        ('boq_cost', '=', 0)])
                    # if boq_products:
                    #     raise UserError("Please configure BOQ Cost on BOQ Products.")
                    project_stages = self.env['project.project.stage'].search(
                        [('type_of_project_ids', '=', record.project_type_id.id),
                         ('type_of_boq', '=', 'struct')])
                    if project_stages:
                        stage_number = 1
                        for stage in project_stages:

                            val = (0, 0, {
                                'display_type': 'line_section',
                                'name': stage.name,
                                'common_code': str(stage_number),
                                'boq_id': record.id
                            })
                            struct.append(val)
                            tasks = self.env['project.task'].search([('project_stage_id', '=', stage.id)],
                                                                    order="task_sequence asc")
                            print("======", tasks)
                            if tasks:
                                task_number = 1
                                for task in tasks:
                                    print("=====tskkkkkkkk", task.task_sequence, task.name)
                                    val = (0, 0, {
                                        'display_type': 'line_note',
                                        'name': task.name,
                                        'common_code': str(stage_number) + '.%s' % (str(task_number)),
                                        'boq_id': record.id
                                    })
                                    struct.append(val)
                                    if task:
                                        if task.product_line_ids and task.type_of_job_work == 'job_work':
                                            line_number = 1
                                            for line in task.product_line_ids:
                                                val = (0, 0, {
                                                    'product_id': line.product_id.id,
                                                    'common_code': str(stage_number) + '.%s' % (
                                                        str(task_number)) + '.%s' % (str(line_number)),
                                                    'boq_id': record.id,
                                                    'inventory_product_id': line.inventory_product_id.id

                                                })
                                                struct.append(val)
                                                line_number += 1
                                        if task.inventory_line_ids and task.type_of_job_work == 'inventory':
                                            line_number = 1
                                            for line in task.inventory_line_ids:
                                                val = (0, 0, {
                                                    'product_id': line.product_id.id,
                                                    'common_code': str(stage_number) + '.%s' % (
                                                        str(task_number)) + '.%s' % (str(line_number)),
                                                    'boq_id': record.id
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
                                                    'common_code': str(stage_number) + '.%s' % (
                                                        str(task_number)) + '.%s' % (str(subtask_number)),
                                                    'boq_id': record.id
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
                                                            'common_code': str(stage_number) + '.%s' % (
                                                                str(task_number))
                                                                           + '.%s' % (str(subtask_number)) + '.%s' % (
                                                                               str(line_number)),
                                                            'boq_id': record.id,
                                                            'inventory_product_id': line.inventory_product_id.id
                                                        })
                                                        struct.append(val)
                                                        line_number += 1
                                                if sub_task and sub_task.inventory_line_ids and sub_task.type_of_job_work == 'inventory':
                                                    line_number = 1
                                                    for line in sub_task.inventory_line_ids:
                                                        val = (0, 0, {
                                                            'product_id': line.product_id.id,
                                                            'common_code': str(stage_number) + '.%s' % (
                                                                str(task_number))
                                                                           + '.%s' % (str(subtask_number)) + '.%s' % (
                                                                               str(line_number)),
                                                            'boq_id': record.id
                                                        })
                                                        struct.append(val)
                                                        line_number += 1
                                                subtask_number += 1
                                    task_number += 1
                            stage_number += 1
                print("====", struct)
                record.update({
                    'po_line_ids': struct,
                })
            if record.type == 'archi':
                sequence = 1
                for line in record.arch_task_line_ids:
                    line.task_seq = line.sequence
                    if line.task_id:
                        line.task_id.task_sequence = line.task_seq
                    sequence += 1
                record.arch_line_ids.unlink()
                arch = []
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
                        tasks = self.env['project.task'].search([('project_stage_id', '=', stage.id)],
                                                                order="task_sequence asc")
                        if tasks:
                            task_number = 1
                            for task in tasks:
                                val = (0, 0, {
                                    'display_type': 'line_note',
                                    'name': task.name,
                                    'common_code': str(stage_number) + '.%s' % (str(task_number))
                                })
                                arch.append(val)
                                if task and task.product_line_ids or task.inventory_line_ids:
                                    if task.product_line_ids and task.type_of_job_work == 'job_work':
                                        line_number = 1
                                        for line in task.product_line_ids:
                                            if line.product_id:
                                                val = (0, 0, {
                                                    'product_id': line.product_id.id,
                                                    'common_code': str(stage_number) + '.%s' % (
                                                        str(task_number)) + '.%s' % (str(line_number)),
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
                                                    'common_code': str(stage_number) + '.%s' % (
                                                        str(task_number)) + '.%s' % (str(line_number)),
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
                                                'common_code': str(stage_number) + '.%s' % (
                                                    str(task_number)) + '.%s' % (str(subtask_number))
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
                                                            'common_code': str(stage_number) + '.%s' % (
                                                                str(task_number))
                                                                           + '.%s' % (str(subtask_number)) + '.%s' % (
                                                                               str(line_number)),
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
                                                            'common_code': str(stage_number) + '.%s' % (
                                                                str(task_number))
                                                                           + '.%s' % (str(subtask_number)) + '.%s' % (
                                                                               str(line_number))
                                                        })
                                                        arch.append(val)
                                                        line_number += 1
                                            subtask_number += 1
                                task_number += 1
                        stage_number += 1
                record.update({
                    'arch_line_ids': arch,
                })
            return {
                'name': 'Set BOQ Structure',
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'project.stage.wizard',
                'res_id': record.id,
                'view_id': self.env.ref('project_custom.set_project_form_view').id,
                'target': 'new',
            }
    # @api.onchange('po_line_ids', 'arch_line_ids')
    # def unlink_lines(self):
    #     for record in self:
    #         selected_lines = self.po_line_ids.filtered(lambda l: l.select_line and l.common_code)
    #         arch_selected_lines = self.po_line_ids.filtered(lambda l: l.select_line and l.common_code)
    #         if selected_lines:
    #             lines = self.env['boq.line.wizard']
    #             sub_task_lines = self.env['boq.line.wizard']
    #             job_lines = self.env['boq.line.wizard']
    #             lines = selected_lines.filtered(lambda l: l.common_code == record.common_code)
    #             if lines:
    #                 sub_task_lines = self.po_line_ids.filtered(
    #                     lambda l: l.common_code == lines.mapped('common_code'))
    #                 if sub_task_lines:
    #                     job_lines = self.po_line_ids.filtered(
    #                         lambda l: l.common_code == sub_task_lines.mapped('common_code'))
    #             lines.unlink()
    #             sub_task_lines.unlink()
    #             job_lines.unlink()
    #         if arch_selected_lines:
    #             lines = self.env['arch.line.wizard']
    #             sub_task_lines = self.env['arch.line.wizard']
    #             job_lines = self.env['arch.line.wizard']
    #             lines = selected_lines.filtered(lambda l: l.common_code == record.common_code)
    #             if lines:
    #                 sub_task_lines = self.po_line_ids.filtered(
    #                     lambda l: l.common_code == lines.mapped('common_code'))
    #                 if sub_task_lines:
    #                     job_lines = self.po_line_ids.filtered(
    #                         lambda l: l.common_code == sub_task_lines.mapped('common_code'))
    #             lines.unlink()
    #             sub_task_lines.unlink()
    #             job_lines.unlink()

    def create_draft_boq(self):
        project_id = self.project_id
        project_id.is_boq_created = True
        if project_id:
            if self.po_line_ids:
                qc_calculation = self.env['qc.calculation']
                line_ids = self.po_line_ids
                for qc in line_ids:
                    if qc.qc_id:
                        if qc.qc_id.job_id.inventory_product_id:
                            product = qc.qc_id.job_id.inventory_product_id
                        elif qc.qc_id.sub_task_id.product_id:
                            product = qc.qc_id.sub_task_id.product_id
                        else:
                            product = qc.qc_id.task_id.product_id
                        line_vals = []
                        for line in qc.qc_id.qc_line_ids:
                            val = (0, 0, {
                                'product_id': line.product_id.id,
                                'uom_id': product.uom_id.id,
                            })
                            line_vals.append(val)
                        vals = {
                            'project_id': project_id.id,
                            'task_id': qc.qc_id.task_id.id,
                            'sub_task_id': qc.qc_id.sub_task_id.id,
                            'job_id': qc.qc_id.job_id.id,
                            'qc_line_ids': line_vals,
                            'product_id': product.id
                        }
                        qc_calculation = self.env['qc.calculation'].create(vals)
                        qc.qc_calculation_id = qc_calculation
                order_lines = []
                arch_lines = []
                for struct_line in self.po_line_ids:
                    unit_price = 0
                    # if struct_line.qc_calculation_id:
                    #     uom = struct_line.qc_calculation_id.product_id.uom_id
                    # else:
                    #     if struct_line.inventory_product_id:
                    #         uom = struct_line.inventory_product_id.uom_id
                    #         unit_price = struct_line.inventory_product_id.boq_cost
                    #     else:
                    uom = struct_line.product_id.uom_id
                    unit_price = struct_line.product_id.boq_cost
                    vals =(0, 0, {
                        'name': struct_line.name,
                        'product_id': struct_line.product_id.id,
                        'inventory_product_id': struct_line.inventory_product_id.id,
                        'display_type': struct_line.display_type,
                        'qc_calculation_id': struct_line.qc_calculation_id.id,
                        'uom_id': uom.id,
                        'common_code': struct_line.common_code,
                        'unit_price': unit_price if unit_price else 0,
                    })
                    order_lines.append(vals)
                for arch_line in self.arch_line_ids:
                    unit_price = 0
                    if arch_line.inventory_product_id:
                        uom = arch_line.inventory_product_id.uom_id
                        unit_price = arch_line.inventory_product_id.boq_cost
                    else:
                        uom = arch_line.product_id.uom_id
                        unit_price = arch_line.product_id.boq_cost
                    vals = (0, 0, {
                        'name': arch_line.name,
                        'product_id': arch_line.product_id.id,
                        'inventory_product_id': arch_line.inventory_product_id.id,
                        'display_type': arch_line.display_type,
                        'qc_calculation_id': arch_line.qc_calculation_id.id,
                        'uom_id': uom.id,
                        'common_code': arch_line.common_code,
                        'unit_price': unit_price if unit_price else 0,
                    })
                    arch_lines.append(vals)
                boq_vals = {
                    'project_id': project_id.id,
                    'partner_id': project_id.partner_id.id,
                    'boq_line_ids': order_lines if self.type == 'struct' else arch_lines,
                    'type_of_boq': 'struct' if self.type == 'struct' else 'archi'
                }
                draft_boq = self.env['project.boq'].create(boq_vals)
                    # draft_boq.update({'arch_line_ids': arch_lines})


class BoqLineWizard(models.TransientModel):
    _name = 'boq.line.wizard'
    _rec_name = 'product_id'

    boq_id = fields.Many2one('project.stage.wizard')
    name = fields.Char(string='Name')
    product_id = fields.Many2one('product.product')
    inventory_product_id = fields.Many2one('product.product')
    qc_id = fields.Many2one('quantity.computation')
    qc_calculation_id = fields.Many2one('qc.calculation')
    display_type = fields.Selection(
        selection=[
            ('line_section', "Section"),
            ('line_note', "Note"),
        ],
        default=False)
    common_code = fields.Char()


class ArchitecturalLineWizard(models.TransientModel):
    _name = 'arch.line.wizard'
    _description = 'Arch Line Wizard'
    _rec_name = 'product_id'

    boq_id = fields.Many2one('project.stage.wizard')
    name = fields.Char(string='Name')
    product_id = fields.Many2one('product.product')
    inventory_product_id = fields.Many2one('product.product')
    qc_id = fields.Many2one('quantity.computation')
    qc_calculation_id = fields.Many2one('qc.calculation')
    display_type = fields.Selection(
        selection=[
            ('line_section', "Section"),
            ('line_note', "Note"),
        ],
        default=False)
    common_code = fields.Char()


class TaskSequence(models.TransientModel):
    _name = 'task.sequence'
    _description = 'Task Sequence'

    boq_id = fields.Many2one('project.stage.wizard')
    sequence = fields.Integer(string='Sequence', default=1)
    task_seq = fields.Integer(string='Task Seq')
    name = fields.Char(string='Name')
    display_type = fields.Selection(
        selection=[
            ('line_section', "Section"),
            ('line_note', "Note"),
        ],
        default=False)
    task_id = fields.Many2one('project.task')


class ArchTaskSequence(models.TransientModel):
    _name = 'arch.task.seq'
    _description = 'Task Sequence'

    boq_id = fields.Many2one('project.stage.wizard')
    sequence = fields.Integer(string='Sequence', default=1)
    task_seq = fields.Integer(string='Task Seq')
    name = fields.Char(string='Name')
    display_type = fields.Selection(
        selection=[
            ('line_section', "Section"),
            ('line_note', "Note"),
        ],
        default=False)
    task_id = fields.Many2one('project.task')
