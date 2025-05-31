from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

class CreateBoqWizard(models.TransientModel):
    _name = 'create.boq.wizard'
    _description = 'Create BOQ Wizard'

    req_update = fields.Boolean()
    type = fields.Selection([
            ('struct', 'Structural'),
            ('archi', 'Architectural')
        ], string='Type of BOQ', required=True)
    partner_id = fields.Many2one('res.partner',string="Customer",required=True)
    wizard_line_ids = fields.One2many('boq.master.wizard.line', 'wizard_id', string="BOQ Lines")
    struct_name_selection = fields.Selection(selection="_get_struct_name_selection",string='Name')
    archi_name_selection = fields.Selection(selection="_get_archi_name_selection",string='Name')
    
    @api.model
    def _get_struct_name_selection(self):
        domain = [('name','!=',False),('boq_type','=','struct')]
        records = self.env['boq.master'].search(domain)
        unique_names = list(set(record.name for record in records))
        return [(name, name) for name in unique_names]
    
    @api.model
    def _get_archi_name_selection(self):
        domain = [('name','!=',False),('boq_type','=','archi')]
        records = self.env['boq.master'].search(domain)
        unique_names = list(set(record.name for record in records))
        return [(name, name) for name in unique_names]

    @api.onchange('type')
    def _onchange_type(self):
        self.struct_name_selection = None
        self.archi_name_selection = None
        self.wizard_line_ids = [(5, 0, 0)]
    

    @api.onchange('wizard_line_ids.is_delete')
    def _onchange_w_lines(self):
        self.req_update = True

    @api.onchange('type','struct_name_selection','archi_name_selection')
    def _onchange_type_and_name(self):
        self.wizard_line_ids = [(5, 0, 0)]
        name =''
        # Fetch BOQ Masters of selected type
        if self.type == 'archi':
            name = self.archi_name_selection
        elif self.type == 'struct':
            name = self.struct_name_selection
            

        boq_masters = self.env['boq.master'].search([('boq_type', '=', self.type),('name','=',name)])
        
        last_project_stage = None
        last_parent_task = None
        last_sub_task = None
        last_job_work = None
        
        line_vals = []
        count = 0
        for master in boq_masters:
            if master.project_stage and last_project_stage != master.project_stage:
                line_vals.append((0,0,{
                    'name': master.project_stage,
                    'is_project_stage': True,
                    'display_type': 'line_section',
                    'product_id': False,
                    'uom_id': False,
                    'sequence':count,
                }))
                last_project_stage = master.project_stage
                count+=1

            for line in master.boq_line_ids:
                boq_products = line.product_ids
                
                if line.parent_task and line.parent_task != last_parent_task:
                    line_vals.append((0,0,{
                        'name': line.parent_task ,
                        'is_parent_task': True,
                        'display_type': 'line_note',
                        'product_id': False,
                        'uom_id': False,
                        'sequence':count,
                        'create_qty_computation': line.create_product_qty_computation if not line.job_work and not line.sub_task else False,
                        'show_qty_computation' : not line.job_work and not line.sub_task,
                    }))
                    last_parent_task = line.parent_task
                    count+=1

                if line.sub_task and line.sub_task != last_sub_task:
                    line_vals.append((0,0,{
                        'name': f"\t\t\t{line.sub_task}",
                        'display_type': 'line_note',
                        'is_sub_task': True,
                        'product_id': False,
                        'uom_id': False,
                        'sequence':count,
                        'create_qty_computation': line.create_product_qty_computation if not line.job_work else False,
                        'show_qty_computation' : not line.job_work,
                    }))
                    last_sub_task = line.sub_task
                    count+=1

                if line.job_work and line.job_work != last_job_work:
                    line_vals.append((0,0,{
                        'name': f"\t\t\t\t\t\t{line.job_work}" ,
                        'display_type': 'line_note',
                        'is_job_work': True,
                        'product_id': False,
                        'uom_id': False,
                        'sequence':count,
                        'create_qty_computation': line.create_product_qty_computation,
                        'show_qty_computation' : True,
                    }))
                    last_job_work = line.job_work
                    count+=1

                if boq_products:
                    for boq_product in boq_products:
                        line_vals.append((0, 0, {
                            'product_id': boq_product.product_id.id,
                            'uom_id': boq_product.uom_id.id,
                            'sequence':count,
                            'boq_line_id': line.id
                        }))
                        count+=1
        self.wizard_line_ids = line_vals

    def action_remove_lines(self):
        if not self.req_update:
            lines_to_rm = self.wizard_line_ids.filtered(lambda x:x.is_delete)
            lines_to_rm.unlink()
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'create.boq.wizard',
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'new',
            }
        else:
            raise UserError("You Must Select at least one line to Remove")
        
    
        
    def action_create_draft_boq(self):
        if self.wizard_line_ids:
            vals = []
            qty_computation_records = []
            last_parent_task = None
            last_sub_task = None
            last_job_work = None
            is_qty_computation = False
            last_qty_computation_id = False
            project_stage_no = 0
            parent_task_no = 0
            sub_task_no = 0
            job_work_no = 0
            # create_qty_computation = False
            # for index, w_boq_line in enumerate(self.wizard_line_ids):
            for w_boq_line in self.wizard_line_ids:
                if is_qty_computation:
                    if not w_boq_line.display_type:
                        if not last_qty_computation_id:
                            boq_m_line = w_boq_line.boq_line_id
                            qc_lines = []
                            if boq_m_line:
                                for particular in boq_m_line.particular_ids:
                                    if particular.name:
                                        qc_lines.append((0,0,{
                                            'particular': particular.name,
                                            # 'uom_id': w_boq_line.uom_id.id,
                                        }))
                            qc_vals = {
                                'task_id': last_parent_task,
                                'sub_task_id': last_sub_task,
                                'job_id': last_job_work,
                                'qc_line_ids': qc_lines,
                                'product_ids': [(6, 0, [w_boq_line.product_id.id])]
                                # 'product_id': w_boq_line.product_id.id
                            }
                            qc_calculation = self.env['qc.calculation'].create(qc_vals)
                            w_boq_line.qc_calculation_id = qc_calculation.id
                            last_qty_computation_id = qc_calculation
                            qty_computation_records.append(qc_calculation.id)
                        elif last_qty_computation_id:
                            last_qty_computation_id.write({
                                    'product_ids': [(4, w_boq_line.product_id.id)]
                                })
                            w_boq_line.qc_calculation_id = last_qty_computation_id.id
                                
                    else:
                        is_qty_computation = False
                        last_qty_computation_id = False

                if w_boq_line.is_project_stage:
                    project_stage_no+=1
                    parent_task_no = sub_task_no = job_work_no = 0
                elif w_boq_line.is_parent_task:
                    last_parent_task = (w_boq_line.name).strip('\t') 
                    parent_task_no+=1
                    last_sub_task = last_job_work = None
                    sub_task_no = job_work_no = 0
                    if w_boq_line.create_qty_computation:
                        is_qty_computation = True
                elif w_boq_line.is_sub_task:
                    last_sub_task = (w_boq_line.name).strip('\t')
                    sub_task_no+=1
                    last_job_work = None
                    job_work_no = 0
                    if w_boq_line.create_qty_computation:
                        is_qty_computation = True
                        # if index + 1 < len(self.wizard_line_ids):
                        #     next_line = self.wizard_line_ids[index + 1]
                        #     if next_line.is_job_work:
                        #         next_line.create_qty_computation = True
                        # else:
                        #     is_qty_computation = True

                elif w_boq_line.is_job_work:
                    last_job_work = (w_boq_line.name).strip('\t')
                    job_work_no+=1
                    if w_boq_line.create_qty_computation:
                        is_qty_computation = True
                if w_boq_line.display_type:
                    vals.append((0, 0, {
                        'name': (w_boq_line.name).strip('\t'),
                        'display_type': w_boq_line.display_type,
                        'common_code': w_boq_line.create_common_code(project_stage_no,parent_task_no,sub_task_no,job_work_no),
                    }))
                else:
                    vals.append((0, 0, {
                        'product_id': w_boq_line.product_id.id,
                        'qc_calculation_id': w_boq_line.qc_calculation_id.id,
                        'display_type': w_boq_line.display_type,
                        'uom_id': w_boq_line.uom_id.id,
                        'unit_price': w_boq_line.product_id.boq_cost if w_boq_line.product_id else 0,
                    }))
            boq_vals = {
                    # 'project_id': project_id.id,
                    'partner_id': self.partner_id.id,
                    'boq_line_ids': vals,
                    'type_of_boq': self.type
                }
            boq = self.env['project.boq'].create(boq_vals)
            if qty_computation_records:
                recs = self.env['qc.calculation'].browse(qty_computation_records)
                if recs:
                    recs.write({'boq_id':boq.id})
            if boq:
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'project.boq',
                    'view_mode': 'form',
                    'res_id': boq.id,
                    'target': 'current',
                }
            else:
                raise UserError("An error occurred while creating the BOQ.")
        else:
            raise ValidationError("Can't create BOQ with blank BOQ lines.")

            


    def action_update_rec(self):        
        self.req_update = False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'create.boq.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }
    


