# Copyright (c) 2024, Metactical and contributors
# For license information, please see license.txt

import frappe
from datetime import datetime
from dateutil.relativedelta import relativedelta
from frappe.utils import getdate
from erpnext_paki.custom_scripts.bom.bom import get_item_group_with_children

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)

	return columns, data

def get_data(filters):
	item_groups = get_item_group_with_children({"parent": "Raw Material To Stock"})
	item_groups += get_item_group_with_children({"parent": "Factory BOM"})
	item_groups = tuple(item_groups)

	if not len(item_groups):
		return []

	conditions = ""
	if filters.get("supplier"):
		conditions = f' and supplier="{filters.get("supplier")}"'
	
	if filters.get("items"):
		items_list = str(tuple(filters.get("items"))) if filters.get("items") else ""
		if items_list.endswith(",)"):
			items_list = items_list[:-2] + ")"

		conditions += f' and item_code IN {items_list}'

	if filters.get("limit") and filters.get("limit") != "ALL":
		conditions += f" limit {filters.get('limit')}"

	items = frappe.db.sql(f"""
		SELECT
			item_code, stock_uom, item_group, min_order_qty,
			item_name, description, `tabItem`.image, supplier, supplier_part_no,
			supplier_group
		FROM
			`tabItem`
		Left JOIN
			`tabItem Supplier` ON `tabItem Supplier`.parent = `tabItem`.name
		LEFT JOIN
			`tabSupplier` ON `tabSupplier`.name = `tabItem Supplier`.supplier
		WHERE 
			item_group in {item_groups} AND 
			has_variants=0 AND
			supplier_group="Raw Material"
			{conditions} 
	""", as_dict=1)

	for row in items:
		item_groups = get_item_group_parents(row.get("item_group"))
		row["item_groups"] = item_groups

		# usage of the item as a raw material
		usage = get_stock_entries(row.get("item_code"))
		row["previousyusage"] = usage.get("previousyusage")
		row["currentyearusage"] = usage.get("currentyearusage")
		row["usagelast10days"] = usage.get("usagelast10days")
		row["usagelast30days"] = usage.get("usagelast30days")
		row["usage_last60days"] = usage.get("usage_last60days")

		# get stock entries for from the first date last year to today
		qoh = get_qty(row.get("item_code"), filters.get("warehouse"))
		row["totalqoh"] = qoh
		
		# get stock entries for from the first date last year to today
		row["w01_raw_material"] = get_qty(row.get("item_code"), "W01 - Storage (Raw Materials) - PAK")
		row["w02_work_in_progress"] = get_qty(row.get("item_code"), "W02 - Work In Progress - PAK")

		# purchase related information
		purchase_order_items = get_purchase_order_items(row.get("item_code"))
		row["qty_on_order"] = get_pending_orders(purchase_order_items)
		row["date_last_received"] = get_last_received_date(row.get("item_code"))
		row["qty_reorderlast_time"] = get_qty_reorder_last_time(purchase_order_items)
		row["orderfreq12m"] = get_total_orders_12m(purchase_order_items)
		row["avgorderqty"] = get_average_quantity_ordered(purchase_order_items)

		# cost
		row["cost"] = get_minimum_cost(row.get("item_code"), filters.get("supplier"))

		# show image and item code as a link
		row['image'] = f'<img src="{row.get("image")}" style="width: 50px; height: 50px;">' if row.get("image") else ""
		row["item_code"] = f'<a href="/app/item/{row.get("item_code")}" target="_blank">{row.get("item_code")}</a>'

	return items

def get_average_quantity_ordered(purchase_order_items):
	total_qty_ordered = sum([row.qty for row in purchase_order_items])
	
	return total_qty_ordered/len(purchase_order_items) if len(purchase_order_items) > 0 else 0

