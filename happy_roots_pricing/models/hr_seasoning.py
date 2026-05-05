from odoo import api, fields, models


class HrSeasoning(models.Model):
    """
    Catálogo de condimentos — equivale a la sección '7. CONDIMENTOS MALUQUER'
    de la hoja Supuestos. Cada registro es un sabor/condimento con su precio
    USD/kg y código de proveedor.
    """
    _name = 'hr.seasoning'
    _description = 'Happy Roots — Catálogo de Condimentos'
    _order = 'name'
    _rec_name = 'display_name_full'

    name = fields.Char('Nombre del condimento', required=True)
    code = fields.Char('Código proveedor', help='Código Maluquer (ej. 72889, 72656)')
    display_name_full = fields.Char(
        compute='_compute_display_name', store=True, string='Nombre completo')

    price_per_kg_usd = fields.Float(
        'Precio USD/kg', required=True, digits=(10, 4),
        help='Precio del condimento por kilogramo, en dólares US. '
             'Fuente: cotización Maluquer #26138 (nov-2025) o estimación.')
    is_confirmed = fields.Boolean(
        'Precio confirmado', default=False,
        help='True = cotización formal recibida. '
             'False = SUPUESTO — requiere cotización Maluquer antes del primer embarque.')
    quotation_ref = fields.Char(
        'Referencia cotización', default='Maluquer #26138',
        help='Número de oferta del proveedor.')
    quotation_date = fields.Date('Fecha cotización', default='2025-11-18')
    valid_until = fields.Date('Vigencia cotización', default='2025-12-18')
    supplier_id = fields.Many2one(
        'res.partner', 'Proveedor', domain=[('supplier_rank', '>', 0)])
    presentation = fields.Char(
        'Presentación', default='Saco 25 kg · contado sin crédito',
        help='Formato de venta y condiciones de pago del proveedor.')
    notes = fields.Text('Notas')
    active = fields.Boolean(default=True)

    # Combos que usan este condimento
    combo_ids = fields.One2many('hr.product.combo', 'seasoning_id', 'Combos que lo usan')
    combo_count = fields.Integer(compute='_compute_combo_count', string='# Combos')

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name_full = (
                f'{rec.name} [{rec.code}]' if rec.code else rec.name
            )

    def _compute_combo_count(self):
        for rec in self:
            rec.combo_count = len(rec.combo_ids)

    def action_view_combos(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Combos — {self.name}',
            'res_model': 'hr.product.combo',
            'view_mode': 'list,form',
            'domain': [('seasoning_id', '=', self.id)],
        }

    def name_get(self):
        return [(rec.id, rec.display_name_full) for rec in self]
