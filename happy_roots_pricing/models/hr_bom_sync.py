from odoo import api, fields, models


class HrProductComboBoM(models.Model):
    """
    Extensión de hr.product.combo para generar Bills of Materials (BoMs)
    y configurar la subcontratación con ADM.

    Requiere que mrp y mrp_subcontracting estén instalados.
    Si no están instalados, este modelo no hace nada.

    Flujo:
      1. Happy Roots compra condimento a Maluquer → llega a bodega CR
      2. Happy Roots compra bolsas a Indupark → llega a bodega CR
      3. PO de subcontratación a ADM:
           - ADM recibe: condimento + bolsas desde Happy Roots
           - ADM provee: yuca procesada + maquila + cajas
           - ADM entrega: bolsas terminadas
      4. Al confirmar recepción, Odoo calcula el costo real del producto:
           standard_price = (costo maquila ADM + costo condimento + costo bolsa) / bolsas
      5. Este standard_price reemplaza el EXW estimado del motor de pricing
         → los precios reflejan costos REALES, no estimados.
    """
    _inherit = 'hr.product.combo'

    bom_id = fields.Many2one(
        'mrp.bom', 'BoM (Lista de Materiales)',
        help='Lista de materiales para la subcontratación con ADM.',
        readonly=True)

    def _ensure_bom(self):
        """
        Crea o actualiza la BoM de subcontratación para este combo.
        Solo actúa si mrp + mrp_subcontracting están instalados.
        """
        self.ensure_one()
        if not self.product_id:
            return
        if not self._mrp_available():
            return

        MrpBom = self.env['mrp.bom']
        MrpBomLine = self.env['mrp.bom.line']

        # ── Buscar o crear la BoM ────────────────────────────────────────────
        bom = self.bom_id
        if not bom:
            bom = MrpBom.search([
                ('product_id', '=', self.product_id.id),
                ('type', '=', 'subcontract'),
            ], limit=1)

        if not bom:
            bom = MrpBom.create({
                'product_tmpl_id': self.product_id.product_tmpl_id.id,
                'product_id': self.product_id.id,
                'product_qty': 1.0,
                'type': 'subcontract',
                'subcontractor_ids': [(6, 0, self._get_subcontractor_ids())],
            })
            self.bom_id = bom
        else:
            # Actualizar subcontratistas
            bom.subcontractor_ids = [(6, 0, self._get_subcontractor_ids())]
            self.bom_id = bom

        # ── Actualizar componentes ────────────────────────────────────────────
        bom.bom_line_ids.unlink()

        lines_to_create = []

        # Componente 1: Condimento (Maluquer)
        seasoning_product = self._get_or_create_component_product(
            name=f'Condimento — {self.seasoning_id.name}',
            supplier=self.seasoning_id.supplier_id,
            price_unit=self.seasoning_id.price_per_kg_usd,
            uom_ref='uom.product_uom_kgm',
        )
        if seasoning_product:
            lines_to_create.append({
                'bom_id': bom.id,
                'product_id': seasoning_product.id,
                'product_qty': self.dosification_kg_per_bag,
            })

        # Componente 2: Bolsa laminada (Indupark)
        bag_product = self._get_or_create_component_product(
            name=f'Bolsa laminada {self.base_id.format_weight_g}g',
            supplier=self.base_id.bag_supplier_id,
            price_unit=self.base_id.bag_cost_usd,
            uom_ref='uom.product_uom_unit',
        )
        if bag_product:
            lines_to_create.append({
                'bom_id': bom.id,
                'product_id': bag_product.id,
                'product_qty': 1.0,
            })

        if lines_to_create:
            MrpBomLine.create(lines_to_create)

    def _get_subcontractor_ids(self):
        """Retorna los IDs de res.partner de los subcontratistas (ADM)."""
        ids = []
        if self.base_id.maquila_supplier_id:
            ids.append(self.base_id.maquila_supplier_id.id)
        return ids

    def _get_or_create_component_product(self, name, supplier, price_unit, uom_ref):
        """Busca o crea un producto de componente con su vendor pricelist."""
        ProductTmpl = self.env['product.template']
        uom = self.env.ref(uom_ref, raise_if_not_found=False)
        if not uom:
            return None

        # Buscar por nombre exacto
        tmpl = ProductTmpl.search([('name', '=', name)], limit=1)
        if not tmpl:
            tmpl = ProductTmpl.create({
                'name': name,
                'type': 'consu',
                'sale_ok': False,
                'purchase_ok': True,
                'standard_price': price_unit or 0.0,
                'uom_id': uom.id,
            })

        product = tmpl.product_variant_id

        # Crear o actualizar vendor pricelist (supplierinfo) para precio automático
        if supplier and price_unit:
            Supplierinfo = self.env['product.supplierinfo']
            existing = Supplierinfo.search([
                ('product_tmpl_id', '=', tmpl.id),
                ('partner_id', '=', supplier.id),
            ], limit=1)
            if existing:
                existing.price = price_unit
            else:
                Supplierinfo.create({
                    'product_tmpl_id': tmpl.id,
                    'partner_id': supplier.id,
                    'price': price_unit,
                    'min_qty': 0,
                })

        return product

    @api.model
    def _mrp_available(self):
        """Verifica si mrp está instalado antes de cualquier operación de BoM."""
        return bool(self.env['ir.module.module'].search_count([
            ('name', '=', 'mrp'), ('state', '=', 'installed')
        ]))
