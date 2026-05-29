from odoo import api, fields, models


class HrDestination(models.Model):
    _name = 'hr.destination'
    _description = 'Happy Roots — Destino de Exportación'
    _order = 'sequence, name'

    sequence = fields.Integer(default=10)
    name = fields.Char('Destino', required=True)
    country_id = fields.Many2one('res.country', 'País destino', required=True)
    port_arrival = fields.Char('Puerto / Ciudad de llegada')
    active = fields.Boolean(default=True)
    notes = fields.Text('Notas')

    incoterm_type = fields.Selection([
        ('fob', 'FOB — Free on Board (precio en puerto origen)'),
        ('cif', 'CIF — Cost Insurance Freight (precio en puerto destino)'),
        ('ddp', 'DDP — Delivered Duty Paid (precio en bodega cliente)'),
    ], string='Incoterm', default='ddp', required=True,
       help='Define qué columnas de precio son relevantes para este destino.')

    # ─── FLETE MARÍTIMO ───────────────────────────────────────────────────────
    freight_per_container_usd = fields.Float(
        'Flete marítimo 40HC (USD)', default=3500.0, digits=(10, 2))
    insurance_pct = fields.Float(
        'Seguro carga (%)', default=0.5, digits=(6, 3))

    # ─── ADUANAS Y ARANCELES ─────────────────────────────────────────────────
    tariff_pct = fields.Float(
        'Arancel de importación (%)', default=0.0, digits=(6, 3))
    customs_fixed_per_container = fields.Float(
        'Gastos aduana fijos (USD/contenedor)', default=800.0, digits=(10, 2))

    # ─── ÚLTIMA MILLA ─────────────────────────────────────────────────────────
    last_mile_per_bag_usd = fields.Float(
        'Última milla (USD/bolsa)', default=0.05, digits=(10, 6))

    # ─── CANALES ─────────────────────────────────────────────────────────────
    has_direct_channel = fields.Boolean('Canal directo (retailer)', default=True)
    has_distributor_channel = fields.Boolean('Canal distribuidor', default=True)
    has_dtc_channel = fields.Boolean('Canal DTC', default=True)
    has_amazon_channel = fields.Boolean('Canal Amazon', default=False)
    amazon_fee_pct = fields.Float('Comisión Amazon (%)', default=15.0, digits=(6, 2))
    amazon_fba_per_unit_usd = fields.Float('Amazon FBA (USD/bolsa)', default=0.0, digits=(10, 4))

    combo_price_ids = fields.One2many('hr.destination.price', 'destination_id', 'Precios por combo')
    combo_price_count = fields.Integer(compute='_compute_combo_price_count', string='# Precios')

    def _compute_combo_price_count(self):
        for rec in self:
            rec.combo_price_count = len(rec.combo_price_ids)

    # ─── AUTO-CREACIÓN DE REGISTROS DE PRECIO ────────────────────────────────

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        rec._ensure_all_combo_prices()
        return rec

    def write(self, vals):
        res = super().write(vals)
        if vals.get('active'):
            self._ensure_all_combo_prices()
        return res

    def _ensure_all_combo_prices(self):
        """Crea registros hr.destination.price para todos los combos activos."""
        self.ensure_one()
        DestPrice = self.env['hr.destination.price']
        combos = self.env['hr.product.combo'].search([('state', '=', 'active')])
        existing_combo_ids = set(
            DestPrice.search([('destination_id', '=', self.id)]).mapped('combo_id').ids
        )
        to_create = [
            {'destination_id': self.id, 'combo_id': c.id}
            for c in combos if c.id not in existing_combo_ids
        ]
        if to_create:
            DestPrice.create(to_create)


