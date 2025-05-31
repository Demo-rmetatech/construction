{
    'name': 'All Field Tracking',
    'version': '17.0',
    "category": "Extra Tools",
    'summary': 'Tracks changes to all fields',
    'description': """
        This module tracks changes to every field in the selected model
        and logs them in the chatter automatically.
    """,
    'author': 'Nioses',
    'depends': ['mail','account'],
    'data': [
        'views/ir_model_view.xml',
    ],
    'installable': True,
    'application': False,
}
