from odoo import api, fields, models


class ProductTemplate(models.Model):
    """Extiende el producto nativo con precios HR y destinos de exportación."""
    _inherit = 'product.template'

    hr_combo_ids = fields.One2many(
        'hr.product.combo', 'product_id',
        string='Combos Happy Roots',
        help='Combos de pricing vinculados a este producto.')
    hr_combo_count = fields.Integer(
        compute='_compute_hr_combo_count', string='# Combos HR')

    hr_destination_price_ids = fields.Many2many(
        'hr.destination.price',
        compute='_compute_hr_destination_price_ids',
        string='Precios por destino')

    def _compute_hr_combo_count(self):
        for rec in self:
            rec.hr_combo_count = self.env['hr.product.combo'].search_count([
                ('product_id.product_tmpl_id', '=', rec.id)
            ])

    def _compute_hr_destination_price_ids(self):
        for rec in self:
            combos = self.env['hr.product.combo'].search([
                ('product_id.product_tmpl_id', '=', rec.id),
                ('state', '=', 'active'),
            ])
            if combos:
                prices = self.env['hr.destination.price'].search([
                    ('combo_id', 'in', combos.ids),
                ])
                rec.hr_destination_price_ids = prices
            else:
                rec.hr_destination_price_ids = self.env['hr.destination.price']

    def action_view_hr_combos(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Combos de Pricing — Happy Roots',
            'res_model': 'hr.product.combo',
            'view_mode': 'list,form',
            'domain': [('product_id.product_tmpl_id', '=', self.id)],
        }
