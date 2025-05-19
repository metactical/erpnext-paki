# Copyright (c) 2024, Metactical and contributors
# For license information, please see license.txt

import frappe, json
from frappe import _
from erpnext_paki.custom_scripts.bom.bom import get_item_group_with_children


def execute(filters=None):
	columns, data = get_columns(), get_data(filters)
	return columns, data

def get_data(filters=None):
	item_filter = filters.get("item")
	limit_filter = filters.get("limit")
	
	filters_dict = {"docstatus": 1, "is_active": 1}

	if item_filter:
		filters_dict.update({"item": ["in", item_filter]})

	boms = frappe.db.get_list("BOM", 
				filters= filters_dict, 
				fields=["name", "sample_details", "item",
						"image", "item_name", "retail_sku",
						"raw_material_cost", "operating_cost"], 
				page_length=limit_filter or 10,
				order_by="retail_sku asc"
			)

	result = []
	non_raw_materials = []
	raw_materials = []

	for bom in boms:
		bom_items = frappe.db.sql("""select 
                            		bi.item_name, bi.item_code, bi.description, bi.qty, bi.uom, bi.amount, item_group
                              		from `tabBOM Item` bi
									Join `tabItem` on `tabItem`.name = bi.item_code
                                	where bi.parent = %s""", (bom.name), as_dict=1)

		results, non_raw_materials, raw_materials = get_row(bom, bom_items, non_raw_materials, raw_materials)
		result.extend(results)

	return result

def get_row(bom, bom_items, non_raw_materials, raw_materials):
	paki_settings = frappe.get_doc("Paki Settings")
	whatcanwemake_item_groups = [ig.item_group for ig in paki_settings.item_groups_whatcanwemake]
	
	raw_material_item_groups = []
	for item_group in whatcanwemake_item_groups:
		raw_material_item_groups += get_item_group_with_children({"parent": item_group})
  	
	operating_cost = bom.operating_cost if bom.operating_cost else 0
	raw_material_cost = bom.raw_material_cost if bom.raw_material_cost else 0

	total_cost = operating_cost + raw_material_cost

	qty_we_can_make_now = 0
	qty_we_can_make_future = 0

	rows_list = []

	row = {
			"item": bom.item,
			"retail_sku": bom.retail_sku,
			"item_name": bom.item_name,
			"qty_to_order": bom.sample_details,
			"image": bom.image,
			"raw_material_cost": round(bom.raw_material_cost, 2),
			"operating_cost": round(bom.operating_cost, 2),
			"total_cost": round(operating_cost + raw_material_cost, 2),
		}
	
	pcs_to_make = []  # list of pcs to make by using quantities on hand in each item
	pcs_to_make_future = []  # list of pcs to make by using qoh and qty_on_order in each item

	for bom_item in bom_items:
		qty = get_qty(bom_item.item_code) or 0
		qty_on_order = get_qty_on_order(bom_item.item_code) or 0

		if bom_item.item_group in raw_material_item_groups:
			if qty > 0 or qty_on_order > 0:
				qty_we_can_make_now = qty // bom_item.qty
				qty_we_can_make_future = (qty + qty_on_order) // bom_item.qty
				pcs_to_make.append(qty_we_can_make_now)
				pcs_to_make_future.append(qty_we_can_make_future)
				
			else:
				pcs_to_make.append(0)
				pcs_to_make_future.append(0)
		
		if bom_item.item_code in non_raw_materials:
			continue
		elif bom_item.item_code not in raw_materials:
			item_group = frappe.db.get_value("Item", bom_item.item_code, "item_group")
			if item_group not in raw_material_item_groups:
				non_raw_materials.append(bom_item.item_code)
				continue

		raw_materials.append(bom_item.item_code)

		row.update({
			"bom_item": bom_item.item_code,
			"item_description": bom_item.description,
			"qty_to_make": bom_item.qty,
			"uom": bom_item.uom,
			"qoh": qty,
			"item_cost": bom_item.amount,
			"qty_on_order": qty_on_order,
		})

		rows_list.append(row)
		row = {}

	# get the minimum value from the list of pcs to make
	if pcs_to_make and rows_list:
		rows_list[0]["qty_we_can_make_now"] = min(pcs_to_make)
	
	if pcs_to_make_future and rows_list:
		rows_list[0]["qty_we_can_make_future"] = min(pcs_to_make_future)
	
	return rows_list, non_raw_materials, raw_materials

def get_qty_on_order(item):
	qty = 0
	data = frappe.db.sql("""select sum(qty) as qty from `tabPurchase Order Item`
			join `tabPurchase Order` on `tabPurchase Order`.name = `tabPurchase Order Item`.parent
			where `tabPurchase Order`.status = 'To Receive and Bill' and `tabPurchase Order Item`.item_code = %s
		""",(item), as_dict=1)

	if data:
		if data[0]['qty']:
			if data[0]['qty'] > 0:
				qty = data[0]['qty']
	return qty

def get_qty(item):
	qty = 0
	data= frappe.db.sql("""select actual_qty-reserved_qty AS qty from `tabBin`
		where item_code = %s and warehouse="W01 - Storage (Raw Materials) - PAK"
		""",(item), as_dict=1)
	if data and data[0]['qty'] > 0:
		qty = data[0]['qty']
	return qty

def get_columns():
	return [
		{
			"label": _("ERPSKU"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{
			"label": "RetailSKU",
			"fieldname": "retail_sku",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": "Image",
			"fieldname": "image",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": "Item Name",
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": "BOMItem",
			"fieldname": "bom_item",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": "Item Description",
			"fieldname": "item_description",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": "BOMQtyToMake",
			"fieldname": "qty_to_make",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": "BOMUOM",
			"fieldname": "uom",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": "QOH",
			"fieldname": "qoh",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": "ItemCost",
			"fieldname": "item_cost",
			"fieldtype": "Currency",
			"width": 150,
		},
		{
			"label": "BOMCost",
			"fieldname": "raw_material_cost",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": "OPCost",
			"fieldname": "operating_cost",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": "TTLCost",
			"fieldname": "total_cost",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": "QtyOnOrder",
			"fieldname": "qty_on_order",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": "QtyWeCanMakeNow",
			"fieldname": "qty_we_can_make_now",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": "QtyWeCanMakeFuture",
			"fieldname": "qty_we_can_make_future",
			"fieldtype": "Data",
			"width": 150
		}
	]