def get_purchase_order_items(item_code):
	two_years_before = frappe.utils.getdate() - relativedelta(years=2)
	purchase_order_items = frappe.db.sql(f"""
		SELECT
			qty, status, transaction_date, `tabPurchase Order Item`.parent
		FROM
			`tabPurchase Order Item`
		JOIN
			`tabPurchase Order` ON `tabPurchase Order`.name = `tabPurchase Order Item`.parent
		WHERE
			item_code = '{item_code}' AND `tabPurchase Order`.docstatus = 1 and transaction_date >= {two_years_before}
		order by transaction_date desc
	""", as_dict=1)

	return purchase_order_items

def get_total_orders_12m(purchase_order_items):
	last_12m_date = frappe.utils.getdate() - relativedelta(years=1)
	total_orders = 0
	unique_orders = []
	
	for order in purchase_order_items:
		if order['transaction_date'] >= last_12m_date and order['parent'] not in unique_orders:
			unique_orders.append(order['parent'])

	return len(unique_orders)

def get_qty_reorder_last_time(purchase_order_items):
	qty_reorder_last_time = purchase_order_items[0].qty if len(purchase_order_items) else ""
	return qty_reorder_last_time

def get_last_received_date(item_code):
	last_received_date = frappe.db.sql(f"""
		SELECT
			posting_date
		FROM
			`tabPurchase Receipt Item`
		JOIN
			`tabPurchase Receipt` ON `tabPurchase Receipt`.name = `tabPurchase Receipt Item`.parent
		WHERE
			item_code = '{item_code}' AND `tabPurchase Receipt`.docstatus = 1
		order by posting_date desc
		limit 1
	""", as_dict=1)

	if last_received_date and last_received_date[0]['posting_date']:
		last_received_date = last_received_date[0]['posting_date']
	else:
		last_received_date = None

	return last_received_date

def get_pending_orders(purchase_order_items):
	pending_orders = 0

	for order in purchase_order_items:
		if order['status'] in ["To Receive and Bill", "To Receive"]:
			pending_orders += order['qty']

	return pending_orders

def get_qty(item_code, warehouse=None):
	qty = 0
	if warehouse:
		data = frappe.db.sql("""select actual_qty-reserved_qty AS qty from `tabBin`
			where item_code = %s and warehouse = %s
			""",(item_code, warehouse), as_dict=1)
	else:
		data = frappe.db.sql("""select actual_qty-reserved_qty AS qty from `tabBin`
			where item_code = %s
			""",(item_code), as_dict=1)

	qty = sum([d.qty for d in data])
	return qty

def get_stock_entries(item_code):
	# get stock entries for from the first date last year to today
	previous_year_usage = 0
	current_year_usage = 0
	usagelast10days = 0
	usagelast30days = 0
	usage_last60days = 0

	usage = frappe.db.sql(f"""
		SELECT
			posting_date, qty
		FROM
			`tabStock Entry Detail`
		JOIN
			`tabStock Entry` ON `tabStock Entry`.name = `tabStock Entry Detail`.parent
		WHERE
			stock_entry_type = 'Material Transfer for Manufacture' AND
			item_code = '{item_code}' AND
			`tabStock Entry`.docstatus = 1 AND
			posting_date BETWEEN DATE_FORMAT(CURDATE() - INTERVAL 1 YEAR, '%Y-01-01') AND CURDATE()
	""", as_dict=1)

	today = frappe.utils.getdate()
	previous_year = frappe.utils.getdate().year - 1
	last10_days_date = today - relativedelta(days=10)
	last30_days_date = today - relativedelta(days=30)
	last60_days_date = today - relativedelta(days=60)
	current_year = frappe.utils.getdate().year

	for row in usage:
		posting_year = frappe.utils.getdate(row.get("posting_date")).year
		posting_date = getdate(row.get("posting_date"))

		if posting_year == previous_year:
			previous_year_usage += int(row.get("qty"))
		if posting_year == current_year:
			current_year_usage += int(row.get("qty"))
		if posting_date >= last10_days_date:
			usagelast10days += int(row.get("qty"))
		if posting_date >= last30_days_date:
			usagelast30days += int(row.get("qty"))
		if posting_date >= last60_days_date:
			usage_last60days += int(row.get("qty"))
		
	return {
		"previousyusage": previous_year_usage,
		"currentyearusage": current_year_usage,
		"usagelast10days": usagelast10days,
		"usagelast30days": usagelast30days,
		"usage_last60days": usage_last60days
	}
	

