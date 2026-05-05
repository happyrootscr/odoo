from odoo import api, fields, models


class ProductTemplate(models.Model):
    """Extiende el producto nativo de Odoo con un smart button a los combos HR."""
    _inherit = 'product.template'

    hr_combo_ids = fields.One2many(
        'hr.product.combo', 'product_id',
        string='Combos Happy Roots',
        help='Combos de pricing vinculados a este producto.')
    hr_combo_count = fields.Integer(
        compute='_compute_hr_combo_count', string='# Combos HR')

    def _compute_hr_combo_count(self):
        for rec in self:
            rec.hr_combo_count = self.env['hr.product.combo'].search_count([
                ('product_id.product_tmpl_id', '=', rec.id)
            ])

    def action_view_hr_combos(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Combos de Pricing — Happy Roots',
            'res_model': 'hr.product.combo',
            'view_mode': 'list,form',
            'domain': [('product_id.product_tmpl_id', '=', self.id)],
        }
