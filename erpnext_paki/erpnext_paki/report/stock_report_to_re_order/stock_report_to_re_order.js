// Copyright (c) 2024, Metactical and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Stock Report to Re-order"] = {
      filters: [
            {
                  label: "Items",
                  fieldname: "items",
                  fieldtype: "MultiSelectList",
                  options: "Item",
                  on_change: () => {
                        frappe.query_report.refresh();
                  },
				  get_data: function(txt) {
						return frappe.db.get_link_options('Item', txt);
				  }
            },
            {
                  label: "Supplier",
                  fieldtype: "Link",
				  fieldname: "supplier",
                  options: "Supplier",
            },
			{
				label: "Limit",
				fieldtype: "Select",
				fieldname: "limit",
				default: "20",
				options: ["20", "500", "1000", "5000", "10000", "ALL"]
			}
      ],
};
