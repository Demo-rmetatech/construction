import json
from odoo import http
from odoo.http import content_disposition, request
from odoo.http import serialize_exception as _serialize_exception
from odoo.tools import html_escape

class XLSXReportController(http.Controller):
    """XlsxReport generating controller"""
    @http.route('/xlsx_reports', type='http', auth='user', methods=['POST'], csrf=False)
    def get_report_xlsx(self, model, options, output_format, **kw):
        """
        Generate an XLSX report based on the provided data and return it as a
        response.
        """
        uid = request.session.uid
        report_obj = request.env[model].with_user(uid)
        options = json.loads(options)
        filename = ''
        # print("=====", report_obj, self, model, options, output_format)
        if str(report_obj) == 'project.boq()':
            project_boq = request.env['project.boq'].search([('id','=', options['model_id'])])
            if project_boq and options['type'] == 'boq':
                if project_boq.project_id:
                    filename = project_boq.project_id.name + ' - ' + project_boq.project_id.partner_id.name
                else:
                    filename = project_boq.partner_id.name

            if project_boq and options['type'] == 'billing':
                if project_boq.project_id:
                    filename = project_boq.project_id.name + ' - ' + 'Progress Report'
                else:
                    filename = project_boq.partner_id.name + ' - ' + 'Progress Report'

        else:
            filename = 'Excel Report'
        token = 'dummy-because-api-expects-one'
        try:
            if output_format == 'xlsx':
                response = request.make_response(
                    None,
                    headers=[
                        ('Content-Type', 'application/vnd.ms-excel'),
                        ('Content-Disposition',
                         content_disposition('%s'%(filename)+ '.xlsx'))
                    ]
                )
                report_obj.get_xlsx_report(options, response)
                response.set_cookie('fileToken', token)
                return response
        except Exception as e:
            se = _serialize_exception(e)
            error = {
                'code': 200,
                'message': 'Odoo Server Error',
                'data': se
            }
            return request.make_response(html_escape(json.dumps(error)))