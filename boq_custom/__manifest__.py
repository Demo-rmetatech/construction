{
    'name': 'BOQ',
    'version': '17.0',
    'summary': 'BOQ Module',
    'description': 'BOQ Module',
    'author': 'Nioses Pvt. Ltd.',
    'company': 'Nioses Pvt. Ltd.',
    'maintainer': 'Nioses Pvt. Ltd.',
    'depends': ['base','product','project','project_custom','documents'],
    'data': [
        'security/ir.model.access.csv',
        'data/boq_cron.xml',
        'views/boq_master_line_view.xml',
        'views/boq_master_view.xml',
        'wizard/show_message_wizard_view.xml',
        'wizard/upload_boq_master_wizard_view.xml',
        'wizard/create_boq_wizard_view.xml',
        'views/menuitem.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'boq_custom/static/src/xml/boq_line_selection.xml',
            'boq_custom/static/src/js/boq_line_selection.js',
            'boq_custom/static/src/js/upload_boq_button.js',
            'boq_custom/static/src/xml/upload_boq_button.xml',
            'boq_custom/static/src/scss/form_controller.scss',
        ],
    },
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': True,

}