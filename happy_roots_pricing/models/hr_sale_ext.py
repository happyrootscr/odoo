from odoo import api, fields, models


class SaleOrder(models.Model):
    """Extiende sale.order con destino HR e incoterm automático."""
    _inherit = 'sale.order'

    hr_destination_id = fields.Many2one(
        'hr.destination', 'Destino HR',
        help='Mercado de destino. Determina el precio correcto según Incoterm.')

    @api.onchange('hr_destination_id')
    def _onchange_hr_destination(self):
        """Sugiere el incoterm y pricelist según el destino seleccionado."""
        if not self.hr_destination_id:
            return
        dest = self.hr_destination_id
        # Sugerir incoterm DDP si existe
        incoterm_ddp = self.env['account.incoterms'].search(
            [('code', '=', 'DDP')], limit=1)
        if incoterm_ddp:
            self.incoterm = incoterm_ddp

    @api.onchange('hr_destination_id', 'incoterm')
    def _onchange_suggest_pricelist(self):
        """Sugiere la pricelist correcta según destino + incoterm."""
        if not self.hr_destination_id or not self.incoterm:
            return
        incoterm_code = self.incoterm.code if self.incoterm else ''
        dest_name = self.hr_destination_id.name

        Pl = self.env['product.pricelist']
        # Buscar pricelist que contenga el nombre del destino
        pricelist = Pl.search([
            ('name', 'ilike', dest_name.split('—')[0].strip()),
            ('active', '=', True),
        ], limit=1)
        if pricelist and not self.pricelist_id:
            self.pricelist_id = pricelist


class SaleOrderLine(models.Model):
    """Muestra el precio DDP del destino en la línea de cotización."""
    _inherit = 'sale.order.line'

    hr_price_ddp = fields.Float(
        'DDP destino', compute='_compute_hr_price_ddp',
        digits=(10, 4), store=False,
        help='Costo DDP para el destino seleccionado en la orden.')

    def _compute_hr_price_ddp(self):
        for line in self:
            dest = line.order_id.hr_destination_id
            if not dest or not line.product_id:
                line.hr_price_ddp = 0.0
                continue
            combo = self.env['hr.product.combo'].search(
                [('product_id', '=', line.product_id.id),
                 ('state', '=', 'active')], limit=1)
            if not combo:
                line.hr_price_ddp = 0.0
                continue
            dest_price = self.env['hr.destination.price'].search(
                [('destination_id', '=', dest.id),
                 ('combo_id', '=', combo.id)], limit=1)
            line.hr_price_ddp = dest_price.price_ddp if dest_price else 0.0
