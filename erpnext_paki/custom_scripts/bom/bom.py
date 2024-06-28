import frappe

def on_validate(doc, method):
    update_sub_operations(doc)

def update_sub_operations(doc):
    if doc.operations:
        doc.sub_operations = []
        for operation in doc.operations:
            sub_operations = frappe.db.get_list("Sub Operation", 
                                                filters={
                                                    "parent": operation.operation,
                                                    "parenttype": "Operation",
                                                    "parentfield": "sub_operations"
                                                },
                                                fields=["operation", "time_in_mins", "description", "workstation"],
                                                order_by="creation, idx asc"
                                            )

            for so in sub_operations:
                doc.append("sub_operations",{
                    "operation": so.operation,
                    "time_in_mins": so.time_in_mins,
                    "description": so.description,
                    "workstation": so.workstation
                })

@frappe.whitelist()
def get_item_group_with_children(*args, **kwargs):
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


