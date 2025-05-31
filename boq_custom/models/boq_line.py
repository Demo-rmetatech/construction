from odoo import models, fields, api, _


class BoqMasterLine(models.Model):
    _name = 'boq.master.line'
    _description = 'BOQ Line model'
    _rec_name = 'parent_task'
    _order="boq_master_id desc, sequence asc, id"

    boq_master_id = fields.Many2one('boq.master', string="BOQ")
    parent_task = fields.Char(string="Parent Task")
    sub_task = fields.Char(string="Sub-tasks")
    job_work = fields.Char(string="Job Work")
    create_product_qty_computation = fields.Boolean(string="Create Quantity Computation")
    product_ids = fields.One2many('boq.line.product','boq_line_id',string="Products")
    particular_ids = fields.One2many('qty.particular','boq_line_id', string="Particulars")
    sequence = fields.Integer(string="Sequence")


class BoqLineProduct(models.Model):
    _name = "boq.line.product"
    _description = "BOQ Line Products"
    _rec_name = 'product_id'

    boq_line_id = fields.Many2one('boq.master.line', string="BOQ Line")
    product_id = fields.Many2one('product.product', string="Product")
    uom_id = fields.Many2one('uom.uom', related="product_id.uom_po_id", string="UOM")

class QtyParticular(models.Model):
    _name = "qty.particular"
    _description = "Quantity Particulars"
    _rec_name = 'name'

    boq_line_id = fields.Many2one('boq.master.line', string="BOQ Line")
    name = fields.Char(string="Particular")
