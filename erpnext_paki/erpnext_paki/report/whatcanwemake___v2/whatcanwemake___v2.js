// Copyright (c) 2025, Metactical and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["WhatCanWeMake - V2"] = {
	"filters": [
		{
			"fieldtype": "MultiSelectList",
			"fieldname": "item",
			"options": "Item",
			"label": "Item",
			on_change: () => {
				frappe.query_report.refresh()
			},
			get_data: function(txt) {
				return frappe.db.get_link_options("Item", txt);
			}
		},
		{
			"fieldname":"limit",
			"label": __("Limit"),
			"fieldtype": "Select",
			"options": ["20", "500", "1000", "5000", "10000"],
			"default": "20"
		}
	]
};