class HrDestinationPrice(models.Model):
    """
    Precio de un combo en un destino específico.
    Todos los campos se calculan AUTOMÁTICAMENTE.
    No se requiere ningún botón ni wizard manual.
    """
    _name = 'hr.destination.price'
    _description = 'Happy Roots — Precio por Destino (auto-calculado)'
    _order = 'destination_id, combo_id'

    destination_id = fields.Many2one(
        'hr.destination', 'Destino', required=True, ondelete='cascade', index=True)
    combo_id = fields.Many2one(
        'hr.product.combo', 'Combo', required=True, ondelete='cascade', index=True)

    # ─── CASCADA DE PRECIOS (todos auto-calculados) ───────────────────────────
    price_exw = fields.Float(
        'EXW (planta CR)', digits=(10, 6),
        compute='_compute_prices', store=True, readonly=True)
    price_fob = fields.Float(
        'FOB Puerto Limón', digits=(10, 6),
        compute='_compute_prices', store=True, readonly=True)
    price_cif = fields.Float(
        'CIF Puerto destino', digits=(10, 6),
        compute='_compute_prices', store=True, readonly=True)
    price_ddp = fields.Float(
        'DDP cliente', digits=(10, 6),
        compute='_compute_prices', store=True, readonly=True)
    price_wholesale_direct = fields.Float(
        'Wholesale Directo', digits=(10, 6),
        compute='_compute_prices', store=True, readonly=True)
    price_wholesale_distributor = fields.Float(
        'Wholesale Distribuidor', digits=(10, 6),
        compute='_compute_prices', store=True, readonly=True)
    price_msrp = fields.Float(
        'MSRP', digits=(10, 6),
        compute='_compute_prices', store=True, readonly=True)
    price_dtc = fields.Float(
        'DTC / eCommerce', digits=(10, 6),
        compute='_compute_prices', store=True, readonly=True)
    price_amazon = fields.Float(
        'Amazon', digits=(10, 6),
        compute='_compute_prices', store=True, readonly=True)

    # ─── RELATED PARA VISTAS ─────────────────────────────────────────────────
    format_weight_g = fields.Integer(related='combo_id.format_weight_g', store=False)
    combo_name = fields.Char(related='combo_id.display_name_full', store=False)

    @api.depends(
        'combo_id.price_fob',
        'combo_id.price_exw',
        'combo_id.bags_per_container',
        'combo_id.state',
        'destination_id.freight_per_container_usd',
        'destination_id.insurance_pct',
        'destination_id.tariff_pct',
        'destination_id.customs_fixed_per_container',
        'destination_id.last_mile_per_bag_usd',
        'destination_id.amazon_fee_pct',
        'destination_id.amazon_fba_per_unit_usd',
    )
    def _compute_prices(self):
        config = self.env['hr.pricing.config'].get_config()
        for rec in self:
            dest = rec.destination_id
            combo = rec.combo_id
            if not dest or not combo or combo.state != 'active':
                rec.price_exw = rec.price_fob = rec.price_cif = 0.0
                rec.price_ddp = rec.price_wholesale_direct = 0.0
                rec.price_wholesale_distributor = rec.price_msrp = 0.0
                rec.price_dtc = rec.price_amazon = 0.0
                continue

            bags = combo.bags_per_container or 1

            # ── CASCADA INCOTERMS ─────────────────────────────────────────────
            fob = combo.price_fob
            freight_pb = dest.freight_per_container_usd / bags
            cif_raw = fob + freight_pb
            cif = cif_raw * (1.0 + dest.insurance_pct / 100.0)
            customs_pb = dest.customs_fixed_per_container / bags
            ddp = (cif * (1.0 + dest.tariff_pct / 100.0)
                   + customs_pb + dest.last_mile_per_bag_usd)

            # ── PRECIOS DE VENTA (márgenes desde config) ─────────────────────
            m_hr = config.margin_hr_pct if config else 0.30
            m_dist = config.distributor_discount_pct if config else 0.20
            m_retail = config.margin_retailer_pct if config else 0.40
            m_dtc = config.dtc_fees_pct if config else 0.20

            ws_direct = ddp / (1.0 - m_hr) if m_hr < 1.0 else ddp
            ws_dist = ws_direct * (1.0 - m_dist)
            msrp = ws_direct / (1.0 - m_retail) if m_retail < 1.0 else ws_direct
            dtc = ddp / (1.0 - m_dtc - m_hr) if (m_dtc + m_hr) < 1.0 else msrp

            a_fee = dest.amazon_fee_pct / 100.0
            a_fba = dest.amazon_fba_per_unit_usd
            amazon = (ddp + a_fba) / (1.0 - a_fee - m_hr) if (a_fee + m_hr) < 1.0 else dtc

            rec.price_exw = combo.price_exw
            rec.price_fob = fob
            rec.price_cif = cif
            rec.price_ddp = ddp
            rec.price_wholesale_direct = ws_direct
            rec.price_wholesale_distributor = ws_dist
            rec.price_msrp = msrp
            rec.price_dtc = dtc
            rec.price_amazon = amazon

    @api.model
    def _cron_recompute_all(self):
        """Cron de respaldo diario: recomputa todos los precios por destino y sincroniza pricelists."""
        all_prices = self.search([])
        all_prices._compute_prices()
        all_prices._auto_sync_pricelists()

    def write(self, vals):
        res = super().write(vals)
        # Cuando cambia cualquier precio, actualiza automáticamente las pricelists de Odoo
        price_fields = {
            'price_wholesale_direct', 'price_wholesale_distributor',
            'price_msrp', 'price_dtc', 'price_amazon',
        }
        if price_fields & set(vals.keys()):
            self._auto_sync_pricelists()
        return res

    def _auto_sync_pricelists(self):
        """
        Crea o actualiza automáticamente los ítems de product.pricelist.
        Sin wizard, sin botón — sucede cada vez que un precio cambia.
        """
        Pl = self.env['product.pricelist']
        PlItem = self.env['product.pricelist.item']
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        if not usd:
            return

        for rec in self:
            product = rec.combo_id.product_id
            if not product or not rec.destination_id:
                continue
            dest = rec.destination_id

            channels = []
            if dest.has_direct_channel and rec.price_wholesale_direct:
                channels.append(('Wholesale Directo', rec.price_wholesale_direct, dest.sequence * 10))
            if dest.has_distributor_channel and rec.price_wholesale_distributor:
                channels.append(('Distribuidor', rec.price_wholesale_distributor, dest.sequence * 10 + 1))
            if dest.has_dtc_channel and rec.price_dtc:
                channels.append(('DTC', rec.price_dtc, dest.sequence * 10 + 2))
            if dest.has_amazon_channel and rec.price_amazon:
                channels.append(('Amazon', rec.price_amazon, dest.sequence * 10 + 3))

            for channel_label, price, seq in channels:
                pl_name = f'HR | {dest.name} | {channel_label}'
                pricelist = Pl.search([('name', '=', pl_name)], limit=1)
                if not pricelist:
                    pricelist = Pl.create({
                        'name': pl_name,
                        'currency_id': usd.id,
                        'sequence': seq,
                    })

                item = PlItem.search([
                    ('pricelist_id', '=', pricelist.id),
                    ('product_id', '=', product.id),
                    ('applied_on', '=', '0_product_variant'),
                ], limit=1)

                if item:
                    item.fixed_price = price
                else:
                    PlItem.create({
                        'pricelist_id': pricelist.id,
                        'applied_on': '0_product_variant',
                        'product_id': product.id,
                        'compute_price': 'fixed',
                        'fixed_price': price,
                        'min_quantity': 0,
                    })
