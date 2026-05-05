from odoo import api, fields, models
from odoo.exceptions import UserError


class HrPricelistPushWizard(models.TransientModel):
    """
    Wizard para sincronizar los precios calculados del motor de pricing HR
    con las listas de precios nativas de Odoo (product.pricelist).
    Crea o actualiza ítems de pricelist para cada canal:
      Canal 1 — Direct-to-Retailer: precio Wholesale HR
      Canal 2 — Distribuidor (UNFI/KeHE): precio Wholesale distribuidor
      Canal 3 — DTC (Shopify/Amazon): precio MSRP
    """
    _name = 'hr.pricelist.push.wizard'
    _description = 'Happy Roots — Sincronizar Precios con Listas de Precios Odoo'

    combo_ids = fields.Many2many(
        'hr.product.combo', string='Combos a sincronizar',
        domain=[('state', '=', 'active'), ('product_id', '!=', False)])

    pricelist_direct_id = fields.Many2one(
        'product.pricelist', 'Lista de precios — Canal Directo',
        help='Pricelist para ventas directas a retailer (Wholesale HR).')
    pricelist_distributor_id = fields.Many2one(
        'product.pricelist', 'Lista de precios — Distribuidor',
        help='Pricelist para UNFI/KeHE (Wholesale con descuento distribuidor).')
    pricelist_dtc_id = fields.Many2one(
        'product.pricelist', 'Lista de precios — DTC',
        help='Pricelist para Shopify/Amazon (MSRP).')

    sync_direct = fields.Boolean('Sincronizar canal directo', default=True)
    sync_distributor = fields.Boolean('Sincronizar distribuidor', default=True)
    sync_dtc = fields.Boolean('Sincronizar DTC', default=True)

    result_summary = fields.Text('Resultado de sincronización', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Buscar listas de precios existentes por nombre convencional
        Pl = self.env['product.pricelist']
        direct = Pl.search([('name', 'ilike', 'Happy Roots Direct')], limit=1)
        distributor = Pl.search([('name', 'ilike', 'Happy Roots Distribuidor')], limit=1)
        dtc = Pl.search([('name', 'ilike', 'Happy Roots DTC')], limit=1)
        res.update({
            'pricelist_direct_id': direct.id if direct else False,
            'pricelist_distributor_id': distributor.id if distributor else False,
            'pricelist_dtc_id': dtc.id if dtc else False,
        })
        return res

    def action_create_pricelists(self):
        """Crea las listas de precios estándar HR si no existen."""
        self.ensure_one()
        Pl = self.env['product.pricelist']
        currency_usd = self.env['res.currency'].search(
            [('name', '=', 'USD')], limit=1)

        created = []
        for name, field in [
            ('Happy Roots Direct — Wholesale', 'pricelist_direct_id'),
            ('Happy Roots Distribuidor — UNFI/KeHE', 'pricelist_distributor_id'),
            ('Happy Roots DTC — Shopify/Amazon', 'pricelist_dtc_id'),
        ]:
            if not getattr(self, field):
                pl = Pl.create({
                    'name': name,
                    'currency_id': currency_usd.id if currency_usd else False,
                })
                self[field] = pl
                created.append(name)

        msg = (
            f'Listas creadas: {", ".join(created)}' if created
            else 'Las listas ya existían. No se crearon nuevas.'
        )
        self.result_summary = msg
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.pricelist.push.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_push_prices(self):
        """Sincroniza los precios calculados con las listas de precios de Odoo."""
        self.ensure_one()
        combos_without_product = self.combo_ids.filtered(lambda c: not c.product_id)
        if combos_without_product:
            names = ', '.join(combos_without_product.mapped('name'))
            raise UserError(
                f'Los siguientes combos no tienen producto Odoo vinculado: {names}. '
                'Vincúlalos antes de sincronizar.')

        Item = self.env['product.pricelist.item']
        synced = 0
        lines = []

        for combo in self.combo_ids:
            product = combo.product_id
            if not product:
                continue

            mappings = []
            if self.sync_direct and self.pricelist_direct_id:
                mappings.append((
                    self.pricelist_direct_id,
                    combo.price_wholesale_direct,
                    'Wholesale HR Direct',
                ))
            if self.sync_distributor and self.pricelist_distributor_id:
                mappings.append((
                    self.pricelist_distributor_id,
                    combo.price_wholesale_distributor,
                    'Wholesale Distribuidor',
                ))
            if self.sync_dtc and self.pricelist_dtc_id:
                mappings.append((
                    self.pricelist_dtc_id,
                    combo.price_msrp,
                    'MSRP DTC',
                ))

            for pricelist, price, channel_name in mappings:
                if price <= 0:
                    continue
                # Buscar ítem existente
                existing = Item.search([
                    ('pricelist_id', '=', pricelist.id),
                    ('product_id', '=', product.id),
                    ('applied_on', '=', '0_product_variant'),
                ], limit=1)

                if existing:
                    existing.write({'fixed_price': price})
                    lines.append(
                        f'✓ Actualizado [{channel_name}] {combo.name}: ${price:.4f}')
                else:
                    Item.create({
                        'pricelist_id': pricelist.id,
                        'applied_on': '0_product_variant',
                        'product_id': product.id,
                        'compute_price': 'fixed',
                        'fixed_price': price,
                    })
                    lines.append(
                        f'+ Creado [{channel_name}] {combo.name}: ${price:.4f}')
                synced += 1

        self.result_summary = (
            f'Sincronización completada: {synced} ítems procesados.\n\n'
            + '\n'.join(lines)
        )
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.pricelist.push.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
