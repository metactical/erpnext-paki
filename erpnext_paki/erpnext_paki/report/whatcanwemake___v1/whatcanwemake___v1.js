// Copyright (c) 2024, Metactical and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["WhatCanWeMake - V1"] = {
	"filters": [
		{
			"fieldtype": "Link",
			"fieldname": "item",
			"options": "Item",
			"label": "Item"
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