class BoqMasterWizardLine(models.TransientModel):
    _name = 'boq.master.wizard.line'
    _description = 'BOQ Master Wizard Line'
    _order = 'wizard_id, sequence, id'


    wizard_id = fields.Many2one('create.boq.wizard', string="Wizard")
    name = fields.Text(string="Name")
    is_project_stage = fields.Boolean()
    is_parent_task = fields.Boolean()
    is_sub_task = fields.Boolean()
    is_job_work = fields.Boolean()
    product_id = fields.Many2one('product.product', string="Products")
    uom_id = fields.Many2one('uom.uom', string="UOM")
    sequence = fields.Integer(string="Sequence")
    is_delete = fields.Boolean(string="Delete")
    qc_calculation_id = fields.Many2one('qc.calculation', string="Quality Computation")
    create_qty_computation = fields.Boolean(string="Qty Computation")
    display_type = fields.Selection(
        selection=[
            ('line_section', "Section"),
            ('line_note', "Note"),
        ],
        default=False)
    boq_line_id = fields.Many2one('boq.master.line')
    show_qty_computation = fields.Boolean(default=False)
    
    def create_common_code(self,project_stage_no=0,parent_task_no=0,sub_task_no=0,job_work_no=0):
        code = ''
        if self.is_project_stage and project_stage_no > 0:
            code = str(project_stage_no) 
        elif self.is_parent_task and parent_task_no > 0:
            code = f"{project_stage_no}.{parent_task_no}"
        elif self.is_sub_task and sub_task_no > 0:
            code = f"{project_stage_no}.{parent_task_no}.{sub_task_no}"
        elif self.is_job_work and job_work_no > 0:
            code = f"{project_stage_no}.{parent_task_no}.{sub_task_no}.{job_work_no}"
        # elif self.product_id and product_no > 0:
        #     code = f"{project_stage_no}.{parent_task_no}.{sub_task_no}.{job_work_no}.{product_no}"
        return code
    
    
    @api.onchange('product_id')
    def _onchange_product(self):
        if self.product_id and not self.uom_id:
            self.uom_id = self.product_id.uom_po_id.id if self.product_id.uom_po_id else False
    

    @api._model_create_multi
    def create(self, val_list):
        for vals in val_list:
            if vals.get('name'):
                if vals.get('is_sub_task'):
                    vals['name'] = "\t\t\t" + vals['name'].lstrip('\t')
                elif vals.get('is_job_work'):
                    vals['name'] = "\t\t\t\t\t\t" + vals['name'].lstrip('\t')
        records = super(BoqMasterWizardLine, self).create(val_list)
        if records and len(records)>1:
            for line in records:
                if line.is_delete:
                    line.write({'is_delete':True})
        return records

    def write(self, vals):
        if 'is_delete' in vals:
            for line in self:
                if line.is_project_stage:
                    propagate = False
                    for wizard_line in line.wizard_id.wizard_line_ids:
                        # print(f"inside\n\n\n")
                        if propagate:
                            if wizard_line.is_project_stage and wizard_line.id != line.id:
                                break
                            wizard_line.is_delete = vals['is_delete']
                        if wizard_line.id == line.id:
                            # print(f"dfghjkl\n\n\n")
                            propagate = True
                elif line.is_parent_task:
                    propagate = False
                    for wizard_line in line.wizard_id.wizard_line_ids:
                        if propagate:
                            if wizard_line != line and (wizard_line.is_parent_task or wizard_line.is_project_stage):
                                break
                            wizard_line.is_delete = vals['is_delete']
                        if wizard_line == line:
                            propagate = True
                elif line.is_sub_task:
                    propagate = False
                    for wizard_line in line.wizard_id.wizard_line_ids:
                        if propagate:
                            if wizard_line != line and (wizard_line.is_sub_task or wizard_line.is_parent_task or wizard_line.is_project_stage):
                                break
                            wizard_line.is_delete = vals['is_delete']
                        if wizard_line == line:
                            propagate = True
                elif line.is_job_work:
                    propagate = False
                    for wizard_line in line.wizard_id.wizard_line_ids:
                        if propagate:
                            if wizard_line != line and (wizard_line.is_job_work or wizard_line.is_sub_task or wizard_line.is_parent_task or wizard_line.is_project_stage):
                                break
                            wizard_line.is_delete = vals['is_delete']
                        if wizard_line == line:
                            propagate = True
        if 'name' in vals:
            for record in self:
                updated_vals = vals.copy()
                if record.is_sub_task:
                    updated_vals['name'] = "\t\t\t" + updated_vals['name'].lstrip('\t')
                elif record.is_job_work:
                    updated_vals['name'] = "\t\t\t\t\t" + updated_vals['name'].lstrip('\t')
                super(BoqMasterWizardLine, record).write(updated_vals)
        else:
            super(BoqMasterWizardLine, self).write(vals)

        
        return True
    