def get_item_group_parents(lower_item_group):
	item_groups = []
	item_group = lower_item_group

	while item_group:
		item_group = frappe.db.get_value("Item Group", item_group, "parent_item_group")
		if item_group and item_group != "All Item GGroupsroups":
			item_groups.append(item_group)

	item_groups.insert(0, lower_item_group)
	item_groups.reverse()

	if len(item_groups) > 1:
		item_groups = ">".join(item_groups)
	else:
		item_groups = item_groups[0]

	return item_groups 


def get_minimum_cost(item, supplier=None):
	min_rate = "N/A"
	min_rate_supplier = "N/A"
	currency = "N/A"


	if not supplier:
		suppliers = frappe.get_all("Item Supplier", filters={"parent": item, "parenttype": "Item"}, fields=["supplier"])
		supplier_list = [supplier.get("supplier") for supplier in suppliers]
	else:
		supplier_list = [supplier] if supplier else []

	if not supplier_list:
		return min_rate

	for supplier in supplier_list:
		price_list = frappe.db.get_value("Supplier", supplier, "default_price_list")
		if not price_list:
			price_list = "Standard Buying"

		item_price = frappe.db.get_values("Item Price", 
												filters={"item_code": item, "price_list": price_list, "buying": 1}, 
												fieldname=["name", "price_list_rate", "currency"],
												as_dict=True
											)

		if not item_price:
			continue
		
		if "(Default Supplier)" in supplier_list or "Default Supplier" in supplier_list:
			min_rate = item_price[0].get("price_list_rate")
			break
		else:
			if min_rate == "N/A" or not min_rate:
				min_rate = item_price[0].get("price_list_rate")
			elif item_price[0].get("price_list_rate") and item_price[0].get("price_list_rate") < min_rate:
				min_rate = item_price[0].get("price_list_rate")
		
	return min_rate

def get_columns():
	return [
		{
			"fieldname": "item_code",
			"label": "ERPNext Item Code",
			"fieldtype": "Data",
			"width": 120
		},
		# {
		# 	"fieldname": "ifw_retailskusuffix",
		# 	"label": "Retail SKU",
		# 	"fieldtype": "Data",
		# 	"width": 120
		# },
		{
			"fieldname": "stock_uom",
			"label": "UOM",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "item_groups",
			"label": "Item Groups",
			"fieldtype": "Data",
			"width": 120
		},
		# {
		# 	"fieldname": "item_class",
		# 	"label": "Item Class",
		# 	"fieldtype": "Data",
		# 	"width": 120
		# },
		{
			"fieldname": "item_name",
			"label": "Item Name",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "description",
			"label": "Item Description",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "image",
			"label": "Image",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "cost",
			"label": "Cost",
			"fieldtype": "Data",
			"width": 120
		},
		# {
		# 	"fieldname": "discontinued",
		# 	"label": "Discontinued",
		# 	"fieldtype": "Data",
		# 	"width": 120
		# },
		{
			"fieldname": "qty_on_order",
			"label": "Qty On Order",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "date_last_received",
			"label": "Date Last Received",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "qty_reorderlast_time",
			"label": "Qty Reorder Last time",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "min_order_qty",
			"label": "Suggested Reorder Qty",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "supplier_part_no",
			"label": "Suplier SKU",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "supplier",
			"label": "Supplier Name",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "w01_raw_material",
			"label": "W01-Raw Material",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "w02_work_in_progress",
			"label": "W02-Work In Progress",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "totalqoh",
			"label": "TotalQOH",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "previousyusage",
			"label": "PreviousYUsage",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "currentyearusage",
			"label": "CurrentYearUsage",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "usagelast10days",
			"label": "UsageLast10Days",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "usagelast30days",
			"label": "UsageLast30Days",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "usage_last60days",
			"label": "usageLast60Days",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "orderfreq12m",
			"label": "OrderFreq12M",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "avgorderqty",
			"label": "AvgOrderQty",
			"fieldtype": "Data",
			"width": 120
		}
	]

