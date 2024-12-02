import frappe

@frappe.whitelist()
def get_item_group_with_children(kwargs):
    parent = kwargs.get("parent", "Raw Material To Stock")
    item_groups = frappe.db.sql("""
        SELECT ig.name 
            from 
                `tabItem Group` ig
            where
                ig.parent_item_group = {parent}
                or ig.name = {parent}
    """.format(parent=frappe.db.escape(parent)), as_dict=True)
    raw_material_item_groups = [ig.name for ig in item_groups]

    return raw_material_item_groups


